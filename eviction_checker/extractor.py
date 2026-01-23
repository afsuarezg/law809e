"""
Entity extractor using LLM to parse eviction notice text.
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, Optional

from .models import ExtractedNotice, NoticeType, Charge, PaymentTerms
from .llm import LLMClient

logger = logging.getLogger(__name__)


class EntityExtractor:
    """Extracts structured entities from eviction notice text."""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or LLMClient(temperature=0.0)

    def extract(self, raw_text: str) -> ExtractedNotice:
        """
        Extract structured information from notice text.

        Args:
            raw_text: Raw text from OCR

        Returns:
            ExtractedNotice with populated fields
        """
        logger.info("Extracting entities from notice text")

        entities = self._extract_entities(raw_text)
        entities['raw_text'] = raw_text
        entities['notice_type'] = NoticeType.THREE_DAY_PAY

        return self._to_extracted_notice(entities)

    def _extract_entities(self, text: str) -> Dict[str, Any]:
        """Extract entities using LLM."""
        system_message = """You are an expert at extracting information from California eviction notices.
Extract ALL information accurately. If something is missing, use null."""

        prompt = f"""Analyze this 3-Day Notice to Pay Rent or Quit and extract information as JSON.

Notice text:
{text}

Extract:
{{
  "landlord_name": "full name of landlord/property manager",
  "tenant_names": ["list of tenant names"],
  "property_address": "rental property address",

  "total_amount_demanded": 1500.00,
  "charges": [
    {{"description": "rent for January 2024", "amount": 1500.00, "is_rent": true}},
    {{"description": "late fee", "amount": 50.00, "is_rent": false}}
  ],

  "notice_date": "2024-01-15",
  "service_date": "2024-01-15",
  "period_start": "2024-01-01",
  "period_end": "2024-01-31",
  "termination_date": "2024-01-18",
  "days_to_comply": 3,

  "payment_terms": {{
    "payee_name": "John Smith",
    "payment_address": "123 Main St, Los Angeles, CA 90001",
    "payment_hours": "Monday-Friday, 9:00 AM to 5:00 PM",
    "payment_methods": ["cash", "check", "money order"]
  }},

  "is_signed": true
}}

IMPORTANT:
- Set "is_rent" to TRUE only for actual rent charges
- Set "is_rent" to FALSE for: late fees, NSF fees, utilities, trash, damages, cleaning, etc.
- Dates should be in YYYY-MM-DD format
- If information is missing, use null

Return ONLY valid JSON."""

        try:
            return self.llm_client.complete_json(prompt, system_message)
        except Exception as e:
            logger.error(f"Entity extraction failed: {e}")
            return {}

    def _to_extracted_notice(self, data: Dict[str, Any]) -> ExtractedNotice:
        """Convert dictionary to ExtractedNotice model."""
        # Parse dates
        for field in ['notice_date', 'service_date', 'period_start', 'period_end', 'termination_date']:
            if field in data and data[field]:
                try:
                    data[field] = datetime.strptime(data[field], '%Y-%m-%d').date()
                except (ValueError, TypeError):
                    data[field] = None

        # Parse amount
        if 'total_amount_demanded' in data and data['total_amount_demanded']:
            try:
                data['total_amount_demanded'] = Decimal(str(data['total_amount_demanded']))
            except (ValueError, TypeError):
                data['total_amount_demanded'] = None

        # Parse charges
        if 'charges' in data and data['charges']:
            charges = []
            for c in data['charges']:
                try:
                    charges.append(Charge(
                        description=c.get('description', ''),
                        amount=Decimal(str(c.get('amount', 0))),
                        is_rent=c.get('is_rent', False)
                    ))
                except Exception as e:
                    logger.warning(f"Could not parse charge: {e}")
            data['charges'] = charges

        # Parse payment terms
        if 'payment_terms' in data and data['payment_terms']:
            try:
                data['payment_terms'] = PaymentTerms(**data['payment_terms'])
            except Exception as e:
                logger.warning(f"Could not parse payment terms: {e}")
                data['payment_terms'] = None

        try:
            return ExtractedNotice(**data)
        except Exception as e:
            logger.error(f"Could not create ExtractedNotice: {e}")
            return ExtractedNotice(
                raw_text=data.get('raw_text', ''),
                notice_type=NoticeType.THREE_DAY_PAY
            )
