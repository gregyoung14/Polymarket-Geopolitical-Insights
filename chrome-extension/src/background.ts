/**
 * Background service worker for Polymarket Insights extension
 *
 * Currently a placeholder for future functionality:
 * - Badge updates
 * - Context menu integration
 * - Cross-tab state sync
 */

chrome.runtime.onInstalled.addListener(() => {
  console.log("Polymarket Insights extension installed");
});

// Listen for messages from content script
chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.type === "ping") {
    sendResponse({ status: "pong" });
  }
  return true;
});

export {};
