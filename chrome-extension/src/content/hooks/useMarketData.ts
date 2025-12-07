import { useState, useEffect, useCallback } from "react";

export interface OutcomeData {
  name: string;
  probability: number | null;
  yesPrice: number | null;
  noPrice: number | null;
  volume: number | null;
}

export interface MarketData {
  title: string;
  totalVolume: number | null;
  outcomes: OutcomeData[];
  url: string;
}

// Scraping utilities (ported from vanilla JS)
const scrapeOutcomes = (): OutcomeData[] => {
  const selectors = [
    '[data-testid="outcome-row"]',
    '[data-testid*="outcome-row"]',
    '[data-testid*="OutcomeRow"]',
    '[data-testid*="market-outcome"]',
    '[data-testid*="table-row"]',
    '[role="row"]',
    'div[class*="OutcomeRow"]',
    'div[class*="outcome-row"]',
    'div[class*="OutcomesList"] div[class*="row"]',
    "tbody tr",
  ];

  const seen = new Set<string>();
  const nodes: Element[] = [];

  selectors.forEach((sel) =>
    document.querySelectorAll(sel).forEach((node) => nodes.push(node))
  );

  // Add rows discovered by buy buttons
  findRowsFromButtons().forEach((n) => nodes.push(n));

  if (!nodes.length) return [];

  return nodes
    .map((node) => parseOutcomeNode(node))
    .filter((o): o is OutcomeData => o !== null)
    .filter((outcome) => {
      const key = outcome.name.toLowerCase();
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
};

const findRowsFromButtons = (): Element[] => {
  const rows: Element[] = [];
  const buttons = Array.from(
    document.querySelectorAll("button, [role='button'], a")
  ).filter((b) => (b.textContent || "").toLowerCase().includes("buy"));

  buttons.forEach((btn) => {
    const row = findOutcomeContainer(btn);
    if (row) rows.push(row);
  });

  return rows;
};

const findOutcomeContainer = (el: Element): Element | null => {
  let node: Element | null = el;
  while (node && node !== document.body) {
    const text = (node.textContent || "").toLowerCase();
    const hasYes = text.includes("buy yes");
    const hasNo = text.includes("buy no");
    const hasBuy = text.includes("buy ");
    const hasPercent = text.match(/\d+(\.\d+)?\s*%/);
    const hasNameish = text.length > 0 && text.length < 600;
    if ((hasYes || hasNo || hasBuy) && hasPercent && hasNameish) return node;
    node = node.parentElement;
  }
  return null;
};

const parseOutcomeNode = (node: Element): OutcomeData | null => {
  const name = findName(node) || inferYesNoName(node);
  if (!name) return null;
  const probability = findProbability(node);
  const yesPrice = findPrice(node, "yes");
  const noPrice = findPrice(node, "no");
  const volume = findVolume(node);
  if (probability == null && yesPrice == null && noPrice == null) return null;
  return { name, probability, yesPrice, noPrice, volume };
};

const findName = (node: Element): string | null => {
  const nameNode =
    node.querySelector('[data-testid*="label"]') ||
    node.querySelector('[data-testid*="outcome-name"]') ||
    node.querySelector('[class*="OutcomeName"]') ||
    node.querySelector('[class*="outcome-name"]') ||
    node.querySelector("h3") ||
    node.querySelector("h4") ||
    node.querySelector("p");

  const text = nameNode?.textContent?.trim();
  if (text) return text;

  const candidates = Array.from(node.querySelectorAll("span, div"))
    .map((n) => n.textContent?.trim() || "")
    .filter(
      (t) =>
        t.length > 1 &&
        t.length < 120 &&
        !t.match(/%|\$|Yes|No|Buy|Sell|Trade|\u00a2/i)
    );
  return candidates[0] || null;
};

// Handle minimal UIs that only show "Buy Yes" / "Buy No" buttons without labels
const inferYesNoName = (node: Element): string | null => {
  const text = (node.textContent || "").toLowerCase();
  const hasYes = text.includes("buy yes");
  const hasNo = text.includes("buy no");
  if (hasYes && hasNo) return "Yes / No";
  if (hasYes) return "Yes";
  if (hasNo) return "No";
  return null;
};

const findProbability = (node: Element): number | null => {
  const text = node.textContent || "";
  const percentSpan = Array.from(node.querySelectorAll("span, div, p")).find(
    (el) => (el.textContent || "").trim().match(/%/)
  );
  const primaryText = percentSpan?.textContent || text;
  const match = primaryText.match(
    /(<\s*\d+(?:\.\d+)?)\s*%|(\d+(?:\.\d+)?)\s*%/
  );
  if (!match) return null;
  if (match[1]) {
    const val = Number(match[1].replace(/</g, "").trim());
    return Math.max(val, 0.5);
  }
  return Number(match[2]);
};

const findPrice = (node: Element, label: string): number | null => {
  const btn = Array.from(
    node.querySelectorAll("button, [role='button'], a")
  ).find((el) => {
    const t = (el.textContent || "").toLowerCase();
    return t.includes(label.toLowerCase());
  });
  const sources = [btn?.textContent || "", node.textContent || ""];
  for (const text of sources) {
    const value = parsePrice(text, label);
    if (value != null) return value;
  }
  return null;
};

const parsePrice = (text: string, label: string): number | null => {
  if (!text) return null;
  const lower = text.toLowerCase();
  if (!lower.includes(label.toLowerCase())) return null;

  const centMatch = text.match(/(\d+(?:\.\d+)?)\s*¢/);
  if (centMatch) return Number(centMatch[1]) / 100;

  const dollarMatch = text.match(/\$?\s*(\d+(?:\.\d+)?)/);
  if (dollarMatch) return Number(dollarMatch[1]);

  return null;
};

const findVolume = (node: Element): number | null => {
  const text = node.textContent || "";
  const volMatch = text.match(/\$\s*([\d,]+(?:\.\d+)?)\s*Vol/i);
  if (volMatch) {
    return parseFloat(volMatch[1].replace(/,/g, ""));
  }
  const volSpan = Array.from(node.querySelectorAll("span, div")).find((el) =>
    (el.textContent || "").toLowerCase().includes("vol")
  );
  if (volSpan) {
    const spanMatch = volSpan.textContent?.match(/\$\s*([\d,]+(?:\.\d+)?)/);
    if (spanMatch) {
      return parseFloat(spanMatch[1].replace(/,/g, ""));
    }
  }
  return null;
};

const getMarketTitle = (): string => {
  const titleNode =
    document.querySelector("h1") ||
    document.querySelector('[data-testid*="market-title"]') ||
    document.querySelector('[class*="MarketTitle"]');
  if (titleNode?.textContent) return titleNode.textContent.trim();
  return document.title || "Polymarket market";
};

const getTotalMarketVolume = (): number | null => {
  const volumePatterns = [/\$\s*([\d,]+(?:\.\d+)?)\s*Vol/gi];
  const headerCandidates = document.querySelectorAll(
    'div[class*="header"], div[class*="market"], div[class*="stats"], span, p'
  );
  for (const el of headerCandidates) {
    const text = el.textContent || "";
    for (const pattern of volumePatterns) {
      pattern.lastIndex = 0;
      const match = pattern.exec(text);
      if (match) {
        const vol = parseFloat(match[1].replace(/,/g, ""));
        if (vol > 100000) return vol;
      }
    }
  }
  return null;
};

export const useMarketData = () => {
  const [data, setData] = useState<MarketData | null>(null);
  const [url, setUrl] = useState(location.href);
  const [isLoading, setIsLoading] = useState(true);

  const refresh = useCallback(() => {
    setIsLoading(true);
    const title = getMarketTitle();
    const totalVolume = getTotalMarketVolume();
    const outcomes = scrapeOutcomes();

    setData({
      title,
      totalVolume,
      outcomes,
      url: location.href,
    });
    setIsLoading(false);
  }, []);

  // Detect URL changes (SPA navigation)
  useEffect(() => {
    const checkUrl = () => {
      if (location.href !== url) {
        setUrl(location.href);
        setData(null); // Clear stale data immediately
      }
    };

    // Check on DOM mutations (SPA navigation)
    const observer = new MutationObserver(checkUrl);
    observer.observe(document, { subtree: true, childList: true });

    // Also check periodically
    const interval = setInterval(checkUrl, 500);

    return () => {
      observer.disconnect();
      clearInterval(interval);
    };
  }, [url]);

  // Re-scrape when URL changes
  useEffect(() => {
    // Debounce the scrape to let DOM settle
    const timeout = setTimeout(refresh, 300);
    return () => clearTimeout(timeout);
  }, [url, refresh]);

  // Observe DOM for outcome changes
  useEffect(() => {
    const debouncedRefresh = debounce(refresh, 500);
    const observer = new MutationObserver(debouncedRefresh);
    observer.observe(document.body, { childList: true, subtree: true });
    return () => observer.disconnect();
  }, [refresh]);

  return { data, isLoading, refresh };
};

// Utility
function debounce<T extends (...args: unknown[]) => void>(
  fn: T,
  ms: number
): T {
  let timer: ReturnType<typeof setTimeout>;
  return ((...args: unknown[]) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  }) as T;
}
