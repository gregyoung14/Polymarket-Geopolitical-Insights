import React, { useState, useEffect } from "react";
import ReactDOM from "react-dom/client";
import App from "./App";

const HOST_ID = "polymarket-insights-extension-root";

// Main wrapper that handles the floating button and panel visibility
const PolymarketInsightsRoot: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [hasAutoOpened, setHasAutoOpened] = useState(false);

  // Auto-open on first load if we detect outcomes
  useEffect(() => {
    if (hasAutoOpened) return;

    const checkOutcomes = () => {
      const hasOutcomeElements =
        document.querySelector('[data-testid*="outcome"]') ||
        document.querySelector('[class*="OutcomeRow"]');

      const hasBuyButton = Array.from(document.querySelectorAll("button")).some(
        (btn) => btn.textContent?.toLowerCase().includes("buy")
      );

      if (hasOutcomeElements || hasBuyButton) {
        setIsOpen(true);
        setHasAutoOpened(true);
      }
    };

    const timeout = setTimeout(checkOutcomes, 1000);
    return () => clearTimeout(timeout);
  }, [hasAutoOpened]);

  return (
    <>
      {/* Floating Action Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        style={{
          position: "fixed",
          bottom: "16px",
          right: "16px",
          zIndex: 2147483647,
          padding: "12px 16px",
          borderRadius: "12px",
          background: "linear-gradient(135deg, #1a2250, #0f1834)",
          color: "#fff",
          fontWeight: 700,
          fontSize: "14px",
          border: "1px solid #1e2745",
          boxShadow: "0 10px 30px rgba(0,0,0,0.35)",
          cursor: "pointer",
          display: "flex",
          alignItems: "center",
          gap: "8px",
          fontFamily: "Inter, system-ui, -apple-system, sans-serif",
        }}
      >
        <span
          style={{
            width: "8px",
            height: "8px",
            borderRadius: "50%",
            background: "#4ade80",
            boxShadow: "0 0 8px rgba(74, 222, 128, 0.5)",
          }}
        />
        Grok
      </button>

      {/* Main Panel */}
      <App isOpen={isOpen} onClose={() => setIsOpen(false)} />
    </>
  );
};

// Mount function - following extension.js pattern
function mount() {
  // Prevent double-mounting
  if (document.getElementById(HOST_ID)) return;

  // Create root element
  const rootDiv = document.createElement("div");
  rootDiv.id = HOST_ID;
  document.body.appendChild(rootDiv);

  // Create React root and render
  const root = ReactDOM.createRoot(rootDiv);
  root.render(
    <React.StrictMode>
      <PolymarketInsightsRoot />
    </React.StrictMode>
  );

  console.log("[Polymarket Insights] Extension mounted");
}

// Initialize with delay to let page load
setTimeout(mount, 1000);
