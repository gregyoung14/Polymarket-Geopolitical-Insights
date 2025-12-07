"""
Analyze Tweets from Prominent Figures for Prediction Events

Extracts signal, analysis, and alpha from tweets of prominent figures
using Grok-4-1-Fast with compressed directive prompts.
Integrates with X API to fetch real tweets.
"""

import json
import os
import asyncio
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any

# Load environment variables
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / '.env'
    load_dotenv(env_path)
except ImportError:
    env_path = Path(__file__).parent / '.env'
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value

from grok_pipeline.grok_client import GrokClient
from auth.utils import get_client


ANALYSIS_SYSTEM_PROMPT = """You are an analytic engine monitoring X (Twitter) for the prediction event: **"{event_description}"**
Operate as a strict extractor of military-relevant signals. No narrative. No speculation beyond evidence.

**RULING CRITERIA**
{ruling_criteria}

**PROCESS**
1. Analyze provided tweets from prominent figures
2. Filter for relevance to {location} (variants: {location_variants})
3. Classify each tweet as ALPHA or NOISE using ruling criteria
4. Extract sentiment: Bullish (favors capture), Bearish (favors defense), Neutral, N/A
5. Assign confidence score 0-1 based on evidence quality

**CONSTRAINTS**
- Evidence only
- No inference beyond stated facts
- Ignore propaganda unless fact-anchored
- Output strict JSON only

**OUTPUT SCHEMA**
For each tweet provide:
- tweet_id
- date
- summary (compressed content)
- classification (ALPHA or NOISE)
- confidence (0-1)
- sentiment (Bullish/Bearish/Neutral/N/A)
- notes (why it matters or doesn't)

Return complete JSON matching the response schema."""


RULING_CRITERIA = {
    "alpha_signal": {
        "description": "Tweets providing substantive insight into the prediction event.",
        "criteria": [
            "Explicit mention of location with prediction of capture or defense by deadline.",
            "Probability estimates (e.g., '50% chance Russia takes X by year-end').",
            "Strategic analysis linking current advances/logistics to potential full capture.",
            "References to timelines, troop movements, or reinforcements specific to the region.",
            "High confidence if from military expert with reasoning."
        ],
        "signaling": "Flag as ALPHA with excerpt and relevance score."
    },
    "noise": {
        "description": "Tweets that mention the topic superficially or unrelated.",
        "criteria": [
            "General war updates without location specifics.",
            "Retweets or quotes without original analysis.",
            "Mentions in historical context only.",
            "Propaganda-style claims without evidence.",
            "Off-topic or emotional rants lacking prediction elements.",
            "Low confidence if vague or unverified claims."
        ],
        "signaling": "Flag as NOISE with brief reason for dismissal."
    }
}


def fetch_tweets_from_figures(
    figures: List[Dict[str, Any]],
    location_keywords: List[str],
    days_back: int = 7,
    max_tweets_per_figure: int = 20
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Fetch real tweets from X API for each prominent figure.
    
    Args:
        figures: List of prominent figure dicts with 'x_handle'
        location_keywords: Keywords to search for (e.g., ['Pokrovsk', 'Pokrovs\'k'])
        days_back: How many days back to search
        max_tweets_per_figure: Max tweets to fetch per figure
    
    Returns:
        Dict mapping handle to list of tweets
    """
    print(f"🔍 Fetching tweets from {len(figures)} figures...")
    print(f"📍 Keywords: {', '.join(location_keywords)}")
    print(f"⏰ Last {days_back} days")
    print()
    
    client = get_client(auth_type='bearer')
    
    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    since_str = start_date.strftime('%Y-%m-%d')
    
    tweets_by_figure = {}
    
    for i, figure in enumerate(figures, 1):
        handle = figure.get('x_handle', '').replace('@', '')
        name = figure.get('name', 'Unknown')
        
        if not handle:
            print(f"  [{i}/{len(figures)}] {name}: No handle, skipping")
            continue
        
        print(f"  [{i}/{len(figures)}] {name} (@{handle})...", end=" ", flush=True)
        
        # Build simple query - just from:handle
        query = f"from:{handle} -is:retweet"
        
        try:
            # Add delay to avoid rate limits
            time.sleep(1)
            
            # Format start_time for API (ISO 8601)
            # tweets search API expects YYYY-MM-DDTHH:mm:ssZ
            start_time_iso = (datetime.utcnow() - timedelta(days=days_back)).strftime('%Y-%m-%dT%H:%M:%SZ')
            
            # Determine API method and max_results per page
            # API usually caps at 100 per request
            api_max = 100 
            
            # Use search_all for > 7 days, search_recent for <= 7 days
            if days_back > 7:
                print(f"    Using Full Archive Search (Last {days_back} days)...")
                response = client.posts.search_all(
                    query=query,
                    max_results=api_max, 
                    start_time=start_time_iso
                )
            else:
                response = client.posts.search_recent(
                    query=query,
                    max_results=api_max,
                    start_time=start_time_iso
                )
            
            tweets = []
            count = 0
            
            # The response is a generator of pages
            # Iterate through pages
            for page in response:
                # Check for data in page
                tweet_data = None
                if hasattr(page, 'data'):
                    tweet_data = page.data
                elif isinstance(page, dict) and 'data' in page:
                    tweet_data = page['data']
                
                if not tweet_data:
                    continue
                    
                # Iterate through tweets in page
                for tweet in (tweet_data if isinstance(tweet_data, list) else [tweet_data]):
                    # Extract fields - handle both dict and object
                    if isinstance(tweet, dict):
                        tweet_text = tweet.get("text", "")
                        tweet_id = tweet.get("id", "")
                        author_id = tweet.get("author_id", "")
                        created_at = tweet.get("created_at", "")
                    else:
                        tweet_text = getattr(tweet, "text", "") or ""
                        tweet_id = getattr(tweet, "id", "") or ""
                        author_id = getattr(tweet, "author_id", "") or ""
                        created_at = getattr(tweet, "created_at", "") or ""
                    
                    tweet_dict = {
                        "id": str(tweet_id),
                        "text": str(tweet_text),
                        "author_id": str(author_id),
                        "created_at": str(created_at),
                        "handle": f"@{handle}",
                        "author_name": name
                    }
                    tweets.append(tweet_dict)
                    count += 1
                    
                    # Check limit if set
                    if max_tweets_per_figure and count >= max_tweets_per_figure:
                        break
                
                # Check limit if set
                if max_tweets_per_figure and count >= max_tweets_per_figure:
                    break
            
            tweets_by_figure[f"@{handle}"] = tweets
            print(f"✓ {count} tweets")
            
        except Exception as e:
            print(f"✗ Error: {str(e)[:50]}")
            tweets_by_figure[f"@{handle}"] = []
            
            # If rate limited, wait longer
            if "429" in str(e):
                print("    ⚠️  Rate limit hit. Waiting 15 seconds...")
                time.sleep(15)
    
    total_tweets = sum(len(tweets) for tweets in tweets_by_figure.values())
    print()
    print(f"📊 Total tweets fetched: {total_tweets}")
    print()
    
    return tweets_by_figure


async def analyze_tweets_for_event(
    prominent_figures_file: str,
    event_description: str,
    location: str,
    location_variants: List[str],
    deadline: str,
    days_back: int = 7,
    max_tweets: int = 20
) -> Dict[str, Any]:
    """
    Analyze tweets from prominent figures for a prediction event.
    
    Args:
        prominent_figures_file: Path to JSON file with prominent figures
        event_description: Full event description
        location: Primary location name
        location_variants: Alternative spellings/names
        deadline: Event deadline (YYYY-MM-DD)
        days_back: How many days back to search
        max_tweets: Max tweets per figure (None for unlimited)
    
    Returns:
        Complete analysis results as dict
    """
    print(f"🔍 Analyzing tweets for: {event_description}")
    print(f"📍 Location: {location} (variants: {', '.join(location_variants)})")
    print(f"📅 Deadline: {deadline}")
    print(f"⏰ Analyzing last {days_back} days")
    print(f"🔎 Max tweets per figure: {max_tweets if max_tweets else 'Unlimited'}")
    print()
    
    # Load prominent figures
    with open(prominent_figures_file) as f:
        figures_data = json.load(f)
    
    figures = figures_data.get("prominent_figures", [])
    print(f"👥 Loaded {len(figures)} prominent figures")
    print()
    
    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    
    # STEP 1: Fetch REAL tweets from X API
    print("🔍 Fetching tweets from X API...")
    all_keywords = [location] + location_variants
    tweets_by_figure = fetch_tweets_from_figures(
        figures=figures,
        location_keywords=all_keywords,
        days_back=days_back,
        max_tweets_per_figure=max_tweets
    )
    
    # Count total tweets
    total_tweets_fetched = sum(len(tweets) for tweets in tweets_by_figure.values())
    
    if total_tweets_fetched == 0:
        print("⚠️  No tweets fetched. Returning empty result.")
        return {
            "prediction_event": event_description,
            "analysis_period": f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
            "summary": {"total_tweets_analyzed": 0, "alpha_count": 0, "noise_count": 0},
            "findings_by_figure": [],
            "recommendations": ["Check X API access"]
        }
    
    
    # Build system prompt
    system_prompt = ANALYSIS_SYSTEM_PROMPT.format(
        event_description=event_description,
        location=location,
        location_variants=", ".join(location_variants),
        ruling_criteria=json.dumps(RULING_CRITERIA, indent=2)
    )
    
    # Build user prompt with REAL fetched tweets
    user_prompt = f"""
Analyze the following REAL tweets fetched from X API for the prediction event:
"{event_description}"

Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}
Deadline: {deadline}
Total tweets fetched: {total_tweets_fetched}

TWEETS BY FIGURE:
"""
    
    # Add real tweets for each figure
    for figure in figures:
        handle = figure.get('x_handle', '')
        lookup_handle = f"@{handle.replace('@', '')}"
        name = figure.get('name', 'Unknown')
        tweets = tweets_by_figure.get(lookup_handle, [])
        
        user_prompt += f"\n--- {name} ({handle}) - {len(tweets)} tweets ---\n"
        
        if tweets:
            for j, tweet in enumerate(tweets, 1):
                text = tweet.get('text', '')[:500]  # Truncate long tweets
                user_prompt += f"\n[{j}] ID: {tweet['id']}\n"
                user_prompt += f"    Date: {tweet['created_at']}\n"
                user_prompt += f"    Text: {text}\n"
        else:
            user_prompt += "No tweets in period.\n"
    
    user_prompt += f"""

---
TASK: For each tweet above:
1. Check if it mentions {location} or related topics
2. Classify as ALPHA (prediction/analysis) or NOISE (superficial)
3. Extract sentiment: Bullish (favors capture), Bearish (favors defense), Neutral
4. Assign confidence 0-1

Return JSON:
{{
  "prediction_event": "{event_description}",
  "analysis_period": "{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
  "summary": {{
    "total_tweets_analyzed": {total_tweets_fetched},
    "total_relevant_tweets": 0,
    "alpha_count": 0,
    "noise_count": 0,
    "sentiment_trend": "",
    "key_insights": []
  }},
  "findings_by_figure": [
    {{
      "name": "",
      "handle": "",
      "total_tweets_retrieved": 0,
      "relevant_tweets": 0,
      "alpha_count": 0,
      "noise_count": 0,
      "sentiment_overall": "",
      "notes": [],
      "tweets": [
        {{
          "tweet_id": "",
          "date": "",
          "summary": "",
          "classification": "ALPHA|NOISE",
          "confidence": 0.0,
          "sentiment": "",
          "notes": ""
        }}
      ]
    }}
  ],
  "ruling_criteria_applied": "alpha_signal and noise criteria",
  "recommendations": []
}}
"""
    
    # Call Grok
    client = GrokClient()
    try:
        print("🤖 Calling Grok-4-1-Fast for tweet analysis...")
        print()
        
        response = await client._call_grok(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.2,
            max_tokens=8000,
            expect_json=True
        )
    finally:
        await client.close()
    
    return response


def analyze_tweets_for_event_sync(
    prominent_figures_file: str,
    event_description: str,
    location: str,
    location_variants: List[str],
    deadline: str,
    days_back: int = 7,
    max_tweets: int = 20
) -> Dict[str, Any]:
    """Synchronous wrapper"""
    return asyncio.run(
        analyze_tweets_for_event(
            prominent_figures_file=prominent_figures_file,
            event_description=event_description,
            location=location,
            location_variants=location_variants,
            deadline=deadline,
            days_back=days_back,
            max_tweets=max_tweets
        )
    )


def print_analysis_summary(results: Dict[str, Any]):
    """Print formatted summary of analysis results"""
    print("=" * 80)
    print("ANALYSIS RESULTS")
    print("=" * 80)
    print()
    
    summary = results.get("summary", {})
    print(f"Event: {results.get('prediction_event')}")
    print(f"Period: {results.get('analysis_period')}")
    print()
    
    print("OVERALL SUMMARY:")
    print(f"  Total Tweets Analyzed: {summary.get('total_tweets_analyzed', 0)}")
    print(f"  Relevant Tweets: {summary.get('total_relevant_tweets', 0)}")
    print(f"  Alpha Signals: {summary.get('alpha_count', 0)}")
    print(f"  Noise: {summary.get('noise_count', 0)}")
    print(f"  Sentiment Trend: {summary.get('sentiment_trend', 'N/A')}")
    print()
    
    print("KEY INSIGHTS:")
    for insight in summary.get('key_insights', []):
        print(f"  • {insight}")
    print()
    
    # Top alpha signals
    print("TOP ALPHA SIGNALS:")
    alpha_tweets = []
    for figure in results.get('findings_by_figure', []):
        for tweet in figure.get('tweets', []):
            if tweet.get('classification') == 'ALPHA':
                alpha_tweets.append({
                    'figure': figure['name'],
                    'handle': figure['handle'],
                    'tweet': tweet
                })
    
    # Sort by confidence
    alpha_tweets.sort(key=lambda x: x['tweet'].get('confidence', 0), reverse=True)
    
    for i, item in enumerate(alpha_tweets[:10], 1):
        tweet = item['tweet']
        print(f"\n{i}. {item['figure']} ({item['handle']})")
        print(f"   Date: {tweet.get('date')}")
        print(f"   Confidence: {tweet.get('confidence', 0):.2f}")
        print(f"   Sentiment: {tweet.get('sentiment')}")
        print(f"   Summary: {tweet.get('summary', '')[:150]}...")
        print(f"   Notes: {tweet.get('notes', '')[:100]}...")
    
    if not alpha_tweets:
        print("  No alpha signals found in analysis period.")
    
    print()
    print("RECOMMENDATIONS:")
    for rec in results.get('recommendations', []):
        print(f"  • {rec}")
    print()


if __name__ == "__main__":
    import sys
    
    print("=" * 80)
    print("PROMINENT FIGURE TWEET ANALYSIS")
    print("=" * 80)
    print()
    
    # Check for API key
    if not os.getenv("GROK_API_KEY"):
        print("❌ ERROR: GROK_API_KEY not found in environment")
        sys.exit(1)
    
    # Get parameters from command line or use defaults
    if len(sys.argv) > 1:
        figures_file = sys.argv[1]
    else:
        # Default: Pokrovsk
        figures_file = "prominent_figures_russia_pokrovsk_dec31_2025.json"
    
    if not os.path.exists(figures_file):
        print(f"❌ ERROR: Figures file not found: {figures_file}")
        print()
        print("Usage: python analyze_prominent_figure_tweets.py [figures_file.json]")
        sys.exit(1)
    
    # Load event details from figures file
    with open(figures_file) as f:
        data = json.load(f)
    
    event = data.get("prediction_event", {})
    event_description = event.get("title", "Unknown event")
    deadline = event.get("deadline", "2025-12-31")
    
    # Determine location and variants
    if "Pokrovsk" in event_description:
        location = "Pokrovsk"
        location_variants = ["Pokrovs'k", "Pokrovske", "Myrnohrad sector"]
    elif "Kupiansk" in event_description:
        location = "Kupiansk"
        location_variants = ["Kupyansk", "Куп'янськ", "Kupjansk"]
    else:
        location = "Unknown"
        location_variants = []
    
    print(f"Analyzing: {event_description}")
    print(f"Location: {location}")
    print(f"Deadline: {deadline}")
    print()
    
    # Run standardized analysis (60 days provides best signal-to-noise ratio)
    days = 60
    max_tweets = 100
    
    print(f"\n{'='*40}")
    print(f"🚀 STARTING STANDARDIZED ANALYSIS: {days} DAYS")
    print(f"{'='*40}\n")
    print(f"Config: Full Archive Search (Capped at {max_tweets} tweets/figure)")
        
    try:
        results = analyze_tweets_for_event_sync(
            prominent_figures_file=figures_file,
            event_description=event_description,
            location=location,
            location_variants=location_variants,
            deadline=deadline,
            days_back=days,
            max_tweets=max_tweets
        )
        
        # Print summary
        print_analysis_summary(results)
        
        # Save results to standard filename
        output_file = figures_file.replace("prominent_figures_", "tweet_analysis_")
        
        with open(output_file, "w") as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"💾 Saved analysis to: {output_file}")
        
    except Exception as e:
        print(f"❌ ERROR in analysis run: {e}")
        import traceback
        traceback.print_exc()
            
    print("\n✅ Analysis completed.")
