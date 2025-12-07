"""
Structured response schemas for each step of the pipeline.
These define the exact JSON structure Grok should return.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import json


class FilterType(str, Enum):
    """Available filter types"""
    MARKET_LINKS = "market_links"
    BREAKING_NEWS = "breaking_news_verified"
    RESOLUTION_LANGUAGE = "resolution_language"
    NEWS_AGENCIES = "news_agencies"
    FINANCE_CRYPTO = "finance_crypto_events"


class SignalSentiment(str, Enum):
    """Signal sentiment classification"""
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    MIXED = "mixed"


class ConfidenceLevel(str, Enum):
    """Confidence in the signal"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ============================================================================
# STEP 1: Event → Filter Selection
# ============================================================================

@dataclass
class FilterRecommendation:
    """A single filter recommendation from Grok"""
    filter_type: FilterType
    justification: str
    priority: int  # 1-5, where 1 is highest priority
    confidence: ConfidenceLevel
    custom_query: Optional[str] = None  # Override default query if provided

    def to_dict(self) -> Dict[str, Any]:
        return {
            "filter_type": self.filter_type.value,
            "justification": self.justification,
            "priority": self.priority,
            "confidence": self.confidence.value,
            "custom_query": self.custom_query
        }


@dataclass
class FilterSelectionResponse:
    """Grok's response: which filters to apply for this event"""
    event_id: str
    event_description: str
    recommended_filters: List[FilterRecommendation]
    reasoning: str  # Overall strategy explanation
    estimated_signal_volume: str  # "low", "medium", "high"
    search_time_window: str  # e.g., "last_24h", "last_7d"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_description": self.event_description,
            "recommended_filters": [f.to_dict() for f in self.recommended_filters],
            "reasoning": self.reasoning,
            "estimated_signal_volume": self.estimated_signal_volume,
            "search_time_window": self.search_time_window
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "FilterSelectionResponse":
        """Parse Grok's response into this schema"""
        filters = []
        for f in data["recommended_filters"]:
            filter_type_str = f["filter_type"].lower().replace("_", "_")
            # Try to match to our enum
            try:
                filter_type = FilterType(filter_type_str)
            except ValueError:
                # If exact match fails, try common variations
                mapping = {
                    "market_links": FilterType.MARKET_LINKS,
                    "breaking_news": FilterType.BREAKING_NEWS,
                    "news": FilterType.NEWS_AGENCIES,
                    "resolution_language": FilterType.RESOLUTION_LANGUAGE,
                    "finance": FilterType.FINANCE_CRYPTO,
                    "crypto": FilterType.FINANCE_CRYPTO,
                }
                filter_type = mapping.get(filter_type_str, FilterType.MARKET_LINKS)
            
            filters.append(FilterRecommendation(
                filter_type=filter_type,
                justification=f["justification"],
                priority=f["priority"],
                confidence=ConfidenceLevel(f["confidence"].lower()),
                custom_query=f.get("custom_query")
            ))
        return FilterSelectionResponse(
            event_id=data["event_id"],
            event_description=data["event_description"],
            recommended_filters=filters,
            reasoning=data["reasoning"],
            estimated_signal_volume=data["estimated_signal_volume"],
            search_time_window=data["search_time_window"]
        )


# ============================================================================
# STEP 2: Filters → Raw Tweets (internal, not from Grok)
# ============================================================================

@dataclass
class TweetData:
    """A single tweet from the search results"""
    tweet_id: str
    text: str
    author_id: str
    author_username: str
    created_at: str
    matching_filters: List[str]  # Which filters this tweet matched
    is_verified: bool
    is_retweet: bool
    engagement_metrics: Dict[str, int]  # likes, retweets, replies, quotes

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tweet_id": self.tweet_id,
            "text": self.text,
            "author_id": self.author_id,
            "author_username": self.author_username,
            "created_at": self.created_at,
            "matching_filters": self.matching_filters,
            "is_verified": self.is_verified,
            "is_retweet": self.is_retweet,
            "engagement_metrics": self.engagement_metrics
        }


@dataclass
class TweetCollectionResult:
    """Result from executing filters and collecting tweets"""
    event_id: str
    filters_executed: List[FilterType]
    tweets_collected: List[TweetData]
    total_tweets: int
    timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "filters_executed": [f.value for f in self.filters_executed],
            "tweets_collected": [t.to_dict() for t in self.tweets_collected],
            "total_tweets": self.total_tweets,
            "timestamp": self.timestamp
        }


# ============================================================================
# STEP 3: Tweets → Signal Analysis (Grok analyzes sentiment/signal)
# ============================================================================

@dataclass
class SignalMetrics:
    """Quantified metrics from tweet analysis"""
    total_tweets_analyzed: int
    verified_tweets: int
    engagement_score: float  # 0-100, weighted by likes/retweets
    sentiment_breakdown: Dict[SignalSentiment, int]  # Count per sentiment
    dominant_sentiment: SignalSentiment
    key_themes: List[str]  # Extracted themes/topics
    top_mentioned_entities: List[str]  # Companies, people, events mentioned

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_tweets_analyzed": self.total_tweets_analyzed,
            "verified_tweets": self.verified_tweets,
            "engagement_score": self.engagement_score,
            "sentiment_breakdown": {s.value: c for s, c in self.sentiment_breakdown.items()},
            "dominant_sentiment": self.dominant_sentiment.value,
            "key_themes": self.key_themes,
            "top_mentioned_entities": self.top_mentioned_entities
        }


@dataclass
class SignalAnalysisResponse:
    """Grok's analysis of tweets: quantified signal strength"""
    event_id: str
    analysis_timestamp: str
    metrics: SignalMetrics
    overall_signal_strength: float  # 0-100
    signal_confidence: ConfidenceLevel
    interpretation: str  # Human-readable explanation
    prediction_market_implication: str  # What this means for prediction markets
    recommended_next_steps: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "analysis_timestamp": self.analysis_timestamp,
            "metrics": self.metrics.to_dict(),
            "overall_signal_strength": self.overall_signal_strength,
            "signal_confidence": self.signal_confidence.value,
            "interpretation": self.interpretation,
            "prediction_market_implication": self.prediction_market_implication,
            "recommended_next_steps": self.recommended_next_steps
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "SignalAnalysisResponse":
        """Parse Grok's response into this schema"""
        sentiment_breakdown = {
            SignalSentiment(s): c
            for s, c in data["metrics"]["sentiment_breakdown"].items()
        }
        metrics = SignalMetrics(
            total_tweets_analyzed=data["metrics"]["total_tweets_analyzed"],
            verified_tweets=data["metrics"]["verified_tweets"],
            engagement_score=data["metrics"]["engagement_score"],
            sentiment_breakdown=sentiment_breakdown,
            dominant_sentiment=SignalSentiment(data["metrics"]["dominant_sentiment"]),
            key_themes=data["metrics"]["key_themes"],
            top_mentioned_entities=data["metrics"]["top_mentioned_entities"]
        )
        return SignalAnalysisResponse(
            event_id=data["event_id"],
            analysis_timestamp=data["analysis_timestamp"],
            metrics=metrics,
            overall_signal_strength=data["overall_signal_strength"],
            signal_confidence=ConfidenceLevel(data["signal_confidence"]),
            interpretation=data["interpretation"],
            prediction_market_implication=data["prediction_market_implication"],
            recommended_next_steps=data["recommended_next_steps"]
        )


# ============================================================================
# STEP 4: Signal Persistence & Time-Series Tracking
# ============================================================================

@dataclass
class SignalSnapshot:
    """A single point-in-time snapshot of signal for an event"""
    timestamp: str
    signal_strength: float  # 0-100
    sentiment: SignalSentiment
    tweet_count: int
    engagement_score: float
    key_themes: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "signal_strength": self.signal_strength,
            "sentiment": self.sentiment.value,
            "tweet_count": self.tweet_count,
            "engagement_score": self.engagement_score,
            "key_themes": self.key_themes
        }


@dataclass
class EventSignalTimeSeries:
    """Track signal evolution for a single event over time"""
    event_id: str
    event_description: str
    created_at: str
    snapshots: List[SignalSnapshot]
    current_signal_strength: float
    trend: str  # "increasing", "decreasing", "stable"
    estimated_resolution_time: Optional[str] = None

    def add_snapshot(self, snapshot: SignalSnapshot) -> None:
        """Add a new signal reading"""
        self.snapshots.append(snapshot)
        self.current_signal_strength = snapshot.signal_strength

    def get_signal_trend(self) -> str:
        """Calculate trend from recent snapshots"""
        if len(self.snapshots) < 2:
            return "insufficient_data"
        
        recent = self.snapshots[-5:]  # Last 5 snapshots
        if len(recent) < 2:
            return "insufficient_data"
        
        avg_recent = sum(s.signal_strength for s in recent) / len(recent)
        avg_before = sum(s.signal_strength for s in self.snapshots[:-5]) / (len(self.snapshots) - 5) if len(self.snapshots) > 5 else avg_recent
        
        if avg_recent > avg_before * 1.1:
            return "increasing"
        elif avg_recent < avg_before * 0.9:
            return "decreasing"
        else:
            return "stable"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_description": self.event_description,
            "created_at": self.created_at,
            "snapshots": [s.to_dict() for s in self.snapshots],
            "current_signal_strength": self.current_signal_strength,
            "trend": self.trend,
            "estimated_resolution_time": self.estimated_resolution_time
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, default=str)


# ============================================================================
# Prompts for Grok (structured instructions)
# ============================================================================

FILTER_SELECTION_SYSTEM_PROMPT = """
You are an expert in prediction market signal detection. Given a prediction event, 
you must intelligently select which filters to apply to detect high-signal tweets about that event.

Available filters:
1. MARKET_LINKS: Direct links to polymarket.com, kalshi.com, manifold.markets
2. BREAKING_NEWS: Verified accounts sharing breaking news/announcements
3. RESOLUTION_LANGUAGE: "Officially announced", "declared winner", "confirmed"
4. NEWS_AGENCIES: AP, Reuters, Bloomberg, major news outlets
5. FINANCE_CRYPTO: Crypto/finance specific events (ETF approvals, SEC decisions)

For each event, respond with a JSON object containing:
- event_id: Unique identifier for this event
- event_description: What the event is
- recommended_filters: Array of filter recommendations, each with:
  - filter_type: One of the filter types above
  - justification: Why this filter is appropriate
  - priority: 1-5 (1=highest priority)
  - confidence: "high", "medium", or "low"
  - custom_query: Optional custom query override
- reasoning: Overall strategy explanation
- estimated_signal_volume: "low", "medium", or "high"
- search_time_window: "last_24h", "last_7d", or "last_30d"

Be specific and strategic. Only recommend filters that will catch relevant signals.
"""

SIGNAL_ANALYSIS_SYSTEM_PROMPT = """
You are an expert financial analyst specializing in prediction market signal analysis.
Given a set of tweets collected about a prediction market event, you must:

1. Analyze sentiment (bullish, bearish, neutral, mixed)
2. Quantify signal strength (0-100)
3. Extract key themes and entities
4. Calculate engagement metrics
5. Assess confidence in your analysis
6. Provide market implications

Respond with a JSON object containing:
- event_id: Event being analyzed
- analysis_timestamp: When this analysis was performed
- metrics: Detailed metrics including:
  - total_tweets_analyzed: Number of tweets
  - verified_tweets: Count of verified account tweets
  - engagement_score: 0-100, weighted by engagement
  - sentiment_breakdown: Counts per sentiment
  - dominant_sentiment: Most common sentiment
  - key_themes: Top themes extracted from tweets
  - top_mentioned_entities: Important entities mentioned
- overall_signal_strength: 0-100 confidence that event will resolve
- signal_confidence: "high", "medium", or "low"
- interpretation: Plain English explanation of what the data shows
- prediction_market_implication: What this means for betting/markets
- recommended_next_steps: Array of recommended actions

Be analytical and quantitative. Avoid speculation.
"""

