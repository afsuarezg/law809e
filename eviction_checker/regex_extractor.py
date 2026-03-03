"""
Regex-based entity extractor for eviction notices.

Alternative to LLM extraction - faster, free, no dependencies,
but less flexible with unusual formats.
"""

import re
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional, List, Tuple

from .models import ExtractedNotice, NoticeType, Charge, PaymentTerms

logger = logging.getLogger(__name__)


class RegexExtractor:
    """Extracts entities from eviction notices using regex patterns."""

    # Money patterns
    MONEY_PATTERN = r'\$\s*([\d,]+(?:\.\d{2})?)'

    # Date patterns
    DATE_PATTERNS = [
        r'(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})',  # MM/DD/YYYY or MM-DD-YYYY
        r'(\w+)\s+(\d{1,2}),?\s+(\d{4})',  # January 15, 2024
        r'(\d{1,2})\s+(\w+)\s+(\d{4})',  # 15 January 2024
    ]

    # Phone pattern
    PHONE_PATTERN = r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'

    # Common month names
    MONTHS = {
        'january': 1, 'february': 2, 'march': 3, 'april': 4,
        'may': 5, 'june': 6, 'july': 7, 'august': 8,
        'september': 9, 'october': 10, 'november': 11, 'december': 12,
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'jun': 6,
        'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
    }

    def extract(self, raw_text: str) -> ExtractedNotice:
        """
        Extract structured information from notice text using regex.

        Args:
            raw_text: Raw text from OCR

        Returns:
            ExtractedNotice with populated fields
        """
        logger.info("Extracting entities using regex patterns")

        text_lower = raw_text.lower()

        # Extract all components
        tenant_names = self._extract_tenant_names(raw_text)
        landlord_name = self._extract_landlord_name(raw_text)
        property_address = self._extract_property_address(raw_text)

        amounts = self._extract_amounts(raw_text)
        total_amount = amounts[0] if amounts else None
        charges = self._extract_charges(raw_text, amounts)

        dates = self._extract_dates(raw_text)
        notice_date, service_date, period_start, period_end, termination_date = self._classify_dates(dates, raw_text)

        payment_terms = self._extract_payment_terms(raw_text)

        is_signed = self._check_signature(raw_text)
        has_forfeiture_declaration = self._check_forfeiture_language(raw_text)

        return ExtractedNotice(
            raw_text=raw_text,
            notice_type=NoticeType.THREE_DAY_PAY,
            landlord_name=landlord_name,
            tenant_names=tenant_names,
            property_address=property_address,
            total_amount_demanded=total_amount,
            charges=charges,
            notice_date=notice_date,
            service_date=service_date,
            period_start=period_start,
            period_end=period_end,
            termination_date=termination_date,
            payment_terms=payment_terms,
            is_signed=is_signed,
            has_forfeiture_declaration=has_forfeiture_declaration,
        )

    def _extract_tenant_names(self, text: str) -> List[str]:
        """Extract tenant names from notice."""
        names = []

        # Pattern: "TO: Name" or "TO: Name1, Name2"
        to_match = re.search(r'TO:\s*([^\n]+)', text, re.IGNORECASE)
        if to_match:
            to_line = to_match.group(1).strip()
            # Remove common suffixes
            to_line = re.sub(r'\s*AND ALL OTHER OCCUPANTS.*', '', to_line, flags=re.IGNORECASE)
            to_line = re.sub(r'\s*et\.?\s*al\.?', '', to_line, flags=re.IGNORECASE)

            # Split by comma or "and"
            parts = re.split(r',\s*|\s+and\s+', to_line, flags=re.IGNORECASE)
            for part in parts:
                part = part.strip()
                if part and len(part) > 2 and not part.lower().startswith('all '):
                    names.append(part)

        return names if names else []

    def _extract_landlord_name(self, text: str) -> Optional[str]:
        """Extract landlord/property manager name."""
        patterns = [
            r'(?:signed|from|landlord|property manager|agent)[:\s]+([A-Z][a-zA-Z\s]+(?:LLC|Inc\.?|Corp\.?|Management|Properties)?)',
            r'([A-Z][a-zA-Z\s]+(?:Management|Properties|Rentals|LLC|Inc\.?))',
            r'_{3,}\s*\n\s*([A-Z][a-zA-Z\s]+)',  # Name after signature line
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                name = match.group(1).strip()
                if len(name) > 3 and len(name) < 100:
                    return name

        return None

    def _extract_property_address(self, text: str) -> Optional[str]:
        """Extract rental property address."""
        patterns = [
            r'(?:property|premises|located at|address)[:\s]+([^\n]+)',
            r'(?:PROPERTY ADDRESS|PREMISES)[:\s]+([^\n]+)',
            r'(\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Boulevard|Blvd|Lane|Ln|Way|Court|Ct)[,.\s]+(?:Apt\.?|Unit|#)?\s*\w*[,.\s]+[A-Za-z\s]+,?\s*(?:CA|California)\s*\d{5})',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                address = match.group(1).strip()
                # Clean up
                address = re.sub(r'\s+', ' ', address)
                if len(address) > 10:
                    return address

        return None

    def _extract_amounts(self, text: str) -> List[Decimal]:
        """Extract all dollar amounts from text."""
        amounts = []
        matches = re.findall(self.MONEY_PATTERN, text)

        for match in matches:
            try:
                # Remove commas and convert
                amount_str = match.replace(',', '')
                amount = Decimal(amount_str)
                if amount > 0:
                    amounts.append(amount)
            except InvalidOperation:
                continue

        # Sort by value descending (total is usually largest)
        amounts.sort(reverse=True)
        return amounts

    def _extract_charges(self, text: str, amounts: List[Decimal]) -> List[Charge]:
        """Extract itemized charges."""
        charges = []
        text_lower = text.lower()

        # Common charge patterns
        charge_patterns = [
            (r'rent\s+(?:for\s+)?(?:\w+\s+)?\d{4}[:\s]*\$?\s*([\d,]+(?:\.\d{2})?)', True),
            (r'(?:monthly\s+)?rent[:\s]*\$?\s*([\d,]+(?:\.\d{2})?)', True),
            (r'late\s+fee[s]?[:\s]*\$?\s*([\d,]+(?:\.\d{2})?)', False),
            (r'(?:nsf|returned check)\s+fee[s]?[:\s]*\$?\s*([\d,]+(?:\.\d{2})?)', False),
            (r'utilit(?:y|ies)[:\s]*\$?\s*([\d,]+(?:\.\d{2})?)', False),
            (r'(?:water|electric|gas)[:\s]*\$?\s*([\d,]+(?:\.\d{2})?)', False),
            (r'trash[:\s]*\$?\s*([\d,]+(?:\.\d{2})?)', False),
            (r'(?:cleaning|damage)[s]?[:\s]*\$?\s*([\d,]+(?:\.\d{2})?)', False),
        ]

        for pattern, is_rent in charge_patterns:
            match = re.search(pattern, text_lower)
            if match:
                try:
                    amount = Decimal(match.group(1).replace(',', ''))
                    desc = "Rent" if is_rent else pattern.split('\\')[0].replace('(?:', '').replace(')', '').strip()
                    charges.append(Charge(
                        description=desc.title(),
                        amount=amount,
                        is_rent=is_rent
                    ))
                except (InvalidOperation, IndexError):
                    continue

        # If no specific charges found but we have amounts, assume largest is rent
        if not charges and amounts:
            charges.append(Charge(
                description="Rent",
                amount=amounts[0],
                is_rent=True
            ))

        return charges

    def _extract_dates(self, text: str) -> List[Tuple[datetime, str]]:
        """Extract all dates from text with context."""
        dates = []

        for pattern in self.DATE_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                try:
                    date_obj = self._parse_date_match(match)
                    if date_obj:
                        # Get surrounding context
                        start = max(0, match.start() - 50)
                        end = min(len(text), match.end() + 20)
                        context = text[start:end].lower()
                        dates.append((date_obj, context))
                except (ValueError, KeyError):
                    continue

        return dates

    def _parse_date_match(self, match) -> Optional[datetime]:
        """Parse a regex date match into datetime."""
        groups = match.groups()

        if len(groups) == 3:
            # Check if first group is month name
            if groups[0].lower() in self.MONTHS:
                # Format: January 15, 2024
                month = self.MONTHS[groups[0].lower()]
                day = int(groups[1])
                year = int(groups[2])
            elif groups[1].lower() in self.MONTHS:
                # Format: 15 January 2024
                day = int(groups[0])
                month = self.MONTHS[groups[1].lower()]
                year = int(groups[2])
            else:
                # Format: MM/DD/YYYY
                month = int(groups[0])
                day = int(groups[1])
                year = int(groups[2])
                if year < 100:
                    year += 2000

            return datetime(year, month, day)

        return None

    def _classify_dates(self, dates: List[Tuple[datetime, str]], text: str):
        """Classify extracted dates by their purpose."""
        notice_date = None
        service_date = None
        period_start = None
        period_end = None
        termination_date = None

        for date_obj, context in dates:
            date_val = date_obj.date()

            if 'served' in context or 'service' in context:
                service_date = date_val
            elif 'dated' in context or 'date:' in context or 'signed' in context:
                notice_date = date_val
            elif 'deadline' in context or 'expire' in context or 'comply' in context or 'within' in context:
                termination_date = date_val
            elif 'from' in context or 'period' in context or 'beginning' in context:
                period_start = date_val
            elif 'to' in context or 'through' in context or 'ending' in context:
                period_end = date_val

        # If we have notice_date but not service_date, they're often the same
        if notice_date and not service_date:
            service_date = notice_date

        return notice_date, service_date, period_start, period_end, termination_date

    def _extract_payment_terms(self, text: str) -> Optional[PaymentTerms]:
        """Extract payment information."""
        payee_name = None
        payment_address = None
        payment_hours = None
        payment_methods = []

        # Payee name
        payee_patterns = [
            r'(?:pay(?:able)?|made)\s+to[:\s]+([A-Za-z\s]+(?:LLC|Inc\.?|Management|Properties)?)',
            r'rent\s+must\s+be\s+paid\s+to[:\s]+([^\n]+)',
        ]
        for pattern in payee_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                payee_name = match.group(1).strip()
                break

        # Payment address - look for address near payment info
        addr_match = re.search(
            r'(?:address|payment.*?at)[:\s]+(\d+[^\n]+(?:CA|California)\s*\d{5})',
            text, re.IGNORECASE
        )
        if addr_match:
            payment_address = addr_match.group(1).strip()

        # Payment hours
        hours_patterns = [
            r'(?:hours?|available)[:\s]+([^\n]*(?:am|pm|AM|PM)[^\n]*)',
            r'((?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)[\w\s,-]+(?:am|pm|AM|PM)[^\n]*)',
        ]
        for pattern in hours_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                payment_hours = match.group(1).strip()
                break

        # Payment methods
        method_keywords = {
            'cash': 'cash',
            'check': 'check',
            'money order': 'money order',
            'cashier': 'cashier\'s check',
            'certified': 'certified check',
        }
        text_lower = text.lower()
        for keyword, method in method_keywords.items():
            if keyword in text_lower:
                payment_methods.append(method)

        if payee_name or payment_address or payment_hours:
            return PaymentTerms(
                payee_name=payee_name,
                payment_address=payment_address,
                payment_hours=payment_hours,
                payment_methods=payment_methods if payment_methods else None
            )

        return None

    def _check_signature(self, text: str) -> bool:
        """Check if notice appears to be signed."""
        signature_indicators = [
            r'_{3,}',  # Signature line
            r'/s/',  # Electronic signature
            r'signed[:\s]',
            r'signature',
        ]

        for pattern in signature_indicators:
            if re.search(pattern, text, re.IGNORECASE):
                return True

        return False

    def _check_forfeiture_language(self, text: str) -> bool:
        """Check if notice contains a forfeiture declaration."""
        forfeiture_patterns = [
            r'forfeit',
            r'forfeiture',
            r'lease.{0,30}(terminated|void|ended)',
            r'tenancy.{0,30}(terminated|void|ended)',
            r'declare.{0,30}(terminated|void|forfeited)',
            r'legal proceedings.{0,60}recover possession.{0,120}unlawful detainer',
        ]
        return any(re.search(p, text, re.IGNORECASE) for p in forfeiture_patterns)
