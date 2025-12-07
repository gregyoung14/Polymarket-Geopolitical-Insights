"""
Foundational Data Service

Generates comprehensive event data (Facts, Odds, Arbitrage, Charts) 
using the xAI SDK with agentic tools (Web Search, X Search).
"""

import json
import os
import asyncio
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path
from pydantic import BaseModel, Field

# Load .env file
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / '.env'
    load_dotenv(env_path)
except ImportError:
    pass

# xAI SDK Imports
try:
    from xai_sdk import Client
    from xai_sdk.chat import system, user
    from xai_sdk.tools import web_search, x_search
except ImportError:
    raise ImportError("Please install xai_sdk: pip install xai-sdk")


# --- Data Models ---

class MarketOdds(BaseModel):
    """Odds data for a specific prediction market platform"""
    platform: str = Field(..., description="Platform name (e.g. Polymarket, Kalshi)")
    market_title: str
    yes_price: float = Field(..., description="Price for Yes share (0.00-1.00)")
    no_price: float = Field(..., description="Price for No share (0.00-1.00)")
    yes_probability: float = Field(..., description="Implied probability of Yes (0-100)")
    no_probability: float = Field(..., description="Implied probability of No (0-100)")
    volume_usd: Optional[float] = None
    total_series_volume_usd: Optional[float] = None
    resolution_criteria: Optional[str] = None
    last_updated: str = Field(..., description="ISO date string")


class ArbitrageOpportunity(BaseModel):
    """Arbitrage or hedging opportunity details"""
    description: str
    estimated_edge: str = Field(..., description="Estimated profit margin (e.g. '3-5%')")
    recommended_action: str = Field(..., description="Specific action to take")


class ChartDataset(BaseModel):
    """Chart.js dataset structure"""
    label: Optional[str] = None
    data: List[float]
    backgroundColor: List[str]
    borderColor: Optional[List[str]] = None
    borderWidth: Optional[int] = 1


class ChartData(BaseModel):
    """Chart.js data structure"""
    labels: List[str]
    datasets: List[ChartDataset]


class ChartOptions(BaseModel):
    """Chart.js options structure"""
    responsive: bool = True
    plugins: Dict[str, Any] = {}


class ProbabilityVisualization(BaseModel):
    """Complete chart configuration for frontend rendering"""
    chart_type: str = Field(..., description="pie, bar, line, etc.")
    title: str
    data: ChartData
    options: ChartOptions


class FoundationalData(BaseModel):
    """Master container for all event data"""
    event_query: str
    generated_at: str
    facts_summary: str
    current_odds: List[MarketOdds]
    arbitrage_opportunities: List[ArbitrageOpportunity]
    probability_visualization: ProbabilityVisualization
    sources: List[str] = Field(default_factory=list, description="List of X post URLs used as sources")


# --- Service ---

FOUNDATIONAL_SYSTEM_PROMPT = """You are a prediction market data aggregator and analyst. 
Your goal is to provide accurate, real-time-simulated data about prediction events.

CRITICAL RULES:
1. You must ONLY analyze and recommend outcomes that are EXPLICITLY listed in the query.
2. Do NOT suggest outcomes that are not in the provided list.
3. If the query lists specific outcomes (e.g., "December 6", "December 7", etc.), your analysis must focus ONLY on those options.
4. For each listed outcome, provide a probability estimate.

You must generate structured JSON containing:
1. A factual summary of the event status.
2. Current odds from major platforms (Polymarket is primary) - ONLY for the outcomes listed.
3. Arbitrage or hedging opportunities - ONLY referencing the listed outcomes.
4. Visualization data formatted for Chart.js.

If you cannot access live real-time data, provide the most accurate estimate based on your knowledge cutoff and recent trends, but clearly mark it as an estimate in the summary.

IMPORTANT: Search for the Polymarket URL if provided to read user comments and positions on the market."""


# --- Singleton xAI Client ---
# The xAI Client is just an interface - it doesn't hold conversation state.
# Each chat.create() call creates a new conversation context.
# Reusing the client avoids initialization overhead.

_xai_client: Optional[Client] = None
_xai_client_api_key: Optional[str] = None


def _get_xai_client(api_key: Optional[str] = None) -> Client:
    """Get or create singleton xAI Client. Thread-safe lazy initialization."""
    global _xai_client, _xai_client_api_key
    
    resolved_key = api_key or os.getenv("GROK_API_KEY") or os.getenv("XAI_API_KEY")
    if not resolved_key:
        raise ValueError("GROK_API_KEY or XAI_API_KEY not found in environment variables")
    
    # Reinitialize if API key changed
    if _xai_client is None or _xai_client_api_key != resolved_key:
        print("🔧 Initializing xAI SDK Client (singleton)...")
        _xai_client = Client(api_key=resolved_key)
        _xai_client_api_key = resolved_key
        print("✅ xAI Client ready")
    
    return _xai_client


class FoundationalDataService:
    """Service to generate foundational data for events using xAI SDK"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GROK_API_KEY") or os.getenv("XAI_API_KEY")
        if not self.api_key:
            raise ValueError("GROK_API_KEY or XAI_API_KEY not found in environment variables")
        
        # Use singleton xAI Client (avoids reinitializing on every call)
        self.client = _get_xai_client(self.api_key)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def generate_data(self, event_query: str) -> FoundationalData:
        """
        Generate full foundational data for an event query using xAI Agentic Tools.
        """
        print(f"📊 Generating foundational data for: '{event_query}'")
        
        schema = FoundationalData.model_json_schema()
        
        user_prompt = f"""
Analyze this prediction event: "{event_query}"

Use your 'web_search' and 'x_search' tools to find the latest real-time information, news, and odds.
Research the current status, recent developments, and market sentiment.

After gathering information, provide a comprehensive data object matching the following JSON schema.

REQUIREMENTS:
1. facts_summary: Concise, neutral, up-to-date summary based on your research.
2. current_odds: Estimate current odds from your search results.
3. arbitrage_opportunities: Look for spreads.
4. probability_visualization: Create a 'pie' chart.
5. sources: List the URLs of the sources you found.

JSON SCHEMA:
{json.dumps(schema, indent=2)}

Respond with ONLY valid JSON matching this schema. Do not include markdown formatting like ```json.
"""

        # Run the synchronous SDK call in a thread to avoid blocking async loop
        def _consume_search():
            content = ""
            cites = []
            for event in self._run_agentic_search(user_prompt):
                if event["type"] == "content":
                    content = event["content"]
                elif event["type"] == "citations":
                    cites = event["citations"]
            return content, cites

        response_text, citations = await asyncio.to_thread(_consume_search)
        
        # Parse JSON from response
        if isinstance(response_text, str):
            # Clean up potential markdown
            clean_text = response_text.strip()
            if clean_text.startswith("```json"):
                clean_text = clean_text.split("```json", 1)[1]
            if clean_text.endswith("```"):
                clean_text = clean_text.rsplit("```", 1)[0]
            clean_text = clean_text.strip()
            
            try:
                response_dict = json.loads(clean_text)
            except json.JSONDecodeError:
                # Fallback: try to find JSON object in text
                start = clean_text.find("{")
                end = clean_text.rfind("}") + 1
                if start >= 0 and end > start:
                    response_dict = json.loads(clean_text[start:end])
                else:
                    raise ValueError(f"Could not parse JSON from response: {response_text[:100]}...")
        else:
            response_dict = response_text

        # Ensure generated_at is set
        if "generated_at" not in response_dict or not response_dict.get("generated_at"):
            response_dict["generated_at"] = datetime.now().isoformat()
            
        # Ensure event_query is set
        if "event_query" not in response_dict or not response_dict.get("event_query"):
            response_dict["event_query"] = event_query
            
        # Ensure sources are populated from citations if not in JSON
        if not response_dict.get("sources") and citations:
            response_dict["sources"] = citations

        # Validate and return
        return FoundationalData.model_validate(response_dict)

    def _run_agentic_search(self, prompt: str, timeout_seconds: int = 180):
        """
        Internal method to run the synchronous xAI SDK chat stream.
        Yields events: {'type': str, ...}
        
        Args:
            prompt: The search prompt
            timeout_seconds: Maximum time to wait for the stream (default 3 minutes)
        """
        import time
        start_time = time.time()
        
        print("🤖 [Foundational] Grok Agent Initializing...")
        yield {"type": "log", "message": "🤖 Grok Agent Initializing..."}
        
        try:
            # Create chat with tools (xAI SDK pattern)
            print("🔧 [Foundational] Creating chat with tools...")
            chat = self.client.chat.create(
                model="grok-4-1-fast",  # Reasoning model with tool support
                tools=[
                    web_search(),
                    x_search()
                ],
            )
            
            # Append messages using SDK helpers
            print("📝 [Foundational] Appending system prompt and user query...")
            chat.append(system(FOUNDATIONAL_SYSTEM_PROMPT))
            chat.append(user(prompt))
            
            final_content = ""
            is_thinking = True
            last_response = None
            chunk_count = 0
            
            print("🚀 [Foundational] Starting stream...")
            yield {"type": "log", "message": "Starting foundational stream..."}
            
            for response, chunk in chat.stream():
                chunk_count += 1
                elapsed = time.time() - start_time
                
                # Check timeout
                if elapsed > timeout_seconds:
                    print(f"\n⏰ [Foundational] TIMEOUT after {elapsed:.1f}s and {chunk_count} chunks")
                    yield {"type": "error", "error": f"Foundational search timed out after {timeout_seconds}s"}
                    break
                
                last_response = response
                
                # Log progress every 10 chunks
                if chunk_count % 10 == 0:
                    print(f"📊 [Foundational] Progress: {chunk_count} chunks, {elapsed:.1f}s elapsed")
                
                # View the server-side tool calls as they are being made in real-time
                for tool_call in chunk.tool_calls:
                    msg = f"Calling tool: {tool_call.function.name}"
                    args = tool_call.function.arguments
                    print(f"\n  > [Foundational] {msg} args={args[:100]}...")
                    yield {
                        "type": "tool_call", 
                        "tool": tool_call.function.name, 
                        "args": args
                    }
                
                if response.usage and response.usage.reasoning_tokens and is_thinking:
                    print(f"\r💭 [Foundational] Thinking... ({response.usage.reasoning_tokens} tokens)", end="", flush=True)
                    yield {"type": "thinking", "tokens": response.usage.reasoning_tokens}
                
                if chunk.content and is_thinking:
                    print(f"\n\n✅ [Foundational] Final Response Generation Started after {elapsed:.1f}s...")
                    yield {"type": "log", "message": f"Final Response Generation Started after {elapsed:.1f}s..."}
                    is_thinking = False
                
                if chunk.content and not is_thinking:
                    final_content += chunk.content
            
            elapsed = time.time() - start_time
            print(f"\n🏁 [Foundational] Stream complete: {chunk_count} chunks in {elapsed:.1f}s")
            
            if last_response:
                print("\n📚 [Foundational] Citations:")
                print(last_response.citations)
                yield {"type": "citations", "citations": last_response.citations}
                
                print("\n📈 [Foundational] Usage:")
                print(last_response.usage)
                yield {"type": "usage", "usage": last_response.usage}
                
                print(f"\n🛠️ [Foundational] Server Side Tool Usage:")
                print(last_response.server_side_tool_usage)
                print(f"\n🛠️ [Foundational] Tool Calls:")
                print(last_response.tool_calls)
                
                yield {"type": "content", "content": final_content}
                return
            
            yield {"type": "content", "content": final_content}
            
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"\n❌ [Foundational] ERROR after {elapsed:.1f}s: {e}")
            import traceback
            traceback.print_exc()
            yield {"type": "error", "error": str(e)}


# --- Sync Wrapper ---

def get_foundational_data_sync(event_query: str) -> FoundationalData:
    """Synchronous wrapper for easy use in scripts"""
    async def _run():
        async with FoundationalDataService() as service:
            return await service.generate_data(event_query)
    
    return asyncio.run(_run())

def stream_foundational_data_sync(event_query: str):
    """
    Synchronous generator that yields logs/events and finally the FoundationalData object.
    Yields: dict (event) or FoundationalData (final result)
    """
    service = FoundationalDataService()
    
    # We need to reconstruct the prompt logic here to stream it
    schema = FoundationalData.model_json_schema()
    user_prompt = f"""
Analyze this prediction event: "{event_query}"

Use your 'web_search' and 'x_search' tools to find the latest real-time information, news, and odds.
Research the current status, recent developments, and market sentiment.

After gathering information, provide a comprehensive data object matching the following JSON schema.

REQUIREMENTS:
1. facts_summary: Concise, neutral, up-to-date summary based on your research.
2. current_odds: Estimate current odds from your search results.
3. arbitrage_opportunities: Look for spreads.
4. probability_visualization: Create a 'pie' chart.
5. sources: List the URLs of the sources you found.

JSON SCHEMA:
{json.dumps(schema, indent=2)}

Respond with ONLY valid JSON matching this schema. Do not include markdown formatting like ```json.
"""

    # Run the generator
    # Since the SDK is sync, we can just iterate directly
    response_text = ""
    citations = []
    
    for event in service._run_agentic_search(user_prompt):
        if event["type"] == "content":
            response_text = event["content"]
        elif event["type"] == "citations":
            citations = event["citations"]
        
        yield event

    # Parse JSON (same logic as generate_data)
    if isinstance(response_text, str):
        clean_text = response_text.strip()
        if clean_text.startswith("```json"):
            clean_text = clean_text.split("```json", 1)[1]
        if clean_text.endswith("```"):
            clean_text = clean_text.rsplit("```", 1)[0]
        clean_text = clean_text.strip()
        
        try:
            response_dict = json.loads(clean_text)
        except json.JSONDecodeError:
            start = clean_text.find("{")
            end = clean_text.rfind("}") + 1
            if start >= 0 and end > start:
                response_dict = json.loads(clean_text[start:end])
            else:
                yield {"type": "error", "message": f"Could not parse JSON: {response_text[:100]}..."}
                return
    else:
        response_dict = response_text

    # Ensure fields
    if "generated_at" not in response_dict or not response_dict.get("generated_at"):
        response_dict["generated_at"] = datetime.now().isoformat()
    if "event_query" not in response_dict or not response_dict.get("event_query"):
        response_dict["event_query"] = event_query
    if not response_dict.get("sources") and citations:
        response_dict["sources"] = citations

    # Yield final object
    yield FoundationalData.model_validate(response_dict)


if __name__ == "__main__":
    # Demo
    query = "Will Russia capture all of Kupiansk by December 31"
    print(f"Running demo for: {query}")
    
    try:
        data = get_foundational_data_sync(query)
        print("\n✅ Data Generated Successfully!")
        print(json.dumps(data.model_dump(), indent=2, default=str))
        
        # Save to file
        with open("foundational_data_demo.json", "w") as f:
            json.dump(data.model_dump(), f, indent=2, default=str)
        print("\n💾 Saved to foundational_data_demo.json")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
