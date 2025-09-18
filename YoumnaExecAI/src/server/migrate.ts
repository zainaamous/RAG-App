import { migrate } from 'drizzle-orm/postgres-js/migrator';
import { sql, db } from './storage';

async function runMigrations() {
  const logger = console;
  
  try {
    logger.log('🔄 [Migration] Starting database migration...');
    
    // Create the notion_pages table
    await sql`
      CREATE TABLE IF NOT EXISTS notion_pages (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        url TEXT,
        parent_id TEXT,
        parent_type TEXT,
        is_archived BOOLEAN DEFAULT false,
        created_time TIMESTAMP NOT NULL,
        last_edited_time TIMESTAMP NOT NULL,
        properties JSONB,
        icon JSONB,
        cover JSONB,
        synced_at TIMESTAMP DEFAULT NOW(),
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
      );
    `;

    // Create indexes for notion_pages
    await sql`CREATE INDEX IF NOT EXISTS notion_pages_title_idx ON notion_pages(title);`;
    await sql`CREATE INDEX IF NOT EXISTS notion_pages_parent_idx ON notion_pages(parent_id);`;
    await sql`CREATE INDEX IF NOT EXISTS notion_pages_synced_at_idx ON notion_pages(synced_at);`;
    await sql`CREATE INDEX IF NOT EXISTS notion_pages_last_edited_idx ON notion_pages(last_edited_time);`;

    // Create the notion_blocks table
    await sql`
      CREATE TABLE IF NOT EXISTS notion_blocks (
        id TEXT PRIMARY KEY,
        page_id TEXT NOT NULL REFERENCES notion_pages(id) ON DELETE CASCADE,
        parent_id TEXT,
        type TEXT NOT NULL,
        has_children BOOLEAN DEFAULT false,
        is_archived BOOLEAN DEFAULT false,
        content JSONB NOT NULL,
        plain_text TEXT,
        rich_text JSONB,
        created_time TIMESTAMP NOT NULL,
        last_edited_time TIMESTAMP NOT NULL,
        synced_at TIMESTAMP DEFAULT NOW(),
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
      );
    `;

    // Create indexes for notion_blocks
    await sql`CREATE INDEX IF NOT EXISTS notion_blocks_page_idx ON notion_blocks(page_id);`;
    await sql`CREATE INDEX IF NOT EXISTS notion_blocks_type_idx ON notion_blocks(type);`;
    await sql`CREATE INDEX IF NOT EXISTS notion_blocks_parent_idx ON notion_blocks(parent_id);`;
    await sql`CREATE INDEX IF NOT EXISTS notion_blocks_synced_at_idx ON notion_blocks(synced_at);`;
    await sql`CREATE INDEX IF NOT EXISTS notion_blocks_plain_text_idx ON notion_blocks(plain_text);`;

    // Create the notion_sync_status table
    await sql`
      CREATE TABLE IF NOT EXISTS notion_sync_status (
        id SERIAL PRIMARY KEY,
        sync_type TEXT NOT NULL,
        status TEXT NOT NULL,
        started_at TIMESTAMP NOT NULL DEFAULT NOW(),
        completed_at TIMESTAMP,
        total_pages INTEGER DEFAULT 0,
        processed_pages INTEGER DEFAULT 0,
        total_blocks INTEGER DEFAULT 0,
        processed_blocks INTEGER DEFAULT 0,
        error_message TEXT,
        metadata JSONB,
        last_cursor TEXT,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
      );
    `;

    logger.log('✅ [Migration] Database migration completed successfully!');
    logger.log('📊 [Migration] Created tables:');
    logger.log('   - notion_pages (with indexes)');
    logger.log('   - notion_blocks (with indexes)');  
    logger.log('   - notion_sync_status');

    // Verify tables were created
    const tables = await sql`
      SELECT table_name FROM information_schema.tables 
      WHERE table_schema = 'public' AND table_name LIKE 'notion_%'
      ORDER BY table_name;
    `;
    
    logger.log('🔍 [Migration] Verified tables:', tables.map(t => t.table_name));
    
  } catch (error) {
    logger.error('❌ [Migration] Failed to run migration:', error);
    throw error;
  } finally {
    await sql.end();
  }
}

// Run migration
runMigrations();