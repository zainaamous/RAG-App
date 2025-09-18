import { createTool } from "@mastra/core/tools";
import type { IMastraLogger } from "@mastra/core/logger";
import { z } from "zod";
import { getClient } from "../../triggers/slackTriggers";
import { format } from "node:util";

async function sendSlackMessage({
  channel,
  message,
  threadTs,
  logger,
}: {
  channel: string;
  message: string;
  threadTs?: string;
  logger?: IMastraLogger;
}) {
  try {
    logger?.info("💬 [SlackResponseTool] Sending message to Slack:", { 
      channel, 
      messageLength: message.length,
      isThread: !!threadTs 
    });
    
    const { slack } = await getClient();
    
    // Send the message
    const response = await slack.chat.postMessage({
      channel: channel,
      text: message,
      thread_ts: threadTs,
      unfurl_links: false,
      unfurl_media: false,
    });
    
    if (!response.ok) {
      throw new Error(`Slack API error: ${response.error}`);
    }
    
    logger?.info("✅ [SlackResponseTool] Message sent successfully:", { 
      channel,
      timestamp: response.ts,
      messageId: response.message?.ts
    });
    
    return {
      success: true,
      timestamp: response.ts,
      channel: response.channel,
      message_id: response.message?.ts,
    };
  } catch (error) {
    const errorMessage = format(error);
    logger?.error("❌ [SlackResponseTool] Error sending message:", { 
      error: errorMessage,
      channel,
      messageLength: message.length 
    });
    throw new Error(`Failed to send Slack message: ${errorMessage}`);
  }
}

export const slackResponseTool = createTool({
  id: "slack-response-tool",
  description: "Send a response message to a Slack channel or thread. Use this to reply to users in Slack conversations.",
  inputSchema: z.object({
    channel: z.string().describe("Slack channel ID where the message should be sent"),
    message: z.string().describe("The message content to send to Slack"),
    threadTs: z.string().optional().describe("Thread timestamp if replying to a specific message thread"),
  }),
  outputSchema: z.object({
    success: z.boolean().describe("Whether the message was sent successfully"),
    timestamp: z.string().optional().describe("Timestamp of the sent message"),
    channel: z.string().optional().describe("Channel where the message was sent"),
    message_id: z.string().optional().describe("Unique identifier for the sent message"),
  }),
  execute: async ({ context: { channel, message, threadTs }, mastra }) => {
    const logger = mastra?.getLogger();
    logger?.info("🔧 [SlackResponseTool] Starting execution with params:", { 
      channel, 
      messageLength: message.length,
      hasThread: !!threadTs 
    });
    
    const result = await sendSlackMessage({ channel, message, threadTs, logger });
    
    logger?.info("✅ [SlackResponseTool] Completed successfully");
    return result;
  },
});