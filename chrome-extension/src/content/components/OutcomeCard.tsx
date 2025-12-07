import React from "react";
import type { OutcomeData } from "../hooks/useMarketData";
import { cn } from "@/lib/utils";

interface OutcomeCardProps {
  outcome: OutcomeData;
}

export const OutcomeCard: React.FC<OutcomeCardProps> = ({ outcome }) => {
  const formatPrice = (num: number | null) => {
    if (num == null || Number.isNaN(num)) return "—";
    return `$${Number(num).toFixed(2)}`;
  };

  const formatVolume = (vol: number | null) => {
    if (vol == null) return null;
    return `$${vol.toLocaleString()}`;
  };

  return (
    <div className="rounded-lg border border-ge-border bg-ge-panel p-3 mb-2">
      <div className="flex items-center justify-between gap-2 mb-2">
        <span className="font-semibold text-sm text-ge-text truncate flex-1">
          {outcome.name}
        </span>
        <span className="text-sm text-ge-muted whitespace-nowrap">
          {outcome.probability != null ? `${outcome.probability}%` : "–"}
        </span>
      </div>

      <div className="flex gap-2 flex-wrap">
        <Chip variant="success">Yes: {formatPrice(outcome.yesPrice)}</Chip>
        <Chip variant="error">No: {formatPrice(outcome.noPrice)}</Chip>
      </div>

      {outcome.volume != null && (
        <div className="text-xs text-ge-muted mt-2">
          Vol: {formatVolume(outcome.volume)}
        </div>
      )}
    </div>
  );
};

interface ChipProps {
  children: React.ReactNode;
  variant?: "default" | "success" | "error" | "warning";
}

const Chip: React.FC<ChipProps> = ({ children, variant = "default" }) => {
  return (
    <span
      className={cn(
        "px-2 py-1 rounded-md text-xs border border-ge-border bg-ge-bg",
        variant === "success" && "text-ge-success",
        variant === "error" && "text-ge-error",
        variant === "warning" && "text-ge-warning",
        variant === "default" && "text-ge-muted"
      )}
    >
      {children}
    </span>
  );
};

export default OutcomeCard;

