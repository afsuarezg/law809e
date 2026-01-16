"""
Base validator class for eviction notice validation.

All specific validators inherit from this base class.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
import yaml
import logging
from pathlib import Path

from ..parser.structured_data import (
    ExtractedNotice,
    Defect,
    Severity,
    ValidationContext
)
import config

logger = logging.getLogger(__name__)


class BaseValidator(ABC):
    """Abstract base class for notice validators."""

    def __init__(self, load_rules: bool = True):
        """
        Initialize validator.

        Args:
            load_rules: Whether to load validation rules from YAML
        """
        self.rules = {}
        self.common_rules = {}

        if load_rules:
            self._load_rules()

    def _load_rules(self):
        """Load validation rules from YAML file."""
        try:
            with open(config.RULES_FILE, 'r') as f:
                rules_data = yaml.safe_load(f)

            # Load notice type specific rules
            notice_type_key = self.get_notice_type_key()
            if notice_type_key and notice_type_key in rules_data.get('notice_types', {}):
                self.rules = rules_data['notice_types'][notice_type_key]
                logger.debug(f"Loaded {len(self.rules.get('validation_rules', []))} rules for {notice_type_key}")

            # Load common rules
            self.common_rules = rules_data.get('common_rules', [])
            logger.debug(f"Loaded {len(self.common_rules)} common rules")

        except Exception as e:
            logger.error(f"Failed to load validation rules: {e}")
            raise

    @abstractmethod
    def get_notice_type_key(self) -> str:
        """
        Get the YAML key for this notice type.

        Returns:
            String key matching notice_types in requirements.yaml
        """
        pass

    def validate(
        self,
        notice: ExtractedNotice,
        context: Optional[ValidationContext] = None
    ) -> List[Defect]:
        """
        Validate an eviction notice.

        Args:
            notice: Extracted notice data
            context: Optional additional context for validation

        Returns:
            List of defects found
        """
        logger.info(f"Validating {notice.notice_type} notice")

        defects = []

        # Run common validations
        defects.extend(self._validate_common_requirements(notice))

        # Run notice-specific validations
        defects.extend(self._validate_specific_requirements(notice, context))

        logger.info(f"Validation complete. Found {len(defects)} defects")

        return defects

    def _validate_common_requirements(self, notice: ExtractedNotice) -> List[Defect]:
        """
        Validate common requirements that apply to all notice types.

        Args:
            notice: Extracted notice data

        Returns:
            List of defects
        """
        defects = []

        # Check for tenant name
        if not notice.tenant_names or len(notice.tenant_names) == 0:
            defects.append(self._create_defect(
                rule_id="COM-001",
                rule_data=self._get_common_rule("COM-001"),
                evidence="No tenant name(s) found in notice"
            ))

        # Check for property address
        if not notice.property_address:
            defects.append(self._create_defect(
                rule_id="COM-002",
                rule_data=self._get_common_rule("COM-002"),
                evidence="No property address found in notice"
            ))

        # Check for signature
        if not notice.is_signed:
            defects.append(self._create_defect(
                rule_id="COM-003",
                rule_data=self._get_common_rule("COM-003"),
                evidence="Notice does not appear to be signed"
            ))

        # Check for date
        if not notice.notice_date and not notice.service_date:
            defects.append(self._create_defect(
                rule_id="COM-004",
                rule_data=self._get_common_rule("COM-004"),
                evidence="No date found on notice"
            ))

        return defects

    @abstractmethod
    def _validate_specific_requirements(
        self,
        notice: ExtractedNotice,
        context: Optional[ValidationContext]
    ) -> List[Defect]:
        """
        Validate notice-specific requirements.

        Must be implemented by subclasses.

        Args:
            notice: Extracted notice data
            context: Optional validation context

        Returns:
            List of defects
        """
        pass

    def _create_defect(
        self,
        rule_id: str,
        rule_data: dict,
        evidence: Optional[str] = None
    ) -> Defect:
        """
        Create a Defect object from rule data.

        Args:
            rule_id: Rule identifier
            rule_data: Rule data from YAML
            evidence: Optional evidence text from notice

        Returns:
            Defect object
        """
        return Defect(
            defect_id=rule_id,
            title=rule_data.get('name', '').replace('_', ' ').title(),
            severity=Severity(rule_data.get('severity', 'major')),
            description=rule_data.get('description', ''),
            statute_violated=rule_data.get('statute', '') or ', '.join(rule_data.get('case_law', [])),
            case_law=rule_data.get('case_law', []),
            tenant_action=rule_data.get('tenant_action', ''),
            detected_by='rule',
            evidence=evidence
        )

    def _get_common_rule(self, rule_id: str) -> dict:
        """
        Get a common rule by ID.

        Args:
            rule_id: Rule identifier

        Returns:
            Rule data dictionary
        """
        for rule in self.common_rules:
            if rule.get('rule_id') == rule_id:
                return rule
        return {}

    def _get_specific_rule(self, rule_id: str) -> dict:
        """
        Get a notice-specific rule by ID.

        Args:
            rule_id: Rule identifier

        Returns:
            Rule data dictionary
        """
        for rule in self.rules.get('validation_rules', []):
            if rule.get('rule_id') == rule_id:
                return rule
        return {}

    def _check_required_element(
        self,
        notice: ExtractedNotice,
        element_name: str,
        value: any
    ) -> Optional[Defect]:
        """
        Check if a required element is present.

        Args:
            notice: Extracted notice
            element_name: Name of the element to check
            value: Value to check (None/empty means missing)

        Returns:
            Defect if element is missing, None otherwise
        """
        # Find the element in required_elements
        for element in self.rules.get('required_elements', []):
            if element.get('element') == element_name:
                if not value or (isinstance(value, list) and len(value) == 0):
                    return Defect(
                        defect_id=f"{self.get_notice_type_key().upper()}-REQ",
                        title=f"Missing Required Element: {element.get('description')}",
                        severity=Severity.MAJOR if element.get('required') else Severity.MINOR,
                        description=f"Notice is missing: {element.get('description')}",
                        statute_violated=element.get('statute', ''),
                        case_law=element.get('case_law', '').split(';') if element.get('case_law') else [],
                        tenant_action="This missing information may invalidate the notice.",
                        detected_by='rule',
                        evidence=f"Required element '{element_name}' not found"
                    )
        return None
