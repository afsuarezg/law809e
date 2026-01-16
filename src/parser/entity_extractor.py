"""
Entity extraction module using LLM.

Extracts structured information from eviction notice text.
"""

import logging
from typing import Dict, Any
from decimal import Decimal
from datetime import datetime

from .structured_data import ExtractedNotice, NoticeType, Charge, PaymentTerms
from ..llm.client import LLMClient

logger = logging.getLogger(__name__)


class EntityExtractor:
    """Extracts structured entities from eviction notice text using LLM."""

    def __init__(self, llm_client: LLMClient = None):
        """
        Initialize entity extractor.

        Args:
            llm_client: Optional LLM client (creates default if not provided)
        """
        self.llm_client = llm_client or LLMClient(temperature=0.1)

    def extract(self, raw_text: str) -> ExtractedNotice:
        """
        Extract structured information from notice text.

        Args:
            raw_text: Raw text from OCR

        Returns:
            ExtractedNotice with populated fields
        """
        logger.info("Extracting entities from notice text")

        # First, classify notice type
        notice_type = self._classify_notice_type(raw_text)
        logger.info(f"Classified as: {notice_type}")

        # Extract entities based on notice type
        if notice_type == NoticeType.THREE_DAY_PAY:
            entities = self._extract_three_day_pay_entities(raw_text)
        elif notice_type == NoticeType.THREE_DAY_CURE:
            entities = self._extract_three_day_cure_entities(raw_text)
        elif notice_type in [NoticeType.THIRTY_DAY, NoticeType.SIXTY_DAY]:
            entities = self._extract_termination_notice_entities(raw_text)
        else:
            # Generic extraction
            entities = self._extract_generic_entities(raw_text)

        # Add raw text and notice type
        entities['raw_text'] = raw_text
        entities['notice_type'] = notice_type

        # Convert to ExtractedNotice model
        notice = self._dict_to_extracted_notice(entities)

        logger.info("Entity extraction complete")
        return notice

    def _classify_notice_type(self, text: str) -> NoticeType:
        """
        Classify the type of eviction notice.

        Args:
            text: Notice text

        Returns:
            NoticeType enum
        """
        prompt = f"""Analyze this eviction notice and determine its type.

Notice text:
{text[:2000]}  # First 2000 chars should be enough

Respond with ONLY one of these values:
- 3_day_pay_or_quit
- 3_day_cure_or_quit
- 3_day_unconditional_quit
- 30_day_notice
- 60_day_notice
- 90_day_notice
- unknown

Look for keywords like:
- "pay rent or quit" = 3_day_pay_or_quit
- "cure or quit", "perform covenant" = 3_day_cure_or_quit
- "30 days notice", "30-day notice" = 30_day_notice
- "60 days notice", "60-day notice" = 60_day_notice

Response (one value only):"""

        try:
            response = self.llm_client.complete(prompt).strip().lower()

            # Map response to NoticeType
            for notice_type in NoticeType:
                if notice_type.value in response:
                    return notice_type

            logger.warning(f"Could not classify notice type from response: {response}")
            return NoticeType.UNKNOWN

        except Exception as e:
            logger.error(f"Notice classification failed: {e}")
            return NoticeType.UNKNOWN

    def _extract_three_day_pay_entities(self, text: str) -> Dict[str, Any]:
        """Extract entities specific to 3-day pay or quit notice."""
        system_message = """You are an expert at extracting information from California eviction notices.
Extract structured data accurately. Use null for missing fields."""

        prompt = f"""Extract all information from this 3-Day Notice to Pay Rent or Quit.

Notice text:
{text}

Extract and return JSON with this structure:
{{
  "landlord_name": "name of landlord or property manager",
  "tenant_names": ["list", "of", "tenant", "names"],
  "property_address": "complete property address",
  "total_amount_demanded": 1500.00,
  "charges": [
    {{"description": "rent for January 2024", "amount": 1500.00, "is_rent": true}}
  ],
  "notice_date": "2024-01-15",
  "service_date": "2024-01-15",
  "period_start": "2024-01-01",
  "period_end": "2024-01-31",
  "days_to_comply": 3,
  "payment_terms": {{
    "payee_name": "John Smith",
    "payment_address": "123 Main St, Suite 100, City, CA 90000",
    "payment_hours": "Monday-Friday, 9:00 AM to 5:00 PM",
    "payment_methods": ["cash", "check", "money order"]
  }},
  "is_signed": true,
  "signature_name": "John Smith",
  "service_method": "personal",
  "confidence_notes": "All fields clearly stated"
}}

CRITICAL:
- In "charges" array, set "is_rent" to false for late fees, utilities, damages, NSF fees, or any non-rent charges
- Only charges explicitly labeled as rent should have "is_rent": true
- If multiple charges listed, create separate objects for each
- Use YYYY-MM-DD format for dates
- Use null for missing fields"""

        try:
            result = self.llm_client.complete_json(prompt, system_message)
            return result
        except Exception as e:
            logger.error(f"Entity extraction failed: {e}")
            return self._get_empty_extraction()

    def _extract_three_day_cure_entities(self, text: str) -> Dict[str, Any]:
        """Extract entities specific to 3-day cure or quit notice."""
        system_message = """You are an expert at extracting information from California eviction notices.
Extract structured data accurately."""

        prompt = f"""Extract information from this 3-Day Notice to Cure or Quit.

Notice text:
{text}

Return JSON with:
{{
  "landlord_name": "...",
  "tenant_names": ["..."],
  "property_address": "...",
  "notice_date": "YYYY-MM-DD",
  "service_date": "YYYY-MM-DD",
  "days_to_comply": 3,
  "lease_violation": "specific description of violation",
  "cure_requirements": "what tenant must do to cure",
  "lease_clause_reference": "section or clause number if referenced",
  "is_signed": true,
  "signature_name": "...",
  "service_method": "personal"
}}"""

        try:
            result = self.llm_client.complete_json(prompt, system_message)
            return result
        except Exception as e:
            logger.error(f"Entity extraction failed: {e}")
            return self._get_empty_extraction()

    def _extract_termination_notice_entities(self, text: str) -> Dict[str, Any]:
        """Extract entities from 30/60 day termination notices."""
        system_message = """You are an expert at extracting information from California eviction notices."""

        prompt = f"""Extract information from this 30-day or 60-day termination notice.

Notice text:
{text}

Return JSON with:
{{
  "landlord_name": "...",
  "tenant_names": ["..."],
  "property_address": "...",
  "notice_date": "YYYY-MM-DD",
  "service_date": "YYYY-MM-DD",
  "termination_date": "YYYY-MM-DD",
  "days_to_comply": 30 or 60,
  "includes_just_cause": true/false,
  "just_cause_reason": "reason if stated",
  "includes_relocation_assistance": true/false,
  "is_signed": true,
  "signature_name": "...",
  "service_method": "personal"
}}"""

        try:
            result = self.llm_client.complete_json(prompt, system_message)
            return result
        except Exception as e:
            logger.error(f"Entity extraction failed: {e}")
            return self._get_empty_extraction()

    def _extract_generic_entities(self, text: str) -> Dict[str, Any]:
        """Extract basic entities when notice type is unknown."""
        logger.info("Using generic entity extraction")

        system_message = """Extract whatever information you can from this eviction notice."""

        prompt = f"""Extract information from this eviction notice.

Notice text:
{text}

Return JSON with available fields:
{{
  "landlord_name": "...",
  "tenant_names": ["..."],
  "property_address": "...",
  "notice_date": "YYYY-MM-DD",
  "is_signed": true,
  "confidence_notes": "describe what you found and what's unclear"
}}"""

        try:
            result = self.llm_client.complete_json(prompt, system_message)
            return result
        except Exception as e:
            logger.error(f"Generic extraction failed: {e}")
            return self._get_empty_extraction()

    def _dict_to_extracted_notice(self, data: Dict[str, Any]) -> ExtractedNotice:
        """
        Convert dictionary to ExtractedNotice model.

        Handles type conversions and nested models.
        """
        # Convert date strings to date objects
        date_fields = ['notice_date', 'service_date', 'period_start', 'period_end', 'termination_date']
        for field in date_fields:
            if field in data and data[field]:
                try:
                    if isinstance(data[field], str):
                        data[field] = datetime.strptime(data[field], '%Y-%m-%d').date()
                except (ValueError, TypeError) as e:
                    logger.warning(f"Could not parse date field {field}: {e}")
                    data[field] = None

        # Convert amount to Decimal
        if 'total_amount_demanded' in data and data['total_amount_demanded']:
            try:
                data['total_amount_demanded'] = Decimal(str(data['total_amount_demanded']))
            except (ValueError, TypeError):
                data['total_amount_demanded'] = None

        # Convert charges
        if 'charges' in data and data['charges']:
            charges = []
            for charge_dict in data['charges']:
                try:
                    charge = Charge(
                        description=charge_dict.get('description', ''),
                        amount=Decimal(str(charge_dict.get('amount', 0))),
                        is_rent=charge_dict.get('is_rent', False)
                    )
                    charges.append(charge)
                except Exception as e:
                    logger.warning(f"Could not parse charge: {e}")
            data['charges'] = charges

        # Convert payment terms
        if 'payment_terms' in data and data['payment_terms']:
            try:
                data['payment_terms'] = PaymentTerms(**data['payment_terms'])
            except Exception as e:
                logger.warning(f"Could not parse payment terms: {e}")
                data['payment_terms'] = None

        # Create ExtractedNotice
        try:
            return ExtractedNotice(**data)
        except Exception as e:
            logger.error(f"Could not create ExtractedNotice: {e}")
            # Return minimal valid notice
            return ExtractedNotice(
                raw_text=data.get('raw_text', ''),
                notice_type=data.get('notice_type', NoticeType.UNKNOWN)
            )

    def _get_empty_extraction(self) -> Dict[str, Any]:
        """Return empty extraction dictionary."""
        return {
            'landlord_name': None,
            'tenant_names': [],
            'property_address': None,
            'total_amount_demanded': None,
            'charges': [],
            'notice_date': None,
            'confidence_notes': 'Extraction failed'
        }
