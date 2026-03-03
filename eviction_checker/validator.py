"""
Validator for 3-Day Notice to Pay Rent or Quit.

Checks for on-the-face defects that can be detected from the document itself.
"""

import re
import logging
from datetime import date, timedelta
from typing import List, Optional

from .models import ExtractedNotice, Defect, Severity

logger = logging.getLogger(__name__)


class NoticeValidator:
    """Validates 3-Day Pay or Quit notices for legal defects."""

    # California judicial holidays (MM-DD format)
    FIXED_HOLIDAYS = ["01-01", "07-04", "11-11", "12-25"]

    def validate(self, notice: ExtractedNotice) -> List[Defect]:
        """
        Validate notice for on-the-face defects.

        Args:
            notice: Extracted notice data

        Returns:
            List of defects found
        """
        defects = []

        checks = [
            self._check_disjunctive_phrasing,        # Defect 1
            self._check_notice_period,               # Defect 2
            self._check_amount_stated,               # Defect 3
            self._check_payee_information,           # Defect 4
            self._check_payment_hours,               # Defect 5
            self._check_financial_institution,       # Defect 6
            self._check_electronic_payment,          # Defect 7
            self._check_rent_age,                    # Defect 8
            self._check_forfeiture_declaration,      # Defect 9
        ]

        for check in checks:
            defect = check(notice)
            if defect:
                defects.append(defect)

        logger.info(f"Validation complete. Found {len(defects)} defects.")
        return defects

    def _check_disjunctive_phrasing(self, notice: ExtractedNotice) -> Optional[Defect]:
        """Check if notice uses 'pay OR quit' language."""
        text = notice.raw_text.lower()

        patterns = [
            r'pay\s+(rent\s+)?or\s+quit',
            r'pay\s+(rent\s+)?or\s+vacate',
            r'pay\s+or\s+move\s+out',
        ]

        if any(re.search(p, text) for p in patterns):
            return None

        return Defect(
            defect_id="MVP-001",
            title="Notice Not Phrased in the Disjunctive",
            severity=Severity.CRITICAL,
            description="The notice must give tenant the option to pay rent OR quit.",
            statute_violated="CCP 1161(2)",
            tenant_action="This defect invalidates the notice.",
            evidence="No 'pay or quit' language found"
        )

    def _check_notice_period(self, notice: ExtractedNotice) -> Optional[Defect]:
        """Check if notice gives 3 business days."""
        if notice.service_date and notice.termination_date:
            # Both dates present: count business days precisely
            business_days = self._count_business_days(
                notice.service_date, notice.termination_date
            )
            if business_days < 3:
                return Defect(
                    defect_id="MVP-002",
                    title="Insufficient Notice Period",
                    severity=Severity.CRITICAL,
                    description=f"Only {business_days} business days given, but 3 required.",
                    statute_violated="CCP 1161(2), 12, 12a",
                    tenant_action="This defect invalidates the notice.",
                    evidence=f"Service: {notice.service_date}, Deadline: {notice.termination_date}"
                )
            return None

        # No service date (common in LLM-generated or typeset notices without
        # a proof-of-service section).  Fall back to the explicit days_to_comply
        # field extracted from text like "WITHIN THREE (3) BUSINESS DAYS".
        if notice.days_to_comply is not None:
            if notice.days_to_comply < 3:
                return Defect(
                    defect_id="MVP-002",
                    title="Insufficient Notice Period",
                    severity=Severity.CRITICAL,
                    description=f"Notice states only {notice.days_to_comply} day(s) to comply; 3 business days required.",
                    statute_violated="CCP 1161(2), 12, 12a",
                    tenant_action="This defect invalidates the notice.",
                    evidence=f"days_to_comply={notice.days_to_comply}"
                )
            # days_to_comply >= 3: period is stated and sufficient
            return None

        # Neither service date nor explicit day count — cannot assess the period
        # on the face of the document.  Give benefit of the doubt.
        return None

    def _count_business_days(self, start: date, end: date) -> int:
        """Count business days excluding weekends and holidays."""
        days = 0
        current = start + timedelta(days=1)

        while current <= end:
            if current.weekday() < 5 and not self._is_holiday(current):
                days += 1
            current += timedelta(days=1)

        return days

    def _is_holiday(self, d: date) -> bool:
        """Check if date is a California judicial holiday."""
        date_str = d.strftime("%m-%d")
        if date_str in self.FIXED_HOLIDAYS:
            return True

        # MLK Day: 3rd Monday in January
        if d.month == 1 and d.weekday() == 0 and 15 <= d.day <= 21:
            return True
        # Presidents Day: 3rd Monday in February
        if d.month == 2 and d.weekday() == 0 and 15 <= d.day <= 21:
            return True
        # Memorial Day: Last Monday in May
        if d.month == 5 and d.weekday() == 0 and d.day >= 25:
            return True
        # Labor Day: 1st Monday in September
        if d.month == 9 and d.weekday() == 0 and d.day <= 7:
            return True
        # Thanksgiving: 4th Thursday in November
        if d.month == 11 and d.weekday() == 3 and 22 <= d.day <= 28:
            return True

        return False

    def _check_amount_stated(self, notice: ExtractedNotice) -> Optional[Defect]:
        """Check if exact rent amount is stated."""
        if not notice.total_amount_demanded or notice.total_amount_demanded == 0:
            return Defect(
                defect_id="MVP-003",
                title="No Exact Amount Stated",
                severity=Severity.CRITICAL,
                description="Notice must state specific dollar amount owed.",
                statute_violated="CCP 1161(2); Bevill v. Zoura (1994)",
                tenant_action="This defect invalidates the notice.",
                evidence="No specific dollar amount found"
            )
        return None

    def _check_payee_information(self, notice: ExtractedNotice) -> Optional[Defect]:
        """Check if payee name, phone, and address are stated."""
        missing = []

        if not notice.payment_terms:
            return Defect(
                defect_id="MVP-004",
                title="Missing All Payee Information",
                severity=Severity.CRITICAL,
                description="Must state name, phone, and address of payee.",
                statute_violated="CCP 1161(2); Schwab v. Rondel Homes (1991)",
                tenant_action="This defect invalidates the notice.",
                evidence="No payment information found"
            )

        if not notice.payment_terms.payee_name:
            missing.append("payee name")
        if not notice.payment_terms.payment_address:
            missing.append("payment address")

        # Check for phone number in raw text
        if not re.search(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', notice.raw_text):
            missing.append("telephone number")

        if missing:
            return Defect(
                defect_id="MVP-004",
                title="Missing Payee Information",
                severity=Severity.CRITICAL,
                description=f"Missing: {', '.join(missing)}",
                statute_violated="CCP 1161(2); Schwab v. Rondel Homes (1991)",
                tenant_action="This defect likely invalidates the notice.",
                evidence=f"Missing: {', '.join(missing)}"
            )

        return None

    def _check_payment_hours(self, notice: ExtractedNotice) -> Optional[Defect]:
        """Check if payment hours are stated for in-person payment."""
        text = notice.raw_text.lower()

        personal_indicators = ['in person', 'personally', 'at the office', 'deliver payment']
        if not any(ind in text for ind in personal_indicators):
            return None

        if not notice.payment_terms or not notice.payment_terms.payment_hours:
            return Defect(
                defect_id="MVP-005",
                title="Missing Payment Hours",
                severity=Severity.CRITICAL,
                description="Must state days/hours when payment can be made in person.",
                statute_violated="CCP 1161(2); Schnell v. City of Santa Monica (1978)",
                tenant_action="This defect invalidates the notice.",
                evidence="In-person payment mentioned but no hours stated"
            )

        return None

    def _check_financial_institution(self, notice: ExtractedNotice) -> Optional[Defect]:
        """Check financial institution payment requirements."""
        text = notice.raw_text.lower()

        # Check if payment at financial institution is mentioned
        bank_indicators = [
            'bank', 'credit union', 'financial institution',
            'wells fargo', 'chase', 'bank of america', 'citibank'
        ]
        if not any(ind in text for ind in bank_indicators):
            return None

        # If bank payment is mentioned, check requirements
        missing = []

        # Check for institution name (already confirmed by indicators above)
        # Check for street address near bank reference
        if not re.search(r'(\d+\s+\w+\s+(st|street|ave|avenue|blvd|boulevard|rd|road|dr|drive))', text):
            missing.append("street address")

        # Check for account number
        if not re.search(r'account\s*(number|#|no\.?)?\s*:?\s*\d+', text):
            missing.append("account number")

        # Check for 5-mile requirement language
        if not re.search(r'(five|5)\s*mile', text) and not re.search(r'within.{0,20}mile', text):
            missing.append("confirmation institution is within 5 miles of property")

        if missing:
            return Defect(
                defect_id="MVP-006",
                title="Incomplete Financial Institution Information",
                severity=Severity.CRITICAL,
                description=f"Payment at financial institution requires: institution name, "
                           f"street address, account number, and must be within 5 miles. "
                           f"Missing: {', '.join(missing)}",
                statute_violated="CCP 1161(2)",
                tenant_action="This defect likely invalidates the notice.",
                evidence=f"Financial institution mentioned but missing: {', '.join(missing)}"
            )

        return None

    def _check_electronic_payment(self, notice: ExtractedNotice) -> Optional[Defect]:
        """Check if electronic payment was previously established."""
        text = notice.raw_text.lower()

        e_payment = ['wire transfer', 'ach', 'electronic funds transfer', 'electronic payment',
                     'venmo', 'zelle', 'paypal', 'online payment', 'direct deposit']
        if not any(p in text for p in e_payment):
            return None

        established = ['previously established', 'previously arranged', 'previously agreed',
                       'as previously', 'already established']
        if any(e in text for e in established):
            return None

        return Defect(
            defect_id="MVP-007",
            title="Electronic Payment Not Previously Established",
            severity=Severity.CRITICAL,
            description="If electronic funds transfer is offered as a payment method, "
                       "the notice must state this method was previously established.",
            statute_violated="CCP 1161(2)",
            tenant_action="This defect invalidates the notice.",
            evidence="Electronic payment mentioned without 'previously established' language"
        )

    def _check_rent_age(self, notice: ExtractedNotice) -> Optional[Defect]:
        """Check if notice seeks rent over one year old."""
        if not notice.notice_date or not notice.period_start:
            return None

        age_days = (notice.notice_date - notice.period_start).days
        if age_days > 365:
            months = age_days // 30
            return Defect(
                defect_id="MVP-008",
                title="Rent Over One Year Old",
                severity=Severity.CRITICAL,
                description=f"The notice seeks rent from {months} months ago. "
                           f"A 3-day notice cannot demand rent that came due more than one year ago.",
                statute_violated="CCP 1161(2); WDT-Winchester v. Nilsson (1994)",
                tenant_action="This defect invalidates the notice for that portion of rent.",
                evidence=f"Rent period: {notice.period_start}, Notice date: {notice.notice_date}"
            )

        return None

    def _check_forfeiture_declaration(self, notice: ExtractedNotice) -> Optional[Defect]:
        """Check if notice declares a forfeiture."""
        if notice.has_forfeiture_declaration is not None:
            found = notice.has_forfeiture_declaration
        else:
            # Fallback: raw-text regex (backward compat for LLM path when field absent)
            text = notice.raw_text.lower()
            forfeiture_patterns = [
                r'forfeit',
                r'forfeiture',
                r'lease.{0,30}(terminated|void|ended)',
                r'tenancy.{0,30}(terminated|void|ended)',
                r'declare.{0,30}(terminated|void|forfeited)',
                r'legal proceedings.{0,60}recover possession.{0,120}unlawful detainer',
            ]
            found = any(re.search(p, text) for p in forfeiture_patterns)

        if found:
            return None

        return Defect(
            defect_id="MVP-009",
            title="No Forfeiture Declaration",
            severity=Severity.CRITICAL,
            description="The notice does not declare a forfeiture of the lease/tenancy.",
            statute_violated="CCP 1161(2)",
            tenant_action="The lack of forfeiture language may invalidate the notice.",
            evidence="No forfeiture or lease termination language found"
        )
