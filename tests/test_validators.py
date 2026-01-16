"""
Tests for eviction notice validators.

Example tests to get started with the test suite.
"""

import pytest
from decimal import Decimal
from datetime import date

from src.parser.structured_data import (
    ExtractedNotice,
    NoticeType,
    Charge,
    PaymentTerms
)
from src.validators import get_validator
from src.validators.three_day_pay import ThreeDayPayValidator


class TestThreeDayPayValidator:
    """Tests for 3-day pay or quit validator."""

    def test_valid_notice_no_defects(self):
        """Test that a valid notice has no defects."""
        notice = ExtractedNotice(
            raw_text="Sample notice text",
            notice_type=NoticeType.THREE_DAY_PAY,
            landlord_name="John Smith",
            tenant_names=["Jane Doe"],
            property_address="123 Main St, Apt 4, Los Angeles, CA 90001",
            total_amount_demanded=Decimal("1500.00"),
            charges=[
                Charge(description="Rent for January 2024", amount=Decimal("1500.00"), is_rent=True)
            ],
            notice_date=date(2024, 2, 1),
            payment_terms=PaymentTerms(
                payee_name="John Smith",
                payment_address="456 Office St, Los Angeles, CA 90002",
                payment_hours="Monday-Friday, 9:00 AM to 5:00 PM"
            ),
            is_signed=True
        )

        validator = ThreeDayPayValidator()
        defects = validator.validate(notice)

        # Should have no defects
        assert len(defects) == 0

    def test_non_rent_charges_defect(self):
        """Test that including late fees creates a critical defect."""
        notice = ExtractedNotice(
            raw_text="Sample notice text",
            notice_type=NoticeType.THREE_DAY_PAY,
            landlord_name="John Smith",
            tenant_names=["Jane Doe"],
            property_address="123 Main St, Los Angeles, CA 90001",
            total_amount_demanded=Decimal("1550.00"),
            charges=[
                Charge(description="Rent", amount=Decimal("1500.00"), is_rent=True),
                Charge(description="Late Fee", amount=Decimal("50.00"), is_rent=False)
            ],
            payment_terms=PaymentTerms(
                payee_name="John Smith",
                payment_address="456 Office St, Los Angeles, CA 90002",
                payment_hours="Monday-Friday, 9:00 AM to 5:00 PM"
            ),
            is_signed=True
        )

        validator = ThreeDayPayValidator()
        defects = validator.validate(notice)

        # Should have at least the non-rent charge defect
        assert len(defects) > 0

        # Find the specific defect
        non_rent_defect = next((d for d in defects if d.defect_id == "3DP-001"), None)
        assert non_rent_defect is not None
        assert non_rent_defect.severity.value == "critical"

    def test_missing_payment_address_defect(self):
        """Test that missing payment address creates a defect."""
        notice = ExtractedNotice(
            raw_text="Sample notice text",
            notice_type=NoticeType.THREE_DAY_PAY,
            landlord_name="John Smith",
            tenant_names=["Jane Doe"],
            property_address="123 Main St, Los Angeles, CA 90001",
            total_amount_demanded=Decimal("1500.00"),
            charges=[
                Charge(description="Rent", amount=Decimal("1500.00"), is_rent=True)
            ],
            payment_terms=None,  # No payment terms
            is_signed=True
        )

        validator = ThreeDayPayValidator()
        defects = validator.validate(notice)

        # Should find payment address defect
        payment_defect = next((d for d in defects if d.defect_id == "3DP-003"), None)
        assert payment_defect is not None

    def test_missing_tenant_name_defect(self):
        """Test that missing tenant name creates a defect."""
        notice = ExtractedNotice(
            raw_text="Sample notice text",
            notice_type=NoticeType.THREE_DAY_PAY,
            landlord_name="John Smith",
            tenant_names=[],  # No tenant names
            property_address="123 Main St, Los Angeles, CA 90001",
            total_amount_demanded=Decimal("1500.00"),
            charges=[
                Charge(description="Rent", amount=Decimal("1500.00"), is_rent=True)
            ],
            payment_terms=PaymentTerms(
                payee_name="John Smith",
                payment_address="456 Office St, Los Angeles, CA 90002",
                payment_hours="Monday-Friday, 9:00 AM to 5:00 PM"
            ),
            is_signed=True
        )

        validator = ThreeDayPayValidator()
        defects = validator.validate(notice)

        # Should find tenant name defect
        tenant_defect = next((d for d in defects if d.defect_id == "COM-001"), None)
        assert tenant_defect is not None


class TestValidatorFactory:
    """Tests for validator factory."""

    def test_get_three_day_pay_validator(self):
        """Test getting validator for 3-day pay notice."""
        validator = get_validator(NoticeType.THREE_DAY_PAY)
        assert validator is not None
        assert isinstance(validator, ThreeDayPayValidator)

    def test_unknown_notice_type_returns_none(self):
        """Test that unknown notice type returns None."""
        validator = get_validator(NoticeType.UNKNOWN)
        assert validator is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
