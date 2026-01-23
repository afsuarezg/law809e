"""
Synthetic eviction notice generator.

Generates valid and invalid 3-day notices with configurable defects.
"""

import random
from datetime import date, timedelta
from typing import List, Optional, Set
from copy import deepcopy

from .models import NoticeData, GeneratedNotice, DefectType
from .templates.base import (
    DISJUNCTIVE_DEMAND,
    NON_DISJUNCTIVE_DEMAND,
    AMOUNT_STATED_LANGUAGE,
    NO_AMOUNT_LANGUAGE,
    PAYMENT_SECTION_FULL,
    PAYMENT_SECTION_MISSING_PHONE,
    PAYMENT_SECTION_MISSING_ADDRESS,
    PERSONAL_PAYMENT_HOURS,
    PERSONAL_PAYMENT_NO_HOURS,
    BANK_PAYMENT_COMPLETE,
    BANK_PAYMENT_INCOMPLETE,
    ELECTRONIC_PAYMENT_ESTABLISHED,
    ELECTRONIC_PAYMENT_NOT_ESTABLISHED,
    FORFEITURE_DECLARATION,
    NO_FORFEITURE_DECLARATION,
)


# Sample data for randomization
SAMPLE_LANDLORDS = [
    ("ABC Property Management", "456 Business Ave, Suite 100, Los Angeles, CA 90001", "(310) 555-1234"),
    ("Golden State Rentals", "789 Oak Street, San Francisco, CA 94102", "(415) 555-5678"),
    ("Sunshine Properties LLC", "321 Palm Drive, San Diego, CA 92101", "(619) 555-9012"),
    ("Bay Area Housing Inc.", "555 Market Street, Oakland, CA 94612", "(510) 555-3456"),
    ("Pacific Coast Apartments", "888 Beach Blvd, Santa Monica, CA 90401", "(424) 555-7890"),
    ("John Smith", "123 Residential Lane, Pasadena, CA 91101", "(626) 555-2345"),
    ("Maria Garcia", "456 Homeowner Way, Long Beach, CA 90802", "(562) 555-6789"),
]

SAMPLE_TENANTS = [
    ["John Doe"],
    ["Jane Smith"],
    ["Robert Johnson", "Mary Johnson"],
    ["Michael Williams"],
    ["David Brown", "Sarah Brown", "James Brown"],
    ["Emily Davis"],
    ["Christopher Martinez", "Jennifer Martinez"],
    ["Daniel Anderson"],
    ["Jessica Taylor"],
    ["Matthew Thomas", "Ashley Thomas"],
]

SAMPLE_ADDRESSES = [
    "123 Main Street, Apt 4B, Los Angeles, CA 90001",
    "456 Oak Avenue, Unit 12, San Francisco, CA 94102",
    "789 Elm Road, San Diego, CA 92101",
    "321 Pine Street, Apt 7, Oakland, CA 94612",
    "555 Maple Drive, Santa Monica, CA 90401",
    "888 Cedar Lane, Unit 3A, Pasadena, CA 91101",
    "111 Birch Court, Long Beach, CA 90802",
    "222 Walnut Street, Apt 5, Burbank, CA 91502",
    "333 Spruce Avenue, Unit 8B, Glendale, CA 91201",
    "444 Willow Way, Irvine, CA 92614",
]

SAMPLE_BANKS = [
    ("Wells Fargo Bank", "100 Bank Street, Los Angeles, CA 90001", "1234567890"),
    ("Chase Bank", "200 Financial Ave, San Francisco, CA 94102", "0987654321"),
    ("Bank of America", "300 Commerce Blvd, San Diego, CA 92101", "1122334455"),
    ("Citibank", "400 Money Lane, Oakland, CA 94612", "5544332211"),
]

ELECTRONIC_METHODS = ["Zelle", "Venmo", "PayPal", "direct ACH transfer", "wire transfer"]


class NoticeGenerator:
    """Generates synthetic eviction notices."""

    def __init__(self, seed: Optional[int] = None):
        """Initialize generator with optional random seed."""
        if seed is not None:
            random.seed(seed)

    def generate_valid_notice(self, data: Optional[NoticeData] = None) -> GeneratedNotice:
        """Generate a completely valid notice."""
        if data is None:
            data = self._random_valid_data()

        text = self._build_notice(data, defects=set())
        return GeneratedNotice(
            text=text,
            data=data,
            defects=[],
            is_valid=True
        )

    def generate_invalid_notice(
        self,
        defects: List[DefectType],
        data: Optional[NoticeData] = None
    ) -> GeneratedNotice:
        """Generate a notice with specific defects."""
        if data is None:
            data = self._random_valid_data()

        # Modify data based on defects
        data = self._apply_defect_data(data, defects)

        text = self._build_notice(data, defects=set(defects))
        return GeneratedNotice(
            text=text,
            data=data,
            defects=defects,
            is_valid=False
        )

    def generate_random_invalid_notice(
        self,
        num_defects: int = 1,
        data: Optional[NoticeData] = None
    ) -> GeneratedNotice:
        """Generate a notice with random defects."""
        all_defects = list(DefectType)
        selected = random.sample(all_defects, min(num_defects, len(all_defects)))
        return self.generate_invalid_notice(selected, data)

    def generate_batch(
        self,
        count: int,
        valid_ratio: float = 0.3,
        max_defects_per_notice: int = 3
    ) -> List[GeneratedNotice]:
        """Generate a batch of notices with specified valid/invalid ratio."""
        notices = []
        num_valid = int(count * valid_ratio)
        num_invalid = count - num_valid

        # Generate valid notices
        for _ in range(num_valid):
            notices.append(self.generate_valid_notice())

        # Generate invalid notices with varying defects
        for _ in range(num_invalid):
            num_defects = random.randint(1, max_defects_per_notice)
            notices.append(self.generate_random_invalid_notice(num_defects))

        random.shuffle(notices)
        return notices

    def _random_valid_data(self) -> NoticeData:
        """Generate random but valid notice data."""
        landlord = random.choice(SAMPLE_LANDLORDS)

        # Random dates (notice within last 30 days, deadline 3+ business days out)
        base_date = date.today() - timedelta(days=random.randint(0, 30))
        deadline = self._add_business_days(base_date, 3)

        # Random rent period (1-3 months back)
        months_back = random.randint(1, 3)
        period_month = base_date.month - months_back
        period_year = base_date.year
        while period_month < 1:
            period_month += 12
            period_year -= 1
        period_start = date(period_year, period_month, 1)
        period_end = date(period_start.year, period_start.month, 28)  # Simplified

        return NoticeData(
            landlord_name=landlord[0],
            landlord_address=landlord[1],
            landlord_phone=landlord[2],
            tenant_names=random.choice(SAMPLE_TENANTS),
            property_address=random.choice(SAMPLE_ADDRESSES),
            rent_amount=random.choice([1200, 1500, 1800, 2000, 2200, 2500, 2800, 3000]),
            rent_period_start=period_start,
            rent_period_end=period_end,
            notice_date=base_date,
            service_date=base_date,
            deadline_date=deadline,
            allow_personal_payment=True,
            payment_hours="Monday through Friday, 9:00 AM to 5:00 PM",
            allow_bank_payment=random.choice([True, False]),
            bank_name=random.choice(SAMPLE_BANKS)[0] if random.choice([True, False]) else None,
            bank_address=random.choice(SAMPLE_BANKS)[1] if random.choice([True, False]) else None,
            bank_account=random.choice(SAMPLE_BANKS)[2] if random.choice([True, False]) else None,
            allow_electronic_payment=False,  # Keep simple for valid
            use_disjunctive=True,
            include_forfeiture=True,
        )

    def _apply_defect_data(self, data: NoticeData, defects: List[DefectType]) -> NoticeData:
        """Modify data to create specific defects."""
        data = deepcopy(data)

        for defect in defects:
            if defect == DefectType.NOT_DISJUNCTIVE:
                data.use_disjunctive = False

            elif defect == DefectType.INSUFFICIENT_PERIOD:
                # Set deadline to only 1-2 days out (not enough)
                data.deadline_date = data.service_date + timedelta(days=random.randint(1, 2))

            elif defect == DefectType.NO_AMOUNT_STATED:
                data.rent_amount = 0  # Will trigger no-amount language

            elif defect == DefectType.MISSING_PAYEE_INFO:
                # Randomly remove one piece of info
                choice = random.choice(["phone", "address", "name"])
                if choice == "phone":
                    data.landlord_phone = ""
                elif choice == "address":
                    data.landlord_address = ""
                else:
                    data.landlord_name = ""

            elif defect == DefectType.MISSING_PAYMENT_HOURS:
                data.allow_personal_payment = True
                data.payment_hours = ""  # Will trigger missing hours

            elif defect == DefectType.FINANCIAL_INSTITUTION_INCOMPLETE:
                data.allow_bank_payment = True
                bank = random.choice(SAMPLE_BANKS)
                data.bank_name = bank[0]
                # Missing address or account
                if random.choice([True, False]):
                    data.bank_address = ""
                    data.bank_account = bank[2]
                else:
                    data.bank_address = bank[1]
                    data.bank_account = ""

            elif defect == DefectType.ELECTRONIC_PAYMENT_NOT_ESTABLISHED:
                data.allow_electronic_payment = True
                data.electronic_method = random.choice(ELECTRONIC_METHODS)

            elif defect == DefectType.RENT_OVER_ONE_YEAR:
                # Set rent period to over a year ago
                data.rent_period_start = data.notice_date - timedelta(days=random.randint(400, 500))
                data.rent_period_end = data.rent_period_start + timedelta(days=30)

            elif defect == DefectType.NO_FORFEITURE:
                data.include_forfeiture = False

        return data

    def _build_notice(self, data: NoticeData, defects: Set[DefectType]) -> str:
        """Build the notice text from data and defects."""
        lines = []

        # Header
        lines.append("=" * 70)
        lines.append("THREE-DAY NOTICE TO PAY RENT OR QUIT")
        lines.append("=" * 70)
        lines.append("")

        # Addressee
        tenant_str = ", ".join(data.tenant_names)
        lines.append(f"TO: {tenant_str}")
        lines.append("    AND ALL OTHER OCCUPANTS IN POSSESSION OF THE PREMISES AT:")
        lines.append("")
        lines.append(f"PROPERTY ADDRESS: {data.property_address}")
        lines.append("")

        # Amount section
        if DefectType.NO_AMOUNT_STATED in defects or data.rent_amount == 0:
            lines.append("PLEASE TAKE NOTICE that the rent on the above-described premises")
            lines.append("occupied by you is now due and unpaid.")
        else:
            lines.append(f"PLEASE TAKE NOTICE that the rent on the above-described premises")
            lines.append(f"occupied by you, in the amount of ${data.rent_amount:,.2f}, for the")
            lines.append(f"period from {data.rent_period_start.strftime('%B %d, %Y')} to")
            lines.append(f"{data.rent_period_end.strftime('%B %d, %Y')}, is now due and unpaid.")
        lines.append("")

        # Demand section (disjunctive or not)
        if DefectType.NOT_DISJUNCTIVE in defects or not data.use_disjunctive:
            lines.append("YOU ARE HEREBY REQUIRED to pay the said rent in full within THREE (3)")
            lines.append("DAYS after service of this notice AND vacate and surrender possession")
            lines.append("of the premises immediately.")
        else:
            lines.append("YOU ARE HEREBY REQUIRED to pay the said rent in full within THREE (3)")
            lines.append("DAYS after service of this notice, or to vacate and surrender")
            lines.append("possession of the premises.")
        lines.append("")

        # Payment information section
        lines.append("-" * 70)
        lines.append("PAYMENT INFORMATION")
        lines.append("-" * 70)
        lines.append("")

        # Payee info (potentially missing pieces)
        if data.landlord_name:
            lines.append(f"Rent must be paid to: {data.landlord_name}")
        if data.landlord_address:
            lines.append(f"Address: {data.landlord_address}")
        if data.landlord_phone:
            lines.append(f"Telephone: {data.landlord_phone}")
        lines.append("")

        # Personal payment hours
        if data.allow_personal_payment:
            if DefectType.MISSING_PAYMENT_HOURS in defects or not data.payment_hours:
                lines.append("Payment may be made in person at our office.")
            else:
                lines.append("Payment may be made in person during the following hours:")
                lines.append(f"    {data.payment_hours}")
        lines.append("")

        # Bank payment info
        if data.allow_bank_payment and data.bank_name:
            if DefectType.FINANCIAL_INSTITUTION_INCOMPLETE in defects:
                lines.append(f"Payment may also be made at {data.bank_name}.")
                if data.bank_address:
                    lines.append(f"    Address: {data.bank_address}")
                if data.bank_account:
                    lines.append(f"    Account: {data.bank_account}")
                # Missing the 5-mile statement
            else:
                lines.append("Payment may also be made at the following financial institution")
                lines.append("located within five (5) miles of the rental property:")
                lines.append(f"    Bank: {data.bank_name}")
                if data.bank_address:
                    lines.append(f"    Address: {data.bank_address}")
                if data.bank_account:
                    lines.append(f"    Account Number: {data.bank_account}")
            lines.append("")

        # Electronic payment
        if data.allow_electronic_payment and data.electronic_method:
            if DefectType.ELECTRONIC_PAYMENT_NOT_ESTABLISHED in defects:
                lines.append(f"Payment may be made via {data.electronic_method}.")
            else:
                lines.append(f"Payment may be made via {data.electronic_method}, as previously")
                lines.append("established between landlord and tenant.")
            lines.append("")

        lines.append("-" * 70)
        lines.append("")

        # Legal notice and forfeiture
        lines.append("PLEASE TAKE NOTICE that if you fail to pay the rent in full OR vacate")
        lines.append("the premises within three (3) days after service of this notice")
        lines.append("(excluding Saturdays, Sundays, and judicial holidays), the undersigned")
        lines.append("will institute legal proceedings against you to recover possession of")
        lines.append("the premises and to recover rents and damages.")
        lines.append("")

        # Forfeiture declaration
        if DefectType.NO_FORFEITURE not in defects and data.include_forfeiture:
            lines.append("NOTICE OF FORFEITURE: Your failure to pay the rent due or vacate the")
            lines.append("premises within the time specified will result in the forfeiture of")
            lines.append("your lease or rental agreement.")
            lines.append("")

        # Signature section
        lines.append("-" * 70)
        lines.append("")
        lines.append(f"Date: {data.notice_date.strftime('%B %d, %Y')}")
        lines.append("")
        lines.append("_" * 40)
        if data.landlord_name:
            lines.append(data.landlord_name)
        lines.append("Landlord/Agent")
        lines.append("")

        # Proof of service
        lines.append("=" * 70)
        lines.append("PROOF OF SERVICE")
        lines.append("=" * 70)
        lines.append("")
        lines.append(f"I served this notice on {data.service_date.strftime('%B %d, %Y')} by:")
        lines.append("[ ] Personal delivery to tenant")
        lines.append("[ ] Substituted service (left with person of suitable age)")
        lines.append("[ ] Posting and mailing")
        lines.append("")
        lines.append(f"Deadline to comply: {data.deadline_date.strftime('%B %d, %Y')}")
        lines.append("")

        return "\n".join(lines)

    def _add_business_days(self, start: date, days: int) -> date:
        """Add business days to a date."""
        current = start
        added = 0
        while added < days:
            current += timedelta(days=1)
            if current.weekday() < 5:  # Monday-Friday
                added += 1
        return current
