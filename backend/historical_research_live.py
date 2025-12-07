"""
Historical Research with LIVE Grok API Integration

This version actually calls the xAI API to answer historical questions.
"""

import json
import os
import asyncio
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from enum import Enum
from pathlib import Path

# Load .env file
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / '.env'
    load_dotenv(env_path)
except ImportError:
    # dotenv not installed, try manual loading
    env_path = Path(__file__).parent / '.env'
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value

# Import existing models
from historical_research import (
    SentimentEnum,
    ConfidenceEnum,
    HistoricalQuestion,
    HistoricalQuestionnaires,
    SignalData,
    HistoricalAnalysisResponse,
    generate_historical_questions
)

# Import Grok client
from grok_pipeline.grok_client import GrokClient


class HistoricalPrecedent(BaseModel):
    """Specific historical event cited as precedent"""
    event_name: str
    date_range: str
    key_metrics: str  # e.g. "11.7 km/day", "50,000 casualties"
    relevance_explanation: str


class HistoricalAnswer(BaseModel):
    """Structured answer to a historical research question"""
    direct_answer: str
    historical_precedents: List[HistoricalPrecedent]
    quantitative_analysis: str
    confidence: ConfidenceEnum
    signal_direction: SentimentEnum
    signal_strength: float = Field(..., ge=0, le=100)


HISTORICAL_ANALYSIS_SYSTEM_PROMPT = """You are a military historian and geopolitical analyst specializing in quantitative conflict analysis and Reference Class Forecasting.

Your goal is to provide objective, data-driven analysis of future events based on historical precedents.

METHODOLOGY:
1. Base Rates: Always start with the "outside view". How often does this type of event happen historically?
2. Reference Classes: Identify the correct class of historical events to compare against.
3. Quantitative Constraints: Look for hard mathematical limits (logistics, distance, speed, economic output).
4. Devil's Advocate: Actively look for evidence that contradicts your initial intuition.

For each answer:
- Cite specific historical precedents with dates and numbers.
- Provide confidence levels based on data quality.
- Distinguish between "possibility" and "probability".
"""

QUESTION_GENERATION_PROMPT = """You are a Senior Research Director planning an investigation into a geopolitical event.

EVENT: {event_description}
DEADLINE: {event_deadline}
CONTEXT: {context}

Your task is to generate {num_questions} targeted research questions that will determine the outcome of this event.

TYPES OF QUESTIONS TO GENERATE:
1. Base Rate / Precedent: "How often has X happened in the past 50 years?"
2. Logistical/Physical Constraints: "Is it mathematically possible to achieve X given Y speed/rate?"
3. Comparative Analysis: "Compare this to [Specific Historical Event]. What is different?"
4. Signposts: "What specific observable indicators would confirm X is happening?"
5. Failure Modes: "What are the most common reasons similar attempts have failed?"

Return a JSON object with a list of questions. Each question must have:
- category: A short uppercase string (e.g., "LOGISTICS", "PRECEDENT")
- question_text: The detailed question to ask.
- context_requirements: What data is needed to answer it.

JSON SCHEMA:
{{
  "questions": [
    {{
      "category": "CATEGORY_NAME",
      "question_text": "...",
      "context_requirements": "..."
    }}
  ]
}}
"""

DEEP_DIVE_PROMPT = """The initial research has returned the following findings, but confidence is not yet definitive.

EVENT: {event_description}

CURRENT FINDINGS:
{findings_summary}

Identify the SINGLE most critical missing piece of information or the biggest uncertainty remaining.
Generate 2 targeted follow-up questions to resolve this uncertainty.

Return JSON:
{{
  "questions": [
    {{
      "category": "DEEP_DIVE_1",
      "question_text": "...",
      "context_requirements": "..."
    }},
    ...
  ]
}}
"""


# --- Singleton GrokClient ---
# The GrokClient is stateless (no conversation context).
# Each _call_grok creates fresh messages.
# Reusing the client avoids HTTP connection pool recreation.

_singleton_grok_client: Optional[GrokClient] = None
_singleton_grok_api_key: Optional[str] = None


def _get_singleton_grok_client(api_key: Optional[str] = None) -> GrokClient:
    """Get or create singleton GrokClient for historical research."""
    global _singleton_grok_client, _singleton_grok_api_key
    
    resolved_key = api_key or os.getenv("GROK_API_KEY")
    if not resolved_key:
        raise ValueError("GROK_API_KEY not found in environment variables")
    
    # Reinitialize if API key changed
    if _singleton_grok_client is None or _singleton_grok_api_key != resolved_key:
        print("🔧 Initializing GrokClient for historical research (singleton)...")
        _singleton_grok_client = GrokClient(api_key=resolved_key)
        _singleton_grok_api_key = resolved_key
        print("✅ GrokClient ready for historical research")
    
    return _singleton_grok_client


class HistoricalResearchClient:
    """Client for conducting historical research using Grok API"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize research client.
        
        Args:
            api_key: Grok API key (defaults to GROK_API_KEY env var)
        """
        self.api_key = api_key or os.getenv("GROK_API_KEY")
        if not self.api_key:
            raise ValueError("GROK_API_KEY not found in environment variables")
        
        # Use singleton GrokClient (avoids reinitializing HTTP client on every call)
        self.grok_client = _get_singleton_grok_client(self.api_key)
    
    async def __aenter__(self):
        """Async context manager entry - client already initialized in __init__"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - no cleanup needed for singleton"""
        # Don't close the singleton client - it's reused across calls
        pass
    
    async def research_event(
        self,
        event_description: str,
        event_id: str,
        event_deadline: Optional[str] = None,
        distance_km: Optional[float] = None,
        days_remaining: Optional[int] = None
    ) -> HistoricalAnalysisResponse:
        """Original non-streaming method (maintained for backward compatibility)"""
        # Collect all chunks from stream and return final result
        final_result = None
        async for event in self.stream_research_event(event_description, event_id, event_deadline, distance_km, days_remaining):
            if event["type"] == "result":
                final_result = event["data"]
            elif event["type"] == "log":
                print(f"[{event['type']}] {event['message']}")
        return final_result

    async def stream_research_event(
        self,
        event_description: str,
        event_id: str,
        event_deadline: Optional[str] = None,
        distance_km: Optional[float] = None,
        days_remaining: Optional[int] = None
    ):
        """
        Conduct full historical research, yielding progress updates.
        Yields:
            {"type": "log", "message": "..."}
            {"type": "result", "data": HistoricalAnalysisResponse}
        """
        # Step 1: Generate dynamic questions
        yield {"type": "log", "message": f"🤖 Generating research plan for: {event_description}"}
        
        questionnaire = await self._generate_questions_with_grok(
            event_description=event_description,
            event_id=event_id,
            event_deadline=event_deadline,
            distance_km=distance_km,
            days_remaining=days_remaining
        )
        
        yield {"type": "log", "message": f"📋 Generated {questionnaire.total_questions} research questions"}
        yield {"type": "log", "message": "🤖 Querying Grok API for historical analysis..."}
        
        # Step 2: Ask Grok all questions and collect answers
        answers = []
        for i, question in enumerate(questionnaire.questions, 1):
            yield {"type": "log", "message": f"  [{i}/{questionnaire.total_questions}] Investigating: {question.category}..."}
            
            answer = await self._ask_question(question, questionnaire)
            answers.append({
                "question": question,
                "answer": answer
            })
            yield {"type": "log", "message": f"  ✓ Answered: {question.category}"}
        
        # Step 3: Deep Dive Check (Iterative Research)
        yield {"type": "log", "message": "🕵️  Analyzing initial findings for gaps..."}
        
        deep_dive_questions = await self._generate_followup_questions(
            questionnaire=questionnaire,
            answers=answers
        )
        
        if deep_dive_questions:
            yield {"type": "log", "message": f"🔍 Deep Dive: Generated {len(deep_dive_questions)} follow-up questions"}
            for i, question in enumerate(deep_dive_questions, 1):
                yield {"type": "log", "message": f"  [DD-{i}] Investigating: {question.category}..."}
                answer = await self._ask_question(question, questionnaire)
                answers.append({
                    "question": question,
                    "answer": answer
                })
                yield {"type": "log", "message": f"  ✓ Answered: {question.category}"}
        
        yield {"type": "log", "message": "🧠 Synthesizing final analysis..."}
        
        # Step 4: Ask Grok to synthesize all answers into structured response
        final_response = await self._synthesize_analysis(
            questionnaire=questionnaire,
            answers=answers
        )
        
        yield {"type": "result", "data": final_response}

    async def _generate_questions_with_grok(
        self,
        event_description: str,
        event_id: str,
        event_deadline: Optional[str],
        distance_km: Optional[float],
        days_remaining: Optional[int]
    ) -> HistoricalQuestionnaires:
        """Dynamically generate research questions using Grok"""
        
        context_parts = []
        if distance_km:
            context_parts.append(f"Distance: {distance_km} km")
        if days_remaining:
            context_parts.append(f"Days Remaining: {days_remaining}")
        if distance_km and days_remaining:
            req_pace = distance_km / days_remaining
            context_parts.append(f"Required Pace: {req_pace:.2f} km/day")
            
        context_str = ", ".join(context_parts)
        
        user_prompt = QUESTION_GENERATION_PROMPT.format(
            event_description=event_description,
            event_deadline=event_deadline or "Not specified",
            context=context_str,
            num_questions=6  # Ask for 6 high-quality questions
        )
        
        response = await self.grok_client._call_grok(
            system_prompt="You are a research planner.",
            user_prompt=user_prompt,
            temperature=0.4,
            expect_json=True
        )
        
        # Parse response into HistoricalQuestion objects
        questions = []
        for i, q_data in enumerate(response.get("questions", []), 1):
            questions.append(HistoricalQuestion(
                question_number=i,
                category=q_data.get("category", "GENERAL"),
                question_text=q_data.get("question_text"),
                context_requirements=q_data.get("context_requirements", "")
            ))
            
        return HistoricalQuestionnaires(
            event_id=event_id,
            event_description=event_description,
            event_deadline=event_deadline,
            distance_to_objective_km=distance_km,
            days_remaining=days_remaining,
            required_daily_advance_km=(distance_km/days_remaining) if (distance_km and days_remaining) else None,
            questions=questions,
            total_questions=len(questions)
        )

    async def _generate_followup_questions(
        self,
        questionnaire: HistoricalQuestionnaires,
        answers: List[dict]
    ) -> List[HistoricalQuestion]:
        """Generate follow-up questions based on initial findings"""
        
        # Summarize findings for the prompt
        findings_summary = ""
        for item in answers:
            q = item['question']
            a = item['answer']
            findings_summary += f"Q: {q.question_text}\nA: {a.direct_answer} (Confidence: {a.confidence})\n\n"
            
        user_prompt = DEEP_DIVE_PROMPT.format(
            event_description=questionnaire.event_description,
            findings_summary=findings_summary
        )
        
        try:
            response = await self.grok_client._call_grok(
                system_prompt="You are a senior analyst identifying gaps in research.",
                user_prompt=user_prompt,
                temperature=0.4,
                expect_json=True
            )
            
            questions = []
            start_idx = questionnaire.total_questions + 1
            for i, q_data in enumerate(response.get("questions", []), start_idx):
                questions.append(HistoricalQuestion(
                    question_number=i,
                    category=q_data.get("category", "DEEP_DIVE"),
                    question_text=q_data.get("question_text"),
                    context_requirements=q_data.get("context_requirements", "")
                ))
            return questions
            
        except Exception as e:
            print(f"⚠️ Failed to generate deep dive questions: {e}")
            return []
    
    async def _ask_question(
        self,
        question: HistoricalQuestion,
        questionnaire: HistoricalQuestionnaires
    ) -> HistoricalAnswer:
        """Ask Grok a single historical question and get structured JSON"""
        
        context = f"""
Event: {questionnaire.event_description}
Deadline: {questionnaire.event_deadline or 'Not specified'}
Distance: {questionnaire.distance_to_objective_km or 'N/A'} km
Days Remaining: {questionnaire.days_remaining or 'N/A'}
Required Daily Advance: {questionnaire.required_daily_advance_km or 'N/A'} km/day

Question Category: {question.category}
"""
        
        # Get schema for strict JSON adherence
        schema = HistoricalAnswer.model_json_schema()
        
        user_prompt = f"""
{context}

QUESTION:
{question.question_text}

Provide your answer as a valid JSON object matching this schema:
{json.dumps(schema, indent=2)}

Ensure all fields are filled. For 'signal_strength', provide a value 0-100 where 0 is no signal and 100 is definitive proof.
"""
        
        # Call Grok API
        response_dict = await self.grok_client._call_grok(
            system_prompt=HISTORICAL_ANALYSIS_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.2,  # Low temp for factual analysis
            max_tokens=2000,
            expect_json=True
        )
        
        # Parse into Pydantic model
        return HistoricalAnswer.model_validate(response_dict)
    
    async def _synthesize_analysis(
        self,
        questionnaire: HistoricalQuestionnaires,
        answers: List[dict]
    ) -> HistoricalAnalysisResponse:
        """
        Ask Grok to synthesize all answers into final structured response.
        """
        
        # Format all Q&A for synthesis
        qa_text = ""
        for i, item in enumerate(answers):
            q = item['question']
            a = item['answer']  # This is now a HistoricalAnswer object
            
            qa_text += f"Q{i+1} [{q.category}]: {q.question_text}\n"
            qa_text += f"ANSWER: {a.direct_answer}\n"
            qa_text += f"QUANTITATIVE: {a.quantitative_analysis}\n"
            qa_text += f"SIGNAL: {a.signal_direction.value.upper()} (Strength: {a.signal_strength}/100)\n"
            qa_text += "PRECEDENTS:\n"
            for p in a.historical_precedents:
                qa_text += f"  - {p.event_name} ({p.date_range}): {p.key_metrics} - {p.relevance_explanation}\n"
            qa_text += "\n" + "-"*40 + "\n\n"
        
        synthesis_prompt = f"""
Based on the following historical research, provide a comprehensive analysis.

EVENT: {questionnaire.event_description}
DEADLINE: {questionnaire.event_deadline}
REQUIRED PACE: {questionnaire.required_daily_advance_km} km/day over {questionnaire.days_remaining} days

RESEARCH FINDINGS:
{qa_text}

Now synthesize this into a structured analysis with:

1. BULLISH SIGNALS (factors supporting the event happening):
   - List each signal with strength (0-100) and confidence level
   - Provide historical precedent for each

2. BEARISH SIGNALS (factors against the event happening):
   - List each signal with strength (0-100) and confidence level
   - Provide historical precedent for each

3. NEUTRAL OBSERVATIONS:
   - Key factors that could go either way

4. OVERALL ASSESSMENT:
   - Overall sentiment (bullish/bearish/neutral/mixed)
   - Overall signal strength (0-100)
   - Overall confidence level
   - Probability estimate (0-100)
   - Detailed reasoning for probability

5. CRITICAL PATH FACTORS:
   - What must happen for event to occur

6. RECOMMENDATION:
   - Clear trading/betting recommendation

Respond with ONLY valid JSON in this exact format:
{{
  "bullish_signals": [
    {{
      "signal_text": "...",
      "direction": "bullish",
      "strength": 45.0,
      "confidence": "high",
      "historical_precedent": "..."
    }}
  ],
  "bearish_signals": [...],
  "neutral_observations": ["...", "..."],
  "overall_sentiment": "bearish",
  "overall_signal_strength": 28.0,
  "overall_confidence": "high",
  "probability_estimate": 15.0,
  "probability_reasoning": "...",
  "critical_path_factors": ["...", "..."],
  "recommendation": "..."
}}
"""
        
        # Call Grok for synthesis
        response = await self.grok_client._call_grok(
            system_prompt=HISTORICAL_ANALYSIS_SYSTEM_PROMPT,
            user_prompt=synthesis_prompt,
            temperature=0.3,
            max_tokens=4000
        )
        
        # Helper to normalize confidence strings
        def normalize_confidence(conf_str: str) -> str:
            if not conf_str:
                return "medium"
            return conf_str.lower().replace(" ", "_")

        # Parse into HistoricalAnalysisResponse
        return HistoricalAnalysisResponse(
            event_id=questionnaire.event_id,
            event_description=questionnaire.event_description,
            analysis_timestamp=datetime.now().isoformat(),
            
            overall_sentiment=SentimentEnum(response["overall_sentiment"]),
            overall_signal_strength=response["overall_signal_strength"],
            overall_confidence=ConfidenceEnum(normalize_confidence(response["overall_confidence"])),
            
            bullish_signals=[
                SignalData(
                    signal_text=s["signal_text"],
                    direction=SentimentEnum(s["direction"]),
                    strength=s["strength"],
                    confidence=ConfidenceEnum(normalize_confidence(s["confidence"])),
                    historical_precedent=s["historical_precedent"]
                ) for s in response["bullish_signals"]
            ],
            bullish_confidence=ConfidenceEnum(
                normalize_confidence(response.get("bullish_confidence", "medium"))
            ),
            
            bearish_signals=[
                SignalData(
                    signal_text=s["signal_text"],
                    direction=SentimentEnum(s["direction"]),
                    strength=s["strength"],
                    confidence=ConfidenceEnum(normalize_confidence(s["confidence"])),
                    historical_precedent=s["historical_precedent"]
                ) for s in response["bearish_signals"]
            ],
            bearish_confidence=ConfidenceEnum(
                normalize_confidence(response.get("bearish_confidence", "medium"))
            ),
            
            neutral_observations=response["neutral_observations"],
            probability_estimate=response["probability_estimate"],
            probability_reasoning=response["probability_reasoning"],
            critical_path_factors=response["critical_path_factors"],
            recommendation=response["recommendation"]
        )


async def analyze_event_live(
    event_description: str,
    event_id: str,
    event_deadline: Optional[str] = None,
    distance_km: Optional[float] = None,
    days_remaining: Optional[int] = None
) -> HistoricalAnalysisResponse:
    """
    Convenience function to analyze an event with live Grok API.
    
    Example:
        response = await analyze_event_live(
            event_description="Will Russia capture Pokrovsk by Dec 31?",
            event_id="russia_pokrovsk_dec31",
            event_deadline="2024-12-31",
            distance_km=85,
            days_remaining=25
        )
    """
    async with HistoricalResearchClient() as client:
        return await client.research_event(
            event_description=event_description,
            event_id=event_id,
            event_deadline=event_deadline,
            distance_km=distance_km,
            days_remaining=days_remaining
        )


# Synchronous wrapper
def analyze_event_live_sync(
    event_description: str,
    event_id: str,
    event_deadline: Optional[str] = None,
    distance_km: Optional[float] = None,
    days_remaining: Optional[int] = None
) -> HistoricalAnalysisResponse:
    """Synchronous version of analyze_event_live"""
    return asyncio.run(
        analyze_event_live(
            event_description=event_description,
            event_id=event_id,
            event_deadline=event_deadline,
            distance_km=distance_km,
            days_remaining=days_remaining
        )
    )


# --- Sync Wrapper ---

def get_historical_analysis_sync(
    event_description: str,
    event_id: str = "demo_event",
    event_deadline: Optional[str] = None,
    days_remaining: Optional[int] = None,
    distance_to_objective_km: Optional[float] = None,
    required_daily_advance_km: Optional[float] = None
) -> HistoricalAnalysisResponse:
    """Synchronous wrapper for easy use in scripts/apps"""
    async def _run():
        async with HistoricalResearchClient() as client:
            return await client.research_event(
                event_description=event_description,
                event_id=event_id,
                event_deadline=event_deadline,
                days_remaining=days_remaining,
                distance_km=distance_to_objective_km
            )
    
    return asyncio.run(_run())


def stream_historical_analysis_sync(
    event_description: str, 
    event_id: str = "demo_event",
    event_deadline: Optional[str] = None,
    days_remaining: Optional[int] = None,
    distance_to_objective_km: Optional[float] = None
):
    """
    Synchronous generator for streaming historical analysis.
    Yields events: {"type": "log"|"result", ...}
    """
    async def _async_gen():
        async with HistoricalResearchClient() as client:
            async for event in client.stream_research_event(
                event_description=event_description,
                event_id=event_id,
                event_deadline=event_deadline,
                days_remaining=days_remaining,
                distance_km=distance_to_objective_km
            ):
                yield event

    # Manually run async generator in sync context
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        gen = _async_gen()
        while True:
            try:
                event = loop.run_until_complete(gen.__anext__())
                yield event
            except StopAsyncIteration:
                break
    finally:
        loop.close()


if __name__ == "__main__":
    # Demo with LIVE API
    print("=" * 80)
    print("LIVE HISTORICAL RESEARCH - Grok API Integration")
    print("=" * 80)
    print()
    
    # Check for API key
    if not os.getenv("GROK_API_KEY"):
        print("❌ ERROR: GROK_API_KEY not found in environment")
        print()
        print("Set your API key:")
        print("  export GROK_API_KEY='your-key-here'")
        print()
        exit(1)
    
    print("🔑 API Key found")
    print("🚀 Starting live analysis...")
    print()
    
    # Run live analysis
    # Example: South Korea Martial Law
    response = analyze_event_live_sync(
        event_description="Will the South Korean President be impeached before Jan 1, 2025?",
        event_id="sk_impeachment_jan1",
        event_deadline="2025-01-01",
        days_remaining=25
    )
    
    print()
    print("=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)
    print()
    print(f"Overall Sentiment: {response.overall_sentiment.value}")
    print(f"Signal Strength: {response.overall_signal_strength}/100")
    print(f"Confidence: {response.overall_confidence.value}")
    print(f"Probability: {response.probability_estimate}%")
    print()
    print(f"Bullish Signals: {len(response.bullish_signals)}")
    for signal in response.bullish_signals:
        print(f"  • {signal.signal_text} ({signal.strength}/100)")
    print()
    print(f"Bearish Signals: {len(response.bearish_signals)}")
    for signal in response.bearish_signals:
        print(f"  • {signal.signal_text} ({signal.strength}/100)")
    print()
    print("Recommendation:")
    print(f"  {response.recommendation}")
    print()
    
    # Save to JSON
    output_file = "historical_analysis_live.json"
    with open(output_file, "w") as f:
        json.dump(response.model_dump(), f, indent=2, default=str)
    
    print(f"💾 Full analysis saved to: {output_file}")
    print()
