"""
Base templates for eviction notices.
"""

VALID_NOTICE_TEMPLATE = """
THREE-DAY NOTICE TO PAY RENT OR QUIT

TO: {tenant_names}
    AND ALL OTHER OCCUPANTS IN POSSESSION OF THE PREMISES LOCATED AT:

PROPERTY ADDRESS: {property_address}

PLEASE TAKE NOTICE that the rent on the above-described premises occupied by you,
in the amount of ${rent_amount:.2f}, for the period from {rent_period_start} to
{rent_period_end}, is now due and unpaid.

YOU ARE HEREBY REQUIRED to pay the said rent in full within THREE (3) DAYS after
service of this notice, or to vacate and surrender possession of the premises.

{payment_section}

PLEASE TAKE NOTICE that if you fail to pay the rent in full OR vacate the premises
within three (3) days after service of this notice (excluding Saturdays, Sundays,
and judicial holidays), the undersigned will institute legal proceedings against
you to recover possession of the premises, to declare the forfeiture of your lease
or rental agreement, and to recover rents and damages.

{forfeiture_section}

Date: {notice_date}

_______________________________
{landlord_name}
Landlord/Agent

PROOF OF SERVICE

I served this notice on {service_date} by:
[ ] Personal delivery to tenant
[ ] Substituted service
[ ] Posting and mailing
"""

# Alternative demand language (non-disjunctive - DEFECTIVE)
NON_DISJUNCTIVE_DEMAND = """YOU ARE HEREBY REQUIRED to pay the said rent in full within THREE (3) DAYS after
service of this notice AND vacate and surrender possession of the premises immediately."""

# Disjunctive demand (VALID)
DISJUNCTIVE_DEMAND = """YOU ARE HEREBY REQUIRED to pay the said rent in full within THREE (3) DAYS after
service of this notice, or to vacate and surrender possession of the premises."""

# Payment section with personal payment and hours (VALID)
PAYMENT_SECTION_FULL = """PAYMENT INFORMATION:

Rent must be paid to: {landlord_name}
Address: {landlord_address}
Telephone: {landlord_phone}

{personal_payment_hours}
{bank_payment_info}
{electronic_payment_info}

Sincerely awaiting your payment."""

# Personal payment hours (VALID)
PERSONAL_PAYMENT_HOURS = """Payment may be made in person during the following days and hours:
{payment_hours}"""

# Bank payment info - complete (VALID)
BANK_PAYMENT_COMPLETE = """Payment may also be made at the following financial institution located within
five (5) miles of the rental property:
Bank Name: {bank_name}
Bank Address: {bank_address}
Account Number: {bank_account}"""

# Bank payment info - incomplete (DEFECTIVE)
BANK_PAYMENT_INCOMPLETE = """Payment may also be made at {bank_name}."""

# Electronic payment - established (VALID)
ELECTRONIC_PAYMENT_ESTABLISHED = """Payment may be made via {electronic_method}, as previously established
between landlord and tenant."""

# Electronic payment - not established (DEFECTIVE)
ELECTRONIC_PAYMENT_NOT_ESTABLISHED = """Payment may be made via {electronic_method}."""

# Forfeiture declaration (VALID)
FORFEITURE_DECLARATION = """NOTICE OF FORFEITURE: Your failure to pay the rent due or vacate the premises
within the time specified will result in the forfeiture of your lease or rental
agreement, and legal proceedings will be initiated to recover possession."""

# No forfeiture (DEFECTIVE)
NO_FORFEITURE_DECLARATION = ""

# No amount stated (DEFECTIVE)
NO_AMOUNT_LANGUAGE = """PLEASE TAKE NOTICE that the rent on the above-described premises occupied by you
is now due and unpaid. You owe all past-due rent."""

# Amount stated (VALID)
AMOUNT_STATED_LANGUAGE = """PLEASE TAKE NOTICE that the rent on the above-described premises occupied by you,
in the amount of ${rent_amount:.2f}, for the period from {rent_period_start} to
{rent_period_end}, is now due and unpaid."""

# Payment section missing info (DEFECTIVE)
PAYMENT_SECTION_MISSING_PHONE = """PAYMENT INFORMATION:

Rent must be paid to: {landlord_name}
Address: {landlord_address}

Payment may be made in person during business hours."""

PAYMENT_SECTION_MISSING_ADDRESS = """PAYMENT INFORMATION:

Rent must be paid to: {landlord_name}
Telephone: {landlord_phone}"""

PAYMENT_SECTION_MISSING_NAME = """PAYMENT INFORMATION:

Address: {landlord_address}
Telephone: {landlord_phone}"""

# Personal payment without hours (DEFECTIVE)
PERSONAL_PAYMENT_NO_HOURS = """Payment may be made in person at our office."""
