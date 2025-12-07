"""
Pipeline Orchestrator: Coordinates the multi-step flow.

Flow:
1. Accept random prediction event
2. Call Grok to select appropriate filters
3. Execute filters to collect tweets
4. Call Grok to analyze tweets and quantify signal
5. Persist signal snapshot for time-series tracking
"""

import json
import os
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .grok_client import GrokClientSync
from .schemas import (
    EventSignalTimeSeries,
    FilterSelectionResponse,
    FilterType,
    SignalAnalysisResponse,
    SignalSnapshot,
    TweetCollectionResult,
    TweetData,
)

try:
    # Imported once up front; avoids inline imports and subprocess installs later.
    from tweets.runner import search_recent
except ImportError:  # pragma: no cover - dependency/ENV issue
    search_recent = None


class PipelineOrchestrator:
    """Orchestrates the multi-step Grok pipeline"""

    def __init__(self, grok_api_key: Optional[str] = None):
        """
        Initialize the orchestrator.

        Args:
            grok_api_key: Optional Grok API key (defaults to env var)
        """
        self.grok_client = GrokClientSync(api_key=grok_api_key)
        self.event_timeseries: Dict[str, EventSignalTimeSeries] = {}

    def process_event_direct_search(
        self,
        event_description: str,
        search_query: str,
        event_id: Optional[str] = None,
        max_tweets: int = 100,
        *,
        verbose: bool = True,
        progress_hook: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        """
        Direct search without Grok filter selection.
        Searches for raw query, then chunks results into 25 for analysis.
        """
        log = print if verbose else (lambda *args, **kwargs: None)
        hook = progress_hook or (lambda *_args, **_kwargs: None)
        if not event_id:
            event_id = f"event_{uuid.uuid4().hex[:8]}"

        log(f"\n{'='*80}")
        log(f"DIRECT SEARCH: {event_description}")
        log(f"Query: {search_query}")
        log(f"{'='*80}\n")

        # Collect tweets
        log(f"[1/2] Searching X API directly...")
        hook("search_started", {"event_id": event_id, "query": search_query})
        try:
            tweets_data = self._search_tweets(search_query)
            tweets_collected = tweets_data[:max_tweets]
            log(f"✓ Collected {len(tweets_collected)} tweets\n")
            hook("search_succeeded", {"event_id": event_id, "count": len(tweets_collected)})
        except Exception as e:
            log(f"✗ Search failed: {e}\n")
            hook("search_failed", {"event_id": event_id, "error": str(e)})
            return {"status": "error", "error": str(e), "event_id": event_id}

        if not tweets_collected:
            log("⚠ No tweets found for query; skipping analysis.\n")
            hook("no_tweets", {"event_id": event_id})
            return {
                "status": "no_tweets",
                "event_id": event_id,
                "tweets_collected": 0,
                "chunks_analyzed": 0,
            }

        # Chunk into 25 and analyze each chunk
        log(f"[2/2] Analyzing {len(tweets_collected)} tweets in chunks of 25...")
        chunk_size = 25
        all_analyses = []
        total_chunks = (len(tweets_collected) + chunk_size - 1) // chunk_size
        
        for i in range(0, len(tweets_collected), chunk_size):
            chunk = tweets_collected[i:i+chunk_size]
            chunk_num = (i // chunk_size) + 1
            log(f"\n  Chunk {chunk_num}/{total_chunks} ({len(chunk)} tweets)...")
            hook("chunk_started", {
                "event_id": event_id,
                "chunk": chunk_num,
                "total_chunks": total_chunks,
                "size": len(chunk),
            })
            try:
                signal_response = self.grok_client.analyze_signal(
                    event_id=f"{event_id}_chunk{chunk_num}",
                    tweets=[t.to_dict() if hasattr(t, 'to_dict') else t for t in chunk],
                    filters_used=["direct_search"],
                    context=event_description
                )
                log(f"    ✓ Signal: {signal_response.overall_signal_strength:.1f}/100")
                log(f"    ✓ Sentiment: {signal_response.metrics.dominant_sentiment}")
                all_analyses.append(signal_response)
                hook("chunk_succeeded", {
                    "event_id": event_id,
                    "chunk": chunk_num,
                    "total_chunks": total_chunks,
                    "signal": signal_response.overall_signal_strength,
                    "sentiment": str(signal_response.metrics.dominant_sentiment),
                })
            except Exception as e:
                log(f"    ✗ Analysis failed: {e}")
                hook("chunk_failed", {
                    "event_id": event_id,
                    "chunk": chunk_num,
                    "total_chunks": total_chunks,
                    "error": str(e),
                })
                continue

        log(f"\n{'='*80}")
        log(f"RESULTS")
        log(f"{'='*80}\n")

        if all_analyses:
            # Aggregate results
            avg_signal = sum(a.overall_signal_strength for a in all_analyses) / len(all_analyses)
            log(f"✅ Analyzed {len(all_analyses)} chunks")
            log(f"   Average Signal: {avg_signal:.1f}/100")
            hook("analysis_complete", {
                "event_id": event_id,
                "chunks": len(all_analyses),
                "avg_signal": avg_signal,
            })
            
            # Show each chunk
            for i, analysis in enumerate(all_analyses, 1):
                log(f"\n   Chunk {i}:")
                log(f"      Signal: {analysis.overall_signal_strength:.1f}/100")
                log(f"      Sentiment: {analysis.metrics.dominant_sentiment}")
                log(f"      Themes: {', '.join(analysis.metrics.key_themes[:3])}")
                log(f"      Implication: {analysis.prediction_market_implication[:100]}...")
            
            return {
                "status": "success",
                "event_id": event_id,
                "tweets_collected": len(tweets_collected),
                "chunks_analyzed": len(all_analyses),
                "avg_signal": avg_signal,
                "chunk_analyses": [a.to_dict() for a in all_analyses]
            }
        else:
            log(f"⚠️  No successful analyses")
            hook("analysis_complete", {
                "event_id": event_id,
                "chunks": 0,
                "avg_signal": 0.0,
            })
            return {
                "status": "partial",
                "event_id": event_id,
                "tweets_collected": len(tweets_collected),
                "chunks_analyzed": 0
            }

    def process_event(
        self,
        event_description: str,
        prediction_markets: Optional[List[str]] = None,
        event_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Complete pipeline: Event → Filters → Tweets → Signal → Persist.
        
        Args:
            event_description: Description of the prediction event
            prediction_markets: Optional list of relevant markets
            event_id: Optional event ID (generated if not provided)
        
        Returns:
            Dictionary with complete pipeline results
        """
        # Generate event ID if not provided
        if not event_id:
            event_id = f"event_{uuid.uuid4().hex[:8]}"

        print(f"\n{'='*80}")
        print(f"PIPELINE START: {event_id}")
        print(f"{'='*80}\n")

        # ====================================================================
        # STEP 1: Event → Filter Selection
        # ====================================================================
        print(f"[1/4] Selecting filters for: {event_description}")
        try:
            filter_response = self.grok_client.select_filters(
                event_id=event_id,
                event_description=event_description,
                prediction_markets=prediction_markets
            )
            print(f"✓ Selected {len(filter_response.recommended_filters)} filters")
            print(f"  Reasoning: {filter_response.reasoning}\n")
        except Exception as e:
            print(f"✗ Filter selection failed: {e}\n")
            return {"status": "error", "error": str(e), "event_id": event_id}

        # ====================================================================
        # STEP 2: Filters → Raw Tweets
        # ====================================================================
        print(f"[2/4] Executing filters to collect tweets...")
        try:
            tweets_result = self._execute_filters(
                event_id=event_id,
                filter_response=filter_response
            )
            print(f"✓ Collected {tweets_result.total_tweets} tweets")
            print(f"  Filters executed: {[f.value for f in tweets_result.filters_executed]}\n")
        except Exception as e:
            print(f"✗ Tweet collection failed: {e}\n")
            return {"status": "error", "error": str(e), "event_id": event_id}

        # Return early if no tweets collected
        if tweets_result.total_tweets == 0:
            print("⚠ No tweets collected. Skipping signal analysis.\n")
            return {
                "status": "no_tweets",
                "event_id": event_id,
                "filter_response": filter_response.to_dict(),
                "tweets_result": tweets_result.to_dict()
            }

        # ====================================================================
        # STEP 3: Tweets → Signal Analysis
        # ====================================================================
        print(f"[3/4] Analyzing signal from tweets...")
        signal_response = None
        try:
            # Prepare tweets for Grok (convert to dict format)
            tweet_dicts = [t.to_dict() for t in tweets_result.tweets_collected]
            
            signal_response = self.grok_client.analyze_signal(
                event_id=event_id,
                tweets=tweet_dicts,
                filters_used=[f.value for f in tweets_result.filters_executed],
                context=event_description
            )
            print(f"✓ Signal strength: {signal_response.overall_signal_strength}/100")
            print(f"  Dominant sentiment: {signal_response.metrics.dominant_sentiment.value}")
            print(f"  Confidence: {signal_response.signal_confidence.value}")
            print(f"  Implication: {signal_response.prediction_market_implication}\n")
        except Exception as e:
            print(f"⚠️  Signal analysis failed: {e}")
            print(f"  Proceeding with tweet data only\n")
            signal_response = None

        # ====================================================================
        # STEP 4: Signal → Persistence
        # ====================================================================
        timeseries = None
        if signal_response:
            print(f"[4/4] Persisting signal snapshot...")
            try:
                timeseries = self._persist_signal(
                    event_id=event_id,
                    event_description=event_description,
                    signal_response=signal_response
                )
                print(f"✓ Signal persisted")
                print(f"  Trend: {timeseries.trend}")
                print(f"  Total snapshots: {len(timeseries.snapshots)}\n")
            except Exception as e:
                print(f"⚠️  Signal persistence failed: {e}\n")

        print(f"{'='*80}")
        print(f"PIPELINE COMPLETE: {event_id}")
        print(f"{'='*80}\n")

        # Return complete pipeline results
        return {
            "status": "success",
            "event_id": event_id,
            "event_description": event_description,
            "filter_response": filter_response.to_dict(),
            "tweets_result": tweets_result.to_dict(),
            "signal_response": signal_response.to_dict() if signal_response else None,
            "timeseries": timeseries.to_dict() if timeseries else None
        }

    def _execute_filters(
        self,
        event_id: str,
        filter_response: FilterSelectionResponse
    ) -> TweetCollectionResult:
        """
        Execute selected filters against the X API.
        
        This is where we actually search for tweets using the recommended filters.
        """
        # Sort by priority
        sorted_filters = sorted(
            filter_response.recommended_filters,
            key=lambda x: x.priority
        )

        all_tweets = []
        executed_filters = []

        # Execute each filter in priority order
        for filter_rec in sorted_filters:
            filter_type = filter_rec.filter_type
            executed_filters.append(filter_type)

            # Use custom query if provided, otherwise use default
            query = filter_rec.custom_query or self._get_default_query(filter_type)

            print(f"  • Executing {filter_type.value}: {query[:60]}...")

            try:
                tweets = self._search_tweets(query)
                for tweet in tweets:
                    tweet_obj = TweetData(
                        tweet_id=tweet.get("id", ""),
                        text=tweet.get("text", ""),
                        author_id=tweet.get("author_id", ""),
                        author_username=tweet.get("author_username", "unknown"),
                        created_at=tweet.get("created_at", ""),
                        matching_filters=[filter_type.value],
                        is_verified=tweet.get("is_verified", False),
                        is_retweet=tweet.get("is_retweet", False),
                        engagement_metrics=tweet.get("engagement_metrics", {})
                    )
                    all_tweets.append(tweet_obj)

            except Exception as e:
                print(f"    (Error: {e})")
                continue

        return TweetCollectionResult(
            event_id=event_id,
            filters_executed=executed_filters,
            tweets_collected=all_tweets,
            total_tweets=len(all_tweets),
            timestamp=datetime.utcnow().isoformat()
        )

    def _search_tweets(self, query: str, *, max_results: int = 100) -> List[Dict[str, Any]]:
        """
        Execute a tweet search using the X API via `tweets.runner.search_recent`.

        Returns a normalized list of tweet dictionaries. Raises a RuntimeError
        if required dependencies or environment variables are missing.
        """
        if search_recent is None:
            raise RuntimeError(
                "tweets.runner.search_recent is unavailable. "
                "Ensure the tweets package is installed and on PYTHONPATH."
            )

        bearer = os.getenv("X_BEARER_TOKEN")
        if not bearer:
            raise RuntimeError("X_BEARER_TOKEN is not set; cannot query X API.")

        tweets = search_recent(query, max_results=max_results)
        normalized: List[Dict[str, Any]] = []

        for tweet in tweets:
            if isinstance(tweet, dict):
                normalized.append(tweet)
                continue

            normalized.append({
                "id": getattr(tweet, "id", ""),
                "text": getattr(tweet, "text", ""),
                "author_id": getattr(tweet, "author_id", ""),
                "author_username": getattr(tweet, "username", "unknown"),
                "created_at": getattr(tweet, "created_at", ""),
                "is_verified": getattr(tweet, "is_verified", False),
                "is_retweet": getattr(tweet, "is_retweet", False),
                "engagement_metrics": getattr(tweet, "engagement_metrics", {}),
            })

        return normalized

    def _get_default_query(self, filter_type: FilterType) -> str:
        """Get the default query for a filter type"""
        default_queries = {
            FilterType.MARKET_LINKS: "(url:polymarket.com OR url:kalshi.com) -is:retweet",
            FilterType.BREAKING_NEWS: "(\"breaking news\" OR \"just announced\") is:verified -is:retweet lang:en",
            FilterType.RESOLUTION_LANGUAGE: "(\"officially announced\" OR \"declared winner\") is:verified -is:retweet",
            FilterType.NEWS_AGENCIES: "(from:AP OR from:Reuters OR from:Bloomberg) -is:retweet",
            FilterType.FINANCE_CRYPTO: "(bitcoin OR ethereum) (ETF OR approval OR SEC) is:verified -is:retweet",
        }
        return default_queries.get(filter_type, "")

    def _persist_signal(
        self,
        event_id: str,
        event_description: str,
        signal_response: SignalAnalysisResponse
    ) -> EventSignalTimeSeries:
        """
        Create or update the time-series tracking for this event.
        """
        # Create snapshot from signal analysis
        snapshot = SignalSnapshot(
            timestamp=signal_response.analysis_timestamp,
            signal_strength=signal_response.overall_signal_strength,
            sentiment=signal_response.metrics.dominant_sentiment,
            tweet_count=signal_response.metrics.total_tweets_analyzed,
            engagement_score=signal_response.metrics.engagement_score,
            key_themes=signal_response.metrics.key_themes
        )

        # Get or create timeseries
        if event_id not in self.event_timeseries:
            self.event_timeseries[event_id] = EventSignalTimeSeries(
                event_id=event_id,
                event_description=event_description,
                created_at=datetime.utcnow().isoformat(),
                snapshots=[],
                current_signal_strength=0.0,
                trend="stable"
            )

        timeseries = self.event_timeseries[event_id]
        timeseries.add_snapshot(snapshot)
        timeseries.trend = timeseries.get_signal_trend()

        return timeseries

    def get_event_timeseries(self, event_id: str) -> Optional[EventSignalTimeSeries]:
        """Get the signal time-series for an event"""
        return self.event_timeseries.get(event_id)

    def get_all_timeseries(self) -> Dict[str, EventSignalTimeSeries]:
        """Get all tracked event time-series"""
        return self.event_timeseries

    def save_timeseries(self, filepath: str) -> None:
        """Save all event time-series to a JSON file"""
        data = {
            event_id: ts.to_dict()
            for event_id, ts in self.event_timeseries.items()
        }
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=str)

    def close(self):
        """Close the Grok client"""
        self.grok_client.close()

