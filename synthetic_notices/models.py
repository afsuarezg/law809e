"""
Data models for synthetic notice generation.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional
from enum import Enum


class DefectType(str, Enum):
    """The 9 on-the-face defects for 3-day notices."""
    NOT_DISJUNCTIVE = "not_disjunctive"
    INSUFFICIENT_PERIOD = "insufficient_period"
    NO_AMOUNT_STATED = "no_amount_stated"
    MISSING_PAYEE_INFO = "missing_payee_info"
    MISSING_PAYMENT_HOURS = "missing_payment_hours"
    FINANCIAL_INSTITUTION_INCOMPLETE = "financial_institution_incomplete"
    ELECTRONIC_PAYMENT_NOT_ESTABLISHED = "electronic_payment_not_established"
    RENT_OVER_ONE_YEAR = "rent_over_one_year"
    NO_FORFEITURE = "no_forfeiture"


@dataclass
class NoticeData:
    """Data used to generate a notice."""
    # Parties
    landlord_name: str = "ABC Property Management"
    landlord_address: str = "456 Business Ave, Suite 100, Los Angeles, CA 90001"
    landlord_phone: str = "(310) 555-1234"
    tenant_names: List[str] = field(default_factory=lambda: ["John Doe"])
    property_address: str = "123 Main Street, Apt 4B, Los Angeles, CA 90001"

    # Financial
    rent_amount: float = 1500.00
    rent_period_start: date = field(default_factory=lambda: date(2024, 1, 1))
    rent_period_end: date = field(default_factory=lambda: date(2024, 1, 31))

    # Dates
    notice_date: date = field(default_factory=lambda: date(2024, 1, 15))
    service_date: date = field(default_factory=lambda: date(2024, 1, 15))
    deadline_date: date = field(default_factory=lambda: date(2024, 1, 19))

    # Payment options
    allow_personal_payment: bool = True
    payment_hours: str = "Monday through Friday, 9:00 AM to 5:00 PM"
    allow_bank_payment: bool = False
    bank_name: Optional[str] = None
    bank_address: Optional[str] = None
    bank_account: Optional[str] = None
    allow_electronic_payment: bool = False
    electronic_method: Optional[str] = None

    # Language flags
    use_disjunctive: bool = True
    include_forfeiture: bool = True


@dataclass
class GeneratedNotice:
    """A generated notice with metadata."""
    text: str
    data: Optional[NoticeData]
    defects: List[DefectType]
    is_valid: bool
    template_file: Optional[str] = None
    template_created_date: Optional[str] = None

    def to_dict(self) -> dict:
        result = {
            "text": self.text,
            "defects": [d.value for d in self.defects],
            "is_valid": self.is_valid,
            "template_file": self.template_file,
            "template_created_date": self.template_created_date,
        }
        
        # Add metadata if data is available (rule-based generator)
        # LLM-generated notices have data=None
        if self.data is not None:
            result["metadata"] = {
                "landlord": self.data.landlord_name,
                "tenant": self.data.tenant_names,
                "property": self.data.property_address,
                "amount": self.data.rent_amount,
                "notice_date": str(self.data.notice_date),
                "service_date": str(self.data.service_date),
                "deadline_date": str(self.data.deadline_date),
            }
        else:
            result["metadata"] = None
        
        return result
