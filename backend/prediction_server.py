"""
Prediction Server - FastAPI with SSE streaming for Grokedge Chrome Extension

Thin API layer over foundational_data.py and historical_research_live.py
with caching to avoid burning through Grok API credits.

PARALLELIZED: Foundational, Historical, and Prominent Figures Sentiment analyses run concurrently.
"""

# Standard library
import json
import hashlib
import asyncio
import os
import logging
import sys
import time
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, AsyncGenerator
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

# Third-party
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

# Local - core services
from foundational_data import FoundationalDataService, FoundationalData
from historical_research_live import HistoricalResearchClient, HistoricalAnalysisResponse
from prominent_figure_service import generate_prominent_figures
from analyze_prominent_figure_tweets import analyze_tweets_for_event, fetch_tweets_from_figures

# Load environment variables
load_dotenv(Path(__file__).parent / ".env")

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("prediction_server")

# Thread pool for sync operations
executor = ThreadPoolExecutor(max_workers=4)

# --- Pydantic Models ---

class OutcomeData(BaseModel):
    """Single outcome from Polymarket"""
    model_config = {"populate_by_name": True}
    
    name: str
    probability: Optional[float] = None
    yesPrice: Optional[float] = None
    noPrice: Optional[float] = None
    volume_usd: Optional[float] = Field(None, alias="volume")


class AnalyzeRequest(BaseModel):
    """Request payload from Chrome extension"""
    market_id: Optional[str] = None
    market_title: str
    market_url: Optional[str] = None  # Polymarket URL for searching comments
    total_volume_usd: Optional[float] = None
    outcomes: List[OutcomeData]
    force_refresh: bool = False


class GrokOutcomeEstimate(BaseModel):
    """Grok's probability estimate for a specific outcome"""
    outcome_name: str
    grok_probability: float  # Grok's estimate (0-100)
    market_probability: float  # Current market price (0-100)
    delta: float  # grok_probability - market_probability (positive = undervalued)
    reasoning: str
    recommendation: str  # "BUY", "SELL", or "HOLD"


class CachedResult(BaseModel):
    """Cached analysis result"""
    cache_key: str
    created_at: str
    expires_at: str
    market_title: str
    foundational_data: Optional[Dict[str, Any]] = None
    historical_analysis: Optional[Dict[str, Any]] = None
    prominent_figures_analysis: Optional[Dict[str, Any]] = None  # Prominent Figures Sentiment from prominent figures
    outcome_estimates: Optional[List[Dict[str, Any]]] = None  # Per-outcome Grok estimates


# --- Cache ---

CACHE_TTL_MINUTES = 30
_cache: Dict[str, CachedResult] = {}


def generate_cache_key(request: AnalyzeRequest) -> str:
    """
    Generate deterministic cache key from request.
    
    IMPORTANT: Only use STABLE identifiers - NOT prices/volumes which fluctuate!
    This ensures the same market returns the same cache key across page loads.
    """
    # Use only outcome names (sorted), not their volatile prices/volumes
    sorted_outcome_names = sorted([o.name.strip().lower() for o in request.outcomes])
    
    payload = {
        # Prefer market_id if available (most stable), fallback to title
        "market_id": request.market_id or request.market_title,
        "outcome_names": sorted_outcome_names,
    }
    raw = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def get_cached(key: str) -> Optional[CachedResult]:
    """Get cached result if not expired"""
    if key not in _cache:
        return None
    cached = _cache[key]
    if datetime.fromisoformat(cached.expires_at) < datetime.now():
        del _cache[key]
        return None
    return cached


def set_cached(key: str, result: CachedResult):
    """Store result in cache"""
    _cache[key] = result


# --- FastAPI App ---

app = FastAPI(
    title="GrokEdge Prediction Server",
    description="Streaming Grok analysis for Polymarket outcomes (Parallelized)",
    version="0.2.0",
)

# Allow CORS for local extension development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    """Health check endpoint"""
    logger.info("Health check requested")
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests"""
    logger.info(f"📥 {request.method} {request.url.path} from {request.client.host if request.client else 'unknown'}")
    response = await call_next(request)
    logger.info(f"📤 {request.method} {request.url.path} -> {response.status_code}")
    return response


@app.get("/analyze/{cache_key}")
async def get_cached_analysis(cache_key: str):
    """Retrieve cached analysis result"""
    logger.info(f"🔍 Cache lookup for key: {cache_key}")
    cached = get_cached(cache_key)
    if not cached:
        logger.warning(f"❌ Cache miss for key: {cache_key}")
        raise HTTPException(status_code=404, detail="Cache miss or expired")
    logger.info(f"✅ Cache hit for key: {cache_key}")
    return cached


@app.post("/analyze")
async def analyze_market(request: AnalyzeRequest, http_request: Request):
    """
    Analyze market outcomes using Grok.
    Returns Server-Sent Events stream with progress updates.
    
    PARALLELIZED: Foundational and Historical analyses run concurrently.
    Supports cancellation when client disconnects.
    """
    logger.info(f"🎯 Analyze request received:")
    logger.info(f"   Market: {request.market_title}")
    logger.info(f"   Outcomes: {len(request.outcomes)}")
    logger.info(f"   Total Volume: ${request.total_volume_usd}")
    logger.info(f"   Force Refresh: {request.force_refresh}")
    
    cache_key = generate_cache_key(request)
    logger.info(f"   Cache Key: {cache_key}")

    # Check cache unless force refresh
    if not request.force_refresh:
        cached = get_cached(cache_key)
        if cached:
            logger.info(f"⚡ Returning cached result for {cache_key}")
            async def cached_stream():
                yield f"event: cached\ndata: {json.dumps({'cache_key': cache_key})}\n\n"
                yield f"event: result\ndata: {json.dumps(cached.model_dump())}\n\n"
                yield "event: done\ndata: {}\n\n"
            return StreamingResponse(
                cached_stream(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Cache-Key": cache_key,
                },
            )

    logger.info(f"🚀 Starting PARALLEL analysis stream for {cache_key}")
    return StreamingResponse(
        run_parallel_analysis_stream(request, cache_key, http_request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Cache-Key": cache_key,
        },
    )


def generate_outcome_estimates(
    outcomes: List[OutcomeData],
    foundational_data: Optional[Dict[str, Any]],
    historical_analysis: Optional[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Generate per-outcome probability estimates from analysis results.
    
    For each outcome, we compare Grok's estimate to market price and determine:
    - delta (grok - market): positive = undervalued, negative = overvalued
    - recommendation: BUY if delta > 5%, SELL if delta < -5%, else HOLD
    """
    estimates = []
    
    # Get the overall probability from historical analysis
    overall_prob = None
    overall_sentiment = None
    recommendation_text = ""
    
    if historical_analysis:
        overall_prob = historical_analysis.get("probability_estimate")
        overall_sentiment = historical_analysis.get("overall_sentiment")
        recommendation_text = historical_analysis.get("recommendation", "")
    
    # Get any odds data from foundational analysis
    foundational_odds = {}
    if foundational_data and "current_odds" in foundational_data:
        for odds in foundational_data.get("current_odds", []):
            # Defensive: skip if odds is not a dict (sometimes API returns strings)
            if not isinstance(odds, dict):
                logger.warning(f"⚠️ Skipping non-dict odds item: {type(odds)}")
                continue
            # Try to match by market title
            market_title = odds.get("market_title", "").lower()
            foundational_odds[market_title] = odds
    
    # For each outcome, generate an estimate
    for outcome in outcomes:
        market_prob = outcome.probability or (outcome.yesPrice * 100 if outcome.yesPrice else None) or 50
        
        # Try to find specific estimate from foundational data
        grok_prob = None
        reasoning = ""
        
        # Check if foundational data has specific outcome odds
        outcome_name_lower = outcome.name.lower().strip()
        for title, odds in foundational_odds.items():
            if outcome_name_lower in title or title in outcome_name_lower:
                grok_prob = odds.get("yes_probability")
                break
        
        # If no specific odds, use overall probability estimate for primary outcome
        # For multi-outcome markets, distribute based on sentiment
        if grok_prob is None and overall_prob is not None:
            if len(outcomes) == 1:
                # Single outcome - use overall probability directly
                grok_prob = overall_prob
                reasoning = f"Based on historical analysis (sentiment: {overall_sentiment})"
            elif len(outcomes) == 2:
                # Binary market (Yes/No or similar)
                # Typically the first outcome is the "positive" case
                idx = outcomes.index(outcome) if outcome in outcomes else 0
                if idx == 0:
                    grok_prob = overall_prob
                else:
                    grok_prob = 100 - overall_prob
                reasoning = f"Binary market estimate based on {overall_sentiment} sentiment"
            else:
                # Multi-outcome market - use market probability as baseline
                # Adjust based on sentiment direction
                adjustment = 0
                if overall_sentiment == "bullish":
                    # Favor earlier/primary outcomes
                    idx = outcomes.index(outcome) if outcome in outcomes else len(outcomes)
                    adjustment = max(0, 10 - idx * 3)
                elif overall_sentiment == "bearish":
                    # Favor later outcomes
                    idx = outcomes.index(outcome) if outcome in outcomes else 0
                    adjustment = max(0, idx * 2 - 5)
                
                grok_prob = min(95, max(5, market_prob + adjustment))
                reasoning = f"Multi-outcome estimate (sentiment: {overall_sentiment})"
        
        if grok_prob is None:
            grok_prob = market_prob  # Fallback to market price
            reasoning = "Using market price as estimate (no specific data)"
        
        # Calculate delta
        delta = round(grok_prob - market_prob, 1)
        
        # Determine recommendation
        if delta > 5:
            rec = "BUY"
            reasoning += f". Undervalued by {delta}% - consider buying YES"
        elif delta < -5:
            rec = "SELL"
            reasoning += f". Overvalued by {abs(delta)}% - consider selling YES or buying NO"
        else:
            rec = "HOLD"
            reasoning += f". Fair value (delta: {delta}%)"
        
        # Add recommendation context from historical if available
        if recommendation_text and outcome.name.lower() in recommendation_text.lower():
            reasoning = recommendation_text
        
        estimates.append({
            "outcome_name": outcome.name,
            "grok_probability": round(grok_prob, 1),
            "market_probability": round(market_prob, 1),
            "delta": delta,
            "reasoning": reasoning,
            "recommendation": rec,
        })
    
    # Sort by absolute delta (biggest opportunity first)
    estimates.sort(key=lambda x: abs(x["delta"]), reverse=True)
    
    return estimates


# Sentinel to signal task completion
class TaskComplete:
    def __init__(self, task_name: str, result: Any = None, error: str = None):
        self.task_name = task_name
        self.result = result
        self.error = error


async def run_parallel_analysis_stream(
    request: AnalyzeRequest, cache_key: str, http_request: Request
) -> AsyncGenerator[str, None]:
    """
    Generator that yields SSE events during PARALLEL Grok analysis.
    All three analyses (foundational, historical, Prominent Figures Sentiment) run concurrently.
    Supports cancellation when client disconnects.
    """
    start_time = time.time()
    logger.info(f"📊 [Parallel] Starting parallel analysis for {cache_key}")
    
    # Track running tasks for cancellation
    running_tasks: List[asyncio.Task] = []
    cancelled = False
    
    yield f"event: status\ndata: {json.dumps({'stage': 'init', 'message': 'Starting parallel analysis...', 'cache_key': cache_key, 'parallel': True})}\n\n"

    # Build context prompt from market data
    outcomes_text = "\n".join([
        f"- {o.name}: {o.probability}% (Yes ${o.yesPrice}, No ${o.noPrice}, Vol ${o.volume_usd or 'N/A'})"
        for o in request.outcomes
    ])
    
    # Build the list of valid outcome names for strict selection
    valid_outcomes_list = [o.name for o in request.outcomes]
    valid_outcomes_json = json.dumps(valid_outcomes_list)
    
    # Include Polymarket URL if available for searching user comments
    market_url_context = ""
    if request.market_url:
        market_url_context = f"\nPolymarket URL: {request.market_url}\n(Search this URL on X/Twitter to find user comments and positions on this market)"
    
    event_query = f"""
Market: {request.market_title}
Total Volume: ${request.total_volume_usd or 'Unknown'}
{market_url_context}

CURRENT OUTCOMES (ONLY THESE ARE VALID):
{outcomes_text}

CRITICAL INSTRUCTION: You must ONLY analyze and make recommendations for the outcomes listed above.
Do NOT suggest or recommend any outcome that is not in this exact list: {valid_outcomes_json}

Analyze this prediction market. For EACH outcome listed above, provide:
1. Your probability estimate (what you think the true probability should be)
2. Whether the market is overpriced or underpriced
3. BUY/SELL/HOLD recommendation based on the delta between your estimate and market price

Search for recent news, X/Twitter sentiment (including the Polymarket URL if provided), and any relevant information.
"""

    # Shared queue for events from both analyses
    event_queue: asyncio.Queue = asyncio.Queue()
    
    # Results storage
    results = {
        "foundational": None,
        "historical": None,
        "prominent_figures": None,  # Prominent Figures Sentiment from prominent figures
        "outcome_estimates": None,  # Per-outcome Grok estimates
    }
    
    async def run_foundational_in_thread():
        """Run sync foundational analysis in thread, push events to queue"""
        logger.info(f"🔬 [Foundational] Starting in thread...")
        foundational_start = time.time()
        
        def sync_foundational():
            """Sync function that runs in thread pool"""
            events = []
            result_data = None
            event_count = 0
            try:
                logger.info(f"🔬 [Foundational] Creating service...")
                service = FoundationalDataService()
                logger.info(f"🔬 [Foundational] Starting agentic search...")
                
                for event in service._run_agentic_search(event_query, timeout_seconds=180):
                    event_count += 1
                    events.append(("foundational", event))
                    
                    # Log each event for debugging
                    event_type = event.get("type", "unknown")
                    if event_type in ["log", "tool_call", "error"]:
                        logger.debug(f"🔬 [Foundational] Event #{event_count}: {event_type} - {event.get('message', event.get('tool', event.get('error', '')))[:80]}")
                    
                    # Extract result from content event
                    if event["type"] == "content":
                        content = event["content"]
                        logger.info(f"🔬 [Foundational] Got content ({len(content)} chars)")
                        try:
                            clean = content.strip()
                            if clean.startswith("```json"):
                                clean = clean.split("```json", 1)[1]
                            if clean.endswith("```"):
                                clean = clean.rsplit("```", 1)[0]
                            clean = clean.strip()
                            
                            start = clean.find("{")
                            end = clean.rfind("}") + 1
                            if start >= 0 and end > start:
                                data = json.loads(clean[start:end])
                                data["event_query"] = request.market_title
                                data["generated_at"] = datetime.now().isoformat()
                                result_data = data
                                logger.info(f"✅ [Foundational] Parsed result successfully")
                            else:
                                logger.warning(f"⚠️ [Foundational] No JSON object found in content")
                        except Exception as parse_err:
                            logger.error(f"❌ [Foundational] Parse error: {parse_err}")
                            events.append(("foundational", {"type": "error", "error": str(parse_err)}))
                    
                    elif event["type"] == "error":
                        logger.error(f"❌ [Foundational] Error event: {event.get('error', 'unknown')}")
                            
            except Exception as e:
                logger.error(f"❌ [Foundational] Exception in sync_foundational: {e}", exc_info=True)
                events.append(("foundational", {"type": "error", "error": str(e)}))
            
            logger.info(f"🔬 [Foundational] Sync function complete: {event_count} events, result={'yes' if result_data else 'no'}")
            return events, result_data
        
        # Run in thread pool with a timeout wrapper
        try:
            loop = asyncio.get_event_loop()
            logger.info(f"🔬 [Foundational] Running in executor...")
            
            # Use asyncio.wait_for to add a global timeout
            events, result_data = await asyncio.wait_for(
                loop.run_in_executor(executor, sync_foundational),
                timeout=200  # 200 second global timeout
            )
            
            elapsed = time.time() - foundational_start
            logger.info(f"🔬 [Foundational] Executor returned: {len(events)} events in {elapsed:.1f}s")
            
        except asyncio.TimeoutError:
            elapsed = time.time() - foundational_start
            logger.error(f"❌ [Foundational] GLOBAL TIMEOUT after {elapsed:.1f}s")
            events = [("foundational", {"type": "error", "error": f"Foundational analysis timed out after {elapsed:.1f}s"})]
            result_data = None
        except Exception as e:
            logger.error(f"❌ [Foundational] Executor error: {e}", exc_info=True)
            events = [("foundational", {"type": "error", "error": str(e)})]
            result_data = None
        
        # Push all events to queue
        for source, event in events:
            await event_queue.put((source, event))
        
        # Signal completion
        results["foundational"] = result_data
        await event_queue.put(TaskComplete("foundational", result_data))
        elapsed = time.time() - foundational_start
        logger.info(f"✅ [Foundational] Complete in {elapsed:.1f}s (result={'success' if result_data else 'failed'})")
    
    async def run_historical():
        """Run async historical analysis, push events to queue"""
        logger.info(f"📜 [Historical] Starting...")
        
        try:
            await event_queue.put(("historical", {"type": "status", "message": "Starting historical research..."}))
            
            async with HistoricalResearchClient() as client:
                result = await client.research_event(
                    event_description=request.market_title,
                    event_id=cache_key,
                )
                result_data = result.model_dump()
                results["historical"] = result_data
                
                await event_queue.put(("historical", {
                    "type": "complete",
                    "sentiment": result.overall_sentiment.value,
                    "probability": result.probability_estimate,
                    "confidence": result.overall_confidence.value,
                }))
                
        except Exception as e:
            logger.error(f"❌ [Historical] Error: {e}", exc_info=True)
            await event_queue.put(("historical", {"type": "error", "error": str(e)}))
        
        await event_queue.put(TaskComplete("historical", results["historical"]))
        logger.info(f"✅ [Historical] Complete")

    async def run_prominent_figures():
        """
        Run Prominent Figures Sentiment analysis from prominent figures.
        Full pipeline (matching app.py/Streamlit):
        1. Generate prominent figures list using Grok (async)
        2. Fetch tweets from X API (sync, run in thread)
        3. Analyze tweets for alpha signals (async)
        
        Runs in parallel with foundational and historical analyses.
        All async calls stay in the main event loop to avoid nested loop issues.
        """
        logger.info(f"📱 [Prominent Figures Sentiment] Starting prominent figures analysis pipeline...")
        x_start = time.time()
        temp_file = None
        
        try:
            # Step 1: Generate prominent figures using Grok (async - stays in main loop)
            await event_queue.put(("x_sentiment", {"type": "status", "message": "🔍 Identifying prominent figures with Grok..."}))
            logger.info(f"📱 [Prominent Figures Sentiment] Step 1: Generating prominent figures for '{request.market_title}'")
            
            # Call async function directly - no nested event loop!
            figures_data = await generate_prominent_figures(request.market_title)
            
            num_figures = len(figures_data.get("prominent_figures", []))
            figures = figures_data.get("prominent_figures", [])
            logger.info(f"📱 [Prominent Figures Sentiment] Generated {num_figures} prominent figures")
            await event_queue.put(("x_sentiment", {"type": "status", "message": f"✅ Identified {num_figures} experts"}))
            
            if num_figures == 0:
                logger.warning(f"📱 [Prominent Figures Sentiment] No figures generated, skipping tweet analysis")
                await event_queue.put(("x_sentiment", {"type": "status", "message": "No experts found, skipping..."}))
                results["prominent_figures"] = {"analysis": None, "figures_meta": figures_data}
                await event_queue.put(TaskComplete("x_sentiment", results.get("prominent_figures")))
                return
            
            # Extract location from market title
            title_lower = request.market_title.lower()
            location = "Target"
            location_variants = []
            
            if "pokrovsk" in title_lower:
                location = "Pokrovsk"
                location_variants = ["Pokrovs'k", "Pokrovske", "Myrnohrad"]
            elif "kupiansk" in title_lower or "kupyansk" in title_lower:
                location = "Kupiansk"
                location_variants = ["Kupyansk", "Kupjansk"]
            elif "kherson" in title_lower:
                location = "Kherson"
                location_variants = ["Херсон"]
            elif "bakhmut" in title_lower:
                location = "Bakhmut"
                location_variants = ["Артемівськ", "Artemivsk"]
            else:
                # Use first significant word as location fallback
                words = [w for w in request.market_title.split() if len(w) > 4]
                if words:
                    location = words[0]
            
            # Step 2: Fetch tweets (sync blocking - run in thread)
            await event_queue.put(("x_sentiment", {"type": "status", "message": f"📡 Fetching tweets from {num_figures} experts..."}))
            logger.info(f"📱 [Prominent Figures Sentiment] Step 2: Fetching tweets (location={location})")
            
            all_keywords = [location] + location_variants
            tweets_by_figure = await asyncio.to_thread(
                fetch_tweets_from_figures,
                figures=figures,
                location_keywords=all_keywords,
                days_back=7,
                max_tweets_per_figure=20
            )
            
            total_tweets = sum(len(tweets) for tweets in tweets_by_figure.values())
            logger.info(f"📱 [Prominent Figures Sentiment] Fetched {total_tweets} tweets from {len(tweets_by_figure)} figures")
            await event_queue.put(("x_sentiment", {"type": "status", "message": f"📊 Fetched {total_tweets} tweets, analyzing..."}))
            
            if total_tweets == 0:
                logger.warning(f"📱 [Prominent Figures Sentiment] No tweets found, returning empty result")
                results["prominent_figures"] = {
                    "analysis": {"summary": {"total_tweets_analyzed": 0, "alpha_count": 0}},
                    "figures_meta": figures_data
                }
                await event_queue.put(("x_sentiment", {
                    "type": "complete",
                    "sentiment": "unknown",
                    "alpha_count": 0,
                    "signal_count": 0,
                    "num_figures": num_figures,
                }))
                await event_queue.put(TaskComplete("x_sentiment", results.get("prominent_figures")))
                return
            
            # Step 3: Save to temp file and analyze (need file for analyze_tweets_for_event)
            temp_file = f"/tmp/temp_figures_{cache_key}_{int(time.time())}.json"
            with open(temp_file, "w") as f:
                json.dump(figures_data, f, indent=2)
            
            deadline = figures_data.get("prediction_event", {}).get("deadline", "2025-12-31")
            
            # Call async analysis directly - stays in main event loop!
            logger.info(f"📱 [Prominent Figures Sentiment] Step 3: Analyzing tweets with Grok")
            response = await analyze_tweets_for_event(
                prominent_figures_file=temp_file,
                event_description=request.market_title,
                location=location,
                location_variants=location_variants,
                deadline=deadline,
                days_back=7,
                max_tweets=20
            )
            
            # Store both the analysis results and the figures metadata
            results["prominent_figures"] = {
                "analysis": response,
                "figures_meta": figures_data
            }
            
            # Extract key info for SSE
            summary = response.get("summary", {})
            await event_queue.put(("x_sentiment", {
                "type": "complete",
                "sentiment": summary.get("sentiment_trend", "unknown"),
                "alpha_count": summary.get("alpha_count", 0),
                "signal_count": summary.get("total_tweets_analyzed", 0),
                "num_figures": num_figures,
            }))
            
            elapsed = time.time() - x_start
            logger.info(f"✅ [Prominent Figures Sentiment] Complete in {elapsed:.1f}s: {num_figures} figures, {summary.get('alpha_count', 0)} alpha signals")
                
        except Exception as e:
            logger.error(f"❌ [Prominent Figures Sentiment] Error: {e}", exc_info=True)
            await event_queue.put(("x_sentiment", {"type": "error", "error": str(e)}))
        
        finally:
            # Clean up temp file
            if temp_file and os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                    logger.info(f"📱 [Prominent Figures Sentiment] Cleaned up temp file: {temp_file}")
                except Exception as cleanup_err:
                    logger.warning(f"📱 [Prominent Figures Sentiment] Failed to clean up temp file: {cleanup_err}")
        
        await event_queue.put(TaskComplete("x_sentiment", results.get("prominent_figures")))
        logger.info(f"✅ [Prominent Figures Sentiment] Task complete")

    # Start all three tasks concurrently
    yield f"event: status\ndata: {json.dumps({'stage': 'parallel_start', 'message': 'Starting foundational, historical, and Prominent Figures Sentiment analysis in parallel...'})}\n\n"
    
    foundational_task = asyncio.create_task(run_foundational_in_thread())
    historical_task = asyncio.create_task(run_historical())
    x_sentiment_task = asyncio.create_task(run_prominent_figures())
    running_tasks = [foundational_task, historical_task, x_sentiment_task]
    
    # Track completion
    tasks_complete = {"foundational": False, "historical": False, "x_sentiment": False}
    
    # Stream events as they arrive from all analyses
    try:
        while not all(tasks_complete.values()):
            # Check if client disconnected
            if await http_request.is_disconnected():
                logger.warning(f"⚠️ [Parallel] Client disconnected! Cancelling tasks for {cache_key}")
                cancelled = True
                for task in running_tasks:
                    if not task.done():
                        task.cancel()
                yield f"event: cancelled\ndata: {json.dumps({'message': 'Analysis cancelled by client'})}\n\n"
                return
            
            try:
                item = await asyncio.wait_for(event_queue.get(), timeout=0.5)
                
                if isinstance(item, TaskComplete):
                    tasks_complete[item.task_name] = True
                    elapsed = time.time() - start_time
                    yield f"event: task_complete\ndata: {json.dumps({'task': item.task_name, 'elapsed_seconds': round(elapsed, 1)})}\n\n"
                    logger.info(f"🏁 [{item.task_name}] Task complete after {elapsed:.1f}s")
                    continue
                
                source, event = item
                event_type = event.get("type", "unknown")
                
                # Format SSE based on event type and source
                if event_type == "log":
                    yield f"event: log\ndata: {json.dumps({'source': source, 'message': event['message']})}\n\n"
                elif event_type == "tool_call":
                    yield f"event: tool_call\ndata: {json.dumps({'source': source, 'tool': event['tool'], 'args': event.get('args', '')[:200]})}\n\n"
                elif event_type == "thinking":
                    yield f"event: thinking\ndata: {json.dumps({'source': source, 'tokens': event['tokens']})}\n\n"
                elif event_type == "citations":
                    cites = event.get("citations", [])
                    if cites:
                        yield f"event: citations\ndata: {json.dumps({'source': source, 'urls': [str(c) for c in cites[:10]]})}\n\n"
                elif event_type == "status":
                    yield f"event: status\ndata: {json.dumps({'source': source, 'stage': source, 'message': event['message']})}\n\n"
                elif event_type == "complete":
                    if source == "historical":
                        yield f"event: historical_complete\ndata: {json.dumps({'sentiment': event['sentiment'], 'probability': event['probability'], 'confidence': event['confidence']})}\n\n"
                    elif source == "x_sentiment":
                        yield f"event: x_sentiment_complete\ndata: {json.dumps({'sentiment': event.get('sentiment', 'unknown'), 'alpha_count': event.get('alpha_count', 0), 'signal_count': event.get('signal_count', 0)})}\n\n"
                elif event_type == "error":
                    yield f"event: error\ndata: {json.dumps({'source': source, 'stage': source, 'error': event['error']})}\n\n"
                    
            except asyncio.TimeoutError:
                # No events, loop continues to check for disconnect
                continue
                
    except asyncio.CancelledError:
        logger.warning(f"⚠️ [Parallel] Stream cancelled for {cache_key}")
        for task in running_tasks:
            if not task.done():
                task.cancel()
        return
    
    # Wait for all three tasks to fully complete (should be done already)
    await asyncio.gather(foundational_task, historical_task, x_sentiment_task, return_exceptions=True)
    
    # Calculate total time
    total_time = time.time() - start_time
    logger.info(f"⏱️ [Parallel] Total analysis time: {total_time:.1f}s")
    
    # Generate per-outcome estimates from foundational and historical data
    outcome_estimates = generate_outcome_estimates(
        request.outcomes, 
        results["foundational"], 
        results["historical"]
    )
    results["outcome_estimates"] = outcome_estimates
    if outcome_estimates:
        logger.info(f"📊 Generated {len(outcome_estimates)} outcome estimates")
        yield f"event: outcome_estimates\ndata: {json.dumps({'estimates': outcome_estimates})}\n\n"
    
    # Cache and return final result
    now = datetime.now()
    cached_result = CachedResult(
        cache_key=cache_key,
        created_at=now.isoformat(),
        expires_at=(now + timedelta(minutes=CACHE_TTL_MINUTES)).isoformat(),
        market_title=request.market_title,
        foundational_data=results["foundational"],
        historical_analysis=results["historical"],
        prominent_figures_analysis=results["prominent_figures"],
        outcome_estimates=outcome_estimates,
    )
    set_cached(cache_key, cached_result)

    yield f"event: result\ndata: {json.dumps({**cached_result.model_dump(), 'total_time_seconds': round(total_time, 1)})}\n\n"
    yield "event: done\ndata: {}\n\n"
    logger.info(f"🏁 [Parallel] Stream ended for {cache_key} in {total_time:.1f}s")


# --- Main ---

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", 8000))
    print(f"🚀 Starting GrokEdge Prediction Server on port {port}")
    print(f"📡 SSE endpoint: POST http://localhost:{port}/analyze")
    print(f"💾 Cache TTL: {CACHE_TTL_MINUTES} minutes")
    print(f"⚡ PARALLELIZED: Foundational + Historical run concurrently")
    
    uvicorn.run(app, host="0.0.0.0", port=port)
