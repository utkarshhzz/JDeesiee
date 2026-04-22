"""
Models package — imports all ORM models so they register with Base.metadata.

WHY THIS FILE MATTERS:
    Alembic discovers tables through Base.metadata. Models only register
    with Base when their classes are imported. This file ensures ALL models
    are imported when you do 'from app.models import Base'.
"""

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.candidate import Candidate
from app.models.search_event import SearchEvent
from app.models.match_result import MatchResult
from app.models.webhook_event import WebhookEvent
from app.models.rai_report import RAIReport
from app.models.prompt_variant import PromptVariant, PromptExperiment


__all__ = [
    "Base",
    "TimestampMixin",
    "UUIDPrimaryKeyMixin",
    "Candidate",
    "SearchEvent",
    "MatchResult",
    "WebhookEvent",
    "RAIReport",
    "PromptVariant",
    "PromptExperiment",
]
