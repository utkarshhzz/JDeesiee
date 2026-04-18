"""
1. Bias detection: Were certain demographic groups under-represented?
    2. JD language analysis: Does the JD use exclusionary language?
    3. Filter impact: How much did filters narrow the candidate pool?
    4. Fairness metrics: Statistical measures of result fairness.
    """

from __future__ import annotations

import uuid
from datetime import datetime
from sqlalchemy import DateTime, SmallInteger, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import ForeignKey
from app.models.base import Base, UUIDPrimaryKeyMixin

