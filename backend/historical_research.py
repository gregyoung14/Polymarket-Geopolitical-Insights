"""
Historical Research Question Generator and Analysis Framework

Self-contained module for generating historical research questions about 
geopolitical events and collecting structured analysis responses.
"""

import json
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from enum import Enum


class SentimentEnum(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    MIXED = "mixed"


class ConfidenceEnum(str, Enum):
    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


class HistoricalQuestion(BaseModel):
    """Individual historical research question"""
    question_number: int
    category: str
    question_text: str
    context_requirements: str
    can_fire_independently: bool = True


class HistoricalQuestionnaires(BaseModel):
    """List of historical questions for an event"""
    event_id: str
    event_description: str
    event_deadline: Optional[str] = None
    distance_to_objective_km: Optional[float] = None
    days_remaining: Optional[int] = None
    required_daily_advance_km: Optional[float] = None
    questions: List[HistoricalQuestion]
    total_questions: int


class SignalData(BaseModel):
    """Individual signal with direction and strength"""
    signal_text: str
    direction: SentimentEnum
    strength: float = Field(..., ge=0, le=100)  # 0-100
    confidence: ConfidenceEnum
    historical_precedent: str


class HistoricalAnalysisResponse(BaseModel):
    """Structured response from historical analysis"""
    event_id: str
    event_description: str
    analysis_timestamp: str
    
    # Overall assessment
    overall_sentiment: SentimentEnum
    overall_signal_strength: float = Field(..., ge=0, le=100)
    overall_confidence: ConfidenceEnum
    
    # Bullish signals
    bullish_signals: List[SignalData]
    bullish_confidence: ConfidenceEnum
    
    # Bearish signals
    bearish_signals: List[SignalData]
    bearish_confidence: ConfidenceEnum
    
    # Neutral observations
    neutral_observations: List[str]
    
    # Probability estimate
    probability_estimate: float = Field(..., ge=0, le=100)
    probability_reasoning: str
    
    # Key limiting factors
    critical_path_factors: List[str]
    
    # Recommendation
    recommendation: str


def generate_historical_questions(
    event_description: str,
    event_id: str,
    event_deadline: Optional[str] = None,
    distance_km: Optional[float] = None,
    days_remaining: Optional[int] = None
) -> HistoricalQuestionnaires:
    """
    Generate historical research questions for a geopolitical event.
    
    Args:
        event_description: Event description (e.g., "Will Russia capture Pokrovsk by Dec 31?")
        event_id: Unique event identifier
        event_deadline: Target date
        distance_km: Distance to objective in kilometers
        days_remaining: Days until deadline
    
    Returns:
        HistoricalQuestionnaires with all questions
    """
    
    required_daily_advance = None
    if distance_km and days_remaining and days_remaining > 0:
        required_daily_advance = distance_km / days_remaining
    
    # Build Q1 with optional distance/timeline info
    q1_text = f"Context: {event_description}"
    if distance_km and days_remaining and required_daily_advance:
        q1_text += f" Distance required: {distance_km} km in {days_remaining} days ({required_daily_advance:.1f} km/day)."
    q1_text += " In the entire Ukraine conflict since 2022, what is the fastest sustained advance rate Russia has achieved over a multi-week period? Cite specific operations with dates, distances, and daily rates. Then assess the feasibility of a rapid military operation achieving the stated objective."
    
    questions = [
        HistoricalQuestion(
            question_number=1,
            category="OFFENSIVE_PACE_PRECEDENT",
            question_text=q1_text,
            context_requirements="Access to military operations database, Ukraine conflict timeline, Russian advance rates"
        ),
        HistoricalQuestion(
            question_number=2,
            category="WINTER_WARFARE_IMPACT",
            question_text=f"Context: {event_description} This is winter in Eastern Ukraine (freezing temps, mud, reduced visibility). Historically, how much slower do Russian mechanized offensives move during winter months (December-February) compared to spring/summer? Provide specific data from 2022-23 and 2023-24 winter campaigns. What is the typical winter advance rate?",
            context_requirements="Seasonal warfare data, weather impact analysis, 2022-2024 operational records"
        ),
        HistoricalQuestion(
            question_number=3,
            category="SUPPLY_LINE_CAPACITY",
            question_text=f"Context: Objective is deep in territory requiring extended supply lines. What is current ammunition expenditure rate per day? How does this compare to peak 2022 levels? If supply lines are disrupted (bridges, rails), can offensive operations be sustained at required pace for the timeline?",
            context_requirements="Russian logistics data, ammunition expenditure rates, supply line vulnerability assessment"
        ),
        HistoricalQuestion(
            question_number=4,
            category="UKRAINIAN_DEFENSIVE_PRECEDENT",
            question_text=f"Context: {event_description} Ukraine has defended major cities despite being outnumbered (Kyiv, Kharkiv, Mariupol). Based on historical Ukrainian defensive performance in similar situations, how effective is prepared urban defense against Russian assault? What percentage of assaults on prepared Ukrainian defenses have succeeded vs. stalled?",
            context_requirements="Ukraine defense case studies, urban warfare outcomes, defensive effectiveness metrics"
        ),
        HistoricalQuestion(
            question_number=5,
            category="MATH_FEASIBILITY",
            question_text="Context: The fastest Russian advances in Ukraine have been 5-10 km/day, but only for 1-2 weeks maximum. Is there ANY historical precedent for Russia sustaining such advances for extended periods while facing prepared defenses, in winter, over extended supply lines? What mathematical constraints limit offensive pace?",
            context_requirements="Military history database, advance rate analysis, statistical precedent"
        ),
        HistoricalQuestion(
            question_number=6,
            category="FORCE_CONCENTRATION",
            question_text=f"Context: Reports suggest Russia is concentrating maximum forces at this objective. Historically, when Russia concentrates forces maximally at one point, how much faster do offensives progress? Can concentration overcome logistics/weather constraints? Cite 2022-2024 examples where force concentration succeeded or failed.",
            context_requirements="Russian concentration tactics, operational outcomes, force multiplier analysis"
        ),
        HistoricalQuestion(
            question_number=7,
            category="MANPOWER_ATTRITION",
            question_text=f"Context: Russia has suffered massive casualties in 2024. Can military forces sustain an intensive assault while replacing 500-1000+ casualties per day? At what casualty rates do offensives slow or halt? Is current manpower sustainable for a multi-week intensive operation?",
            context_requirements="Casualty data, manpower availability, attrition rates 2024"
        ),
        HistoricalQuestion(
            question_number=8,
            category="FORTIFICATION_STATUS",
            question_text=f"Context: Has Ukraine had time to fortify the objective? Compared to Mariupol (heavily fortified, ~90 days to fall) or Bakhmut (partially fortified, ~100 days), how fortified is the objective likely to be? Do prepared defenses add sufficient time to make a {days_remaining}-day capture mathematically impossible?",
            context_requirements="Fortification data, urban defense timelines, defensive advantage metrics"
        ),
        HistoricalQuestion(
            question_number=9,
            category="BREAKTHROUGH_VS_CONSOLIDATION",
            question_text=f"Context: {event_description} Russia might achieve a breakthrough at one point, but capturing the entire objective requires sustained advance, then urban assault, then consolidation. How long have urban assaults historically taken (Mariupol, Severodonetsk, Soledar)? Can city conquest be completed in <{days_remaining} days from today, or is it typically a 60-90 day process?",
            context_requirements="Urban assault timelines, city conquest case studies, consolidation periods"
        ),
        HistoricalQuestion(
            question_number=10,
            category="WEATHER_TIMING",
            question_text=f"Context: {event_description} When does mud season typically freeze over in Eastern Ukraine? December often still has mud. Is December a tactically favorable month for a major offensive, or do most Russian offensives accelerate in spring? What does historical timing tell us about offensive capability in late December?",
            context_requirements="Weather records, seasonal mud patterns, historical offensive timing"
        ),
        HistoricalQuestion(
            question_number=11,
            category="POLITICAL_PRESSURE",
            question_text=f"Context: {event_description} Is there political pressure (Putin, military, domestic) to achieve this by the deadline for propaganda purposes? Historically, does political deadline pressure lead to reckless tactics, faster breakthroughs, or costly stalls? Can artificial deadlines accelerate real military capability?",
            context_requirements="Russian political analysis, propaganda objectives, leadership decision-making patterns"
        ),
        HistoricalQuestion(
            question_number=12,
            category="SIGNAL_SYNTHESIS",
            question_text=f"Context: {event_description} After analyzing all historical precedents, what is the strongest evidence for (bullish) and against (bearish) this outcome by the deadline? Assign a confidence level to each directional signal. Provide an overall probability estimate (0-100) with detailed reasoning.",
            context_requirements="Synthesis of all previous analyses, probability assessment, confidence calibration"
        ),
    ]
    
    return HistoricalQuestionnaires(
        event_id=event_id,
        event_description=event_description,
        event_deadline=event_deadline,
        distance_to_objective_km=distance_km,
        days_remaining=days_remaining,
        required_daily_advance_km=required_daily_advance,
        questions=questions,
        total_questions=len(questions)
    )


def demo_question_generation():
    """Demo: Generate questions for Pokrovsk event"""
    print("=" * 80)
    print("HISTORICAL RESEARCH QUESTION GENERATOR - DEMO")
    print("=" * 80)
    print()
    
    # Generate questions
    questionnaire = generate_historical_questions(
        event_description="Will Russia capture all of Pokrovsk by December 31, 2024?",
        event_id="russia_pokrovsk_dec31",
        event_deadline="2024-12-31",
        distance_km=85,
        days_remaining=25
    )
    
    print(f"Event: {questionnaire.event_description}")
    print(f"Deadline: {questionnaire.event_deadline}")
    print(f"Distance: {questionnaire.distance_to_objective_km} km")
    print(f"Days remaining: {questionnaire.days_remaining}")
    print(f"Required daily advance: {questionnaire.required_daily_advance_km:.2f} km/day")
    print()
    print(f"Total questions generated: {questionnaire.total_questions}")
    print()
    
    for q in questionnaire.questions[:3]:
        print(f"Q{q.question_number} [{q.category}]")
        print(f"  {q.question_text[:100]}...")
        print()
    
    print()
    print("=" * 80)
    print("SAMPLE HISTORICAL ANALYSIS RESPONSE")
    print("=" * 80)
    print()
    
    # Create sample response
    sample_response = HistoricalAnalysisResponse(
        event_id="russia_pokrovsk_dec31",
        event_description="Will Russia capture all of Pokrovsk by December 31, 2024?",
        analysis_timestamp=datetime.now().isoformat(),
        
        overall_sentiment=SentimentEnum.BEARISH,
        overall_signal_strength=28,
        overall_confidence=ConfidenceEnum.HIGH,
        
        bullish_signals=[
            SignalData(
                signal_text="Russian force concentration at this front is largest since 2022",
                direction=SentimentEnum.BULLISH,
                strength=45,
                confidence=ConfidenceEnum.HIGH,
                historical_precedent="Similar concentrations in 2022 Kharkiv offensive achieved 5 km/day for 2-3 weeks"
            ),
            SignalData(
                signal_text="Pokrovsk lacks Kyiv-style prepared defenses",
                direction=SentimentEnum.BULLISH,
                strength=35,
                confidence=ConfidenceEnum.MEDIUM,
                historical_precedent="Lightly defended cities (Izyum, Kupiansk) fell in 3-5 days in 2022"
            ),
        ],
        bullish_confidence=ConfidenceEnum.MEDIUM,
        
        bearish_signals=[
            SignalData(
                signal_text="Required pace (3.4 km/day) exceeds any sustained 25-day Russian offensive in Ukraine",
                direction=SentimentEnum.BEARISH,
                strength=85,
                confidence=ConfidenceEnum.VERY_HIGH,
                historical_precedent="Max sustained: Kharkiv 2022 (5 km/day for 14 days only); Bakhmut took 100 days"
            ),
            SignalData(
                signal_text="Winter conditions + prepared defenses = 40-50% slower advance rate",
                direction=SentimentEnum.BEARISH,
                strength=75,
                confidence=ConfidenceEnum.HIGH,
                historical_precedent="2022-23 winter offensives dropped from 3-5 km/day to 0.5-1.5 km/day"
            ),
            SignalData(
                signal_text="Supply lines at maximum extension would be vulnerable to Ukrainian strikes",
                direction=SentimentEnum.BEARISH,
                strength=70,
                confidence=ConfidenceEnum.HIGH,
                historical_precedent="Crimea bridge damage, rail cuts in 2024 reduced supply by 30-40%"
            ),
            SignalData(
                signal_text="Urban assault + consolidation historically takes 60-90 days minimum",
                direction=SentimentEnum.BEARISH,
                strength=80,
                confidence=ConfidenceEnum.VERY_HIGH,
                historical_precedent="Mariupol: 90 days, Bakhmut: 100 days, Severodonetsk: 45 days"
            ),
        ],
        bearish_confidence=ConfidenceEnum.VERY_HIGH,
        
        neutral_observations=[
            "Mud season freeze-over timing is critical; unclear if ground will harden before Dec 31",
            "Russian casualty rates sustainable at current manpower levels for ~15 more days",
            "Ukrainian reinforcements could arrive at objective in 10-15 days",
        ],
        
        probability_estimate=15,
        probability_reasoning="Mathematical analysis: 3.4 km/day required pace exceeds historical precedent by 2-3x for sustained periods. Winter conditions alone reduce expected pace to 1-1.5 km/day. Urban conquest requires 60-90 days minimum. Only viable if Russian breakthrough creates encirclement, but even then timeline is unrealistic. Probability: 10-20%.",
        
        critical_path_factors=[
            "Winter mud season timing - must freeze over before key mechanized advances",
            "Ukrainian defensive fortification progress in remaining days",
            "Russian supply line vulnerability to continued strikes",
            "Breakthrough point creation - if achieved, accelerates everything; if not, pace slows further",
            "Urban assault complexity - even light defenses in urban terrain extend timelines",
        ],
        
        recommendation="BEARISH outlook. While Russian concentration and Ukrainian fatigue are real, the mathematical constraints (3.4 km/day required vs. 0.5-1.5 km/day historical winter pace) and urban assault timelines make capture by Dec 31 extremely unlikely. Consider betting against this outcome. Monitor: supply line disruptions, freezing timelines, breakthrough attempts.",
    )
    
    print(f"Overall Sentiment: {sample_response.overall_sentiment.value}")
    print(f"Signal Strength: {sample_response.overall_signal_strength}/100")
    print(f"Confidence: {sample_response.overall_confidence.value}")
    print()
    print(f"Probability Estimate: {sample_response.probability_estimate}%")
    print()
    print(f"Bullish Signals ({len(sample_response.bullish_signals)}):")
    for signal in sample_response.bullish_signals:
        print(f"  • {signal.signal_text} ({signal.strength}/100)")
    print()
    print(f"Bearish Signals ({len(sample_response.bearish_signals)}):")
    for signal in sample_response.bearish_signals:
        print(f"  • {signal.signal_text} ({signal.strength}/100)")
    print()
    print(f"Recommendation:")
    print(f"  {sample_response.recommendation}")
    print()
    print("=" * 80)


if __name__ == "__main__":
    demo_question_generation()

