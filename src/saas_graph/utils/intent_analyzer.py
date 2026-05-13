"""Lightweight rule-based intent analysis and time reference parsing."""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Optional

from ..models.intent import QueryIntent, QueryType, TimeReference

_FOLLOW_UP_PATTERNS = [
    r"^(what about|how about|and |also |show me|now )",
    r"^(can you|could you|please) (also|show|add|include)",
    r"^(same|that) (but|for|with)",
]

_TIME_PATTERNS = [
    (r"\blast\s+month\b", "last month"),
    (r"\bthis\s+month\b", "this month"),
    (r"\blast\s+year\b", "last year"),
    (r"\bthis\s+year\b", "this year"),
    (r"\blast\s+week\b", "last week"),
    (r"\bthis\s+quarter\b", "this quarter"),
    (r"\blast\s+quarter\b", "last quarter"),
    (r"\byesterday\b", "yesterday"),
    (r"\btoday\b", "today"),
    (r"\b(ytd|year.to.date)\b", "year to date"),
]


class IntentAnalyzer:
    """Rule-based query intent extraction.

    Identifies query type, time references, and follow-up status.
    """

    def is_follow_up(self, query: str) -> bool:
        q = query.lower().strip()
        return any(re.search(p, q) for p in _FOLLOW_UP_PATTERNS)

    def analyze(self, query: str) -> QueryIntent:
        q = query.lower()
        query_type = self._detect_type(q)
        time_ref = self._detect_time(q)
        return QueryIntent(
            query_type=query_type,
            time_reference=time_ref,
            is_follow_up=self.is_follow_up(query),
            raw_query=query,
            confidence=0.7 if query_type != QueryType.UNKNOWN else 0.3,
        )

    @staticmethod
    def _detect_type(q: str) -> QueryType:
        if any(w in q for w in ("how many", "count", "total", "sum", "average", "avg")):
            return QueryType.AGGREGATION
        if any(w in q for w in ("list", "show", "all", "which")):
            return QueryType.LISTING
        if any(w in q for w in ("compare", "vs", "versus", "difference", "between")):
            return QueryType.COMPARISON
        if any(w in q for w in ("trend", "over time", "month by month", "growth")):
            return QueryType.TREND
        if any(w in q for w in ("top", "highest", "lowest", "best", "worst", "rank")):
            return QueryType.LISTING
        return QueryType.UNKNOWN

    @staticmethod
    def _detect_time(q: str) -> Optional[TimeReference]:
        for pattern, label in _TIME_PATTERNS:
            if re.search(pattern, q, re.IGNORECASE):
                today = date.today()
                start, end = _resolve_dates(label, today)
                return TimeReference(
                    phrase=label,
                    start_date=start.isoformat() if start else None,
                    end_date=end.isoformat() if end else None,
                )
        return None


from typing import Tuple as _Tuple

def _resolve_dates(label: str, today: date) -> _Tuple[Optional[date], Optional[date]]:
    if label == "yesterday":
        d = today - timedelta(days=1)
        return d, d
    if label == "today":
        return today, today
    if label == "last week":
        start = today - timedelta(days=today.weekday() + 7)
        end = start + timedelta(days=6)
        return start, end
    if label == "this month":
        return today.replace(day=1), today
    if label == "last month":
        first = today.replace(day=1)
        last_month_end = first - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)
        return last_month_start, last_month_end
    if label == "this year":
        return today.replace(month=1, day=1), today
    if label == "last year":
        start = today.replace(year=today.year - 1, month=1, day=1)
        end = today.replace(year=today.year - 1, month=12, day=31)
        return start, end
    if label == "year to date":
        return today.replace(month=1, day=1), today
    return None, None
