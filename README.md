# Polymarket Insights 🔮

**A real-time prediction market analysis engine powered by Grok AI**

Polymarket Insights combines a Chrome extension for live market scraping with a sophisticated backend that leverages Grok's agentic capabilities to deliver actionable intelligence for prediction market trading. The system runs three parallel analysis pipelines (foundational data, historical precedents, and X/Twitter sentiment) to generate probability estimates and trading recommendations.

---

## 🏗️ Architecture Overview

### System Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    Chrome Extension                              │
│  (Polymarket.com Side Panel)                                    │
│  • Auto-scrapes market outcomes                                 │
│  • Sends to backend via SSE                                     │
│  • Displays real-time streaming results                         │
└─────────────────────────────────┬───────────────────────────────┘
                                  │ POST /analyze
                    ┌─────────────┴──────────────┐
                    │ FastAPI Backend            │
                    │ (prediction_server.py)     │
                    └─────────────┬──────────────┘
                                  │
        ┌─────────────────────────┼─────────────────────────┐
        │                         │                         │
        ▼                         ▼                         ▼
   ┌──────────────┐      ┌──────────────┐      ┌──────────────────┐
   │ Foundational │      │  Historical  │      │ Prominent Figures│
   │ Data Service │      │  Research    │      │ Sentiment        │
   │              │      │              │      │                  │
   │ • Web Search │      │ • Questions  │      │ • X API Scrape   │
   │ • X Search   │      │ • Grok LLM   │      │ • Grok Analysis  │
   │ • Agentic    │      │   Inference  │      │ • Signal Extract │
   └──────────────┘      └──────────────┘      └──────────────────┘
        │                     │                         │
        └─────────────────────┼─────────────────────────┘
                              │
                    ┌─────────▼──────────┐
                    │  Grok Outcome      │
                    │  Estimator         │
                    │                    │
                    │ Synthesizes all 3  │
                    │ pipelines into     │
                    │ per-outcome BUY/   │
                    │ SELL/HOLD + delta  │
                    └────────────────────┘
```

---

## 🧠 Backend Logic (The Real Magic)

### High-Level Flow

1. **Request Intake** → Chrome extension sends market title, outcomes, and URLs
2. **Cache Check** → If recent analysis exists, stream cached results
3. **Parallel Analysis** → Launch 3 concurrent pipelines:
   - **Foundational Data** → Web + X search for context
   - **Historical Research** → Generate questions, get Grok answers
   - **Prominent Figures** → Scrape X tweets, analyze sentiment
4. **Outcome Estimation** → Grok synthesizes all 3 signals into per-outcome probability deltas
5. **Stream Results** → SSE streams logs, thinking tokens, and final result back to extension

### Core Components

#### 1. **prediction_server.py** - The Orchestrator

FastAPI backend that coordinates the entire analysis pipeline.

**Key Functions:**
- `POST /analyze` - Main analysis endpoint with SSE streaming
- `GET /analyze/{cache_key}` - Retrieve cached results
- `run_parallel_analysis_stream()` - Executes all 3 pipelines concurrently
- `generate_outcome_estimates()` - Synthesizes findings into trading recommendations

**Caching Strategy:**
- Cache key based on: market title + outcome names + URL (stable identifiers)
- 30-minute TTL
- In-memory storage (can be upgraded to Redis)
- Avoid re-analyzing the same market within 30 minutes

**SSE Streaming:**
- Each task completion sends a JSON event to the client
- Clients receive real-time logs, progress updates, thinking tokens
- Final result includes all synthesis data

#### 2. **foundational_data.py** - Context Intelligence

Uses Grok's agentic tools (web search, X search) to gather contextual information.

**Output Structure:**
```python
@dataclass
class FoundationalData:
    facts: str                    # Key facts about the event
    search_results: List[str]     # Web search URLs
    x_posts_summary: str          # X/Twitter insights
    market_odds: List[MarketOdds] # Odds across platforms
    arbitrage_opportunities: List[ArbitrageOpportunity]
    charts: List[ProbabilityVisualization]
```

**Process:**
1. Web search for event-related news/articles
2. X search for trending discussions
3. Extract odds data from multiple platforms
4. Identify arbitrage opportunities
5. Generate visualizations (pie charts, timelines)

**Grok Integration:**
```python
# Uses xAI SDK with agentic tools
client = Client(api_key=GROK_API_KEY)
response = client.messages.create(
    model="grok-4-latest",
    messages=[
        system("You are a market researcher..."),
        user(f"Research: {event_title}")
    ],
    tools=[web_search, x_search]  # Agentic tools
)
```

#### 3. **historical_research_live.py** - Reference Class Forecasting

Generates domain-specific historical questions and gets Grok's answers via live API.

**Methodology:**
- **Base Rates** - "How often does this type of event happen?"
- **Reference Classes** - Compare against historical precedents
- **Quantitative Analysis** - Apply hard constraints (logistics, distance, time)
- **Devil's Advocate** - Flag contradicting evidence

**Process:**
1. Generate domain-specific questions (e.g., for military events, ask about troop movements, supply lines, historical parallels)
2. Call Grok with military historian prompt
3. Extract confidence levels and signal direction
4. Compile into structured response

**Example Questions Generated:**
```
"Historical Analysis: Russian capturing all of [location] by [date]"
- "What is the historical base rate of [specific scenario]?"
- "What are the key logistical constraints on [movement type]?"
- "What precedents exist for [historical parallel]?"
```

**Grok Response Structure:**
```python
class HistoricalAnalysisResponse(BaseModel):
    overall_sentiment: SentimentEnum  # bullish/bearish/neutral
    probability_estimate: int         # 0-100
    overall_confidence: ConfidenceEnum # high/medium/low
    overall_signal_strength: int      # 0-100
    recommendation: str               # Trading recommendation
    historical_precedents: List[HistoricalPrecedent]
```

#### 4. **analyze_prominent_figure_tweets.py** - X Sentiment Analysis

Scrapes tweets from relevant figures and extracts alpha signals.

**Process:**
1. **Fetch Tweets** - Uses X API to fetch tweets from curated figures
2. **Filter** - Apply location keywords and date ranges
3. **Classify** - Each tweet is either ALPHA (actionable) or NOISE
4. **Extract Sentiment** - Bullish/Bearish/Neutral based on tweet content
5. **Confidence Scoring** - 0-1 score based on evidence quality

**ALPHA Signal Criteria:**
- Explicit probability estimates ("50% chance Russia takes X by year-end")
- Strategic analysis linking current situation to outcomes
- References to timelines, troop movements, logistics
- High-confidence sources with reasoning

**NOISE Criteria:**
- Generic war updates without specifics
- Propaganda-style claims without evidence
- Historical context only
- Retweets without original analysis

**Grok Prompt Strategy:**
```python
ANALYSIS_SYSTEM_PROMPT = """You are an analytic engine monitoring X for: **"{event_description}"**

CLASSIFY each tweet:
1. Is it ALPHA (actionable signal) or NOISE?
2. What's the sentiment: Bullish/Bearish/Neutral?
3. Confidence 0-1 based on evidence quality
4. Why does it matter?

OUTPUT: Strict JSON with tweet_id, classification, sentiment, confidence, notes
"""
```

#### 5. **generate_outcome_estimates()** - The Synthesis Engine

Combines all 3 pipelines into per-outcome trading recommendations.

**Algorithm:**
```
For each outcome:
  1. Extract market probability from price (e.g., $0.75 = 75%)
  2. Get Grok's estimated probability from historical + foundational analysis
  3. Calculate delta = grok_probability - market_probability
  4. Overlay prominent figures sentiment (bullish/bearish adjusts estimate)
  5. Generate recommendation:
     - BUY if delta > 5% and high confidence
     - SELL if delta < -5% and high confidence
     - HOLD if |delta| < 5%
  6. Generate reasoning from all 3 pipeline outputs
```

**Output:**
```python
class GrokOutcomeEstimate(BaseModel):
    outcome_name: str
    grok_probability: float      # 0-100
    market_probability: float    # 0-100
    delta: float                 # Positive = undervalued, Negative = overvalued
    reasoning: str               # Why this estimate
    recommendation: str          # BUY/SELL/HOLD
```

---

## 💻 Frontend: Chrome Extension

### Architecture

The Chrome extension is a **Manifest V3** content script that injects a floating side panel into Polymarket.com.

### File Structure

```
chrome-extension/
├── manifest.json               # MV3 config
├── src/
│   ├── background.ts          # Service worker (minimal)
│   ├── content/
│   │   ├── index.tsx          # Entry point, DOM injection
│   │   ├── App.tsx            # Main React component
│   │   ├── hooks/
│   │   │   ├── useMarketData  # Scrapes DOM for outcomes
│   │   │   └── useAnalysis    # SSE streaming logic
│   │   └── index.css
│   └── [other components]
├── package.json
├── tsconfig.json
├── tailwind.config.js         # Tailwind CSS
└── manifest.json
```

### Key Components

#### **App.tsx** - Main UI Component

**Responsibilities:**
- Render floating panel on right side of screen
- Display market title, outcomes, volume
- Handle analyze button clicks
- Stream results in real-time
- Display final sentiment/probability/recommendation

**Key Features:**
- Inline styles (Tailwind doesn't work in injected content)
- Fixed positioning (zIndex: 2147483647)
- Smooth animations and transitions
- Live progress indicators for parallel tasks
- Outcome sorting by trading opportunity (largest delta first)

**UI Sections:**
```
┌─ Header ─────────────────────┐
│ 🟢 Polymarket Insights | 🔄 ✕ │
├──────────────────────────────┤
│ Market Title                  │
│ Total Volume: $XXX,XXX        │
│                               │
│ Outcomes:                     │
│ ┌ Outcome 1  75%  $0.75/$0.25 │  ← Sorted by delta
│ │ 🔮 Grok: 80% vs Mkt: 75%   │
│ │ Delta: +5.0%                │
│ ├ Outcome 2  25%  $0.25/$0.75 │
│ └ ...                         │
│                               │
│ 🔮 Analyze with Grok Button  │
│                               │
│ Progress Pills:               │
│ [🔬 Foundational ✓] [📜...] │
│                               │
│ Logs:                         │
│ > Fetching market data...    │
│ > Running analysis...        │
│                               │
│ Result Card:                  │
│ Sentiment: BULLISH            │
│ Probability: 75%              │
│ Confidence: HIGH              │
│ Recommendation: ...           │
├──────────────────────────────┤
│ Built for Grok/X experiments │
└──────────────────────────────┘
```

#### **useMarketData.tsx** - DOM Scraping

Scrapes Polymarket DOM to extract:
- Market title
- Total volume
- Outcomes (name, probability %, yes/no prices, volume)

**Scraping Strategy:**
```typescript
// Targets common Polymarket selectors
const selectors = [
    '[data-testid="outcome-row"]',
    'div[class*="OutcomeRow"]',
    // fallback selectors
];

// Extract prices from buy buttons
const yesPrice = parseFloat(buyButton.textContent);
const noPrice = 1 - yesPrice;

// Volume detection via regex
const volumeRegex = /\$[\d,]+(?:\.\d{2})?\s*Vol/;
```

**Update Strategy:**
- Polls DOM every 5 seconds
- Recalculates when outcomes change
- Resets analysis when URL changes

#### **useAnalysis.tsx** - SSE Streaming

Manages analysis state and SSE connection to backend.

**Process:**
1. When "Analyze" clicked, send market data to `/analyze` endpoint
2. Open SSE connection to receive streaming events
3. Parse events:
   - `log` - Streaming log entries
   - `progress` - Task progress updates
   - `thinking_tokens` - Grok's internal reasoning
   - `result` - Final analysis
   - `error` - Error messages
4. Update UI state in real-time
5. Cache result for 30 minutes

**Event Flow:**
```
Client                          Server
  │                              │
  ├─ POST /analyze ──────────────>│
  │                              │
  │<─ SSE: {"type": "log"} ──────┤
  │                              │
  │<─ SSE: {"type": "progress"}─┤
  │                              │
  │<─ SSE: {"type": "thinking"}─┤
  │                              │
  │<─ SSE: {"type": "result"}───┤
  │<─ SSE: [DONE] ──────────────┤
  │                              │
```

### DOM Injection

**How the panel gets into Polymarket:**
```typescript
const HOST_ID = "polymarket-insights-extension-root";

// In content/index.tsx:
const root = document.createElement("div");
root.id = HOST_ID;
document.body.appendChild(root);

// React renders the App component
ReactDOM.createRoot(root).render(<PolymarketInsightsRoot />);
```

**Styling Strategy:**
- All styles are inline (Tailwind CSS doesn't work in injected scripts)
- Custom keyframes injected into `<head>` for animations
- z-index set to max (2147483647) to stay above Polymarket UI

### Key Features

**1. Outcome Sorting by Alpha**
```typescript
// When Grok estimates are available, sort by delta
enhancedOutcomes.sort((a, b) => b.sortDelta - a.sortDelta);

// Display biggest arbitrage opportunities first
```

**2. Real-time Progress Tracking**
```typescript
┌ Progress Pills ─────────────────┐
│ 🔬 Foundational: 2.3s           │
│ 📜 Historical: ⏳ (spinning)    │
│ 📱 Prominent Figures: (waiting) │
└─────────────────────────────────┘
```

**3. Per-Outcome Recommendations**
```
If delta > 5%:  🟢 BUY (undervalued)
If delta < -5%: 🔴 SELL (overvalued)
Otherwise:      ⚪ HOLD (fair value)
```

---

## 🔧 Installation & Setup

### Prerequisites
- Node.js + Bun (for extension)
- Python 3.11+ (for backend)
- Chrome/Chromium
- X API credentials (for tweet scraping)
- Grok/xAI API credentials

### Backend Setup

```bash
# From project root
cd backend

# Install Python dependencies
uv sync

# Create .env file
cp env.example .env

# Fill in credentials:
# GROK_API_KEY=your-xai-api-key
# X_API_KEY=your-x-api-key
# X_API_SECRET=your-x-api-secret
# X_BEARER_TOKEN=your-x-bearer-token
# GROK_API_URL=https://api.x.ai

# Start server
uv run python prediction_server.py
# Server runs on http://localhost:8000
```

### Chrome Extension Setup

**Option A: Development Mode (Hot Reload)**
```bash
cd chrome-extension
bun install
bun run dev
# Opens Chrome with hot-reload enabled
```

**Option B: Manual Load**
```bash
cd chrome-extension
bun install
bun run build

# Then:
# 1. Open Chrome → chrome://extensions
# 2. Enable "Developer mode" (top right)
# 3. Click "Load unpacked"
# 4. Select chrome-extension/ folder
# 5. Visit polymarket.com
```

### Environment Variables

Create `backend/.env`:
```bash
# Grok/xAI API
GROK_API_KEY=xai_...
GROK_API_URL=https://api.x.ai

# X/Twitter API (for tweet scraping)
X_API_KEY=...
X_API_SECRET=...
X_BEARER_TOKEN=...

# Optional: External data sources
KALSHI_API_KEY=...
POLYMARKET_GRAPHQL_URL=https://...

# Server config
SERVER_PORT=8000
SERVER_HOST=0.0.0.0
CACHE_TTL_MINUTES=30
```

---

## 📊 API Reference

### POST /analyze

**Request:**
```json
{
  "market_title": "Will Russia capture [location] by [date]?",
  "market_url": "https://polymarket.com/event/...",
  "total_volume_usd": 500000,
  "outcomes": [
    {
      "name": "Yes, [location] captured",
      "probability": 0.75,
      "yesPrice": 0.75,
      "noPrice": 0.25,
      "volume": 250000
    },
    {
      "name": "No, [location] not captured",
      "probability": 0.25,
      "yesPrice": 0.25,
      "noPrice": 0.75,
      "volume": 250000
    }
  ],
  "force_refresh": false
}
```

**Response (SSE Stream):**
```
event: log
data: {"type": "status", "message": "Starting foundational data analysis..."}

event: log
data: {"type": "tool-call", "message": "Executing web_search: '[location] military situation'"}

event: progress
data: {"task": "foundational", "status": "active", "elapsed": 2.3}

event: thinking
data: {"tokens": 1247}

event: result
data: {
  "foundational_data": {...},
  "historical_analysis": {...},
  "prominent_figures_analysis": {...},
  "outcome_estimates": [
    {
      "outcome_name": "Yes, [location] captured",
      "grok_probability": 80,
      "market_probability": 75,
      "delta": 5.0,
      "reasoning": "Based on recent supply line movements...",
      "recommendation": "BUY"
    },
    ...
  ]
}

event: DONE
data: [DONE]
```

### GET /analyze/{cache_key}

Retrieves a cached analysis result.

**Response:**
```json
{
  "cache_key": "sha256_hash",
  "created_at": "2025-01-21T20:00:00Z",
  "expires_at": "2025-01-21T20:30:00Z",
  "market_title": "...",
  "foundational_data": {...},
  "historical_analysis": {...},
  "prominent_figures_analysis": {...},
  "outcome_estimates": [...]
}
```

### GET /health

Health check endpoint.

**Response:**
```json
{
  "status": "ok",
  "timestamp": "2025-01-21T20:00:00Z"
}
```

---

## 🎯 Data Flow Examples

### Example 1: Simple Market Analysis

**User Input:**
- Visits polymarket.com
- Opens market "Will Trump announce something by Feb 1?"
- Clicks "🔮 Analyze with Grok"

**Backend Flow:**
1. **Foundational** - Web search for recent Trump news, X search for trending takes
2. **Historical** - Analyze historical probability of similar announcements
3. **Prominent Figures** - Extract sentiment from political analysts on X
4. **Synthesis** - Combine signals into outcome estimates

**Output to Extension:**
```
Overall Sentiment: BULLISH (70%)
Recommendation: Trump announcement likely by deadline
Confidence: HIGH
Sources: 15 web articles, 40 X posts

Outcome: Yes, Trump announces
├─ Grok Est: 72%
├─ Market: 65%
├─ Delta: +7% (BUY)
└─ Reason: Recent pattern suggests announcement cycle active
```

### Example 2: Geopolitical Event

**User Input:**
- Market: "Russia captures [city] by March 1?"
- Outcomes: Yes (80% market) vs No (20% market)

**Backend Flow:**
1. **Foundational**
   - Web search: Latest military movements, logistics reports
   - X search: Military analysts discussing supply lines
   - Result: "Current advance rate 2.5 km/day, 150 km remaining = 60 days needed"

2. **Historical**
   - Questions: "Historical base rate of capturing territory on this timeline?"
   - "What are logistical constraints?"
   - Grok Answer: "Only succeeded 35% of attempts with current supply situation"

3. **Prominent Figures**
   - Analyst A: "Supply lines overstretched, 40% chance" (BEARISH)
   - Analyst B: "Recent breakthrough, 75% chance" (BULLISH)
   - Result: Mixed sentiment, slight bullish bias

4. **Synthesis**
   - Market says: 80% Yes
   - Historical precedent says: 35% Yes
   - Sentiment says: 55% Yes (mixed)
   - **Recommendation: SELL** (market overvaluing Yes at 80%)

---

## 🚀 Performance & Optimization

### Parallel Execution

All 3 analysis pipelines run **concurrently**, not sequentially:
```python
# All start at same time, total time = max(foundational, historical, x_sentiment)
# Not: foundational + historical + x_sentiment time added together

asyncio.gather(
    run_foundational_in_thread(),
    run_historical(),
    run_prominent_figures()
)
```

**Typical Timing:**
- Foundational: 8-12 seconds (web/X search)
- Historical: 5-8 seconds (Grok inference)
- Prominent Figures: 6-10 seconds (tweet fetch + analysis)
- **Total: ~12 seconds** (parallel, not 25+ seconds sequential)

### Caching Strategy

**Cache Key Generation:**
```python
cache_key = hash(market_title + sorted(outcome_names) + market_url)
# Stable regardless of price/volume changes
# Same market = same cache if analyzed within 30 minutes
```

**Cache Benefits:**
- Reduces Grok API calls (and costs)
- Instant results for repeated queries
- Can be toggled with `force_refresh=true`

### Memory Management

- In-memory cache (upgradeable to Redis)
- Thread pool with 4 workers for CPU-bound operations
- Connection pooling for HTTP requests
- Streaming responses (don't buffer entire result)

---

## 🔍 Debugging & Troubleshooting

### Extension Not Loading

1. Check manifest.json syntax
2. Verify chrome-extension folder exists
3. Ensure Developer mode is ON in chrome://extensions
4. Check browser console (F12) for errors

### No Market Data Detected

1. Verify DOM selectors in useMarketData.tsx
2. Polymarket may have changed HTML structure
3. Check browser console for scraping errors
4. Try manual selection in extension UI

### Analysis Not Streaming

1. Verify backend is running: `curl http://localhost:8000/health`
2. Check backend logs for errors
3. Verify CORS is enabled (should be in prediction_server.py)
4. Check browser Network tab for SSE connection

### Grok API Errors

1. Verify GROK_API_KEY is set correctly
2. Check API rate limits (xAI dashboard)
3. Ensure model name is correct ("grok-4-latest")
4. Review Grok API documentation: https://docs.x.ai

### X/Twitter API Issues

1. Verify X credentials in .env
2. Check X API rate limits
3. Ensure tweet collection is within API bounds
4. Review X API documentation

---

## 📈 Data Sources

### Foundational Data Sources

- **Web Search** - General news, articles, official reports
- **X/Twitter Search** - Real-time discussions, expert takes
- **Market Data** - Polymarket prices, Kalshi odds (if integrated)

### Historical Research Sources

- **Grok LLM** - Historical precedents, reference classes
- **Quantitative Analysis** - Base rates, logistics calculations
- **Expert Domain Knowledge** - Military, political, economic

### Prominent Figures

Currently configured for military/geopolitical events:
- Military analysts and strategists
- Defense contractors
- Geopolitical commentators
- News organizations

Can be customized in `prominent_figure_service.py`

---

## 🧬 Code Organization

```
backend/
├── prediction_server.py         # Main FastAPI app
├── foundational_data.py         # Web/X search intelligence
├── historical_research_live.py  # Historical Q&A with Grok
├── analyze_prominent_figure_tweets.py  # X sentiment analysis
├── prominent_figure_service.py  # Figure list + categorization
├── historical_research.py       # Question generation
├── grok_pipeline/
│   ├── grok_client.py          # xAI SDK wrapper
│   ├── schemas.py              # Data models
│   ├── orchestrator.py         # (unused, for future expansion)
│   ├── example_events.py       # Example market definitions
│   └── agentgrok.py           # (demo code)
├── auth/
│   └── utils.py               # API client initialization
├── .env                       # Credentials (not in git)
└── requirements.txt           # Python dependencies

chrome-extension/
├── manifest.json              # MV3 config
├── src/
│   ├── background.ts          # Service worker
│   ├── content/
│   │   ├── index.tsx          # Entry point
│   │   ├── App.tsx            # Main component (800+ lines)
│   │   ├── hooks/
│   │   │   ├── useMarketData.tsx   # DOM scraping
│   │   │   ├── useAnalysis.tsx     # SSE + state management
│   │   │   └── useCache.tsx
│   │   └── styles/
│   └── [UI components]
├── package.json
├── tsconfig.json
└── tailwind.config.js
```

---

## 🎓 Key Concepts

### 1. Reference Class Forecasting

Instead of guessing, we ask: "What does history tell us about this type of event?"

- **Base Rate** - "How often does this happen?"
- **Reference Class** - "What similar events can we compare to?"
- **Key Variables** - "What factors matter most?"

### 2. Agentic Tools

Grok doesn't just generate text; it can use tools:
```python
tools=[web_search, x_search]
# Grok decides WHEN and HOW to use these tools
# Results fed back into reasoning loop
```

### 3. Alpha Signals

Trading advantage comes from non-public information:
- Recent military movements from analysis
- Expert sentiment shift on X
- Historical precedents overlooked by market

### 4. Probability Calibration

```
Market probability = 75% (from price)
Grok probability = 82% (from analysis)
Delta = +7% (market undervaluing Yes)
→ Recommendation: BUY
```

---

## 🚦 Known Limitations

1. **Polymarket DOM Changes** - Selectors may break if Polymarket updates HTML
2. **API Rate Limits** - X API and Grok API have rate limits
3. **Context Length** - Very long market discussions may exceed token limits
4. **Data Freshness** - Analysis cached for 30 minutes (may miss breaking news)
5. **Accuracy** - Grok estimates are probabilistic, not certainties

---

## 🔮 Future Enhancements

- [ ] Redis caching for multi-instance deployments
- [ ] Persistent result storage (PostgreSQL)
- [ ] Backtesting against historical markets
- [ ] A/B testing different analysis strategies
- [ ] Integration with more prediction markets (Kalshi, Manifold)
- [ ] Custom prompt engineering per event type
- [ ] Real-time market impact monitoring
- [ ] Discord/Telegram alerting for major shifts

---

## 📝 License

This project is for educational and experimental purposes. Use responsibly and in compliance with xAI, X, and prediction market terms of service.

---

## 🤝 Contributing

To extend this system:

1. **Add new analysis pipeline** - Create new module in backend
2. **Add data source** - Integrate new API in foundational_data.py
3. **Customize prompt** - Adjust system prompts in individual modules
4. **Add market support** - Extend chrome extension selectors

---

**Built with Grok AI, FastAPI, React, and Tailwind CSS** 🚀
