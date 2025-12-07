import React from "react";
import type { AnalysisResult as AnalysisResultType, Signal } from "../hooks/useAnalysis";
import {
  Accordion,
  AccordionItem,
  AccordionTrigger,
  AccordionContent,
} from "./ui/accordion";
import { cn } from "@/lib/utils";

interface AnalysisResultProps {
  result: AnalysisResultType;
  citations: string[];
}

export const AnalysisResult: React.FC<AnalysisResultProps> = ({
  result,
  citations,
}) => {
  const historical = result.historicalAnalysis;

  if (!historical) {
    return (
      <div className="mt-3 p-3 rounded-lg border border-ge-border bg-ge-panel">
        <p className="text-ge-muted text-sm">
          Analysis incomplete. Check logs for errors.
        </p>
      </div>
    );
  }

  const sentimentColors: Record<string, string> = {
    bullish: "text-ge-success",
    bearish: "text-ge-error",
    neutral: "text-ge-warning",
    mixed: "text-purple-400",
  };

  return (
    <div className="mt-3 space-y-3">
      {/* Main Result Card */}
      <div className="rounded-lg border border-blue-500/50 bg-gradient-to-br from-ge-panel to-ge-bg p-4">
        <div className="flex items-center justify-between mb-3">
          <span
            className={cn(
              "text-lg font-bold uppercase",
              sentimentColors[historical.overall_sentiment]
            )}
          >
            {historical.overall_sentiment}
          </span>
          <span className="text-3xl font-extrabold text-ge-text">
            {historical.probability_estimate}%
          </span>
        </div>

        <div className="flex items-center gap-4 text-xs text-ge-muted mb-3">
          <span>
            Confidence:{" "}
            <span className="text-ge-text capitalize">
              {historical.overall_confidence}
            </span>
          </span>
          <span>
            Signal:{" "}
            <span className="text-ge-text">
              {historical.overall_signal_strength}/100
            </span>
          </span>
        </div>

        <div className="p-3 rounded-md bg-ge-bg text-sm text-ge-text leading-relaxed">
          {historical.recommendation}
        </div>
      </div>

      {/* Collapsible Sections */}
      <Accordion type="multiple" className="space-y-2">
        {/* Probability Reasoning */}
        <AccordionItem value="reasoning" className="border-0">
          <div className="rounded-lg border border-ge-border bg-ge-panel overflow-hidden">
            <AccordionTrigger className="px-3 hover:no-underline">
              <span className="text-sm font-medium">🧠 Probability Reasoning</span>
            </AccordionTrigger>
            <AccordionContent className="px-3">
              <p className="text-sm text-ge-muted leading-relaxed">
                {historical.probability_reasoning}
              </p>
            </AccordionContent>
          </div>
        </AccordionItem>

        {/* Bullish Signals */}
        {historical.bullish_signals.length > 0 && (
          <AccordionItem value="bullish" className="border-0">
            <div className="rounded-lg border border-ge-border bg-ge-panel overflow-hidden">
              <AccordionTrigger className="px-3 hover:no-underline">
                <span className="text-sm font-medium text-ge-success">
                  🐂 Bullish Signals ({historical.bullish_signals.length})
                </span>
              </AccordionTrigger>
              <AccordionContent className="px-3">
                <SignalList signals={historical.bullish_signals} />
              </AccordionContent>
            </div>
          </AccordionItem>
        )}

        {/* Bearish Signals */}
        {historical.bearish_signals.length > 0 && (
          <AccordionItem value="bearish" className="border-0">
            <div className="rounded-lg border border-ge-border bg-ge-panel overflow-hidden">
              <AccordionTrigger className="px-3 hover:no-underline">
                <span className="text-sm font-medium text-ge-error">
                  🐻 Bearish Signals ({historical.bearish_signals.length})
                </span>
              </AccordionTrigger>
              <AccordionContent className="px-3">
                <SignalList signals={historical.bearish_signals} />
              </AccordionContent>
            </div>
          </AccordionItem>
        )}

        {/* Critical Path Factors */}
        {historical.critical_path_factors.length > 0 && (
          <AccordionItem value="critical" className="border-0">
            <div className="rounded-lg border border-ge-border bg-ge-panel overflow-hidden">
              <AccordionTrigger className="px-3 hover:no-underline">
                <span className="text-sm font-medium">
                  🎯 Critical Path Factors
                </span>
              </AccordionTrigger>
              <AccordionContent className="px-3">
                <ul className="space-y-1">
                  {historical.critical_path_factors.map((factor, i) => (
                    <li
                      key={i}
                      className="text-sm text-ge-muted flex items-start gap-2"
                    >
                      <span className="text-ge-accent">•</span>
                      {factor}
                    </li>
                  ))}
                </ul>
              </AccordionContent>
            </div>
          </AccordionItem>
        )}

        {/* Neutral Observations */}
        {historical.neutral_observations.length > 0 && (
          <AccordionItem value="neutral" className="border-0">
            <div className="rounded-lg border border-ge-border bg-ge-panel overflow-hidden">
              <AccordionTrigger className="px-3 hover:no-underline">
                <span className="text-sm font-medium text-ge-warning">
                  ⚖️ Neutral Observations
                </span>
              </AccordionTrigger>
              <AccordionContent className="px-3">
                <ul className="space-y-1">
                  {historical.neutral_observations.map((obs, i) => (
                    <li key={i} className="text-sm text-ge-muted">
                      {obs}
                    </li>
                  ))}
                </ul>
              </AccordionContent>
            </div>
          </AccordionItem>
        )}

        {/* Citations */}
        {citations.length > 0 && (
          <AccordionItem value="citations" className="border-0">
            <div className="rounded-lg border border-ge-border bg-ge-panel overflow-hidden">
              <AccordionTrigger className="px-3 hover:no-underline">
                <span className="text-sm font-medium text-blue-400">
                  📚 Sources ({citations.length})
                </span>
              </AccordionTrigger>
              <AccordionContent className="px-3">
                <ul className="space-y-1">
                  {citations.map((url, i) => (
                    <li key={i} className="text-xs truncate">
                      <a
                        href={url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-400 hover:underline"
                      >
                        {url}
                      </a>
                    </li>
                  ))}
                </ul>
              </AccordionContent>
            </div>
          </AccordionItem>
        )}
      </Accordion>
    </div>
  );
};

const SignalList: React.FC<{ signals: Signal[] }> = ({ signals }) => (
  <div className="space-y-2">
    {signals.map((signal, i) => (
      <div key={i} className="p-2 rounded bg-ge-bg">
        <div className="flex items-center justify-between mb-1">
          <span className="text-sm text-ge-text">{signal.signal_text}</span>
          <span className="text-xs text-ge-muted">{signal.strength}/100</span>
        </div>
        {signal.historical_precedent && (
          <p className="text-xs text-ge-muted mt-1 italic">
            📜 {signal.historical_precedent}
          </p>
        )}
      </div>
    ))}
  </div>
);

export default AnalysisResult;

