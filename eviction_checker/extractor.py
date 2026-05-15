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

    def __init__(self, llm_client: Optional[LLMClient] = None, provider: Optional[str] = None):
        """
        Initialize EntityExtractor.
        
        Args:
            llm_client: Optional pre-configured LLMClient. If None, creates one.
            provider: Optional provider name ("ollama", "openai", "anthropic") to force a specific provider.
                     If None, uses default priority (Ollama > OpenAI > Anthropic).
        """
        if llm_client is not None:
            self.llm_client = llm_client
        elif provider:
            # Create LLMClient with specific provider preference
            self.llm_client = LLMClient(temperature=0.0, preferred_provider=provider)
        else:
            self.llm_client = LLMClient(temperature=0.0)

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

        # If extraction completely failed, raise an explicit error so the
        # caller can distinguish system failure from a defective notice.
        if not entities:
            raise RuntimeError("LLM entity extraction failed – no data returned")

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

  "is_signed": true,
  "has_forfeiture_declaration": true
}}

IMPORTANT:
- Set "is_rent" to TRUE only for actual rent charges
- Set "is_rent" to FALSE for: late fees, NSF fees, utilities, trash, damages, cleaning, etc.
- Dates should be in YYYY-MM-DD format
- If information is missing, use null
- For "total_amount_demanded": look for embedded sentences like "the total amount of rent due and unpaid is: $X", "amount of $X", "the sum of $X", or a standalone dollar figure
- For "days_to_comply": extract the integer from phrases like "WITHIN THREE (3) BUSINESS DAYS" → 3, "within one (1) day" → 1, "within 3 days" → 3
- For "service_date": look in a proof-of-service section at the bottom: "I served this notice on [date]", "Date Served: [date]", or "served on [date]"
- For "payment_terms.payee_name": extract the entity name from "made payable to X", "paid to X", "payable to [company]", "payable to [Name]", "remit (payment) to X", "send (rent/payment) to X", or "pay landlord/owner at [name]"
- For "payment_terms.payment_hours": look for explicit days/hours when payment may be made. Common phrasings include "Usual days and hours for rent collection are: [hours]", "Hours of operation: [hours]", "Office hours: [hours]", or "Payment may be made between [hours]". Capture the exact day/time range if present, even when it follows an "In person" checkbox or list bullet.
- For "has_forfeiture_declaration": set true if the notice contains ANY of the following:
  (a) explicit forfeiture language: "forfeit", "forfeited", "forfeiture of the lease", "declared forfeited", "deemed forfeited", "declare a forfeiture", "lease shall be void"; OR
  (b) tenancy-termination language: "tenancy is terminated", "tenancy will be terminated", "tenancy will be declared terminated"; OR
  (c) consequence language combining recovery-of-possession with an unlawful detainer action: e.g. "legal proceedings to recover possession of the premises" together with "unlawful detainer".
  Set false ONLY if the notice contains none of the above — i.e. it describes no consequence for non-payment at all.

Return ONLY valid JSON."""

        try:
            return self.llm_client.complete_json(prompt, system_message)
        except Exception as e:
            logger.error(f"Entity extraction failed: {e}")
            # Return empty dict – the caller (extract) will turn this into an
            # explicit RuntimeError so it can be surfaced to the user.
            return {}

    # Fields that are usually required to render a meaningful defect report;
    # if the LLM returns None for these, downstream validation may misclassify.
    _CRITICAL_FIELDS = ("landlord_name", "total_amount_demanded")

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

        # Flag missing critical fields up front — downstream defect reports
        # are misleading if these are silently None.
        missing_critical = [f for f in self._CRITICAL_FIELDS if not data.get(f)]
        if missing_critical:
            logger.warning(
                "LLM extraction returned None for critical field(s): %s. "
                "Defect detection may be unreliable.",
                ", ".join(missing_critical),
            )

        try:
            return ExtractedNotice(**data)
        except Exception as e:
            logger.error(
                "Could not create ExtractedNotice (%s: %s). "
                "Falling back to raw-text-only notice. Keys present in extracted data: %s",
                type(e).__name__,
                e,
                sorted(data.keys()),
            )
            return ExtractedNotice(
                raw_text=data.get('raw_text', ''),
                notice_type=NoticeType.THREE_DAY_PAY
            )
