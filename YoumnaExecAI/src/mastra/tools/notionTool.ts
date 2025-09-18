import { createTool } from "@mastra/core/tools";
import type { IMastraLogger } from "@mastra/core/logger";
import { z } from "zod";
import { getUncachableNotionClient } from "../../integrations/notion";

// Utility function for retry logic with exponential backoff
async function retryWithBackoff<T>(
  operation: () => Promise<T>,
  maxRetries: number = 3,
  baseDelay: number = 1000,
  logger?: IMastraLogger
): Promise<T> {
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      return await operation();
    } catch (error: any) {
      const isRateLimit = error?.status === 429 || error?.code === "rate_limited";
      const isLastAttempt = attempt === maxRetries;
      
      if (!isRateLimit || isLastAttempt) {
        throw error;
      }
      
      const delay = baseDelay * Math.pow(2, attempt - 1);
      logger?.warn(`🔄 [NotionTool] Rate limited, retrying in ${delay}ms (attempt ${attempt}/${maxRetries})`);
      await new Promise(resolve => setTimeout(resolve, delay));
    }
  }
  throw new Error("Max retries exceeded");
}

// Utility function to format error messages properly
function formatError(error: any): string {
  if (error?.message) {
    return error.message;
  }
  if (typeof error === 'string') {
    return error;
  }
  if (error?.code && error?.status) {
    return `Notion API error (${error.code}): ${error.status}`;
  }
  return JSON.stringify(error);
}

// Enhanced title extraction function
function extractTitle(page: any): string {
  // Try different possible title property names
  const titleProperties = ['title', 'Title', 'Name', 'name'];
  
  for (const prop of titleProperties) {
    const property = page.properties?.[prop];
    if (property) {
      if (property.type === 'title' && property.title?.[0]?.plain_text) {
        return property.title[0].plain_text;
      }
      if (property.type === 'rich_text' && property.rich_text?.[0]?.plain_text) {
        return property.rich_text[0].plain_text;
      }
    }
  }
  
  // Fallback: check if page has a title in the object itself
  if (page.title?.[0]?.plain_text) {
    return page.title[0].plain_text;
  }
  
  return "Untitled";
}

async function searchNotionDatabase({
  query,
  maxResults = 50,
  logger,
}: {
  query: string;
  maxResults?: number;
  logger?: IMastraLogger;
}) {
  try {
    logger?.info("🔍 [NotionTool] Searching Notion database for:", { query, maxResults });
    
    const notion = await getUncachableNotionClient();
    let allResults: any[] = [];
    let hasMore = true;
    let nextCursor: string | undefined = undefined;
    
    // Implement full pagination
    while (hasMore && allResults.length < maxResults) {
      const pageSize = Math.min(100, maxResults - allResults.length);
      
      const searchResponse = await retryWithBackoff(async () => {
        return notion.search({
          query: query,
          filter: {
            property: "object",
            value: "page",
          },
          sort: {
            direction: "descending",
            timestamp: "last_edited_time",
          },
          page_size: pageSize,
          start_cursor: nextCursor,
        });
      }, 3, 1000, logger);
      
      allResults = allResults.concat(searchResponse.results);
      hasMore = searchResponse.has_more;
      nextCursor = searchResponse.next_cursor || undefined;
      
      logger?.info("📝 [NotionTool] Paginated search progress:", { 
        currentResults: allResults.length, 
        hasMore, 
        maxResults 
      });
    }
    
    logger?.info("📝 [NotionTool] Search completed, total results:", { resultCount: allResults.length });
    
    const formattedResults = allResults.map((page: any) => {
      const title = extractTitle(page);
      
      return {
        id: page.id,
        title: title,
        url: page.url,
        last_edited: page.last_edited_time,
        created: page.created_time,
        object_type: page.object,
        parent_type: page.parent?.type,
      };
    });
    
    return {
      results: formattedResults,
      query: query,
      total_results: allResults.length,
      has_more: hasMore,
    };
  } catch (error) {
    const errorMessage = formatError(error);
    logger?.error("❌ [NotionTool] Error searching Notion:", { error: errorMessage });
    throw new Error(`Failed to search Notion: ${errorMessage}`);
  }
}

// Recursive function to extract text from blocks with full support for all block types
async function extractBlockContent(
  blockId: string,
  notion: any,
  depth: number = 0,
  logger?: IMastraLogger
): Promise<string[]> {
  const indent = "  ".repeat(depth);
  const content: string[] = [];
  
  let hasMore = true;
  let nextCursor: string | undefined = undefined;
  
  // Paginate through all blocks
  while (hasMore) {
    const blocksResponse = await retryWithBackoff(async () => {
      return notion.blocks.children.list({
        block_id: blockId,
        page_size: 100,
        start_cursor: nextCursor,
      });
    }, 3, 1000, logger);
    
    for (const block of blocksResponse.results) {
      let text = "";
      
      // Extract text based on block type
      switch (block.type) {
        case "paragraph":
          if (block.paragraph?.rich_text) {
            text = block.paragraph.rich_text.map((rt: any) => rt.plain_text).join("");
          }
          break;
          
        case "heading_1":
          if (block.heading_1?.rich_text) {
            text = "# " + block.heading_1.rich_text.map((rt: any) => rt.plain_text).join("");
          }
          break;
          
        case "heading_2":
          if (block.heading_2?.rich_text) {
            text = "## " + block.heading_2.rich_text.map((rt: any) => rt.plain_text).join("");
          }
          break;
          
        case "heading_3":
          if (block.heading_3?.rich_text) {
            text = "### " + block.heading_3.rich_text.map((rt: any) => rt.plain_text).join("");
          }
          break;
          
        case "bulleted_list_item":
          if (block.bulleted_list_item?.rich_text) {
            text = indent + "• " + block.bulleted_list_item.rich_text.map((rt: any) => rt.plain_text).join("");
          }
          break;
          
        case "numbered_list_item":
          if (block.numbered_list_item?.rich_text) {
            text = indent + "1. " + block.numbered_list_item.rich_text.map((rt: any) => rt.plain_text).join("");
          }
          break;
          
        case "to_do":
          if (block.to_do?.rich_text) {
            const checked = block.to_do.checked ? "☑" : "☐";
            text = indent + checked + " " + block.to_do.rich_text.map((rt: any) => rt.plain_text).join("");
          }
          break;
          
        case "toggle":
          if (block.toggle?.rich_text) {
            text = indent + "▶ " + block.toggle.rich_text.map((rt: any) => rt.plain_text).join("");
          }
          break;
          
        case "code":
          if (block.code?.rich_text) {
            const language = block.code.language || "text";
            const codeText = block.code.rich_text.map((rt: any) => rt.plain_text).join("");
            text = indent + "```" + language + "\n" + codeText + "\n```";
          }
          break;
          
        case "quote":
          if (block.quote?.rich_text) {
            text = indent + "> " + block.quote.rich_text.map((rt: any) => rt.plain_text).join("");
          }
          break;
          
        case "callout":
          if (block.callout?.rich_text) {
            const icon = block.callout.icon?.emoji || "💡";
            text = indent + icon + " " + block.callout.rich_text.map((rt: any) => rt.plain_text).join("");
          }
          break;
          
        case "divider":
          text = indent + "---";
          break;
          
        case "table":
          text = indent + "[Table with " + (block.table?.table_width || 0) + " columns]";
          break;
          
        case "table_row":
          if (block.table_row?.cells) {
            const cells = block.table_row.cells.map((cell: any) => 
              cell.map((rt: any) => rt.plain_text).join("")
            );
            text = indent + "| " + cells.join(" | ") + " |";
          }
          break;
          
        case "image":
          const imageUrl = block.image?.external?.url || block.image?.file?.url || "";
          text = indent + "![Image](" + imageUrl + ")";
          break;
          
        case "file":
          const fileName = block.file?.name || "File";
          text = indent + "📎 " + fileName;
          break;
          
        case "bookmark":
          const bookmarkUrl = block.bookmark?.url || "";
          text = indent + "🔖 [Bookmark](" + bookmarkUrl + ")";
          break;
          
        case "link_preview":
          const linkUrl = block.link_preview?.url || "";
          text = indent + "🔗 [Link Preview](" + linkUrl + ")";
          break;
          
        case "embed":
          const embedUrl = block.embed?.url || "";
          text = indent + "📺 [Embed](" + embedUrl + ")";
          break;
          
        default:
          // For unknown block types, try to extract any rich_text content
          if (block[block.type]?.rich_text) {
            text = indent + block[block.type].rich_text.map((rt: any) => rt.plain_text).join("");
          } else {
            text = indent + `[${block.type}]`;
          }
      }
      
      if (text.trim()) {
        content.push(text);
      }
      
      // Recursively process child blocks if they exist
      if (block.has_children) {
        logger?.info("🔍 [NotionTool] Processing child blocks for:", { blockId: block.id, type: block.type });
        const childContent = await extractBlockContent(block.id, notion, depth + 1, logger);
        content.push(...childContent);
      }
    }
    
    hasMore = blocksResponse.has_more;
    nextCursor = blocksResponse.next_cursor || undefined;
  }
  
  return content;
}

async function getNotionPageContent({
  pageId,
  logger,
}: {
  pageId: string;
  logger?: IMastraLogger;
}) {
  try {
    logger?.info("📄 [NotionTool] Retrieving page content for:", { pageId });
    
    const notion = await getUncachableNotionClient();
    
    // Get page details with retry logic
    const page = await retryWithBackoff(async () => {
      return notion.pages.retrieve({ page_id: pageId });
    }, 3, 1000, logger);
    
    // Extract page title
    const pageTitle = extractTitle(page);
    logger?.info("📝 [NotionTool] Page title extracted:", { title: pageTitle });
    
    // Get all page content recursively
    const contentArray = await extractBlockContent(pageId, notion, 0, logger);
    const content = contentArray.join("\n");
    
    logger?.info("✅ [NotionTool] Successfully retrieved page content:", { 
      pageId, 
      contentLength: content.length,
      blocksProcessed: contentArray.length
    });
    
    return {
      page_id: pageId,
      title: pageTitle,
      content: content,
      blocks_count: contentArray.length,
      page_info: {
        id: page.id,
        created_time: (page as any).created_time,
        last_edited_time: (page as any).last_edited_time,
        url: (page as any).url,
        archived: (page as any).archived,
        parent: (page as any).parent,
      },
    };
  } catch (error) {
    const errorMessage = formatError(error);
    logger?.error("❌ [NotionTool] Error retrieving page content:", { error: errorMessage });
    throw new Error(`Failed to retrieve page content: ${errorMessage}`);
  }
}

export const notionSearchTool = createTool({
  id: "notion-search-tool",
  description: "Search Notion knowledge base for pages and databases that contain relevant information. Supports full pagination to retrieve comprehensive results from large workspaces.",
  inputSchema: z.object({
    query: z.string().describe("Search query to find relevant information in Notion. Can include keywords, phrases, or specific terms."),
    maxResults: z.number().optional().default(50).describe("Maximum number of results to return (default: 50, max: 100)"),
  }),
  outputSchema: z.object({
    results: z.array(z.object({
      id: z.string().describe("Unique page ID"),
      title: z.string().describe("Page title"),
      url: z.string().describe("Direct URL to the page"),
      last_edited: z.string().describe("Last edit timestamp"),
      created: z.string().describe("Creation timestamp"),
      object_type: z.string().describe("Type of object (page, database)"),
      parent_type: z.string().optional().describe("Type of parent container"),
    })),
    query: z.string().describe("Original search query"),
    total_results: z.number().describe("Total number of results found"),
    has_more: z.boolean().describe("Whether there are more results available"),
  }),
  execute: async ({ context: { query, maxResults = 50 }, mastra }) => {
    const logger = mastra?.getLogger();
    logger?.info("🔧 [NotionSearchTool] Starting execution with params:", { query, maxResults });
    
    const result = await searchNotionDatabase({ query, maxResults, logger });
    
    logger?.info("✅ [NotionSearchTool] Completed successfully, returning:", { 
      resultCount: result.total_results,
      hasMore: result.has_more 
    });
    return result;
  },
});

export const notionPageContentTool = createTool({
  id: "notion-page-content-tool",
  description: "Retrieve comprehensive content from a specific Notion page including all block types, nested structures, and formatted text. Supports recursive traversal of child blocks.",
  inputSchema: z.object({
    pageId: z.string().describe("Notion page ID to retrieve content from (found from search results)"),
  }),
  outputSchema: z.object({
    page_id: z.string().describe("Page ID"),
    title: z.string().describe("Page title"),
    content: z.string().describe("Complete page content in markdown-like format"),
    blocks_count: z.number().describe("Total number of blocks processed"),
    page_info: z.object({
      id: z.string(),
      created_time: z.string(),
      last_edited_time: z.string(),
      url: z.string(),
      archived: z.boolean(),
      parent: z.any(),
    }).describe("Page metadata"),
  }),
  execute: async ({ context: { pageId }, mastra }) => {
    const logger = mastra?.getLogger();
    logger?.info("🔧 [NotionPageContentTool] Starting execution with pageId:", { pageId });
    
    const result = await getNotionPageContent({ pageId, logger });
    
    logger?.info("✅ [NotionPageContentTool] Completed successfully:", {
      title: result.title,
      contentLength: result.content.length,
      blocksCount: result.blocks_count
    });
    return result;
  },
});