# Polymarket Insights (Chrome MV3)

Slide-in side panel on `polymarket.com` that scrapes market outcomes (name, probability %, yes/no prices, volume) and sends them to a local Grok-powered analysis server.

## Structure

- `manifest.json` — MV3 config (content script + service worker stub).
- `src/background.js` — placeholder for future messaging/telemetry.
- `src/content.js` — injects the panel, scrapes outcomes, streams analysis from server.

## Quick Start

### 1. Start the prediction server

```bash
# From project root
uv run python prediction_server.py
# or
uv run uvicorn prediction_server:app --reload --port 8000
```

The server exposes:

- `POST /analyze` — SSE streaming endpoint for Grok analysis
- `GET /analyze/{cache_key}` — retrieve cached results
- `GET /health` — healthcheck

### 2. Load the extension

**Option A: Using extension.js (recommended for dev)**

```bash
cd polymarket-insights/chrome-extension
bun run dev
```

This opens a managed Chrome instance with hot-reload.

**Option B: Manual load**

1. Open Chrome → `chrome://extensions`
2. Enable **Developer mode**
3. Click **Load unpacked** and choose `polymarket-insights/chrome-extension`
4. Navigate to a Polymarket market page

### 3. Use the extension

1. Open any Polymarket market page (e.g., `https://polymarket.com/event/...`)
2. The Polymarket Insights panel slides in automatically
3. Click **"🔮 Analyze with Grok"** to run sentiment analysis
4. Watch streaming logs as Grok researches the market
5. View the final sentiment, probability estimate, and recommendation

## UI Features

- **Floating Grok button** (bottom-right) toggles the panel
- **Market detection** — auto-extracts title, total volume, and outcomes
- **Per-outcome data** — name, probability %, yes/no prices, volume
- **Streaming analysis** — live tool calls, thinking tokens, citations
- **Result card** — sentiment, probability, confidence, recommendation
- **30-minute cache** — avoids burning API credits on repeated analysis

## Scraping Notes

Targets common Polymarket structures:

- `[data-testid="outcome-row"]`
- `div[class*="OutcomeRow"]`
- Buy button discovery (finds parent rows with buy buttons)
- Volume patterns like `$391,457 Vol.`

If Polymarket changes its DOM, adjust selectors in `scrapeOutcomes()` / `parseOutcomeNode()` / `findVolume()` inside `src/content.js`.

## Environment

Ensure your `.env` file in the project root has:

```
GROK_API_KEY=your-xai-api-key
```

## Dependencies

**Python (uv)**

```bash
uv sync
```

**Extension (bun)**

```bash
cd grokedge/chrome-extension
bun install
```
