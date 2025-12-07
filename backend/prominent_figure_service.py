import json
import os
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime

# Import analysis functionality
from analyze_prominent_figure_tweets import analyze_tweets_for_event, fetch_tweets_from_figures

# Import Grok Client
try:
    from grok_pipeline.grok_client import GrokClient
except ImportError:
    # Use fallback if not found in package struct
    import sys
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from grok_pipeline.grok_client import GrokClient


FIGURE_GENERATION_SYSTEM_PROMPT = """You are an expert researcher identifying high-signal sources on X (Twitter) for specific geopolitical prediction events.

TASK:
Identify 20 prominent figures on X who are credible experts relevant to the following prediction event:
"{event_description}"

CRITERIA:
- Must have an active X account.
- Must be a subject matter expert (e.g., military analyst, OSINT, local reporter, geopolitical strategist).
- Must have a track record of factual reporting or accurate analysis.
- Balance between large accounts and high-quality niche experts.

OUTPUT JSON SCHEMA:
{{
  "prediction_event": {{
    "title": "{event_description}",
    "deadline": "2025-12-31" // Infer if possible
  }},
  "prominent_figures": [
    {{
      "name": "Full Name",
      "x_handle": "handle_without_at", 
      "category": "OSINT|Military Analyst|Journalist|official",
      "expertise": "Short description of area of focus",
      "credibility_score": 85, // 0-100 rating of reliability
      "signal_weight": 0.85, // 0-1 float for analysis weighting
      "rationale": "Why they are relevant to this specific event"
    }}
  ]
}}

Ensure handles are accurate. Do not invent handles.
"""

async def generate_prominent_figures(event_description: str) -> Dict[str, Any]:
    """
    Generate a list of prominent figures for an event using Grok.
    """
    client = GrokClient()
    try:
        user_prompt = f"Identify 20 prominent figures for: {event_description}"
        
        system_prompt = FIGURE_GENERATION_SYSTEM_PROMPT.format(
            event_description=event_description
        )
        
        response = await client._call_grok(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.3,
            max_tokens=4000,
            expect_json=True
        )
        return response
    finally:
        await client.close()

def generate_prominent_figures_sync(event_description: str) -> Dict[str, Any]:
    """Synchronous wrapper for figure generation"""
    return asyncio.run(generate_prominent_figures(event_description))

def run_full_analysis_pipeline_sync(
    event_description: str,
    days_back: int = 60,
    max_tweets: int = 100
) -> Dict[str, Any]:
    """
    Run the full pipeline:
    1. Generate Figures
    2. Fetch Tweets
    3. Analyze Tweets
    """
    # Step 1: Generate Figures
    figures_data = generate_prominent_figures_sync(event_description)
    
    # Save temp file for the analysis script which expects a file path
    # (Or refactor analysis script to accept dict, but for speed we'll save)
    temp_file = f"temp_figures_{int(datetime.now().timestamp())}.json"
    with open(temp_file, "w") as f:
        json.dump(figures_data, f, indent=2)
        
    try:
        # Determine location keywords from event
        # Simple heuristic or use Grok, strictly for this quick implementation we'll look for keywords
        # or defaults.
        # Actually, analyze_tweets_for_event expects many args.
        # We can try to infer location from event description
        
        location = "Target Location"
        if "Pokrovsk" in event_description:
            location = "Pokrovsk"
            variants = ["Pokrovs'k", "Myrnohrad"]
        elif "Kupiansk" in event_description:
            location = "Kupiansk"
            variants = ["Kupyansk"]
        else:
            location = event_description.split()[0] # Fallback
            variants = []
            
        deadline = figures_data.get("prediction_event", {}).get("deadline", "2025-12-31")

        # Step 2 & 3: Analyze
        # Reuse the existing async function but via sync wrapper
        results = asyncio.run(
            analyze_tweets_for_event(
                prominent_figures_file=temp_file,
                event_description=event_description,
                location=location,
                location_variants=variants,
                deadline=deadline,
                days_back=days_back,
                max_tweets=max_tweets
            )
        )
        return results, figures_data
        
    finally:
        # Clean up temp file
        if os.path.exists(temp_file):
            os.remove(temp_file)

def stream_full_analysis_pipeline_sync(
    event_description: str,
    days_back: int = 60,
    max_tweets: int = 100
):
    """
    Synchronous generator for streaming prominent figure analysis.
    Yields events: {"type": "log"|"result", ...}
    """
    yield {"type": "log", "message": f"🔍 Identifying prominent figures for: {event_description}"}
    
    # Step 1: Generate Figures
    figures_data = generate_prominent_figures_sync(event_description)
    num_figures = len(figures_data.get("prominent_figures", []))
    yield {"type": "log", "message": f"✅ Identified {num_figures} experts."}
    
    # Save temp file
    temp_file = f"temp_figures_{int(datetime.now().timestamp())}.json"
    with open(temp_file, "w") as f:
        json.dump(figures_data, f, indent=2)
        
    try:
        location = "Target Location"
        if "Pokrovsk" in event_description:
            location = "Pokrovsk"
            variants = ["Pokrovs'k", "Myrnohrad"]
        elif "Kupiansk" in event_description:
            location = "Kupiansk"
            variants = ["Kupyansk"]
        else:
            location = event_description.split()[0]
            variants = []
            
        deadline = figures_data.get("prediction_event", {}).get("deadline", "2025-12-31")

        yield {"type": "log", "message": f"📡 Conncting to X API (Latest {days_back} days)..."}
        yield {"type": "log", "message": f"🎯 Target: {location} (Deadline: {deadline})"}
        yield {"type": "log", "message": "⏳ Fetching and Analyzing Tweets (this may take 1-2 mins)..."}

        # Step 2 & 3: Analyze
        results = asyncio.run(
            analyze_tweets_for_event(
                prominent_figures_file=temp_file,
                event_description=event_description,
                location=location,
                location_variants=variants,
                deadline=deadline,
                days_back=days_back,
                max_tweets=max_tweets
            )
        )
        
        yield {"type": "log", "message": "✅ Analysis Complete."}
        yield {"type": "result", "data": (results, figures_data)}
        
    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)
