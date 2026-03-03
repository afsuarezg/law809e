"""
Tests for the notice validator.
"""

import pytest
from datetime import date
from decimal import Decimal

from eviction_checker.models import (
    ExtractedNotice,
    NoticeType,
    Charge,
    PaymentTerms,
    Severity
)
from eviction_checker.validator import NoticeValidator


@pytest.fixture
def validator():
    return NoticeValidator()


@pytest.fixture
def valid_notice():
    """A notice with no defects."""
    return ExtractedNotice(
        raw_text="""
        3-DAY NOTICE TO PAY RENT OR QUIT

        To: John Doe
        Property: 123 Main St, Los Angeles, CA 90001

        You owe $1,500.00 for rent for January 2024.

        Pay the above amount OR quit and vacate the premises within 3 days.

        NOTICE: Your failure to pay rent or vacate will result in forfeiture
        of your lease and tenancy will be terminated.

        Payment must be made to:
        ABC Property Management
        456 Business Ave, Suite 100
        Los Angeles, CA 90002
        Phone: (310) 555-1234

        Office hours: Monday-Friday 9:00 AM to 5:00 PM

        Dated: January 15, 2024
        Signed: Jane Smith, Property Manager
        """,
        notice_type=NoticeType.THREE_DAY_PAY,
        landlord_name="Jane Smith",
        tenant_names=["John Doe"],
        property_address="123 Main St, Los Angeles, CA 90001",
        total_amount_demanded=Decimal("1500.00"),
        charges=[
            Charge(description="Rent for January 2024", amount=Decimal("1500.00"), is_rent=True)
        ],
        notice_date=date(2024, 1, 15),
        service_date=date(2024, 1, 15),
        termination_date=date(2024, 1, 19),  # 3 business days later
        period_start=date(2024, 1, 1),
        period_end=date(2024, 1, 31),
        payment_terms=PaymentTerms(
            payee_name="ABC Property Management",
            payment_address="456 Business Ave, Suite 100, Los Angeles, CA 90002",
            payment_hours="Monday-Friday 9:00 AM to 5:00 PM",
            payment_methods=["cash", "check", "money order"]
        ),
        is_signed=True
    )


class TestValidNotice:
    def test_valid_notice_has_no_defects(self, validator, valid_notice):
        defects = validator.validate(valid_notice)
        assert len(defects) == 0


class TestDisjunctivePhrasing:
    """MVP-001: Notice must give tenant option to pay OR quit."""

    def test_missing_disjunctive_language(self, validator):
        notice = ExtractedNotice(
            raw_text="You must pay $1500 immediately. Forfeiture declared.",
            notice_type=NoticeType.THREE_DAY_PAY,
            total_amount_demanded=Decimal("1500")
        )
        defects = validator.validate(notice)
        assert any(d.defect_id == "MVP-001" for d in defects)

    def test_has_pay_or_quit(self, validator):
        notice = ExtractedNotice(
            raw_text="Pay rent or quit within 3 days. Forfeiture. Phone: (310) 555-1234",
            notice_type=NoticeType.THREE_DAY_PAY,
            total_amount_demanded=Decimal("1500"),
            payment_terms=PaymentTerms(payee_name="Landlord", payment_address="123 Main St")
        )
        defects = validator.validate(notice)
        assert not any(d.defect_id == "MVP-001" for d in defects)

    def test_has_pay_or_vacate(self, validator):
        notice = ExtractedNotice(
            raw_text="Pay rent or vacate. Forfeiture. Phone: (310) 555-1234",
            notice_type=NoticeType.THREE_DAY_PAY,
            total_amount_demanded=Decimal("1500"),
            payment_terms=PaymentTerms(payee_name="Landlord", payment_address="123 Main St")
        )
        defects = validator.validate(notice)
        assert not any(d.defect_id == "MVP-001" for d in defects)


class TestNoticePeriod:
    """MVP-002: Must give 3 business days excluding weekends/holidays."""

    def test_missing_service_date_no_days_is_not_defect(self, validator):
        # Per updated logic: missing service_date with no days_to_comply gives
        # benefit of the doubt — cannot assess the period on the face of the doc.
        notice = ExtractedNotice(
            raw_text="Pay rent or quit. Forfeiture.",
            notice_type=NoticeType.THREE_DAY_PAY,
            service_date=None,
            days_to_comply=None,
        )
        defects = validator.validate(notice)
        assert not any(d.defect_id == "MVP-002" for d in defects)

    def test_missing_service_date_with_insufficient_days_is_defect(self, validator):
        # days_to_comply explicitly states fewer than 3 → still a genuine defect.
        notice = ExtractedNotice(
            raw_text="Pay rent or quit. Forfeiture. Phone: (310) 555-1234",
            notice_type=NoticeType.THREE_DAY_PAY,
            service_date=None,
            days_to_comply=1,
            total_amount_demanded=Decimal("1500"),
            payment_terms=PaymentTerms(payee_name="Landlord", payment_address="123 Main St"),
        )
        defects = validator.validate(notice)
        assert any(d.defect_id == "MVP-002" for d in defects)

    def test_insufficient_notice_period(self, validator):
        notice = ExtractedNotice(
            raw_text="Pay rent or quit. Forfeiture. Phone: (310) 555-1234",
            notice_type=NoticeType.THREE_DAY_PAY,
            service_date=date(2024, 1, 15),
            termination_date=date(2024, 1, 16),  # Only 1 day
            total_amount_demanded=Decimal("1500"),
            payment_terms=PaymentTerms(payee_name="Landlord", payment_address="123 Main St")
        )
        defects = validator.validate(notice)
        period_defects = [d for d in defects if d.defect_id == "MVP-002"]
        assert len(period_defects) == 1
        assert period_defects[0].severity == Severity.CRITICAL


class TestAmountStated:
    """MVP-003: Must state exact dollar amount of rent due."""

    def test_no_amount_stated(self, validator):
        notice = ExtractedNotice(
            raw_text="Pay rent or quit. You owe back rent. Forfeiture.",
            notice_type=NoticeType.THREE_DAY_PAY,
            total_amount_demanded=None
        )
        defects = validator.validate(notice)
        assert any(d.defect_id == "MVP-003" for d in defects)

    def test_zero_amount(self, validator):
        notice = ExtractedNotice(
            raw_text="Pay rent or quit. Forfeiture.",
            notice_type=NoticeType.THREE_DAY_PAY,
            total_amount_demanded=Decimal("0")
        )
        defects = validator.validate(notice)
        assert any(d.defect_id == "MVP-003" for d in defects)

    def test_amount_stated(self, validator):
        notice = ExtractedNotice(
            raw_text="Pay rent or quit. You owe $1500. Forfeiture. Phone: (310) 555-1234",
            notice_type=NoticeType.THREE_DAY_PAY,
            total_amount_demanded=Decimal("1500"),
            payment_terms=PaymentTerms(payee_name="Landlord", payment_address="123 Main St")
        )
        defects = validator.validate(notice)
        assert not any(d.defect_id == "MVP-003" for d in defects)


class TestPayeeInformation:
    """MVP-004: Must state name, telephone, and address of payee."""

    def test_no_payment_terms(self, validator):
        notice = ExtractedNotice(
            raw_text="Pay rent or quit. Forfeiture.",
            notice_type=NoticeType.THREE_DAY_PAY,
            payment_terms=None
        )
        defects = validator.validate(notice)
        assert any(d.defect_id == "MVP-004" for d in defects)

    def test_missing_phone(self, validator):
        notice = ExtractedNotice(
            raw_text="Pay rent or quit. Forfeiture.",
            notice_type=NoticeType.THREE_DAY_PAY,
            total_amount_demanded=Decimal("1500"),
            payment_terms=PaymentTerms(
                payee_name="Landlord",
                payment_address="123 Main St"
            )
        )
        defects = validator.validate(notice)
        payee_defects = [d for d in defects if d.defect_id == "MVP-004"]
        assert len(payee_defects) == 1
        assert "telephone" in payee_defects[0].evidence.lower()

    def test_all_payee_info_present(self, validator):
        notice = ExtractedNotice(
            raw_text="Pay rent or quit. Forfeiture. Call (310) 555-1234",
            notice_type=NoticeType.THREE_DAY_PAY,
            total_amount_demanded=Decimal("1500"),
            payment_terms=PaymentTerms(
                payee_name="ABC Management",
                payment_address="123 Main St, LA, CA 90001"
            )
        )
        defects = validator.validate(notice)
        assert not any(d.defect_id == "MVP-004" for d in defects)


class TestPaymentHours:
    """MVP-005: If personal payment, must state days and hours."""

    def test_in_person_without_hours(self, validator):
        notice = ExtractedNotice(
            raw_text="Pay rent or quit. Pay in person at the office. Forfeiture. Phone: (310) 555-1234",
            notice_type=NoticeType.THREE_DAY_PAY,
            total_amount_demanded=Decimal("1500"),
            payment_terms=PaymentTerms(
                payee_name="Landlord",
                payment_address="123 Main St"
            )
        )
        defects = validator.validate(notice)
        assert any(d.defect_id == "MVP-005" for d in defects)

    def test_no_personal_payment_mentioned(self, validator):
        notice = ExtractedNotice(
            raw_text="Pay rent or quit. Mail payment. Forfeiture. Phone: (310) 555-1234",
            notice_type=NoticeType.THREE_DAY_PAY,
            total_amount_demanded=Decimal("1500"),
            payment_terms=PaymentTerms(
                payee_name="Landlord",
                payment_address="123 Main St"
            )
        )
        defects = validator.validate(notice)
        assert not any(d.defect_id == "MVP-005" for d in defects)


class TestFinancialInstitution:
    """MVP-006: If bank payment, must have name, address, account, within 5 miles."""

    def test_bank_missing_account_number(self, validator):
        notice = ExtractedNotice(
            raw_text="Pay rent or quit. Pay at Wells Fargo. Forfeiture. Phone: (310) 555-1234",
            notice_type=NoticeType.THREE_DAY_PAY,
            total_amount_demanded=Decimal("1500"),
            payment_terms=PaymentTerms(
                payee_name="Landlord",
                payment_address="123 Main St"
            )
        )
        defects = validator.validate(notice)
        assert any(d.defect_id == "MVP-006" for d in defects)

    def test_no_bank_mentioned(self, validator):
        notice = ExtractedNotice(
            raw_text="Pay rent or quit. Forfeiture. Phone: (310) 555-1234",
            notice_type=NoticeType.THREE_DAY_PAY,
            total_amount_demanded=Decimal("1500"),
            payment_terms=PaymentTerms(
                payee_name="Landlord",
                payment_address="123 Main St"
            )
        )
        defects = validator.validate(notice)
        assert not any(d.defect_id == "MVP-006" for d in defects)


class TestElectronicPayment:
    """MVP-007: Electronic payment must be previously established."""

    def test_electronic_not_established(self, validator):
        notice = ExtractedNotice(
            raw_text="Pay rent or quit. Pay via Zelle or Venmo. Forfeiture. Phone: (310) 555-1234",
            notice_type=NoticeType.THREE_DAY_PAY,
            total_amount_demanded=Decimal("1500"),
            payment_terms=PaymentTerms(
                payee_name="Landlord",
                payment_address="123 Main St"
            )
        )
        defects = validator.validate(notice)
        assert any(d.defect_id == "MVP-007" for d in defects)

    def test_electronic_previously_established(self, validator):
        notice = ExtractedNotice(
            raw_text="Pay rent or quit. Pay via Zelle as previously established. Forfeiture. Phone: (310) 555-1234",
            notice_type=NoticeType.THREE_DAY_PAY,
            total_amount_demanded=Decimal("1500"),
            payment_terms=PaymentTerms(
                payee_name="Landlord",
                payment_address="123 Main St"
            )
        )
        defects = validator.validate(notice)
        assert not any(d.defect_id == "MVP-007" for d in defects)


class TestRentAge:
    """MVP-008: Cannot demand rent over one year old."""

    def test_rent_over_one_year(self, validator):
        notice = ExtractedNotice(
            raw_text="Pay rent or quit. Forfeiture. Phone: (310) 555-1234",
            notice_type=NoticeType.THREE_DAY_PAY,
            notice_date=date(2024, 6, 1),
            period_start=date(2023, 1, 1),  # 17 months ago
            total_amount_demanded=Decimal("1500"),
            payment_terms=PaymentTerms(
                payee_name="Landlord",
                payment_address="123 Main St"
            )
        )
        defects = validator.validate(notice)
        assert any(d.defect_id == "MVP-008" for d in defects)

    def test_rent_within_one_year(self, validator):
        notice = ExtractedNotice(
            raw_text="Pay rent or quit. Forfeiture. Phone: (310) 555-1234",
            notice_type=NoticeType.THREE_DAY_PAY,
            notice_date=date(2024, 6, 1),
            period_start=date(2024, 5, 1),  # 1 month ago
            total_amount_demanded=Decimal("1500"),
            payment_terms=PaymentTerms(
                payee_name="Landlord",
                payment_address="123 Main St"
            )
        )
        defects = validator.validate(notice)
        assert not any(d.defect_id == "MVP-008" for d in defects)


class TestForfeitureDeclaration:
    """MVP-009: Notice must declare forfeiture."""

    def test_no_forfeiture(self, validator):
        notice = ExtractedNotice(
            raw_text="Pay rent or quit. Phone: (310) 555-1234",
            notice_type=NoticeType.THREE_DAY_PAY,
            total_amount_demanded=Decimal("1500"),
            payment_terms=PaymentTerms(
                payee_name="Landlord",
                payment_address="123 Main St"
            )
        )
        defects = validator.validate(notice)
        assert any(d.defect_id == "MVP-009" for d in defects)

    def test_has_forfeiture(self, validator):
        notice = ExtractedNotice(
            raw_text="Pay rent or quit. Failure to comply will result in forfeiture. Phone: (310) 555-1234",
            notice_type=NoticeType.THREE_DAY_PAY,
            total_amount_demanded=Decimal("1500"),
            payment_terms=PaymentTerms(
                payee_name="Landlord",
                payment_address="123 Main St"
            )
        )
        defects = validator.validate(notice)
        assert not any(d.defect_id == "MVP-009" for d in defects)

    def test_lease_terminated_language(self, validator):
        notice = ExtractedNotice(
            raw_text="Pay rent or quit. Your lease will be terminated. Phone: (310) 555-1234",
            notice_type=NoticeType.THREE_DAY_PAY,
            total_amount_demanded=Decimal("1500"),
            payment_terms=PaymentTerms(
                payee_name="Landlord",
                payment_address="123 Main St"
            )
        )
        defects = validator.validate(notice)
        assert not any(d.defect_id == "MVP-009" for d in defects)

    def test_extracted_true_overrides_missing_raw_text(self, validator):
        """has_forfeiture_declaration=True suppresses MVP-009 even without keywords in raw_text."""
        notice = ExtractedNotice(
            raw_text="Pay rent or quit. Phone: (310) 555-1234",
            notice_type=NoticeType.THREE_DAY_PAY,
            total_amount_demanded=Decimal("1500"),
            payment_terms=PaymentTerms(payee_name="Landlord", payment_address="123 Main St"),
            has_forfeiture_declaration=True,
        )
        defects = validator.validate(notice)
        assert not any(d.defect_id == "MVP-009" for d in defects)

    def test_extracted_false_fires_defect_despite_raw_text(self, validator):
        """has_forfeiture_declaration=False fires MVP-009 even when raw_text has keywords."""
        notice = ExtractedNotice(
            raw_text="Pay rent or quit. Forfeiture declared. Phone: (310) 555-1234",
            notice_type=NoticeType.THREE_DAY_PAY,
            total_amount_demanded=Decimal("1500"),
            payment_terms=PaymentTerms(payee_name="Landlord", payment_address="123 Main St"),
            has_forfeiture_declaration=False,
        )
        defects = validator.validate(notice)
        assert any(d.defect_id == "MVP-009" for d in defects)


class TestBusinessDayCalculation:
    """Test business day calculation helper."""

    def test_excludes_weekends(self, validator):
        # Friday Jan 5 to Monday Jan 8 = 1 business day (Monday; not a holiday)
        days = validator._count_business_days(date(2024, 1, 5), date(2024, 1, 8))
        assert days == 1

    def test_full_week(self, validator):
        # Monday Jan 15 to Friday Jan 19 = 4 business days (but Jan 15 is MLK Day)
        days = validator._count_business_days(date(2024, 1, 15), date(2024, 1, 19))
        assert days == 4  # Tue, Wed, Thu, Fri

    def test_holiday_mlk_day(self, validator):
        # MLK Day is 3rd Monday in January (Jan 15, 2024)
        assert validator._is_holiday(date(2024, 1, 15)) is True
        assert validator._is_holiday(date(2024, 1, 16)) is False

    def test_christmas(self, validator):
        assert validator._is_holiday(date(2024, 12, 25)) is True
        assert validator._is_holiday(date(2024, 12, 26)) is False

    def test_thanksgiving(self, validator):
        # Thanksgiving 2024 is Nov 28 (4th Thursday)
        assert validator._is_holiday(date(2024, 11, 28)) is True
