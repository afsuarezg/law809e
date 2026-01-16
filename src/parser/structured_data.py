"""
Pydantic models for structured eviction notice data.

These models define the structure of extracted information and validation results.
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
    THREE_DAY_UNCONDITIONAL = "3_day_unconditional_quit"
    THIRTY_DAY = "30_day_notice"
    SIXTY_DAY = "60_day_notice"
    NINETY_DAY = "90_day_notice"
    UNKNOWN = "unknown"

    def __str__(self) -> str:
        """Human-readable string representation."""
        mapping = {
            "3_day_pay_or_quit": "3-Day Notice to Pay Rent or Quit",
            "3_day_cure_or_quit": "3-Day Notice to Cure or Quit",
            "3_day_unconditional_quit": "3-Day Unconditional Notice to Quit",
            "30_day_notice": "30-Day Notice to Terminate Tenancy",
            "60_day_notice": "60-Day Notice to Terminate Tenancy",
            "90_day_notice": "90-Day Notice to Terminate Tenancy",
            "unknown": "Unknown Notice Type"
        }
        return mapping.get(self.value, self.value)


class Severity(str, Enum):
    """Severity levels for defects."""
    CRITICAL = "critical"      # Fatal defect, notice definitely invalid
    MAJOR = "major"            # Likely invalidates notice
    MINOR = "minor"            # Technical issue, may not invalidate
    WARNING = "warning"        # Potential issue, needs context


class Charge(BaseModel):
    """Represents a charge listed in the notice."""
    description: str = Field(..., description="Description of the charge (e.g., 'rent', 'late fee')")
    amount: Decimal = Field(..., description="Dollar amount of the charge")
    is_rent: bool = Field(..., description="Whether this charge is for rent specifically")

    @field_validator('amount')
    @classmethod
    def amount_must_be_positive(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError('Amount must be positive')
        return v


class PaymentTerms(BaseModel):
    """Payment terms specified in the notice."""
    payee_name: Optional[str] = Field(None, description="Name of person/entity to receive payment")
    payment_address: Optional[str] = Field(None, description="Address where payment should be made")
    payment_hours: Optional[str] = Field(None, description="Hours during which payment can be made")
    payment_methods: Optional[List[str]] = Field(None, description="Acceptable payment methods")


class ExtractedNotice(BaseModel):
    """Structured data extracted from an eviction notice."""

    # Raw data
    raw_text: str = Field(..., description="Full text extracted from the notice")

    # Classification
    notice_type: NoticeType = Field(..., description="Type of eviction notice")

    # Parties
    landlord_name: Optional[str] = Field(None, description="Name of landlord or property manager")
    tenant_names: List[str] = Field(default_factory=list, description="Names of all tenants listed")
    property_address: Optional[str] = Field(None, description="Address of the rental property")

    # Financial information
    total_amount_demanded: Optional[Decimal] = Field(
        None,
        description="Total dollar amount demanded in the notice"
    )
    charges: List[Charge] = Field(
        default_factory=list,
        description="Itemized list of charges"
    )

    # Dates
    notice_date: Optional[date] = Field(None, description="Date the notice was created")
    service_date: Optional[date] = Field(None, description="Date the notice was served")
    period_start: Optional[date] = Field(None, description="Start of rental period for which rent is owed")
    period_end: Optional[date] = Field(None, description="End of rental period for which rent is owed")
    termination_date: Optional[date] = Field(
        None,
        description="Date tenancy will terminate (for 30/60 day notices)"
    )
    days_to_comply: Optional[int] = Field(None, description="Number of days tenant has to comply")

    # Payment terms (for 3-day pay notices)
    payment_terms: Optional[PaymentTerms] = Field(None, description="Payment instructions")

    # Lease violation information (for cure notices)
    lease_violation: Optional[str] = Field(None, description="Description of lease violation")
    cure_requirements: Optional[str] = Field(None, description="What tenant must do to cure")
    lease_clause_reference: Optional[str] = Field(
        None,
        description="Reference to specific lease provision violated"
    )

    # Legal language and requirements
    includes_just_cause: bool = Field(
        False,
        description="Whether notice includes just cause statement (AB 1482)"
    )
    just_cause_reason: Optional[str] = Field(None, description="Stated reason for termination")
    includes_relocation_assistance: bool = Field(
        False,
        description="Whether notice mentions relocation assistance (AB 1482)"
    )
    statutory_citations: List[str] = Field(
        default_factory=list,
        description="Statutes cited in the notice"
    )

    # Signature and service
    is_signed: bool = Field(False, description="Whether notice is signed")
    signature_name: Optional[str] = Field(None, description="Name of person who signed")
    service_method: Optional[str] = Field(
        None,
        description="Method of service (personal, substituted, post and mail)"
    )

    # Metadata
    confidence_notes: Optional[str] = Field(
        None,
        description="Notes about extraction confidence or ambiguities"
    )

    class Config:
        json_encoders = {
            Decimal: lambda v: float(v),
            date: lambda v: v.isoformat()
        }


class Defect(BaseModel):
    """Represents a legal defect found in the notice."""

    defect_id: str = Field(..., description="Unique defect identifier (e.g., '3DP-001')")
    title: str = Field(..., description="Short title of the defect")
    severity: Severity = Field(..., description="Severity level of the defect")
    description: str = Field(..., description="Detailed description of the defect")
    statute_violated: str = Field(..., description="Statute or case law violated")
    case_law: List[str] = Field(default_factory=list, description="Relevant case law citations")
    tenant_action: str = Field(
        ...,
        description="Recommended action for tenant"
    )
    detected_by: str = Field(..., description="Detection method: 'rule' or 'llm'")
    evidence: Optional[str] = Field(
        None,
        description="Specific text from notice supporting this defect"
    )

    class Config:
        json_encoders = {
            Severity: lambda v: v.value
        }


class DefectReport(BaseModel):
    """Complete defect analysis report for an eviction notice."""

    notice_type: NoticeType = Field(..., description="Type of notice analyzed")
    defects: List[Defect] = Field(default_factory=list, description="List of defects found")
    is_valid: bool = Field(..., description="Whether the notice appears to be legally valid")
    summary: str = Field(..., description="Executive summary of findings")

    # Metadata
    analysis_date: Optional[date] = Field(None, description="Date of analysis")
    ocr_confidence: Optional[float] = Field(None, description="Average OCR confidence score")
    ocr_warnings: List[str] = Field(
        default_factory=list,
        description="Warnings about OCR quality"
    )

    @property
    def critical_defects(self) -> List[Defect]:
        """Get list of critical defects."""
        return [d for d in self.defects if d.severity == Severity.CRITICAL]

    @property
    def major_defects(self) -> List[Defect]:
        """Get list of major defects."""
        return [d for d in self.defects if d.severity == Severity.MAJOR]

    @property
    def minor_defects(self) -> List[Defect]:
        """Get list of minor defects."""
        return [d for d in self.defects if d.severity == Severity.MINOR]

    @property
    def warnings(self) -> List[Defect]:
        """Get list of warnings."""
        return [d for d in self.defects if d.severity == Severity.WARNING]

    @property
    def defect_count(self) -> int:
        """Total number of defects."""
        return len(self.defects)

    def get_defects_by_severity(self, severity: Severity) -> List[Defect]:
        """Get defects of a specific severity level."""
        return [d for d in self.defects if d.severity == severity]

    class Config:
        json_encoders = {
            NoticeType: lambda v: v.value,
            Severity: lambda v: v.value,
            date: lambda v: v.isoformat() if v else None
        }


class ValidationContext(BaseModel):
    """Additional context that may affect validation."""

    # Tenancy information
    tenancy_length_years: Optional[float] = Field(
        None,
        description="How long tenant has lived at property (in years)"
    )
    monthly_rent: Optional[Decimal] = Field(None, description="Current monthly rent amount")
    lease_start_date: Optional[date] = Field(None, description="Date lease began")

    # Property information
    property_year_built: Optional[int] = Field(None, description="Year property was built")
    is_single_family_home: Optional[bool] = Field(None, description="Whether property is single-family")
    is_owner_occupied_duplex: Optional[bool] = Field(
        None,
        description="Whether property is duplex with owner occupying one unit"
    )

    # AB 1482 determination
    is_ab1482_covered: Optional[bool] = Field(
        None,
        description="Whether property is covered by Tenant Protection Act"
    )
    ab1482_exemption_reason: Optional[str] = Field(
        None,
        description="If exempt from AB 1482, the reason"
    )

    # Previous notices
    has_received_prior_notice: Optional[bool] = Field(
        None,
        description="Whether tenant has received prior notices"
    )
    prior_notice_type: Optional[str] = Field(None, description="Type of prior notice")

    class Config:
        json_encoders = {
            Decimal: lambda v: float(v),
            date: lambda v: v.isoformat() if v else None
        }
