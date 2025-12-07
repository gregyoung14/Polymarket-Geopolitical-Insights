import React, { useEffect, useRef } from "react";
import type { LogEntry } from "../hooks/useAnalysis";
import { cn } from "@/lib/utils";

interface StreamingLogProps {
  logs: LogEntry[];
  thinkingTokens: number;
  isActive: boolean;
}

export const StreamingLog: React.FC<StreamingLogProps> = ({
  logs,
  thinkingTokens,
  isActive,
}) => {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs]);

  if (!isActive && logs.length === 0) return null;

  return (
    <div className="mt-3">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-medium text-ge-muted">Activity Log</span>
        {thinkingTokens > 0 && (
          <span className="text-xs text-purple-400 flex items-center gap-1">
            <span className="inline-block w-2 h-2 rounded-full bg-purple-400 animate-pulse" />
            Thinking: {thinkingTokens} tokens
          </span>
        )}
      </div>

      <div
        ref={scrollRef}
        className="rounded-lg border border-ge-border bg-ge-bg p-2 font-mono text-xs max-h-40 overflow-y-auto"
      >
        {logs.length === 0 ? (
          <div className="text-ge-muted text-center py-2">
            Waiting for events...
          </div>
        ) : (
          logs.map((log) => (
            <LogLine key={log.id} log={log} />
          ))
        )}
      </div>
    </div>
  );
};

const LogLine: React.FC<{ log: LogEntry }> = ({ log }) => {
  const typeStyles: Record<string, string> = {
    status: "text-ge-success",
    "tool-call": "text-amber-400",
    thinking: "text-purple-400",
    citation: "text-blue-400",
    error: "text-ge-error",
    info: "text-ge-muted",
  };

  return (
    <div
      className={cn(
        "py-0.5 border-b border-ge-border/30 last:border-0",
        typeStyles[log.type] || "text-ge-text"
      )}
    >
      <span className="opacity-50 mr-2">
        {log.timestamp.toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        })}
      </span>
      {log.message}
    </div>
  );
};

export default StreamingLog;

