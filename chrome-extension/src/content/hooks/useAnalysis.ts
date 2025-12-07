import { useState, useCallback, useRef, useEffect } from "react";
import type { OutcomeData } from "./useMarketData";

const API_URL = "http://localhost:8000";

export type LogEntryType =
  | "status"
  | "tool-call"
  | "thinking"
  | "citation"
  | "error"
  | "info"
  | "foundational"
  | "historical";

export interface LogEntry {
  id: string;
  type: LogEntryType;
  message: string;
  source?: "foundational" | "historical" | "x_sentiment";
  timestamp: Date;
}

// Grok's probability estimate for a specific outcome
export interface GrokOutcomeEstimate {
  outcome_name: string;
  grok_probability: number; // Grok's estimate (0-100)
  market_probability: number; // Current market price (0-100)
  delta: number; // grok_probability - market_probability (positive = undervalued)
  reasoning: string;
  recommendation: "BUY" | "SELL" | "HOLD";
}

// X Sentiment from prominent figures
export interface ProminentFiguresAnalysis {
  event: string;
  analysis_timestamp: string;
  summary: {
    total_signals: number;
    alpha_count: number;
    noise_count: number;
    sentiment_trend: string;
    key_insights: string[];
  };
  top_signals: Array<{
    source: string;
    platform: string;
    date: string;
    summary: string;
    sentiment: string;
    confidence: number;
    classification: "ALPHA" | "NOISE";
    outcome_referenced?: string;
  }>;
  overall_sentiment: string;
  sentiment_strength: number;
  recommendations: string[];
}

export interface AnalysisResult {
  cacheKey: string;
  createdAt: string;
  expiresAt: string;
  marketTitle: string;
  foundationalData: FoundationalData | null;
  historicalAnalysis: HistoricalAnalysis | null;
  prominentFiguresAnalysis: ProminentFiguresAnalysis | null; // X sentiment from experts
  outcomeEstimates: GrokOutcomeEstimate[] | null;
  totalTimeSeconds?: number;
}

export interface FoundationalData {
  event_query: string;
  generated_at: string;
  facts_summary: string;
  current_odds: MarketOdds[];
  arbitrage_opportunities: ArbitrageOpportunity[];
  probability_visualization: unknown;
  sources: string[];
}

export interface MarketOdds {
  platform: string;
  market_title: string;
  yes_price: number;
  no_price: number;
  yes_probability: number;
  no_probability: number;
}

export interface ArbitrageOpportunity {
  description: string;
  estimated_edge: string;
  recommended_action: string;
}

export interface HistoricalAnalysis {
  event_id: string;
  event_description: string;
  analysis_timestamp: string;
  overall_sentiment: "bullish" | "bearish" | "neutral" | "mixed";
  overall_signal_strength: number;
  overall_confidence: "high" | "medium" | "low" | "very_low" | "very_high";
  bullish_signals: Signal[];
  bearish_signals: Signal[];
  neutral_observations: string[];
  probability_estimate: number;
  probability_reasoning: string;
  critical_path_factors: string[];
  recommendation: string;
}

export interface Signal {
  signal_text: string;
  direction: "bullish" | "bearish" | "neutral";
  strength: number;
  confidence: string;
  historical_precedent: string;
}

export type AnalysisStage =
  | "idle"
  | "connecting"
  | "parallel_start"
  | "foundational"
  | "historical"
  | "complete"
  | "error";

// Track parallel task progress
export interface ParallelProgress {
  foundational: { active: boolean; complete: boolean; elapsed?: number };
  historical: { active: boolean; complete: boolean; elapsed?: number };
  x_sentiment: { active: boolean; complete: boolean; elapsed?: number };
}

export const useAnalysis = () => {
  const [stage, setStage] = useState<AnalysisStage>("idle");
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [thinkingTokens, setThinkingTokens] = useState(0);
  const [citations, setCitations] = useState<string[]>([]);
  const [parallelProgress, setParallelProgress] = useState<ParallelProgress>({
    foundational: { active: false, complete: false },
    historical: { active: false, complete: false },
    x_sentiment: { active: false, complete: false },
  });
  const abortRef = useRef<AbortController | null>(null);

  const addLog = useCallback(
    (
      type: LogEntryType,
      message: string,
      source?: "foundational" | "historical" | "x_sentiment"
    ) => {
      setLogs((prev) => [
        ...prev,
        {
          id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
          type,
          message,
          source,
          timestamp: new Date(),
        },
      ]);
    },
    []
  );

  const clearLogs = useCallback(() => {
    setLogs([]);
    setCitations([]);
    setThinkingTokens(0);
    setError(null);
    setParallelProgress({
      foundational: { active: false, complete: false },
      historical: { active: false, complete: false },
      x_sentiment: { active: false, complete: false },
    });
  }, []);

  // Reset ALL analysis state (for URL changes)
  const resetAnalysis = useCallback(() => {
    // Abort any in-flight request
    if (abortRef.current) {
      abortRef.current.abort();
    }
    setStage("idle");
    setLogs([]);
    setResult(null);
    setError(null);
    setThinkingTokens(0);
    setCitations([]);
    setParallelProgress({
      foundational: { active: false, complete: false },
      historical: { active: false, complete: false },
      x_sentiment: { active: false, complete: false },
    });
  }, []);

  // Auto-reset when the page (omnibar URL) changes
  useEffect(() => {
    let lastUrl = location.href;

    const handleUrlChange = () => {
      if (location.href !== lastUrl) {
        resetAnalysis();
        lastUrl = location.href;
      }
    };

    const observer = new MutationObserver(handleUrlChange);
    observer.observe(document, { subtree: true, childList: true });
    const interval = setInterval(handleUrlChange, 500);
    window.addEventListener("hashchange", handleUrlChange);
    window.addEventListener("popstate", handleUrlChange);

    return () => {
      observer.disconnect();
      clearInterval(interval);
      window.removeEventListener("hashchange", handleUrlChange);
      window.removeEventListener("popstate", handleUrlChange);
    };
  }, [resetAnalysis]);

  const analyze = useCallback(
    async (
      marketTitle: string,
      outcomes: OutcomeData[],
      totalVolume: number | null,
      marketUrl: string,
      forceRefresh = false
    ) => {
      // Abort any existing request
      if (abortRef.current) {
        abortRef.current.abort();
      }
      abortRef.current = new AbortController();

      clearLogs();
      setStage("connecting");
      setResult(null);

      const payload = {
        market_title: marketTitle,
        market_url: marketUrl, // Include URL for Grok to search comments
        total_volume_usd: totalVolume,
        outcomes: outcomes.map((o) => ({
          name: o.name,
          probability: o.probability,
          yesPrice: o.yesPrice,
          noPrice: o.noPrice,
          volume: o.volume,
        })),
        force_refresh: forceRefresh,
      };

      try {
        addLog("status", "Connecting to analysis server...");

        const response = await fetch(`${API_URL}/analyze`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
          signal: abortRef.current.signal,
        });

        if (!response.ok) {
          throw new Error(`Server error: ${response.status}`);
        }

        addLog("status", "Connected! Starting parallel analysis...");

        // Read SSE stream
        const reader = response.body?.getReader();
        if (!reader) throw new Error("No response body");

        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          let eventType: string | null = null;

          for (const line of lines) {
            if (line.startsWith("event: ")) {
              eventType = line.slice(7).trim();
            } else if (line.startsWith("data: ") && eventType) {
              try {
                const data = JSON.parse(line.slice(6));
                handleSSEEvent(eventType, data);
              } catch {
                // Ignore parse errors
              }
            }
          }
        }

        setStage("complete");
      } catch (err) {
        if (err instanceof Error && err.name === "AbortError") {
          addLog("info", "Analysis cancelled");
          setStage("idle");
          return;
        }
        const message = err instanceof Error ? err.message : "Unknown error";
        setError(message);
        addLog("error", `Error: ${message}`);
        setStage("error");
      }
    },
    [addLog, clearLogs]
  );

  const handleSSEEvent = (eventType: string, data: Record<string, unknown>) => {
    const source = data.source as
      | "foundational"
      | "historical"
      | "x_sentiment"
      | undefined;

    switch (eventType) {
      case "status":
        if (data.stage === "parallel_start") {
          setStage("parallel_start");
          setParallelProgress({
            foundational: { active: true, complete: false },
            historical: { active: true, complete: false },
            x_sentiment: { active: true, complete: false },
          });
          addLog("status", "⚡ Running 3 analyses in parallel...");
        } else if (data.stage === "init") {
          addLog("status", data.message as string);
        } else {
          addLog("status", `[${source || data.stage}] ${data.message}`, source);
        }
        break;

      case "log":
        addLog("info", `[${source}] ${data.message}`, source);
        break;

      case "tool_call":
        addLog("tool-call", `🛠️ [${source}] ${data.tool}`, source);
        break;

      case "thinking":
        setThinkingTokens(data.tokens as number);
        break;

      case "citations":
        if (Array.isArray(data.urls)) {
          setCitations((prev) => [...prev, ...(data.urls as string[])]);
          addLog(
            "citation",
            `📚 [${source}] Found ${(data.urls as string[]).length} sources`,
            source
          );
        }
        break;

      case "task_complete":
        const taskName = data.task as
          | "foundational"
          | "historical"
          | "x_sentiment";
        const elapsed = data.elapsed_seconds as number;
        setParallelProgress((prev) => ({
          ...prev,
          [taskName]: { active: false, complete: true, elapsed },
        }));
        addLog("status", `✅ ${taskName} complete (${elapsed}s)`);
        break;

      case "historical_complete":
        addLog(
          "status",
          `📊 Historical: ${data.sentiment} (${data.probability}%)`
        );
        break;

      case "x_sentiment_complete":
        addLog(
          "status",
          `📱 Prominent Figures Sentiment: ${data.sentiment} (${data.alpha_count} alpha signals)`
        );
        break;

      case "error":
        addLog("error", `❌ [${source || data.stage}] ${data.error}`);
        break;

      case "cached":
        addLog("status", "⚡ Using cached result (instant!)");
        break;

      case "result":
        setResult(parseResult(data));
        const totalTime = data.total_time_seconds as number | undefined;
        if (totalTime) {
          addLog("status", `🏁 Total time: ${totalTime}s`);
        }
        break;

      case "done":
        addLog("status", "✅ Analysis complete");
        setStage("complete");
        break;
    }
  };

  const cancel = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
    }
  }, []);

  return {
    stage,
    logs,
    result,
    error,
    thinkingTokens,
    citations,
    parallelProgress,
    analyze,
    cancel,
    clearLogs,
    resetAnalysis,
  };
};

function parseResult(data: Record<string, unknown>): AnalysisResult {
  return {
    cacheKey: data.cache_key as string,
    createdAt: data.created_at as string,
    expiresAt: data.expires_at as string,
    marketTitle: data.market_title as string,
    foundationalData: data.foundational_data as FoundationalData | null,
    historicalAnalysis: data.historical_analysis as HistoricalAnalysis | null,
    prominentFiguresAnalysis:
      data.prominent_figures_analysis as ProminentFiguresAnalysis | null,
    outcomeEstimates: data.outcome_estimates as GrokOutcomeEstimate[] | null,
    totalTimeSeconds: data.total_time_seconds as number | undefined,
  };
}
