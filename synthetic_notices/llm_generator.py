"""
LLM-based synthetic eviction notice generator.

Generates valid and invalid 3-day notices using large language models.
Supports multiple LLM providers (OpenAI, Anthropic, etc.).
"""

import os
import random
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import date, timedelta

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    # Load .env file from project root (two levels up from this file)
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    else:
        # Fallback: try loading from current directory
        load_dotenv()
except ImportError:
    # python-dotenv not installed, will use system environment variables only
    pass

from .models import GeneratedNotice, DefectType, NoticeData


class LLMNoticeGenerator:
    """Generates synthetic eviction notices using LLMs."""

    def __init__(
        self,
        provider: str = "openai",
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        seed: Optional[int] = None
    ):
        """
        Initialize LLM generator.
        
        Args:
            provider: LLM provider ("openai", "anthropic", "google")
            model: Model name (e.g., "gpt-4", "claude-3-opus")
            api_key: API key (if None, reads from environment)
            seed: Random seed for reproducibility
        """
        self.provider = provider.lower()
        self.model = model or self._get_default_model()
        self.api_key = api_key or self._get_api_key()
        self.seed = seed
        
        if seed is not None:
            random.seed(seed)
        
        # Load sample notice template
        template_path = Path(__file__).parent / "templates" / "sample_notice.txt"
        if template_path.exists():
            self.sample_template = template_path.read_text()
        else:
            self.sample_template = self._get_default_template()

    def _get_default_model(self) -> str:
        """Get default model for provider."""
        defaults = {
            "openai": "gpt-4",
            "anthropic": "claude-3-opus-20240229",
            "google": "gemini-pro"
        }
        return defaults.get(self.provider, "gpt-4")

    def _get_api_key(self) -> Optional[str]:
        """Get API key from environment."""
        env_vars = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "google": "GOOGLE_API_KEY"
        }
        env_var = env_vars.get(self.provider)
        return os.getenv(env_var) if env_var else None

    def _get_default_template(self) -> str:
        """Get default template if file not found."""
        return """3-DAY NOTICE TO PAY RENT OR QUIT
Date: October 3, 2025
To:
Alex Martinez
1234 Harbor View Drive, Apt. 7
San Diego, CA 92101
From:
Coastal Bay Properties, LLC
c/o Property Management Office
San Diego, CA
YOU ARE HEREBY NOTIFIED that you are in default in the payment of rent for the premises described above. The total amount of rent due and unpaid is:
$1,850.00
This amount represents rent due for the month of September 2025, including applicable late fees as permitted under your rental agreement.
WITHIN THREE (3) DAYS, excluding Saturdays, Sundays, and judicial holidays, after service of this notice, you must either:
PAY the total amount of rent stated above in full, OR
QUIT AND DELIVER UP POSSESSION of the premises to the undersigned.
Payment must be made by certified check, cashier's check, or money order payable to Coastal Bay Properties, LLC, and delivered to the property management office during normal business hours.
FAILURE TO COMPLY with this notice within the time stated will result in the initiation of legal proceedings to recover possession of the premises, including the filing of an unlawful detainer (eviction) action against you.
Landlord / Agent Signature: 
Property Manager, Coastal Bay Properties, LLC"""

    def generate_valid_notice(self, **kwargs) -> GeneratedNotice:
        """Generate a valid notice using LLM."""
        prompt = self._build_valid_prompt(**kwargs)
        text = self._call_llm(prompt)
        return GeneratedNotice(
            text=text,
            data=None,  # LLM doesn't return structured data
            defects=[],
            is_valid=True
        )

    def generate_invalid_notice(
        self,
        defects: List[DefectType],
        **kwargs
    ) -> GeneratedNotice:
        """Generate a notice with specific defects using LLM."""
        prompt = self._build_defect_prompt(defects, **kwargs)
        text = self._call_llm(prompt)
        return GeneratedNotice(
            text=text,
            data=None,
            defects=defects,
            is_valid=False
        )

    def generate_random_invalid_notice(
        self,
        num_defects: int = 1,
        **kwargs
    ) -> GeneratedNotice:
        """Generate a notice with random defects."""
        all_defects = list(DefectType)
        selected = random.sample(all_defects, min(num_defects, len(all_defects)))
        return self.generate_invalid_notice(selected, **kwargs)

    def generate_batch(
        self,
        count: int,
        valid_ratio: float = 0.3,
        max_defects_per_notice: int = 3,
        progress_callback=None,
        **kwargs
    ) -> List[GeneratedNotice]:
        """
        Generate a batch of notices.
        
        Args:
            count: Total number of notices to generate
            valid_ratio: Ratio of valid notices
            max_defects_per_notice: Maximum defects per invalid notice
            progress_callback: Optional callback function(notice, index, total) called after each notice
            **kwargs: Additional arguments passed to generation methods
        """
        notices = []
        num_valid = int(count * valid_ratio)
        num_invalid = count - num_valid

        # Generate valid notices
        for i in range(num_valid):
            notice = self.generate_valid_notice(**kwargs)
            notices.append(notice)
            if progress_callback:
                progress_callback(notice, len(notices), count)

        # Generate invalid notices
        for i in range(num_invalid):
            num_defects = random.randint(1, max_defects_per_notice)
            notice = self.generate_random_invalid_notice(num_defects, **kwargs)
            notices.append(notice)
            if progress_callback:
                progress_callback(notice, len(notices), count)

        random.shuffle(notices)
        return notices

    def _build_valid_prompt(self, **kwargs) -> str:
        """Build prompt for valid notice generation."""
        return f"""You are a legal document generator specializing in California eviction notices.

Generate a valid 3-Day Notice to Pay Rent or Quit for California. The notice must be legally compliant and contain all required elements:

REQUIRED ELEMENTS FOR A VALID NOTICE:
1. Disjunctive demand: Must use "pay OR quit" (not "pay AND quit")
2. Amount stated: Must specify the exact dollar amount of rent owed
3. Rent period: Must specify the period for which rent is due (cannot be more than 12 months old)
4. Three business days: Must give at least 3 business days (excluding weekends and holidays)
5. Payee information: Must include landlord name, address, and phone number
6. Payment hours: If in-person payment is allowed, must specify business hours
7. Financial institution: If bank payment is allowed, must include complete bank info and 5-mile statement
8. Electronic payment: If electronic payment is allowed, must state it was "previously established"
9. Forfeiture declaration: Must include notice of forfeiture

Use the following sample notice as a reference for format and style:

{self.sample_template}

Generate a new valid notice with:
- Different tenant name(s) and address
- Different landlord name and contact information
- Different rent amount (between $1000-$3500)
- Different dates (use current date context)
- Different payment options (can include personal, bank, or electronic payment)

The notice must be completely valid with no legal defects. Return only the notice text, no additional commentary."""

    def _build_defect_prompt(self, defects: List[DefectType], **kwargs) -> str:
        """Build prompt for defective notice generation."""
        defect_descriptions = {
            DefectType.NOT_DISJUNCTIVE: "Use 'pay AND quit' instead of 'pay OR quit'",
            DefectType.INSUFFICIENT_PERIOD: "Give less than 3 business days (e.g., only 1-2 days)",
            DefectType.NO_AMOUNT_STATED: "Do not specify the exact dollar amount of rent owed",
            DefectType.MISSING_PAYEE_INFO: "Omit landlord name, address, or phone number",
            DefectType.MISSING_PAYMENT_HOURS: "Allow in-person payment but don't specify business hours",
            DefectType.FINANCIAL_INSTITUTION_INCOMPLETE: "Include bank payment option but omit address, account number, or 5-mile statement",
            DefectType.ELECTRONIC_PAYMENT_NOT_ESTABLISHED: "Offer electronic payment without stating it was 'previously established'",
            DefectType.RENT_OVER_ONE_YEAR: "Demand rent from more than 12 months ago",
            DefectType.NO_FORFEITURE: "Omit the forfeiture declaration"
        }
        
        defect_list = "\n".join(f"- {defect_descriptions.get(d, d.value)}" for d in defects)
        
        return f"""You are a legal document generator specializing in California eviction notices.

Generate a DEFECTIVE 3-Day Notice to Pay Rent or Quit for California. The notice must contain the following legal defect(s):

DEFECTS TO INCLUDE:
{defect_list}

Use the following sample notice as a reference for format and style:

{self.sample_template}

Generate a new notice with:
- Different tenant name(s) and address
- Different landlord name and contact information
- Different rent amount (between $1000-$3500)
- Different dates (use current date context)
- Different payment options

The notice must contain the specified defect(s) but otherwise follow the format of a real eviction notice. Return only the notice text, no additional commentary."""

    def _call_llm(self, prompt: str) -> str:
        """Call the LLM API."""
        if self.provider == "openai":
            return self._call_openai(prompt)
        elif self.provider == "anthropic":
            return self._call_anthropic(prompt)
        elif self.provider == "google":
            return self._call_google(prompt)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

    def _call_openai(self, prompt: str) -> str:
        """Call OpenAI API."""
        try:
            import openai
        except ImportError:
            raise ImportError("openai package not installed. Install with: pip install openai")
        
        if not self.api_key:
            raise ValueError("OpenAI API key not provided. Set OPENAI_API_KEY environment variable or pass api_key parameter.")
        
        client = openai.OpenAI(api_key=self.api_key)
        
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a legal document generator."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=2000
        )
        
        return response.choices[0].message.content.strip()

    def _call_anthropic(self, prompt: str) -> str:
        """Call Anthropic API."""
        try:
            import anthropic
        except ImportError:
            raise ImportError("anthropic package not installed. Install with: pip install anthropic")
        
        if not self.api_key:
            raise ValueError("Anthropic API key not provided. Set ANTHROPIC_API_KEY environment variable or pass api_key parameter.")
        
        client = anthropic.Anthropic(api_key=self.api_key)
        
        response = client.messages.create(
            model=self.model,
            max_tokens=2000,
            temperature=0.7,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        return response.content[0].text.strip()

    def _call_google(self, prompt: str) -> str:
        """Call Google Gemini API."""
        try:
            import google.generativeai as genai
        except ImportError:
            raise ImportError("google-generativeai package not installed. Install with: pip install google-generativeai")
        
        if not self.api_key:
            raise ValueError("Google API key not provided. Set GOOGLE_API_KEY environment variable or pass api_key parameter.")
        
        genai.configure(api_key=self.api_key)
        model = genai.GenerativeModel(self.model)
        
        response = model.generate_content(
            prompt,
            generation_config={
                "temperature": 0.7,
                "max_output_tokens": 2000,
            }
        )
        
        return response.text.strip()
