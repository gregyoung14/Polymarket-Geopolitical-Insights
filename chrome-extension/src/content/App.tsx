import React, { useEffect, useRef } from "react";
import { useMarketData } from "./hooks/useMarketData";
import {
  useAnalysis,
  type LogEntry,
  type AnalysisResult as AnalysisResultType,
  type GrokOutcomeEstimate,
} from "./hooks/useAnalysis";

// Inline styles for content script (Tailwind doesn't work well in injected content)
const styles = {
  panel: {
    position: "fixed" as const,
    top: 0,
    right: 0,
    height: "100vh",
    width: "360px",
    background: "rgba(11, 16, 33, 0.97)",
    backdropFilter: "blur(8px)",
    borderLeft: "1px solid #1e2745",
    boxShadow: "0 8px 32px rgba(0,0,0,0.4)",
    display: "flex",
    flexDirection: "column" as const,
    zIndex: 2147483647,
    fontFamily: "Inter, system-ui, -apple-system, sans-serif",
    color: "#f6f7fb",
    transition: "transform 250ms ease",
  },
  header: {
    padding: "16px",
    borderBottom: "1px solid #1e2745",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
  },
  title: {
    fontSize: "18px",
    fontWeight: 700,
    display: "flex",
    alignItems: "center",
    gap: "8px",
  },
  dot: {
    width: "8px",
    height: "8px",
    borderRadius: "50%",
    background: "#4ade80",
    boxShadow: "0 0 8px rgba(74, 222, 128, 0.5)",
  },
  body: {
    flex: 1,
    overflowY: "auto" as const,
    padding: "16px",
  },
  marketTitle: {
    fontSize: "14px",
    fontWeight: 600,
    marginBottom: "8px",
    lineHeight: 1.4,
  },
  volumeBadge: {
    display: "inline-block",
    fontSize: "12px",
    color: "#9fb2dd",
    background: "#0f1834",
    padding: "4px 8px",
    borderRadius: "6px",
    marginBottom: "12px",
  },
  card: {
    background: "#0f1834",
    border: "1px solid #1e2745",
    borderRadius: "10px",
    padding: "12px",
    marginBottom: "8px",
  },
  cardRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: "8px",
  },
  cardName: {
    fontSize: "14px",
    fontWeight: 600,
    flex: 1,
  },
  cardProb: {
    fontSize: "13px",
    color: "#9fb2dd",
  },
  chipRow: {
    display: "flex",
    gap: "8px",
    flexWrap: "wrap" as const,
  },
  chip: {
    padding: "4px 8px",
    borderRadius: "6px",
    fontSize: "12px",
    border: "1px solid #1e2745",
    background: "#0b1021",
  },
  chipGreen: { color: "#4ade80" },
  chipRed: { color: "#ef4444" },
  volume: {
    fontSize: "11px",
    color: "#7d8fbe",
    marginTop: "6px",
  },
  button: {
    width: "100%",
    padding: "12px 16px",
    borderRadius: "10px",
    border: "none",
    background: "linear-gradient(135deg, #3b82f6, #8b5cf6)",
    color: "#fff",
    fontSize: "14px",
    fontWeight: 700,
    cursor: "pointer",
    marginTop: "12px",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: "8px",
  },
  buttonDisabled: {
    opacity: 0.6,
    cursor: "not-allowed",
  },
  log: {
    marginTop: "12px",
    background: "#0b122a",
    border: "1px solid #1e2745",
    borderRadius: "8px",
    padding: "8px",
    maxHeight: "150px",
    overflowY: "auto" as const,
    fontFamily: "monospace",
    fontSize: "11px",
  },
  logEntry: {
    padding: "2px 0",
    borderBottom: "1px solid rgba(30, 39, 69, 0.3)",
  },
  resultCard: {
    marginTop: "12px",
    padding: "16px",
    borderRadius: "10px",
    background: "linear-gradient(135deg, #0f1834, #1a2250)",
    border: "1px solid #3b82f6",
  },
  resultHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: "12px",
  },
  sentiment: {
    fontSize: "16px",
    fontWeight: 700,
    textTransform: "uppercase" as const,
  },
  probability: {
    fontSize: "28px",
    fontWeight: 800,
  },
  recommendation: {
    marginTop: "12px",
    padding: "12px",
    background: "#0b122a",
    borderRadius: "8px",
    fontSize: "13px",
    lineHeight: 1.5,
  },
  closeBtn: {
    background: "transparent",
    border: "none",
    color: "#9fb2dd",
    cursor: "pointer",
    fontSize: "20px",
    padding: "4px 8px",
  },
  refreshBtn: {
    background: "transparent",
    border: "none",
    color: "#9fb2dd",
    cursor: "pointer",
    fontSize: "14px",
    padding: "4px 8px",
  },
  footer: {
    padding: "12px 16px",
    borderTop: "1px solid #1e2745",
    fontSize: "11px",
    color: "#7d8fbe",
    textAlign: "center" as const,
  },
  loading: {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    height: "100%",
    color: "#9fb2dd",
  },
  spinner: {
    width: "24px",
    height: "24px",
    border: "2px solid #1e2745",
    borderTopColor: "#3b82f6",
    borderRadius: "50%",
    animation: "spin 0.8s linear infinite",
    marginRight: "8px",
  },
};

// Inject keyframes for spinner
const injectKeyframes = () => {
  if (document.getElementById("grokedge-keyframes")) return;
  const style = document.createElement("style");
  style.id = "grokedge-keyframes";
  style.textContent = `
    @keyframes spin { to { transform: rotate(360deg); } }
  `;
  document.head.appendChild(style);
};

interface AppProps {
  isOpen: boolean;
  onClose: () => void;
}

export const App: React.FC<AppProps> = ({ isOpen, onClose }) => {
  useEffect(() => {
    injectKeyframes();
  }, []);

  const { data: marketData, refresh } = useMarketData();
  const {
    stage,
    logs,
    result,
    thinkingTokens,
    citations,
    parallelProgress,
    analyze,
    cancel,
    resetAnalysis,
  } = useAnalysis();

  // Track the URL to reset analysis when navigating to a new market
  const prevUrlRef = useRef<string | null>(null);

  useEffect(() => {
    if (
      marketData?.url &&
      prevUrlRef.current !== null &&
      prevUrlRef.current !== marketData.url
    ) {
      // URL changed - reset all analysis state
      console.log("[GrokEdge] URL changed, resetting analysis");
      resetAnalysis();
    }
    prevUrlRef.current = marketData?.url || null;
  }, [marketData?.url, resetAnalysis]);

  const isAnalyzing =
    stage !== "idle" && stage !== "complete" && stage !== "error";

  const handleAnalyze = () => {
    if (!marketData) return;
    analyze(
      marketData.title,
      marketData.outcomes,
      marketData.totalVolume,
      marketData.url,
      false
    );
  };

  const formatPrice = (num: number | null) => {
    if (num == null || Number.isNaN(num)) return "—";

    // Always display in cents (handles fractional cents like 1.2¢)
    const cents = Math.round(Number((num * 10000).toFixed(6))) / 100; // stable to 1/100th cent
    return `${cents.toLocaleString("en-US", {
      minimumFractionDigits: cents % 1 === 0 ? 0 : 1,
      maximumFractionDigits: 2,
    })}¢`;
  };

  const panelStyle = {
    ...styles.panel,
    transform: isOpen ? "translateX(0)" : "translateX(100%)",
  };

  return (
    <div style={panelStyle}>
      {/* Header */}
      <div style={styles.header}>
        <div style={styles.title}>
          <span style={styles.dot} />
          GrokEdge
        </div>
        <div>
          <button style={styles.refreshBtn} onClick={refresh} title="Refresh">
            🔄
          </button>
          <button style={styles.closeBtn} onClick={onClose} title="Close">
            ×
          </button>
        </div>
      </div>

      {/* Body */}
      <div style={styles.body}>
        {marketData ? (
          <>
            <div style={styles.marketTitle}>{marketData.title}</div>
            {marketData.totalVolume && (
              <div style={styles.volumeBadge}>
                Total Volume: ${marketData.totalVolume.toLocaleString()}
              </div>
            )}

            {/* Outcomes with Grok Estimates */}
            <OutcomesSection
              outcomes={marketData.outcomes}
              grokEstimates={result?.outcomeEstimates || null}
              formatPrice={formatPrice}
            />

            {/* Analyze Button */}
            <button
              style={{
                ...styles.button,
                ...(marketData.outcomes.length === 0 || isAnalyzing
                  ? styles.buttonDisabled
                  : {}),
              }}
              onClick={isAnalyzing ? cancel : handleAnalyze}
              disabled={marketData.outcomes.length === 0}
            >
              {isAnalyzing ? "⏹ Cancel" : "🔮 Analyze with Grok"}
            </button>

            {/* Parallel Progress Indicator */}
            {isAnalyzing &&
              (parallelProgress.foundational.active ||
                parallelProgress.historical.active ||
                parallelProgress.x_sentiment.active) && (
                <div
                  style={{
                    marginTop: "12px",
                    display: "flex",
                    gap: "8px",
                    flexWrap: "wrap",
                  }}
                >
                  <ProgressPill
                    label="Foundational"
                    active={
                      parallelProgress.foundational.active &&
                      !parallelProgress.foundational.complete
                    }
                    complete={parallelProgress.foundational.complete}
                    elapsed={parallelProgress.foundational.elapsed}
                  />
                  <ProgressPill
                    label="Historical"
                    active={
                      parallelProgress.historical.active &&
                      !parallelProgress.historical.complete
                    }
                    complete={parallelProgress.historical.complete}
                    elapsed={parallelProgress.historical.elapsed}
                  />
                  <ProgressPill
                    label="Prominent Figures Sentiment"
                    active={
                      parallelProgress.x_sentiment.active &&
                      !parallelProgress.x_sentiment.complete
                    }
                    complete={parallelProgress.x_sentiment.complete}
                    elapsed={parallelProgress.x_sentiment.elapsed}
                  />
                </div>
              )}

            {/* Streaming Log */}
            {(isAnalyzing || logs.length > 0) && (
              <div style={styles.log}>
                {thinkingTokens > 0 && (
                  <div style={{ color: "#8b5cf6", marginBottom: "4px" }}>
                    💭 Thinking: {thinkingTokens} tokens
                  </div>
                )}
                {logs.map((log) => (
                  <LogLine key={log.id} log={log} />
                ))}
              </div>
            )}

            {/* Result */}
            {result && <ResultCard result={result} citations={citations} />}
          </>
        ) : (
          <div style={styles.loading}>
            <div style={styles.spinner} />
            Loading market data...
          </div>
        )}
      </div>

      {/* Footer */}
      <div style={styles.footer}>Built for Grok/X sentiment experiments</div>
    </div>
  );
};

const LogLine: React.FC<{ log: LogEntry }> = ({ log }) => {
  const colorMap: Record<string, string> = {
    status: "#4ade80",
    "tool-call": "#f59e0b",
    thinking: "#8b5cf6",
    citation: "#3b82f6",
    error: "#ef4444",
    info: "#9fb2dd",
  };
  return (
    <div style={{ ...styles.logEntry, color: colorMap[log.type] || "#f6f7fb" }}>
      {log.message}
    </div>
  );
};

const ProgressPill: React.FC<{
  label: string;
  active: boolean;
  complete: boolean;
  elapsed?: number;
  stageEmoji?: string;
}> = ({ label, active, complete, elapsed, stageEmoji }) => {
  const bgColor = complete ? "#065f46" : active ? "#1e3a5f" : "#1e2745";
  const borderColor = complete ? "#10b981" : active ? "#3b82f6" : "#1e2745";

  // Default emojis based on label
  const getDefaultEmoji = () => {
    if (label === "Foundational") return "🔬";
    if (label === "Historical") return "📜";
    if (label === "Prominent Figures Sentiment") return "📱";
    return "🔍";
  };
  const emoji =
    stageEmoji || (complete ? "✅" : active ? getDefaultEmoji() : "⏳");

  return (
    <div
      style={{
        flex: 1,
        padding: "8px 12px",
        borderRadius: "8px",
        background: bgColor,
        border: `1px solid ${borderColor}`,
        fontSize: "11px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: "6px",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
        {complete ? (
          <span style={{ color: "#10b981" }}>✅</span>
        ) : active ? (
          <>
            <span
              style={{
                ...styles.spinner,
                width: "10px",
                height: "10px",
                borderWidth: "1.5px",
              }}
            />
            <span style={{ fontSize: "10px" }}>{emoji}</span>
          </>
        ) : (
          <span style={{ fontSize: "10px", opacity: 0.5 }}>⏳</span>
        )}
        <span style={{ color: complete ? "#10b981" : "#9fb2dd" }}>{label}</span>
      </div>
      {elapsed && (
        <span style={{ color: "#6b7280", fontSize: "10px" }}>{elapsed}s</span>
      )}
    </div>
  );
};

// Component to display outcomes with Grok estimates, sorted by arbitrage opportunity
const OutcomesSection: React.FC<{
  outcomes: {
    name: string;
    probability: number | null;
    yesPrice: number | null;
    noPrice: number | null;
    volume: number | null;
  }[];
  grokEstimates: GrokOutcomeEstimate[] | null;
  formatPrice: (num: number | null) => string;
}> = ({ outcomes, grokEstimates, formatPrice }) => {
  const [isExpanded, setIsExpanded] = React.useState(false);
  const INITIAL_DISPLAY_COUNT = 5;

  // Build a map of Grok estimates by outcome name
  const estimateMap = new Map<string, GrokOutcomeEstimate>();
  if (grokEstimates) {
    grokEstimates.forEach((e) => {
      estimateMap.set(e.outcome_name.toLowerCase().trim(), e);
    });
  }

  // Enhance outcomes with Grok data and sort by absolute delta (biggest arbitrage first)
  const enhancedOutcomes = outcomes.map((o) => {
    const estimate = estimateMap.get(o.name.toLowerCase().trim());
    return {
      ...o,
      grokEstimate: estimate || null,
      sortDelta: estimate ? Math.abs(estimate.delta) : 0,
    };
  });

  // Sort by delta (biggest arbitrage opportunity first) when we have estimates
  if (grokEstimates && grokEstimates.length > 0) {
    enhancedOutcomes.sort((a, b) => b.sortDelta - a.sortDelta);
  }

  // Show only first N outcomes unless expanded
  const displayedOutcomes = isExpanded
    ? enhancedOutcomes
    : enhancedOutcomes.slice(0, INITIAL_DISPLAY_COUNT);
  const hasMore = enhancedOutcomes.length > INITIAL_DISPLAY_COUNT;
  const hiddenCount = enhancedOutcomes.length - INITIAL_DISPLAY_COUNT;

  const getDeltaColor = (delta: number) => {
    if (delta > 5) return "#4ade80"; // Green - undervalued, BUY
    if (delta < -5) return "#ef4444"; // Red - overvalued, SELL
    return "#f59e0b"; // Yellow - fair value
  };

  const getRecommendationStyle = (rec: string) => {
    switch (rec) {
      case "BUY":
        return { color: "#4ade80", fontWeight: 700 };
      case "SELL":
        return { color: "#ef4444", fontWeight: 700 };
      default:
        return { color: "#9fb2dd", fontWeight: 500 };
    }
  };

  return (
    <div style={{ marginBottom: "12px" }}>
      <div
        style={{
          fontSize: "12px",
          color: "#9fb2dd",
          marginBottom: "8px",
          display: "flex",
          justifyContent: "space-between",
        }}
      >
        <span>Outcomes ({outcomes.length})</span>
        {grokEstimates && grokEstimates.length > 0 && (
          <span style={{ color: "#8b5cf6" }}>🔮 Sorted by Alpha</span>
        )}
      </div>
      {displayedOutcomes.length > 0 ? (
        displayedOutcomes.map((o, i) => (
          <div
            key={`${o.name}-${i}`}
            style={{
              ...styles.card,
              borderColor:
                o.grokEstimate && Math.abs(o.grokEstimate.delta) > 10
                  ? getDeltaColor(o.grokEstimate.delta)
                  : "#1e2745",
              borderWidth:
                o.grokEstimate && Math.abs(o.grokEstimate.delta) > 10
                  ? "2px"
                  : "1px",
            }}
          >
            <div style={styles.cardRow}>
              <span style={styles.cardName}>{o.name}</span>
              <div
                style={{ display: "flex", alignItems: "center", gap: "8px" }}
              >
                {o.grokEstimate && (
                  <span
                    style={{
                      ...getRecommendationStyle(o.grokEstimate.recommendation),
                      fontSize: "11px",
                      padding: "2px 6px",
                      borderRadius: "4px",
                      background:
                        o.grokEstimate.recommendation === "BUY"
                          ? "rgba(74, 222, 128, 0.15)"
                          : o.grokEstimate.recommendation === "SELL"
                          ? "rgba(239, 68, 68, 0.15)"
                          : "transparent",
                    }}
                  >
                    {o.grokEstimate.recommendation}
                  </span>
                )}
                <span style={styles.cardProb}>
                  {o.probability != null ? `${o.probability}%` : "–"}
                </span>
              </div>
            </div>

            {/* Grok vs Market comparison */}
            {o.grokEstimate && (
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                  marginBottom: "8px",
                  padding: "6px 8px",
                  background: "rgba(139, 92, 246, 0.1)",
                  borderRadius: "6px",
                }}
              >
                <span style={{ fontSize: "11px", color: "#9fb2dd" }}>
                  🔮 Grok:
                </span>
                <span
                  style={{
                    fontSize: "13px",
                    fontWeight: 700,
                    color: "#8b5cf6",
                  }}
                >
                  {o.grokEstimate.grok_probability.toFixed(1)}%
                </span>
                <span style={{ fontSize: "11px", color: "#7d8fbe" }}>vs</span>
                <span style={{ fontSize: "11px", color: "#9fb2dd" }}>
                  Market: {o.grokEstimate.market_probability.toFixed(1)}%
                </span>
                <span
                  style={{
                    fontSize: "12px",
                    fontWeight: 700,
                    color: getDeltaColor(o.grokEstimate.delta),
                    marginLeft: "auto",
                  }}
                >
                  {o.grokEstimate.delta > 0 ? "+" : ""}
                  {o.grokEstimate.delta.toFixed(1)}%
                </span>
              </div>
            )}

            <div style={styles.chipRow}>
              <span style={{ ...styles.chip, ...styles.chipGreen }}>
                Yes: {formatPrice(o.yesPrice)}
              </span>
              <span style={{ ...styles.chip, ...styles.chipRed }}>
                No: {formatPrice(o.noPrice)}
              </span>
            </div>
            {o.volume != null && (
              <div style={styles.volume}>Vol: ${o.volume.toLocaleString()}</div>
            )}
            {o.grokEstimate?.reasoning && (
              <div
                style={{
                  fontSize: "11px",
                  color: "#7d8fbe",
                  marginTop: "6px",
                  fontStyle: "italic",
                  lineHeight: 1.4,
                }}
              >
                {o.grokEstimate.reasoning.slice(0, 150)}
                {o.grokEstimate.reasoning.length > 150 ? "..." : ""}
              </div>
            )}
          </div>
        ))
      ) : (
        <div
          style={{
            ...styles.card,
            textAlign: "center",
            color: "#9fb2dd",
          }}
        >
          No outcomes detected. Try refreshing.
        </div>
      )}

      {/* Expand/Collapse button for outcomes */}
      {hasMore && (
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          style={{
            width: "100%",
            padding: "8px",
            marginTop: "4px",
            background: "rgba(139, 92, 246, 0.1)",
            border: "1px solid rgba(139, 92, 246, 0.3)",
            borderRadius: "8px",
            color: "#9fb2dd",
            fontSize: "12px",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: "6px",
            transition: "all 0.2s ease",
          }}
        >
          <span
            style={{
              transform: isExpanded ? "rotate(180deg)" : "rotate(0deg)",
              transition: "transform 0.2s ease",
              opacity: 0.7,
            }}
          >
            ▼
          </span>
          {isExpanded
            ? "Show less"
            : `Show ${hiddenCount} more outcome${hiddenCount > 1 ? "s" : ""}`}
        </button>
      )}
    </div>
  );
};

const ResultCard: React.FC<{
  result: AnalysisResultType;
  citations: string[];
}> = ({ result, citations }) => {
  const historical = result.historicalAnalysis;
  if (!historical) {
    return (
      <div style={styles.resultCard}>
        <p style={{ color: "#9fb2dd" }}>Analysis incomplete. Check logs.</p>
      </div>
    );
  }

  const sentimentColors: Record<string, string> = {
    bullish: "#4ade80",
    bearish: "#ef4444",
    neutral: "#f59e0b",
    mixed: "#8b5cf6",
  };

  return (
    <div style={styles.resultCard}>
      <div style={styles.resultHeader}>
        <span
          style={{
            ...styles.sentiment,
            color: sentimentColors[historical.overall_sentiment],
          }}
        >
          {historical.overall_sentiment}
        </span>
        <span style={styles.probability}>
          {historical.probability_estimate}%
        </span>
      </div>
      <div style={{ fontSize: "12px", color: "#9fb2dd", marginBottom: "8px" }}>
        Confidence: {historical.overall_confidence} | Signal:{" "}
        {historical.overall_signal_strength}/100
      </div>
      <div style={styles.recommendation}>{historical.recommendation}</div>
      {citations.length > 0 && (
        <div style={{ marginTop: "12px", fontSize: "11px" }}>
          <div style={{ color: "#3b82f6", marginBottom: "4px" }}>
            📚 Sources ({citations.length})
          </div>
          {citations.slice(0, 5).map((url, i) => (
            <div
              key={i}
              style={{
                color: "#9fb2dd",
                overflow: "hidden",
                textOverflow: "ellipsis",
              }}
            >
              <a
                href={url}
                target="_blank"
                rel="noopener noreferrer"
                style={{ color: "#3b82f6" }}
              >
                {url.slice(0, 50)}...
              </a>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default App;
