import { pgTable, text, timestamp, boolean, jsonb, integer, index } from "drizzle-orm/pg-core";
import { relations } from "drizzle-orm";

// Notion Pages table - stores metadata about Notion pages
export const notionPages = pgTable(
  "notion_pages",
  {
    id: text("id").primaryKey(), // Notion page ID
    title: text("title").notNull(),
    url: text("url"),
    parentId: text("parent_id"), // For hierarchical structure
    parentType: text("parent_type"), // 'page', 'database', 'workspace'
    isArchived: boolean("is_archived").default(false),
    createdTime: timestamp("created_time").notNull(),
    lastEditedTime: timestamp("last_edited_time").notNull(),
    properties: jsonb("properties"), // Notion page properties
    icon: jsonb("icon"), // Page icon data
    cover: jsonb("cover"), // Page cover data
    syncedAt: timestamp("synced_at").defaultNow(),
    createdAt: timestamp("created_at").defaultNow(),
    updatedAt: timestamp("updated_at").defaultNow(),
  },
  (table) => ({
    titleIdx: index("notion_pages_title_idx").on(table.title),
    parentIdx: index("notion_pages_parent_idx").on(table.parentId),
    syncedAtIdx: index("notion_pages_synced_at_idx").on(table.syncedAt),
    lastEditedIdx: index("notion_pages_last_edited_idx").on(table.lastEditedTime),
  })
);

// Notion Blocks table - stores the actual content blocks from pages
export const notionBlocks = pgTable(
  "notion_blocks",
  {
    id: text("id").primaryKey(), // Notion block ID
    pageId: text("page_id").notNull().references(() => notionPages.id, { onDelete: "cascade" }),
    parentId: text("parent_id"), // Parent block ID for nested blocks
    type: text("type").notNull(), // Block type (paragraph, heading_1, etc.)
    hasChildren: boolean("has_children").default(false),
    isArchived: boolean("is_archived").default(false),
    content: jsonb("content").notNull(), // Block content data
    plainText: text("plain_text"), // Extracted plain text for search
    richText: jsonb("rich_text"), // Rich text array
    createdTime: timestamp("created_time").notNull(),
    lastEditedTime: timestamp("last_edited_time").notNull(),
    syncedAt: timestamp("synced_at").defaultNow(),
    createdAt: timestamp("created_at").defaultNow(),
    updatedAt: timestamp("updated_at").defaultNow(),
  },
  (table) => ({
    pageIdx: index("notion_blocks_page_idx").on(table.pageId),
    typeIdx: index("notion_blocks_type_idx").on(table.type),
    parentIdx: index("notion_blocks_parent_idx").on(table.parentId),
    syncedAtIdx: index("notion_blocks_synced_at_idx").on(table.syncedAt),
    plainTextIdx: index("notion_blocks_plain_text_idx").on(table.plainText),
  })
);

// Notion Sync Status table - tracks synchronization metadata
export const notionSyncStatus = pgTable("notion_sync_status", {
  id: integer("id").primaryKey().generatedAlwaysAsIdentity(),
  syncType: text("sync_type").notNull(), // 'full', 'incremental', 'page'
  status: text("status").notNull(), // 'running', 'completed', 'failed'
  startedAt: timestamp("started_at").notNull().defaultNow(),
  completedAt: timestamp("completed_at"),
  totalPages: integer("total_pages").default(0),
  processedPages: integer("processed_pages").default(0),
  totalBlocks: integer("total_blocks").default(0),
  processedBlocks: integer("processed_blocks").default(0),
  errorMessage: text("error_message"),
  metadata: jsonb("metadata"), // Additional sync metadata
  lastCursor: text("last_cursor"), // For pagination in incremental syncs
  createdAt: timestamp("created_at").defaultNow(),
  updatedAt: timestamp("updated_at").defaultNow(),
});

// Notion Sync Lock table - provides atomic concurrency control for syncs
export const notionSyncLock = pgTable("notion_sync_lock", {
  lockName: text("lock_name").primaryKey(), // Always 'sync' for singleton lock
  syncId: integer("sync_id").references(() => notionSyncStatus.id, { onDelete: "cascade" }),
  lockedAt: timestamp("locked_at").notNull().defaultNow(),
  lockedBy: text("locked_by"), // Optional identifier for debugging
});

// Database Relations
export const notionPagesRelations = relations(notionPages, ({ many, one }) => ({
  blocks: many(notionBlocks),
  parent: one(notionPages, {
    fields: [notionPages.parentId],
    references: [notionPages.id],
  }),
  children: many(notionPages, {
    relationName: "parent_child",
  }),
}));

export const notionBlocksRelations = relations(notionBlocks, ({ one, many }) => ({
  page: one(notionPages, {
    fields: [notionBlocks.pageId],
    references: [notionPages.id],
  }),
  parent: one(notionBlocks, {
    fields: [notionBlocks.parentId],
    references: [notionBlocks.id],
  }),
  children: many(notionBlocks, {
    relationName: "block_parent_child",
  }),
}));

// Export schema types
export type NotionPage = typeof notionPages.$inferSelect;
export type NotionBlock = typeof notionBlocks.$inferSelect;
export type NotionSyncStatus = typeof notionSyncStatus.$inferSelect;
export type NotionSyncLock = typeof notionSyncLock.$inferSelect;

export type NewNotionPage = typeof notionPages.$inferInsert;
export type NewNotionBlock = typeof notionBlocks.$inferInsert;
export type NewNotionSyncStatus = typeof notionSyncStatus.$inferInsert;
export type NewNotionSyncLock = typeof notionSyncLock.$inferInsert;