"""
Validator module for eviction notices.

Provides factory function to get appropriate validator for each notice type.
"""

from typing import Optional
import logging

from .base import BaseValidator
from .three_day_pay import ThreeDayPayValidator
from ..parser.structured_data import NoticeType

logger = logging.getLogger(__name__)


class NoticeValidatorFactory:
    """Factory for creating notice validators."""

    _validators = {
        NoticeType.THREE_DAY_PAY: ThreeDayPayValidator,
        # Add more validators as they are implemented
        # NoticeType.THREE_DAY_CURE: ThreeDayCureValidator,
        # NoticeType.THIRTY_DAY: ThirtyDayValidator,
        # NoticeType.SIXTY_DAY: SixtyDayValidator,
    }

    @classmethod
    def get_validator(cls, notice_type: NoticeType) -> Optional[BaseValidator]:
        """
        Get appropriate validator for notice type.

        Args:
            notice_type: Type of eviction notice

        Returns:
            Validator instance, or None if no validator available
        """
        validator_class = cls._validators.get(notice_type)

        if validator_class:
            logger.info(f"Creating validator for {notice_type}")
            return validator_class()
        else:
            logger.warning(f"No validator available for {notice_type}")
            return None

    @classmethod
    def register_validator(cls, notice_type: NoticeType, validator_class: type):
        """
        Register a new validator.

        Args:
            notice_type: Notice type
            validator_class: Validator class (must inherit from BaseValidator)
        """
        if not issubclass(validator_class, BaseValidator):
            raise ValueError(f"{validator_class} must inherit from BaseValidator")

        cls._validators[notice_type] = validator_class
        logger.info(f"Registered validator for {notice_type}")


def get_validator(notice_type: NoticeType) -> Optional[BaseValidator]:
    """
    Convenience function to get validator.

    Args:
        notice_type: Type of eviction notice

    Returns:
        Validator instance or None
    """
    return NoticeValidatorFactory.get_validator(notice_type)


__all__ = [
    'BaseValidator',
    'ThreeDayPayValidator',
    'NoticeValidatorFactory',
    'get_validator'
]
