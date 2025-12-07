"""
Grok Pipeline: Multi-step intelligent filtering and signal quantification
for prediction market events.

Pipeline Flow:
1. Event → Filter Selection (Grok decides filters)
2. Filters → Raw Tweets (Execute filters, collect tweets)
3. Tweets → Signal Analysis (Quantify sentiment/strength)
4. Signal → Persistence (Track over time)
"""

__version__ = "0.1.0"

