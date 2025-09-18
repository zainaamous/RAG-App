import { createTool } from "@mastra/core/tools";
import type { IMastraLogger } from "@mastra/core/logger";
import { z } from "zod";
import { Client } from "@notionhq/client";
import { db, sql } from "../../server/storage";
import { notionPages, notionBlocks, notionSyncStatus } from "../../shared/schema";
import { eq, desc } from "drizzle-orm";

// Initialize Notion client
const getNotionClient = () => {
  const token = process.env.NOTION_TOKEN;
  if (!token) {
    throw new Error("NOTION_TOKEN environment variable is required");
  }
  return new Client({ auth: token });
};

// Retry utility with exponential backoff
async function withRetry<T>(
  operation: () => Promise<T>, 
  maxRetries: number = 3, 
  baseDelay: number = 1000,
  logger?: IMastraLogger
): Promise<T> {
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      return await operation();
    } catch (error: any) {
      const isRateLimited = error?.code === "rate_limited" || error?.status === 429;
      const isServerError = error?.status >= 500;
      
      if (attempt === maxRetries || (!isRateLimited && !isServerError)) {
        throw error;
      }

      const delay = baseDelay * Math.pow(2, attempt - 1) + Math.random() * 1000; // Add jitter
      logger?.warn(`🔄 [NotionIngestion] Retry attempt ${attempt}/${maxRetries} after ${delay}ms`, {
        error: error?.message,
        status: error?.status,
        code: error?.code,
      });
      
      await new Promise(resolve => setTimeout(resolve, delay));
    }
  }
  throw new Error("Max retries exceeded");
}

// Helper function to extract plain text from rich text array
const extractPlainText = (richText: any[]): string => {
  if (!Array.isArray(richText)) return "";
  return richText.map(text => text.plain_text || "").join("");
};

// Helper function to process blocks recursively within a transaction
async function processBlocksInTransaction(
  notion: Client,
  blockId: string,
  pageId: string,
  parentId: string | null,
  tx: any,
  logger?: IMastraLogger,
  depth: number = 0
): Promise<number> {
  if (depth > 10) {
    logger?.warn(`⚠️ [NotionIngestion] Maximum depth reached for block ${blockId}`);
    return 0;
  }

  let processedCount = 0;
  let cursor: string | undefined;
  
  do {
    logger?.debug(`🔄 [NotionIngestion] Fetching blocks for ${blockId}, depth ${depth}`);
    
    const response = await withRetry(
      () => notion.blocks.children.list({
        block_id: blockId,
        start_cursor: cursor,
        page_size: 100,
      }),
      3,
      1000,
      logger
    );

    // Collect all block data for batched insert
    const blocksToInsert: any[] = [];

    for (const block of response.results) {
      if (!("type" in block)) continue;

      // Extract plain text based on block type
      let plainText = "";
      let richText: any[] = [];

      try {
        switch (block.type) {
          case "paragraph":
            plainText = extractPlainText(block.paragraph?.rich_text || []);
            richText = block.paragraph?.rich_text || [];
            break;
          case "heading_1":
            plainText = extractPlainText(block.heading_1?.rich_text || []);
            richText = block.heading_1?.rich_text || [];
            break;
          case "heading_2":
            plainText = extractPlainText(block.heading_2?.rich_text || []);
            richText = block.heading_2?.rich_text || [];
            break;
          case "heading_3":
            plainText = extractPlainText(block.heading_3?.rich_text || []);
            richText = block.heading_3?.rich_text || [];
            break;
          case "bulleted_list_item":
            plainText = extractPlainText(block.bulleted_list_item?.rich_text || []);
            richText = block.bulleted_list_item?.rich_text || [];
            break;
          case "numbered_list_item":
            plainText = extractPlainText(block.numbered_list_item?.rich_text || []);
            richText = block.numbered_list_item?.rich_text || [];
            break;
          case "to_do":
            plainText = extractPlainText(block.to_do?.rich_text || []);
            richText = block.to_do?.rich_text || [];
            break;
          case "toggle":
            plainText = extractPlainText(block.toggle?.rich_text || []);
            richText = block.toggle?.rich_text || [];
            break;
          case "code":
            plainText = extractPlainText(block.code?.rich_text || []);
            richText = block.code?.rich_text || [];
            break;
          case "quote":
            plainText = extractPlainText(block.quote?.rich_text || []);
            richText = block.quote?.rich_text || [];
            break;
          case "callout":
            plainText = extractPlainText(block.callout?.rich_text || []);
            richText = block.callout?.rich_text || [];
            break;
        }
      } catch (error) {
        logger?.warn(`⚠️ [NotionIngestion] Failed to extract text from block ${block.id}:`, error);
      }

      blocksToInsert.push({
        id: block.id,
        pageId: pageId,
        parentId: parentId,
        type: block.type,
        hasChildren: block.has_children || false,
        isArchived: block.archived || false,
        content: block as any,
        plainText: plainText || null,
        richText: richText.length > 0 ? richText : null,
        createdTime: new Date(block.created_time),
        lastEditedTime: new Date(block.last_edited_time),
      });

      processedCount++;
    }

    // Batch insert blocks within transaction
    if (blocksToInsert.length > 0) {
      await tx.insert(notionBlocks)
        .values(blocksToInsert)
        .onConflictDoUpdate({
          target: [notionBlocks.id],
          set: {
            type: sql`EXCLUDED.type`,
            hasChildren: sql`EXCLUDED.has_children`,
            isArchived: sql`EXCLUDED.is_archived`,
            content: sql`EXCLUDED.content`,
            plainText: sql`EXCLUDED.plain_text`,
            richText: sql`EXCLUDED.rich_text`,
            lastEditedTime: sql`EXCLUDED.last_edited_time`,
            syncedAt: new Date(),
            updatedAt: sql`NOW()`,
          },
        });
    }

    // Process child blocks recursively
    for (const block of response.results) {
      if ("type" in block && block.has_children) {
        const childCount = await processBlocksInTransaction(
          notion,
          block.id,
          pageId,
          block.id,
          tx,
          logger,
          depth + 1
        );
        processedCount += childCount;
      }
    }

    cursor = response.next_cursor || undefined;
  } while (cursor);

  return processedCount;
}

// Helper function to process blocks recursively (for non-transaction operations)
async function processBlocks(
  notion: Client,
  blockId: string,
  pageId: string,
  parentId: string | null,
  logger?: IMastraLogger,
  depth: number = 0
): Promise<number> {
  if (depth > 10) {
    logger?.warn(`⚠️ [NotionIngestion] Maximum depth reached for block ${blockId}`);
    return 0;
  }

  let processedCount = 0;
  let cursor: string | undefined;
  
  do {
    logger?.debug(`🔄 [NotionIngestion] Fetching blocks for ${blockId}, depth ${depth}`);
    
    const response = await withRetry(
      () => notion.blocks.children.list({
        block_id: blockId,
        start_cursor: cursor,
        page_size: 100,
      }),
      3,
      1000,
      logger
    );

    for (const block of response.results) {
      if (!("type" in block)) continue;

      // Extract plain text based on block type
      let plainText = "";
      let richText: any[] = [];

      try {
        switch (block.type) {
          case "paragraph":
            plainText = extractPlainText(block.paragraph?.rich_text || []);
            richText = block.paragraph?.rich_text || [];
            break;
          case "heading_1":
            plainText = extractPlainText(block.heading_1?.rich_text || []);
            richText = block.heading_1?.rich_text || [];
            break;
          case "heading_2":
            plainText = extractPlainText(block.heading_2?.rich_text || []);
            richText = block.heading_2?.rich_text || [];
            break;
          case "heading_3":
            plainText = extractPlainText(block.heading_3?.rich_text || []);
            richText = block.heading_3?.rich_text || [];
            break;
          case "bulleted_list_item":
            plainText = extractPlainText(block.bulleted_list_item?.rich_text || []);
            richText = block.bulleted_list_item?.rich_text || [];
            break;
          case "numbered_list_item":
            plainText = extractPlainText(block.numbered_list_item?.rich_text || []);
            richText = block.numbered_list_item?.rich_text || [];
            break;
          case "to_do":
            plainText = extractPlainText(block.to_do?.rich_text || []);
            richText = block.to_do?.rich_text || [];
            break;
          case "toggle":
            plainText = extractPlainText(block.toggle?.rich_text || []);
            richText = block.toggle?.rich_text || [];
            break;
          case "code":
            plainText = extractPlainText(block.code?.rich_text || []);
            richText = block.code?.rich_text || [];
            break;
          case "quote":
            plainText = extractPlainText(block.quote?.rich_text || []);
            richText = block.quote?.rich_text || [];
            break;
          case "callout":
            plainText = extractPlainText(block.callout?.rich_text || []);
            richText = block.callout?.rich_text || [];
            break;
        }
      } catch (error) {
        logger?.warn(`⚠️ [NotionIngestion] Failed to extract text from block ${block.id}:`, error);
      }

      // Store block in database
      await db.insert(notionBlocks)
        .values({
          id: block.id,
          pageId: pageId,
          parentId: parentId,
          type: block.type,
          hasChildren: block.has_children || false,
          isArchived: block.archived || false,
          content: block as any,
          plainText: plainText || null,
          richText: richText.length > 0 ? richText : null,
          createdTime: new Date(block.created_time),
          lastEditedTime: new Date(block.last_edited_time),
        })
        .onConflictDoUpdate({
          target: [notionBlocks.id],
          set: {
            type: block.type,
            hasChildren: block.has_children || false,
            isArchived: block.archived || false,
            content: block as any,
            plainText: plainText || null,
            richText: richText.length > 0 ? richText : null,
            lastEditedTime: new Date(block.last_edited_time),
            syncedAt: new Date(),
            updatedAt: sql`NOW()`,
          },
        });

      processedCount++;

      // Recursively process child blocks if they exist
      if (block.has_children) {
        const childCount = await processBlocks(
          notion,
          block.id,
          pageId,
          block.id,
          logger,
          depth + 1
        );
        processedCount += childCount;
      }
    }

    cursor = response.next_cursor || undefined;
  } while (cursor);

  return processedCount;
}

export const fullNotionIngestionTool = createTool({
  id: "full-notion-ingestion-tool",
  description: "Performs full ingestion of all Notion pages and blocks into local database for realtime access",
  inputSchema: z.object({
    syncId: z.number().describe("Sync record ID to update with progress"),
    forceRefresh: z.boolean().default(false).describe("Force refresh of all pages even if not modified"),
    maxPages: z.number().default(1000).describe("Maximum number of pages to process in this run"),
  }),
  outputSchema: z.object({
    syncId: z.number(),
    status: z.string(),
    pagesProcessed: z.number(),
    blocksProcessed: z.number(),
    errors: z.array(z.string()),
    duration: z.number(),
  }),
  execute: async ({ context: { syncId, forceRefresh, maxPages }, mastra }) => {
    const logger = mastra?.getLogger();
    const startTime = Date.now();
    const errors: string[] = [];
    let pagesProcessed = 0;
    let blocksProcessed = 0;
    let lastHeartbeat = Date.now();
    const heartbeatIntervalMs = 2 * 60 * 1000; // 2 minutes
    const heartbeatPageInterval = 10; // Every 10 pages

    logger?.info("🚀 [NotionIngestion] Starting full Notion ingestion", {
      syncId,
      forceRefresh,
      maxPages,
    });

    try {
      const notion = getNotionClient();

      // Search for all pages
      let cursor: string | undefined;
      let hasMore = true;

      while (hasMore && pagesProcessed < maxPages) {
        logger?.info(`📝 [NotionIngestion] Processing batch ${Math.floor(pagesProcessed / 100) + 1}`);

        const response = await withRetry(
          () => notion.search({
            filter: {
              property: "object",
              value: "page",
            },
            sort: {
              direction: "descending",
              timestamp: "last_edited_time",
            },
            start_cursor: cursor,
            page_size: Math.min(100, maxPages - pagesProcessed),
          }),
          3,
          1000,
          logger
        );

        for (const page of response.results) {
          if (!("properties" in page)) continue;
          
          // Type guard for page
          const pageData = page as any;

          try {
            // Extract page title
            let title = "Untitled";
            if (pageData.properties) {
              for (const [key, property] of Object.entries(pageData.properties)) {
                if ((property as any).type === "title" && (property as any).title) {
                  title = extractPlainText((property as any).title);
                  break;
                }
              }
            }

            // Determine parent info
            let parentId: string | null = null;
            let parentType: string = "workspace";
            
            if (pageData.parent) {
              if (pageData.parent.type === "page_id") {
                parentId = pageData.parent.page_id;
                parentType = "page";
              } else if (pageData.parent.type === "database_id") {
                parentId = pageData.parent.database_id;
                parentType = "database";
              }
            }

            // Store page in database
            await db.insert(notionPages)
              .values({
                id: pageData.id,
                title,
                url: pageData.url || null,
                parentId,
                parentType,
                isArchived: pageData.archived || false,
                createdTime: new Date(pageData.created_time),
                lastEditedTime: new Date(pageData.last_edited_time),
                properties: pageData.properties,
                icon: pageData.icon || null,
                cover: pageData.cover || null,
              })
              .onConflictDoUpdate({
                target: [notionPages.id],
                set: {
                  title,
                  url: pageData.url || null,
                  parentId,
                  parentType,
                  isArchived: pageData.archived || false,
                  lastEditedTime: new Date(pageData.last_edited_time),
                  properties: pageData.properties,
                  icon: pageData.icon || null,
                  cover: pageData.cover || null,
                  syncedAt: new Date(),
                  updatedAt: sql`NOW()`,
                },
              });

            pagesProcessed++;

            // Process blocks for this page
            const blockCount = await processBlocks(
              notion,
              page.id,
              page.id,
              null,
              logger
            );
            
            blocksProcessed += blockCount;

            logger?.debug(`✅ [NotionIngestion] Processed page "${title}" with ${blockCount} blocks`);
            
            // More frequent heartbeat updates for production readiness
            const now = Date.now();
            const needsHeartbeat = (
              pagesProcessed % heartbeatPageInterval === 0 ||
              (now - lastHeartbeat) >= heartbeatIntervalMs
            );
            
            if (needsHeartbeat) {
              await db.update(notionSyncStatus)
                .set({
                  processedPages: pagesProcessed,
                  processedBlocks: blocksProcessed,
                  updatedAt: sql`NOW()`,
                })
                .where(eq(notionSyncStatus.id, syncId));
              
              lastHeartbeat = now;
              logger?.debug(`💓 [NotionIngestion] Heartbeat update: ${pagesProcessed} pages, ${blocksProcessed} blocks`);
            }

          } catch (error) {
            const errorMsg = `Failed to process page ${page.id}: ${error}`;
            logger?.error(errorMsg);
            errors.push(errorMsg);
          }
        }

        cursor = response.next_cursor || undefined;
        hasMore = response.has_more && cursor !== undefined;

        // Update sync progress (batch-level heartbeat)
        await db.update(notionSyncStatus)
          .set({
            processedPages: pagesProcessed,
            processedBlocks: blocksProcessed,
            updatedAt: sql`NOW()`,
          })
          .where(eq(notionSyncStatus.id, syncId));
        
        lastHeartbeat = Date.now();
        logger?.info(`📊 [NotionIngestion] Batch heartbeat: ${pagesProcessed} pages, ${blocksProcessed} blocks processed`);
      }

      // Mark sync as completed
      await db.update(notionSyncStatus)
        .set({
          status: "completed",
          completedAt: sql`NOW()`,
          processedPages: pagesProcessed,
          processedBlocks: blocksProcessed,
          totalPages: pagesProcessed,
          totalBlocks: blocksProcessed,
          updatedAt: sql`NOW()`,
        })
        .where(eq(notionSyncStatus.id, syncId));

      const duration = Date.now() - startTime;
      
      logger?.info("✅ [NotionIngestion] Full ingestion completed successfully", {
        syncId,
        pagesProcessed,
        blocksProcessed,
        duration,
        errors: errors.length,
      });

      return {
        syncId,
        status: "completed",
        pagesProcessed,
        blocksProcessed,
        errors,
        duration,
      };

    } catch (error) {
      const errorMsg = `Full ingestion failed: ${error}`;
      logger?.error(errorMsg);
      errors.push(errorMsg);

      // Mark sync as failed
      await db.update(notionSyncStatus)
        .set({
          status: "failed",
          completedAt: sql`NOW()`,
          errorMessage: errorMsg,
          processedPages: pagesProcessed,
          processedBlocks: blocksProcessed,
          updatedAt: sql`NOW()`,
        })
        .where(eq(notionSyncStatus.id, syncId));

      const duration = Date.now() - startTime;

      return {
        syncId,
        status: "failed",
        pagesProcessed,
        blocksProcessed,
        errors,
        duration,
      };
    }
  },
});

export const incrementalNotionIngestionTool = createTool({
  id: "incremental-notion-ingestion-tool",
  description: "Performs incremental sync of modified Notion pages since last sync",
  inputSchema: z.object({
    syncId: z.number().describe("Sync record ID to update with progress"),
    since: z.string().optional().describe("ISO timestamp to sync from (defaults to last successful sync)"),
    maxPages: z.number().default(500).describe("Maximum pages to process in this run"),
  }),
  outputSchema: z.object({
    syncId: z.number(),
    status: z.string(),
    pagesProcessed: z.number(),
    blocksProcessed: z.number(),
    errors: z.array(z.string()),
    duration: z.number(),
    sincePath: z.string(),
  }),
  execute: async ({ context: { syncId, since, maxPages }, mastra }) => {
    const logger = mastra?.getLogger();
    const startTime = Date.now();
    const errors: string[] = [];
    let pagesProcessed = 0;
    let blocksProcessed = 0;
    let lastHeartbeat = Date.now();
    const heartbeatIntervalMs = 2 * 60 * 1000; // 2 minutes
    const heartbeatPageInterval = 10; // Every 10 pages

    // Determine sync timestamp
    let sinceTimestamp: string;
    if (since) {
      sinceTimestamp = since;
    } else {
      // Get last successful sync timestamp
      const lastSync = await db
        .select()
        .from(notionSyncStatus)
        .where(eq(notionSyncStatus.status, "completed"))
        .orderBy(desc(notionSyncStatus.completedAt))
        .limit(1);
        
      sinceTimestamp = lastSync[0]?.completedAt?.toISOString() || new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();
    }

    logger?.info("🔄 [NotionIngestion] Starting incremental sync", {
      syncId,
      sinceTimestamp,
      maxPages,
    });

    try {
      const notion = getNotionClient();

      // Search for recently modified pages
      let cursor: string | undefined;
      let hasMore = true;

      while (hasMore && pagesProcessed < maxPages) {
        const response = await withRetry(
          () => notion.search({
            filter: {
              property: "object",
              value: "page",
            },
            sort: {
              direction: "descending", 
              timestamp: "last_edited_time",
            },
            start_cursor: cursor,
            page_size: Math.min(100, maxPages - pagesProcessed),
          }),
          3,
          1000,
          logger
        );

        let foundOldPage = false;

        for (const page of response.results) {
          if (!("properties" in page)) continue;
          
          // Type guard for page
          const pageData = page as any;

          // Check if page was modified since our timestamp
          const pageLastEdited = new Date(pageData.last_edited_time);
          const sinceDate = new Date(sinceTimestamp);

          if (pageLastEdited <= sinceDate) {
            foundOldPage = true;
            continue; // Skip this page, it's not modified since our threshold
          }

          try {
            // Extract page title
            let title = "Untitled";
            if (pageData.properties) {
              for (const [key, property] of Object.entries(pageData.properties)) {
                if ((property as any).type === "title" && (property as any).title) {
                  title = extractPlainText((property as any).title);
                  break;
                }
              }
            }

            // Determine parent info
            let parentId: string | null = null;
            let parentType: string = "workspace";
            
            if (pageData.parent) {
              if (pageData.parent.type === "page_id") {
                parentId = pageData.parent.page_id;
                parentType = "page";
              } else if (pageData.parent.type === "database_id") {
                parentId = pageData.parent.database_id;
                parentType = "database";
              }
            }

            // Store/update page
            await db.insert(notionPages)
              .values({
                id: pageData.id,
                title,
                url: pageData.url || null,
                parentId,
                parentType,
                isArchived: pageData.archived || false,
                createdTime: new Date(pageData.created_time),
                lastEditedTime: new Date(pageData.last_edited_time),
                properties: pageData.properties,
                icon: pageData.icon || null,
                cover: pageData.cover || null,
              })
              .onConflictDoUpdate({
                target: [notionPages.id],
                set: {
                  title,
                  url: pageData.url || null,
                  parentId,
                  parentType,
                  isArchived: pageData.archived || false,
                  lastEditedTime: new Date(pageData.last_edited_time),
                  properties: pageData.properties,
                  icon: pageData.icon || null,
                  cover: pageData.cover || null,
                  syncedAt: new Date(),
                  updatedAt: sql`NOW()`,
                },
              });

            pagesProcessed++;

            // Use transaction to safely refresh page content
            await db.transaction(async (tx) => {
              // Delete existing blocks for this page
              await tx.delete(notionBlocks).where(eq(notionBlocks.pageId, pageData.id));

              // Process blocks for this page within transaction
              const blockCount = await processBlocksInTransaction(
                notion,
                pageData.id,
                pageData.id,
                null,
                tx,
                logger
              );
              
              blocksProcessed += blockCount;
              
              logger?.debug(`🔄 [NotionIngestion] Updated page "${title}" with ${blockCount} blocks`);
            });
            
            // More frequent heartbeat updates for production readiness
            const now = Date.now();
            const needsHeartbeat = (
              pagesProcessed % heartbeatPageInterval === 0 ||
              (now - lastHeartbeat) >= heartbeatIntervalMs
            );
            
            if (needsHeartbeat) {
              await db.update(notionSyncStatus)
                .set({
                  processedPages: pagesProcessed,
                  processedBlocks: blocksProcessed,
                  updatedAt: sql`NOW()`,
                })
                .where(eq(notionSyncStatus.id, syncId));
              
              lastHeartbeat = now;
              logger?.debug(`💓 [NotionIngestion] Incremental heartbeat: ${pagesProcessed} pages, ${blocksProcessed} blocks`);
            }

          } catch (error) {
            const errorMsg = `Failed to process page ${page.id}: ${error}`;
            logger?.error(errorMsg);
            errors.push(errorMsg);
          }
        }

        cursor = response.next_cursor || undefined;
        hasMore = response.has_more && cursor !== undefined && !foundOldPage;

        // Update sync progress (batch-level heartbeat)
        await db.update(notionSyncStatus)
          .set({
            processedPages: pagesProcessed,
            processedBlocks: blocksProcessed,
            updatedAt: sql`NOW()`,
          })
          .where(eq(notionSyncStatus.id, syncId));
        
        lastHeartbeat = Date.now();
        logger?.info(`📊 [NotionIngestion] Incremental batch heartbeat: ${pagesProcessed} pages, ${blocksProcessed} blocks processed`);
      }

      // Mark sync as completed
      await db.update(notionSyncStatus)
        .set({
          status: "completed",
          completedAt: sql`NOW()`,
          processedPages: pagesProcessed,
          processedBlocks: blocksProcessed,
          totalPages: pagesProcessed,
          totalBlocks: blocksProcessed,
          updatedAt: sql`NOW()`,
        })
        .where(eq(notionSyncStatus.id, syncId));

      const duration = Date.now() - startTime;

      logger?.info("✅ [NotionIngestion] Incremental sync completed", {
        syncId,
        pagesProcessed,
        blocksProcessed,
        duration,
        errors: errors.length,
        sinceTimestamp,
      });

      return {
        syncId,
        status: "completed", 
        pagesProcessed,
        blocksProcessed,
        errors,
        duration,
        sincePath: sinceTimestamp,
      };

    } catch (error) {
      const errorMsg = `Incremental sync failed: ${error}`;
      logger?.error(errorMsg);
      errors.push(errorMsg);

      // Mark sync as failed
      await db.update(notionSyncStatus)
        .set({
          status: "failed",
          completedAt: sql`NOW()`,
          errorMessage: errorMsg,
          processedPages: pagesProcessed,
          processedBlocks: blocksProcessed,
          updatedAt: sql`NOW()`,
        })
        .where(eq(notionSyncStatus.id, syncId));

      const duration = Date.now() - startTime;

      return {
        syncId,
        status: "failed",
        pagesProcessed,
        blocksProcessed,
        errors,
        duration,
        sincePath: sinceTimestamp,
      };
    }
  },
});