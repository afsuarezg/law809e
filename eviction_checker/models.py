"""
Data models for eviction notice validation.
"""

from pydantic import BaseModel, Field, field_validator
from enum import Enum
from decimal import Decimal
from datetime import date
from typing import Optional, List


class NoticeType(str, Enum):
    """Types of eviction notices in California."""
    THREE_DAY_PAY = "3_day_pay_or_quit"
    THREE_DAY_CURE = "3_day_cure_or_quit"
    THIRTY_DAY = "30_day_notice"
    SIXTY_DAY = "60_day_notice"
    UNKNOWN = "unknown"


class Severity(str, Enum):
    """Severity levels for defects."""
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    WARNING = "warning"


class Charge(BaseModel):
    """A charge listed in the notice."""
    description: str
    amount: Decimal
    is_rent: bool = Field(..., description="True only for rent, False for fees/utilities/damages")

    @field_validator('amount')
    @classmethod
    def amount_must_be_positive(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError('Amount must be positive')
        return v


class PaymentTerms(BaseModel):
    """Payment terms specified in the notice."""
    payee_name: Optional[str] = None
    payment_address: Optional[str] = None
    payment_hours: Optional[str] = None
    payment_methods: Optional[List[str]] = None


class ExtractedNotice(BaseModel):
    """Structured data extracted from an eviction notice."""
    raw_text: str
    notice_type: NoticeType = NoticeType.THREE_DAY_PAY

    # Parties
    landlord_name: Optional[str] = None
    tenant_names: List[str] = Field(default_factory=list)
    property_address: Optional[str] = None

    # Financial
    total_amount_demanded: Optional[Decimal] = None
    charges: List[Charge] = Field(default_factory=list)

    # Dates
    notice_date: Optional[date] = None
    service_date: Optional[date] = None
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    termination_date: Optional[date] = None
    days_to_comply: Optional[int] = None

    # Payment terms
    payment_terms: Optional[PaymentTerms] = None

    # Flags
    is_signed: bool = False


class Defect(BaseModel):
    """A legal defect found in the notice."""
    defect_id: str
    title: str
    severity: Severity
    description: str
    statute_violated: str
    case_law: List[str] = Field(default_factory=list)
    tenant_action: str
    evidence: Optional[str] = None


class DefectReport(BaseModel):
    """Complete defect analysis report."""
    notice_type: NoticeType
    defects: List[Defect] = Field(default_factory=list)
    is_valid: bool
    summary: str
    analysis_date: Optional[date] = None

    @property
    def critical_defects(self) -> List[Defect]:
        return [d for d in self.defects if d.severity == Severity.CRITICAL]

    @property
    def defect_count(self) -> int:
        return len(self.defects)
