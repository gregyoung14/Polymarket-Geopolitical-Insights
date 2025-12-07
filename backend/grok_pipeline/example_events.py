"""
Example prediction events to test the pipeline with.

These are realistic events that would appear on prediction markets.
"""

EXAMPLE_EVENTS = [
    {
        "event_id": "bitcoin_etf_2024",
        "description": "Will the spot Bitcoin ETF be approved by the SEC in 2024?",
        "markets": [
            "Polymarket: Bitcoin Spot ETF Approval by 2024-12-31",
            "Kalshi: BTC Spot ETF Approval (expires Dec 2024)",
        ],
        "relevant_keywords": ["Bitcoin", "ETF", "SEC approval", "spot market"],
    },
    {
        "event_id": "2024_election_winner",
        "description": "Who will win the 2024 US Presidential Election?",
        "markets": [
            "Polymarket: 2024 US Presidential Election - Winner",
            "Kalshi: 2024 US Presidential Election",
        ],
        "relevant_keywords": ["election", "voting", "president", "candidate"],
    },
    {
        "event_id": "fed_rate_decision_dec",
        "description": "Will the Federal Reserve cut interest rates at December FOMC meeting?",
        "markets": [
            "Polymarket: Fed Rate Decision December 2024",
        ],
        "relevant_keywords": ["Federal Reserve", "interest rates", "FOMC", "rate cut"],
    },
    {
        "event_id": "tech_stock_crash",
        "description": "Will the Nasdaq drop more than 10% before end of year?",
        "markets": [
            "Polymarket: Nasdaq -10% by 2024-12-31",
        ],
        "relevant_keywords": ["stock market", "Nasdaq", "crash", "correction"],
    },
    {
        "event_id": "ai_breakthrough",
        "description": "Will OpenAI release GPT-5 before 2025?",
        "markets": [
            "Polymarket: OpenAI GPT-5 Release by 2024-12-31",
        ],
        "relevant_keywords": ["AI", "GPT-5", "OpenAI", "breakthrough"],
    },
    {
        "event_id": "crypto_regulation",
        "description": "Will the US Congress pass comprehensive crypto regulation in 2024?",
        "markets": [
            "Polymarket: US Crypto Regulation Bill (2024)",
        ],
        "relevant_keywords": ["cryptocurrency", "regulation", "Congress", "bill"],
    },
    {
        "event_id": "olympic_medal",
        "description": "Will Simone Biles win gold in the vault at 2024 Olympics?",
        "markets": [
            "Polymarket: 2024 Olympics - Simone Biles Vault Gold",
        ],
        "relevant_keywords": ["Olympics", "Simone Biles", "vault", "gymnastics"],
    },
    {
        "event_id": "climate_record",
        "description": "Will 2024 be the hottest year on record?",
        "markets": [
            "Polymarket: 2024 Hottest Year on Record",
        ],
        "relevant_keywords": ["climate", "temperature", "record", "global warming"],
    },
]


def get_random_event():
    """Get a random event from the list"""
    import random
    event = random.choice(EXAMPLE_EVENTS)
    return event["description"], event.get("markets"), event.get("event_id")


def get_event_by_id(event_id: str):
    """Get a specific event by ID"""
    for event in EXAMPLE_EVENTS:
        if event["event_id"] == event_id:
            return event["description"], event.get("markets"), event.get("event_id")
    return None, None, None

