"""
Grok API Client for the pipeline.
Handles communication with Grok API for filter selection and signal analysis.
"""

import asyncio
import json
import os
from typing import Any, Dict, Optional, List, Union

import httpx
from httpx import AsyncClient as HttpxAsyncClient

from .schemas import (
    FilterSelectionResponse,
    SignalAnalysisResponse,
    FILTER_SELECTION_SYSTEM_PROMPT,
    SIGNAL_ANALYSIS_SYSTEM_PROMPT
)


DEFAULT_MODEL = "grok-4-latest"
DEFAULT_BASE_URL = "https://api.x.ai"
DEFAULT_TIMEOUT = 60.0


# --- Singleton httpx.AsyncClient ---
# Reuse connection pool across GrokClient instances for better performance
_shared_http_client: Optional[httpx.AsyncClient] = None
_shared_http_api_key: Optional[str] = None


def _get_shared_http_client(api_key: str) -> httpx.AsyncClient:
    """Get or create shared httpx.AsyncClient with connection pooling."""
    global _shared_http_client, _shared_http_api_key
    
    # Reinitialize if API key changed or client is closed
    if (_shared_http_client is None or 
        _shared_http_api_key != api_key or 
        _shared_http_client.is_closed):
        print("🔧 Initializing shared httpx.AsyncClient (singleton)...")
        _shared_http_client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=DEFAULT_TIMEOUT,
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
        )
        _shared_http_api_key = api_key
        print("✅ Shared HTTP client ready")
    
    return _shared_http_client


class GrokClient:
    """Client for calling Grok API with structured prompts and responses"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = DEFAULT_BASE_URL,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        model: str = DEFAULT_MODEL,
        use_shared_client: bool = True,
    ):
        """
        Initialize Grok client.

        Args:
            api_key: X API key (defaults to env var GROK_API_KEY)
            base_url: Base URL for Grok API
            timeout: Request timeout in seconds
            model: Model to use
            use_shared_client: If True, use singleton HTTP client (recommended for performance)
        """
        self.api_key = api_key or os.getenv("GROK_API_KEY")
        if not self.api_key:
            raise ValueError("GROK_API_KEY not found in environment variables")

        self.base_url = base_url
        self.model = "grok-4-1-fast-non-reasoning"  # Grok 4.1 Fast Reasoning (upgraded)
        self.timeout = timeout
        self._use_shared_client = use_shared_client
        self._owns_client = False
        
        if use_shared_client:
            # Use shared singleton client (better performance, connection reuse)
            self.client = _get_shared_http_client(self.api_key)
        else:
            # Create dedicated client (for isolation if needed)
            self.client = httpx.AsyncClient(
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=self.timeout,
            )
            self._owns_client = True

    async def select_filters(
        self,
        event_id: str,
        event_description: str,
        prediction_markets: Optional[list] = None
    ) -> FilterSelectionResponse:
        """
        Step 1: Ask Grok which filters to apply for this event.
        
        Args:
            event_id: Unique identifier for the event
            event_description: Description of the prediction event
            prediction_markets: Optional list of relevant prediction markets
        
        Returns:
            FilterSelectionResponse with recommended filters
        """
        markets_context = ""
        if prediction_markets:
            markets_context = f"\n\nRelevant prediction markets:\n" + "\n".join(prediction_markets)

        user_prompt = f"""
A new prediction market event has occurred:

Event ID: {event_id}
Description: {event_description}
{markets_context}

Which filters should I apply to detect high-signal tweets about this event?
Respond with ONLY valid JSON matching the specified schema.
"""

        response = await self._call_grok(
            system_prompt=FILTER_SELECTION_SYSTEM_PROMPT,
            user_prompt=user_prompt
        )

        return FilterSelectionResponse.from_dict(response)

    async def analyze_signal(
        self,
        event_id: str,
        tweets: list,
        filters_used: list,
        context: Optional[str] = None
    ) -> SignalAnalysisResponse:
        """
        Step 3: Ask Grok to analyze tweet sentiment and quantify signal strength.
        
        Args:
            event_id: Event being analyzed
            tweets: List of tweet dictionaries
            filters_used: Which filters were applied
            context: Additional context about the event
        
        Returns:
            SignalAnalysisResponse with quantified metrics
        """
        # Format tweets for analysis - limit to top 25 most relevant for consistency
        tweets_text = "\n\n".join([
            f"Tweet {i+1} (from @{t.get('author_username', 'unknown')}, "
            f"verified={t.get('is_verified', False)}):\n{t.get('text', '')}"
            for i, t in enumerate(tweets[:25])  # Limit to 25 for reliability
        ])

        user_prompt = f"""
Analyze the following tweets collected about a prediction market event:

Event ID: {event_id}
Filters Applied: {', '.join(filters_used)}
{f"Context: {context}" if context else ""}

TWEETS:
{tweets_text}

Provide a comprehensive signal analysis including sentiment, strength, and market implications.
Respond with ONLY valid JSON matching the specified schema.
"""

        for attempt in range(3):
            try:
                response = await self._call_grok(
                    system_prompt=SIGNAL_ANALYSIS_SYSTEM_PROMPT,
                    user_prompt=user_prompt
                )
                return SignalAnalysisResponse.from_dict(response)
            except Exception as e:
                if attempt == 2:  # Last attempt
                    raise
                # Wait a bit before retry
                await asyncio.sleep(1)

    async def _call_grok(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 16000,
        expect_json: bool = True,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
        return_full_response: bool = False,
        max_retries: int = 3
    ) -> Any:
        """
        Internal method to call Grok API with retry logic for network errors.
        """
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        if tools:
            payload["tools"] = tools
        if tool_choice:
            payload["tool_choice"] = tool_choice

        last_error = None
        for attempt in range(max_retries):
            try:
                response = await self.client.post(
                    f"{self.base_url}/v1/chat/completions",
                    json=payload,
                )
                response.raise_for_status()
                result = response.json()
                message = result["choices"][0]["message"]
                
                if return_full_response:
                    return message

                # Extract text from response
                text = message["content"]

                if not text or not text.strip():
                    raise RuntimeError(f"Empty response from Grok")

                if not expect_json:
                    return text

                parsed = self._extract_json(text)
                return parsed

            except httpx.HTTPStatusError as e:
                detail = e.response.text if e.response else ""
                raise RuntimeError(
                    f"Grok API error: {e.response.status_code if e.response else 'unknown'} "
                    f"{detail}"
                )
            except (httpx.ReadError, httpx.ConnectError, httpx.TimeoutException) as e:
                # Network errors - retry with exponential backoff
                last_error = e
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) + 0.5  # 0.5s, 2.5s, 4.5s
                    print(f"⚠️ [GrokClient] Network error (attempt {attempt + 1}/{max_retries}): {e}")
                    print(f"   Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                raise RuntimeError(f"Grok API network error after {max_retries} retries: {e}")
            except httpx.HTTPError as e:
                raise RuntimeError(f"Grok API error: {e}")
            except json.JSONDecodeError as e:
                raise RuntimeError(f"Failed to parse Grok response as JSON: {e}\nResponse: {text}")
        
        # Should not reach here, but just in case
        raise RuntimeError(f"Grok API failed after {max_retries} retries: {last_error}")

    @staticmethod
    def _extract_json(text: str) -> Dict[str, Any]:
        """
        Grok sometimes wraps JSON in fences; normalize and parse.
        """
        if "```json" in text:
            json_str = text.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in text:
            json_str = text.split("```", 1)[1].split("```", 1)[0].strip()
        else:
            json_str = text.strip()

        if not json_str:
            raise RuntimeError("No JSON content found in Grok response")

        return json.loads(json_str)

    async def close(self):
        """Close the HTTP client (only if we own it, not for shared client)"""
        if self._owns_client and not self.client.is_closed:
            await self.client.aclose()


# Synchronous wrapper for easier use
class GrokClientSync:
    """Synchronous wrapper around async GrokClient"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = DEFAULT_BASE_URL,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        model: str = DEFAULT_MODEL,
    ):
        """Initialize synchronous Grok client"""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.async_client = GrokClient(api_key, base_url, timeout=timeout, model=model)

    def _run(self, coro):
        """Run a coroutine on the dedicated event loop."""
        if self.loop.is_closed():
            raise RuntimeError("Attempted to use GrokClientSync after it was closed.")
        return self.loop.run_until_complete(coro)

    def select_filters(
        self,
        event_id: str,
        event_description: str,
        prediction_markets: Optional[list] = None
    ) -> FilterSelectionResponse:
        """Synchronous wrapper for select_filters"""
        return self._run(
            self.async_client.select_filters(event_id, event_description, prediction_markets)
        )

    def analyze_signal(
        self,
        event_id: str,
        tweets: list,
        filters_used: list,
        context: Optional[str] = None
    ) -> SignalAnalysisResponse:
        """Synchronous wrapper for analyze_signal"""
        return self._run(
            self.async_client.analyze_signal(event_id, tweets, filters_used, context)
        )

    def close(self):
        """Close the client and its loop."""
        if self.loop.is_closed():
            return
        self.loop.run_until_complete(self.async_client.close())
        self.loop.close()

    def __del__(self):
        """Cleanup on deletion"""
        try:
            self.close()
        except Exception:
            pass

