"""
Validator for 3-Day Notice to Pay Rent or Quit.

Implements validation rules specific to CCP § 1161(2).
"""

from typing import List, Optional
from decimal import Decimal
import logging

from .base import BaseValidator
from ..parser.structured_data import (
    ExtractedNotice,
    Defect,
    ValidationContext,
    Severity
)

logger = logging.getLogger(__name__)


class ThreeDayPayValidator(BaseValidator):
    """Validator for 3-Day Notice to Pay Rent or Quit."""

    def get_notice_type_key(self) -> str:
        return "three_day_pay_or_quit"

    def _validate_specific_requirements(
        self,
        notice: ExtractedNotice,
        context: Optional[ValidationContext]
    ) -> List[Defect]:
        """
        Validate 3-day pay or quit specific requirements.

        Args:
            notice: Extracted notice data
            context: Optional validation context

        Returns:
            List of defects found
        """
        defects = []

        # Rule 3DP-001: Rent only, no other charges
        defects.extend(self._validate_rent_only(notice))

        # Rule 3DP-002: Exact amount specified
        defect = self._validate_exact_amount(notice)
        if defect:
            defects.append(defect)

        # Rule 3DP-003: Payment address required
        defect = self._validate_payment_address(notice)
        if defect:
            defects.append(defect)

        # Rule 3DP-004: Payment person required
        defect = self._validate_payment_person(notice)
        if defect:
            defects.append(defect)

        # Rule 3DP-005: Payment hours required
        defect = self._validate_payment_hours(notice)
        if defect:
            defects.append(defect)

        # Rule 3DP-006: No contradictory demands
        defect = self._validate_no_contradictory_demands(notice)
        if defect:
            defects.append(defect)

        # Rule 3DP-007: Correct calculation (if we have context)
        if context and context.monthly_rent:
            defect = self._validate_calculation(notice, context)
            if defect:
                defects.append(defect)

        # Rule 3DP-008: Rental period specified
        defect = self._validate_rental_period(notice)
        if defect:
            defects.append(defect)

        return defects

    def _validate_rent_only(self, notice: ExtractedNotice) -> List[Defect]:
        """
        Validate that notice demands rent only, no other charges.

        Rule 3DP-001: Critical defect if non-rent charges included.
        """
        defects = []

        # Check if any charges are marked as non-rent
        non_rent_charges = [c for c in notice.charges if not c.is_rent]

        if non_rent_charges:
            charge_descriptions = ', '.join([f"${c.amount} for {c.description}"
                                            for c in non_rent_charges])

            rule_data = self._get_specific_rule("3DP-001")
            defect = self._create_defect(
                rule_id="3DP-001",
                rule_data=rule_data,
                evidence=f"Non-rent charges found: {charge_descriptions}"
            )
            defects.append(defect)

            logger.warning(f"Found {len(non_rent_charges)} non-rent charges in 3-day pay notice")

        return defects

    def _validate_exact_amount(self, notice: ExtractedNotice) -> Optional[Defect]:
        """
        Validate that an exact dollar amount is specified.

        Rule 3DP-002: Critical defect if amount is missing or vague.
        """
        if notice.total_amount_demanded is None or notice.total_amount_demanded == 0:
            rule_data = self._get_specific_rule("3DP-002")
            return self._create_defect(
                rule_id="3DP-002",
                rule_data=rule_data,
                evidence="No specific dollar amount found in notice"
            )

        # Check if amount seems unreasonably high (potential OCR error or mistake)
        if notice.total_amount_demanded > 100000:  # $100k seems unreasonable for rent
            logger.warning(f"Unusually high rent amount: ${notice.total_amount_demanded}")
            # Don't create defect, but log for review

        return None

    def _validate_payment_address(self, notice: ExtractedNotice) -> Optional[Defect]:
        """
        Validate that payment address is specified.

        Rule 3DP-003: Critical defect if missing.
        """
        if not notice.payment_terms or not notice.payment_terms.payment_address:
            rule_data = self._get_specific_rule("3DP-003")
            return self._create_defect(
                rule_id="3DP-003",
                rule_data=rule_data,
                evidence="No payment address specified in notice"
            )

        return None

    def _validate_payment_person(self, notice: ExtractedNotice) -> Optional[Defect]:
        """
        Validate that payee name is specified.

        Rule 3DP-004: Critical defect if missing.
        """
        if not notice.payment_terms or not notice.payment_terms.payee_name:
            rule_data = self._get_specific_rule("3DP-004")
            return self._create_defect(
                rule_id="3DP-004",
                rule_data=rule_data,
                evidence="No payee name specified in notice"
            )

        return None

    def _validate_payment_hours(self, notice: ExtractedNotice) -> Optional[Defect]:
        """
        Validate that payment hours are specified.

        Rule 3DP-005: Critical defect if missing.
        """
        if not notice.payment_terms or not notice.payment_terms.payment_hours:
            rule_data = self._get_specific_rule("3DP-005")
            return self._create_defect(
                rule_id="3DP-005",
                rule_data=rule_data,
                evidence="No payment hours specified in notice"
            )

        return None

    def _validate_no_contradictory_demands(self, notice: ExtractedNotice) -> Optional[Defect]:
        """
        Validate that notice doesn't demand both payment AND possession.

        Rule 3DP-006: Critical defect if notice demands immediate possession
        regardless of payment.
        """
        # This requires analyzing the raw text for contradictory language
        # Look for phrases that suggest immediate possession is demanded
        suspicious_phrases = [
            "must vacate immediately",
            "immediate possession",
            "vacate now",
            "leave immediately regardless"
        ]

        raw_text_lower = notice.raw_text.lower()

        for phrase in suspicious_phrases:
            if phrase in raw_text_lower:
                rule_data = self._get_specific_rule("3DP-006")
                return self._create_defect(
                    rule_id="3DP-006",
                    rule_data=rule_data,
                    evidence=f"Notice contains language suggesting immediate possession: '{phrase}'"
                )

        return None

    def _validate_calculation(
        self,
        notice: ExtractedNotice,
        context: ValidationContext
    ) -> Optional[Defect]:
        """
        Validate that rent amount is correctly calculated.

        Rule 3DP-007: Critical if amount is incorrect.
        Requires context with monthly_rent.
        """
        if not context.monthly_rent:
            return None

        # Calculate expected rent based on period
        if notice.period_start and notice.period_end:
            # Calculate months
            months = (notice.period_end.year - notice.period_start.year) * 12 + \
                    (notice.period_end.month - notice.period_start.month)

            if months <= 0:
                months = 1  # At least one month

            expected_amount = context.monthly_rent * months

            # Allow small variance for rounding
            if abs(notice.total_amount_demanded - expected_amount) > 1:
                rule_data = self._get_specific_rule("3DP-007")
                return self._create_defect(
                    rule_id="3DP-007",
                    rule_data=rule_data,
                    evidence=f"Notice demands ${notice.total_amount_demanded}, "
                            f"but expected ${expected_amount} based on monthly rent "
                            f"of ${context.monthly_rent} for {months} month(s)"
                )

        return None

    def _validate_rental_period(self, notice: ExtractedNotice) -> Optional[Defect]:
        """
        Validate that rental period is specified.

        Rule 3DP-008: Major defect if missing.
        """
        if not notice.period_start and not notice.period_end:
            rule_data = self._get_specific_rule("3DP-008")
            return self._create_defect(
                rule_id="3DP-008",
                rule_data=rule_data,
                evidence="No rental period specified in notice"
            )

        return None
