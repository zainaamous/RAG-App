import { createWorkflow, createStep } from "../inngest";
import { z } from "zod";
import { youmnaAgent } from "../agents/youmnaAgent";
import { getClient } from "../../triggers/slackTriggers";
import { format } from "node:util";

// Step 1: Use the YOUMNA GPT agent to generate a response
const step1 = createStep({
  id: "use-agent",
  description: "Use YOUMNA GPT agent to generate an intelligent response to the user's message",
  inputSchema: z.object({
    message: z.string().describe("The user's message content"),
    threadId: z.string().describe("Thread ID for conversation context"),
    channel: z.string().describe("Slack channel ID"),
    timestamp: z.string().describe("Message timestamp for threading"),
  }),
  outputSchema: z.object({
    response: z.string().describe("Generated response from YOUMNA GPT"),
    channel: z.string().describe("Slack channel ID"),
    threadTs: z.string().describe("Thread timestamp for reply"),
  }),
  execute: async ({ inputData, mastra }) => {
    const logger = mastra?.getLogger();
    logger?.info("🤖 [YOUMNAWorkflow Step1] Starting agent execution:", { 
      messageLength: inputData.message.length,
      channel: inputData.channel,
      threadId: inputData.threadId
    });
    
    // ONLY call the agent's .generate() method - NO other tools or logic
    const { text } = await youmnaAgent.generate([
      { role: "user", content: inputData.message }
    ], {
      resourceId: "youmna-bot",
      threadId: inputData.threadId,
      maxSteps: 5, // Allow tool usage for Notion integration
    });
    
    logger?.info("✅ [YOUMNAWorkflow Step1] Agent response generated:", { 
      responseLength: text.length,
      channel: inputData.channel
    });
    
    return {
      response: text,
      channel: inputData.channel,
      threadTs: inputData.timestamp,
    };
  }
});

// Step 2: Send the agent's response to Slack
const step2 = createStep({
  id: "send-reply",
  description: "Send the agent's response to the Slack channel",
  inputSchema: z.object({
    response: z.string().describe("The agent's response to send"),
    channel: z.string().describe("Slack channel ID"),
    threadTs: z.string().describe("Thread timestamp for reply"),
  }),
  outputSchema: z.object({
    sent: z.boolean().describe("Whether the message was sent successfully"),
    timestamp: z.string().optional().describe("Timestamp of the sent message"),
  }),
  execute: async ({ inputData, mastra }) => {
    const logger = mastra?.getLogger();
    logger?.info("💬 [YOUMNAWorkflow Step2] Sending reply to Slack:", { 
      channel: inputData.channel,
      responseLength: inputData.response.length,
      threadTs: inputData.threadTs
    });
    
    try {
      // ONLY send the reply to Slack - NO other logic
      const { slack } = await getClient();
      
      const response = await slack.chat.postMessage({
        channel: inputData.channel,
        text: inputData.response,
        thread_ts: inputData.threadTs,
        unfurl_links: false,
        unfurl_media: false,
      });
      
      if (!response.ok) {
        throw new Error(`Slack API error: ${response.error}`);
      }
      
      logger?.info("✅ [YOUMNAWorkflow Step2] Reply sent successfully:", { 
        channel: inputData.channel,
        timestamp: response.ts
      });
      
      return {
        sent: true,
        timestamp: response.ts,
      };
    } catch (error) {
      const errorMessage = format(error);
      logger?.error("❌ [YOUMNAWorkflow Step2] Error sending reply:", { 
        error: errorMessage,
        channel: inputData.channel
      });
      
      return {
        sent: false,
      };
    }
  }
});

export const youmnaWorkflow = createWorkflow({
  id: "youmna-workflow",
  description: "YOUMNA GPT Executive Assistant workflow for processing Slack messages",
  inputSchema: z.object({
    message: z.string().describe("The user's message from Slack"),
    threadId: z.string().describe("Thread ID for conversation context"),
    channel: z.string().describe("Slack channel ID"),
    timestamp: z.string().describe("Message timestamp"),
  }),
  outputSchema: z.object({
    sent: z.boolean().describe("Whether the response was sent successfully"),
    timestamp: z.string().optional().describe("Timestamp of the sent message"),
  })
})
  .then(step1)
  .then(step2)
  .commit();