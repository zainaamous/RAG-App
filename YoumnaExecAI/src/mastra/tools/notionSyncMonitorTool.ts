import { createTool } from "@mastra/core/tools";
import type { IMastraLogger } from "@mastra/core/logger";
import { z } from "zod";
import { db, sql } from "../../server/storage";
import { notionSyncStatus, notionSyncLock, notionPages, notionBlocks } from "../../shared/schema";
import { eq, desc, and, gte, lt, count, min, max } from "drizzle-orm";

export const notionSyncStatusTool = createTool({
  id: "notion-sync-status-tool",
  description: "Check the status of Notion sync and determine if a new sync is needed",
  inputSchema: z.object({
    syncIntervalMinutes: z.number().default(15).describe("Minimum minutes between syncs"),
    maxSyncAge: z.number().default(60).describe("Maximum age in minutes before forcing a new sync"),
    staleLockTimeoutMinutes: z.number().default(45).describe("Minutes after which a running sync is considered stale and will be recovered"),
  }),
  outputSchema: z.object({
    syncNeeded: z.boolean(),
    lastSyncId: z.number().optional(),
    lastSyncTime: z.string().optional(),
    lastSyncStatus: z.string().optional(),
    timeSinceLastSync: z.number(),
    recommendation: z.string(),
    runningSyncs: z.number(),
    staleLocksRecovered: z.number(),
    staleLockDetails: z.array(z.object({
      syncId: z.number(),
      startedAt: z.string(),
      lastHeartbeat: z.string(),
      ageMinutes: z.number(),
    })),
  }),
  execute: async ({ context: { syncIntervalMinutes, maxSyncAge, staleLockTimeoutMinutes }, mastra }) => {
    const logger = mastra?.getLogger();
    logger?.info("🔍 [SyncMonitor] Checking Notion sync status", {
      syncIntervalMinutes,
      maxSyncAge,
      staleLockTimeoutMinutes,
    });

    try {
      const now = new Date();
      const staleThreshold = new Date(now.getTime() - staleLockTimeoutMinutes * 60 * 1000);
      
      // First, detect and recover stale locks
      logger?.info('🔍 [SyncMonitor] Checking for stale locks older than', {
        staleLockTimeoutMinutes,
        staleThreshold: staleThreshold.toISOString(),
      });
      
      // Find running syncs that are stale (using updatedAt for heartbeat detection)
      const staleSyncs = await db
        .select({
          id: notionSyncStatus.id,
          startedAt: notionSyncStatus.startedAt,
          updatedAt: notionSyncStatus.updatedAt,
        })
        .from(notionSyncStatus)
        .where(
          and(
            eq(notionSyncStatus.status, "running"),
            lt(notionSyncStatus.updatedAt, staleThreshold)
          )
        );
      
      let staleLocksRecovered = 0;
      const staleLockDetails: any[] = [];
      
      // Recover stale locks atomically
      for (const staleSync of staleSyncs) {
        const ageMinutes = Math.floor((now.getTime() - staleSync.updatedAt.getTime()) / (1000 * 60));
        
        logger?.warn('💀 [SyncMonitor] Recovering stale sync lock', {
          syncId: staleSync.id,
          startedAt: staleSync.startedAt.toISOString(),
          lastHeartbeat: staleSync.updatedAt.toISOString(),
          ageMinutes,
        });
        
        try {
          // Atomically mark as failed and release lock
          await db.transaction(async (tx) => {
            await tx.update(notionSyncStatus)
              .set({
                status: "failed",
                completedAt: sql`NOW()`,
                errorMessage: `Stale sync recovered - no heartbeat for ${ageMinutes} minutes (timeout: ${staleLockTimeoutMinutes}m)`,
                updatedAt: sql`NOW()`,
              })
              .where(eq(notionSyncStatus.id, staleSync.id));
            
            // Release the sync lock tied to this specific syncId (hardened lock release)
            await tx.delete(notionSyncLock)
              .where(
                and(
                  eq(notionSyncLock.lockName, "sync"),
                  eq(notionSyncLock.syncId, staleSync.id)
                )
              );
          });
          
          staleLocksRecovered++;
          staleLockDetails.push({
            syncId: staleSync.id,
            startedAt: staleSync.startedAt.toISOString(),
            lastHeartbeat: staleSync.updatedAt.toISOString(),
            ageMinutes,
          });
          
          logger?.info('✅ [SyncMonitor] Successfully recovered stale sync lock', {
            syncId: staleSync.id,
            ageMinutes,
          });
        } catch (error) {
          logger?.error('❌ [SyncMonitor] Failed to recover stale sync lock', {
            syncId: staleSync.id,
            error,
          });
        }
      }
      
      // Now check for currently running syncs after stale recovery
      const runningCountResult = await db
        .select({ count: count() })
        .from(notionSyncStatus)
        .where(eq(notionSyncStatus.status, "running"));

      const runningCount = Number(runningCountResult[0]?.count || 0);

      if (runningCount > 0) {
        logger?.info("🔄 [SyncMonitor] Sync already running", { runningCount });
        return {
          syncNeeded: false,
          runningSyncs: runningCount,
          staleLocksRecovered,
          staleLockDetails,
          timeSinceLastSync: 0,
          recommendation: `${runningCount} sync(s) already running`,
        };
      }

      // Get the most recent completed sync
      const lastCompletedSync = await db
        .select()
        .from(notionSyncStatus)
        .where(eq(notionSyncStatus.status, "completed"))
        .orderBy(desc(notionSyncStatus.completedAt))
        .limit(1);

      // Reuse the existing 'now' variable declared earlier
      let timeSinceLastSync = Infinity;
      let syncNeeded = false;
      let recommendation = "No previous sync found - full sync needed";
      let lastSyncTime: string | undefined;
      let lastSyncId: number | undefined;
      let lastSyncStatus: string | undefined;

      if (lastCompletedSync.length > 0) {
        const lastSync = lastCompletedSync[0];
        lastSyncId = lastSync.id;
        lastSyncStatus = lastSync.status;
        lastSyncTime = lastSync.completedAt?.toISOString();
        
        if (lastSync.completedAt) {
          timeSinceLastSync = Math.floor((now.getTime() - lastSync.completedAt.getTime()) / (1000 * 60));
          
          if (timeSinceLastSync >= maxSyncAge) {
            syncNeeded = true;
            recommendation = `Last sync was ${timeSinceLastSync} minutes ago, exceeding max age of ${maxSyncAge} minutes`;
          } else if (timeSinceLastSync >= syncIntervalMinutes) {
            syncNeeded = true;
            recommendation = `Last sync was ${timeSinceLastSync} minutes ago, ready for incremental sync`;
          } else {
            syncNeeded = false;
            recommendation = `Last sync was ${timeSinceLastSync} minutes ago, too recent (interval: ${syncIntervalMinutes} minutes)`;
          }
        }
      } else {
        syncNeeded = true;
      }

      // Check for failed syncs in the last hour that might need retry
      const recentFailedSyncs = await db
        .select()
        .from(notionSyncStatus)
        .where(
          and(
            eq(notionSyncStatus.status, "failed"),
            gte(notionSyncStatus.startedAt, new Date(now.getTime() - 60 * 60 * 1000))
          )
        );

      if (recentFailedSyncs.length > 0 && !syncNeeded) {
        syncNeeded = true;
        recommendation += ` + ${recentFailedSyncs.length} failed sync(s) need retry`;
      }

      logger?.info("✅ [SyncMonitor] Sync status check completed", {
        syncNeeded,
        lastSyncId,
        timeSinceLastSync,
        recommendation,
        runningSyncs: runningCount,
        failedSyncs: recentFailedSyncs.length,
      });

      return {
        syncNeeded,
        lastSyncId,
        lastSyncTime,
        lastSyncStatus,
        timeSinceLastSync: timeSinceLastSync === Infinity ? -1 : timeSinceLastSync,
        recommendation,
        runningSyncs: runningCount,
        staleLocksRecovered,
        staleLockDetails,
      };

    } catch (error) {
      logger?.error("❌ [SyncMonitor] Failed to check sync status", { error });
      throw error;
    }
  },
});

export const notionSyncTriggerTool = createTool({
  id: "notion-sync-trigger-tool",
  description: "Intelligently trigger Notion sync based on current status and settings",
  inputSchema: z.object({
    forceSync: z.boolean().default(false).describe("Force sync even if not needed"),
    syncType: z.enum(["auto", "incremental", "full"]).default("auto").describe("Type of sync to perform"),
    syncIntervalMinutes: z.number().default(15).describe("Minimum minutes between syncs"),
    maxSyncAge: z.number().default(60).describe("Maximum age in minutes before forcing a new sync"),
    maxPages: z.number().default(500).describe("Maximum pages to sync in one run"),
  }),
  outputSchema: z.object({
    syncTriggered: z.boolean(),
    syncType: z.string(),
    syncId: z.number().optional(),
    reason: z.string(),
    skippedReason: z.string().optional(),
  }),
  execute: async ({ context: { forceSync, syncType, syncIntervalMinutes, maxSyncAge, maxPages }, mastra }) => {
    const logger = mastra?.getLogger();
    logger?.info("🚀 [SyncTrigger] Evaluating sync trigger", {
      forceSync,
      syncType,
      syncIntervalMinutes,
      maxSyncAge,
      maxPages,
    });

    try {
      // First check sync status - using direct function call to avoid runtime context issues
      const statusResult = await notionSyncStatusTool.execute({
        context: { syncIntervalMinutes, maxSyncAge, staleLockTimeoutMinutes: 45 },
        mastra,
      } as any);

      if (!forceSync && !statusResult.syncNeeded) {
        logger?.info("⏸️ [SyncTrigger] Sync not needed", {
          reason: statusResult.recommendation,
        });
        
        return {
          syncTriggered: false,
          syncType: "none",
          reason: "Sync not needed",
          skippedReason: statusResult.recommendation,
        };
      }

      if (statusResult.runningSyncs > 0 && !forceSync) {
        logger?.info("⏸️ [SyncTrigger] Sync already running", {
          runningSyncs: statusResult.runningSyncs,
        });
        
        return {
          syncTriggered: false,
          syncType: "none",
          reason: "Sync already running",
          skippedReason: `${statusResult.runningSyncs} sync(s) already in progress`,
        };
      }

      // Determine sync type
      let actualSyncType = syncType;
      if (syncType === "auto") {
        // Auto-determine sync type based on conditions
        if (!statusResult.lastSyncTime) {
          actualSyncType = "full";
        } else if (statusResult.timeSinceLastSync >= maxSyncAge) {
          actualSyncType = "full";
        } else {
          actualSyncType = "incremental";
        }
      }

      // Atomically acquire sync lock to prevent race conditions
      let syncRecord;
      try {
        // Use transaction to atomically create both sync record and lock
        const result = await db.transaction(async (tx) => {
          // Try to acquire the sync lock atomically
          try {
            // First create the sync record
            const [newSyncRecord] = await tx.insert(notionSyncStatus).values({
              syncType: actualSyncType,
              status: "running",
              startedAt: sql`NOW()`,
              processedPages: 0,
              processedBlocks: 0,
            }).returning();
            
            // Then try to acquire the lock - this will fail if another sync is running
            await tx.insert(notionSyncLock).values({
              lockName: "sync",
              syncId: newSyncRecord.id,
              lockedAt: sql`NOW()`,
              lockedBy: `trigger-${Date.now()}`,
            });
            
            return newSyncRecord;
          } catch (lockError) {
            // Lock acquisition failed - another sync is running
            throw lockError;
          }
        });
        
        syncRecord = [result];
        logger?.info("🔒 [SyncTrigger] Successfully acquired atomic sync lock", {
          syncId: syncRecord[0].id,
          syncType: actualSyncType,
        });
      } catch (error) {
        // If transaction fails, another sync is already running (race condition prevented)
        logger?.info("❌ [SyncTrigger] Failed to acquire atomic sync lock - race condition prevented", { error });
        return {
          syncTriggered: false,
          syncType: "none", 
          reason: "Sync lock acquisition failed",
          skippedReason: "Another sync started simultaneously (atomic race condition prevented)",
        };
      }

      // Import and execute the appropriate sync tool with proper error handling
      const { fullNotionIngestionTool, incrementalNotionIngestionTool } = await import("./notionIngestionTool");

      let syncResult;
      try {
        if (actualSyncType === "full") {
          logger?.info("🔄 [SyncTrigger] Starting full sync", { syncId: syncRecord[0].id });
          syncResult = await fullNotionIngestionTool.execute({
            context: { 
              syncId: syncRecord[0].id,
              forceRefresh: forceSync,
              maxPages,
            },
            mastra,
          } as any);
        } else {
          logger?.info("🔄 [SyncTrigger] Starting incremental sync", { syncId: syncRecord[0].id });
          syncResult = await incrementalNotionIngestionTool.execute({
            context: { 
              syncId: syncRecord[0].id,
              maxPages,
            },
            mastra,
          } as any);
        }

        // Update sync record to completed on success and release lock
        await db.transaction(async (tx) => {
          await tx.update(notionSyncStatus)
            .set({
              status: "completed",
              completedAt: sql`NOW()`,
              processedPages: syncResult.pagesProcessed || 0,
              processedBlocks: syncResult.blocksProcessed || 0,
              updatedAt: sql`NOW()`,
            })
            .where(eq(notionSyncStatus.id, syncRecord[0].id));
          
          // Release the sync lock tied to this specific syncId (hardened lock release)
          await tx.delete(notionSyncLock)
            .where(
              and(
                eq(notionSyncLock.lockName, "sync"),
                eq(notionSyncLock.syncId, syncRecord[0].id)
              )
            );
        });

      } catch (syncError) {
        // Update sync record to failed on error and release lock
        await db.transaction(async (tx) => {
          await tx.update(notionSyncStatus)
            .set({
              status: "failed", 
              completedAt: sql`NOW()`,
              errorMessage: String(syncError),
              updatedAt: sql`NOW()`,
            })
            .where(eq(notionSyncStatus.id, syncRecord[0].id));
          
          // Release the sync lock tied to this specific syncId (hardened lock release)
          await tx.delete(notionSyncLock)
            .where(
              and(
                eq(notionSyncLock.lockName, "sync"),
                eq(notionSyncLock.syncId, syncRecord[0].id)
              )
            );
        });
        
        logger?.error("❌ [SyncTrigger] Sync execution failed", {
          syncId: syncRecord[0].id,
          error: syncError,
        });
        throw syncError;
      }

      const reason = forceSync 
        ? `Force sync requested (${actualSyncType})`
        : `Auto-triggered ${actualSyncType} sync: ${statusResult.recommendation}`;

      logger?.info("✅ [SyncTrigger] Sync completed successfully", {
        syncType: actualSyncType,
        syncId: syncResult.syncId,
        pagesProcessed: syncResult.pagesProcessed,
        blocksProcessed: syncResult.blocksProcessed,
        duration: syncResult.duration,
      });

      return {
        syncTriggered: true,
        syncType: actualSyncType,
        syncId: syncResult.syncId,
        reason,
      };

    } catch (error) {
      logger?.error("❌ [SyncTrigger] Sync trigger failed", { error });
      throw error;
    }
  },
});

export const notionDataStatsTool = createTool({
  id: "notion-data-stats-tool", 
  description: "Get statistics about locally stored Notion data",
  inputSchema: z.object({}),
  outputSchema: z.object({
    totalPages: z.number(),
    totalBlocks: z.number(),
    lastSyncTime: z.string().optional(),
    oldestPageTime: z.string().optional(),
    newestPageTime: z.string().optional(),
    syncHistory: z.array(z.object({
      id: z.number(),
      syncType: z.string(),
      status: z.string(),
      startedAt: z.string(),
      completedAt: z.string().optional(),
      pagesProcessed: z.number(),
      blocksProcessed: z.number(),
      duration: z.number().optional(),
    })),
  }),
  execute: async ({ mastra }) => {
    const logger = mastra?.getLogger();
    logger?.info("📊 [DataStats] Gathering Notion data statistics");

    try {
      // Get total counts using efficient aggregate queries
      const pageCountResult = await db.select({ count: count() }).from(notionPages);
      const blockCountResult = await db.select({ count: count() }).from(notionBlocks);
      
      const pagesCount = Number(pageCountResult[0]?.count || 0);
      const blocksCount = Number(blockCountResult[0]?.count || 0);

      // Get page time range using efficient MIN/MAX query
      const pageTimeStats = await db
        .select({
          oldestCreated: min(notionPages.createdTime),
          newestEdited: max(notionPages.lastEditedTime),
        })
        .from(notionPages);

      // Get recent sync history
      const recentSyncs = await db
        .select({
          id: notionSyncStatus.id,
          syncType: notionSyncStatus.syncType,
          status: notionSyncStatus.status,
          startedAt: notionSyncStatus.startedAt,
          completedAt: notionSyncStatus.completedAt,
          pagesProcessed: notionSyncStatus.processedPages,
          blocksProcessed: notionSyncStatus.processedBlocks,
        })
        .from(notionSyncStatus)
        .orderBy(desc(notionSyncStatus.startedAt))
        .limit(10);

      // Get last successful sync
      const lastSync = await db
        .select()
        .from(notionSyncStatus)
        .where(eq(notionSyncStatus.status, "completed"))
        .orderBy(desc(notionSyncStatus.completedAt))
        .limit(1);

      const syncHistory = recentSyncs.map(sync => ({
        id: sync.id,
        syncType: sync.syncType,
        status: sync.status,
        startedAt: sync.startedAt.toISOString(),
        completedAt: sync.completedAt?.toISOString(),
        pagesProcessed: sync.pagesProcessed || 0,
        blocksProcessed: sync.blocksProcessed || 0,
        duration: sync.completedAt && sync.startedAt 
          ? Math.round((sync.completedAt.getTime() - sync.startedAt.getTime()) / 1000)
          : undefined,
      }));

      const stats = {
        totalPages: pagesCount,
        totalBlocks: blocksCount,
        lastSyncTime: lastSync[0]?.completedAt?.toISOString(),
        oldestPageTime: pageTimeStats[0]?.oldestCreated?.toISOString(),
        newestPageTime: pageTimeStats[0]?.newestEdited?.toISOString(),
        syncHistory,
      };

      logger?.info("✅ [DataStats] Statistics gathered", stats);
      return stats;

    } catch (error) {
      logger?.error("❌ [DataStats] Failed to gather statistics", { error });
      throw error;
    }
  },
});