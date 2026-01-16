"""
Text extraction module using Tesseract OCR.

Handles OCR configuration and text extraction from preprocessed images.
"""

import pytesseract
from PIL import Image
from typing import Dict, List, Optional
import logging
import re

logger = logging.getLogger(__name__)


class TextExtractor:
    """Extracts text from images using Tesseract OCR."""

    def __init__(self, language: str = 'eng', custom_config: Optional[str] = None):
        """
        Initialize text extractor.

        Args:
            language: Tesseract language code (default: 'eng' for English)
            custom_config: Custom Tesseract configuration string
        """
        self.language = language
        self.custom_config = custom_config or self._default_config()

    def _default_config(self) -> str:
        """
        Get default Tesseract configuration.

        Returns:
            Configuration string optimized for document OCR
        """
        # PSM (Page Segmentation Mode) 3 = Fully automatic page segmentation, but no OSD
        # OEM (OCR Engine Mode) 3 = Default, based on what is available (LSTM + legacy)
        return '--psm 3 --oem 3'

    def extract_text(self, image: Image.Image) -> str:
        """
        Extract text from image using OCR.

        Args:
            image: PIL Image object (should be preprocessed)

        Returns:
            Extracted text as string
        """
        logger.info("Extracting text with Tesseract OCR")

        try:
            text = pytesseract.image_to_string(
                image,
                lang=self.language,
                config=self.custom_config
            )

            logger.info(f"Extracted {len(text)} characters")

            # Post-process text
            text = self._post_process_text(text)

            return text

        except pytesseract.TesseractError as e:
            logger.error(f"Tesseract OCR error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during OCR: {e}")
            raise

    def extract_text_with_confidence(self, image: Image.Image) -> Dict:
        """
        Extract text along with confidence scores.

        Args:
            image: PIL Image object

        Returns:
            Dictionary with text and confidence information
        """
        logger.info("Extracting text with confidence scores")

        try:
            # Get detailed OCR data
            data = pytesseract.image_to_data(
                image,
                lang=self.language,
                config=self.custom_config,
                output_type=pytesseract.Output.DICT
            )

            # Calculate average confidence
            confidences = [int(conf) for conf in data['conf'] if conf != '-1']
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0

            # Reconstruct text
            text = self._reconstruct_text_from_data(data)
            text = self._post_process_text(text)

            # Find low confidence words
            low_confidence_words = []
            for i, conf in enumerate(data['conf']):
                if conf != '-1' and int(conf) < 60:  # Low confidence threshold
                    word = data['text'][i]
                    if word.strip():
                        low_confidence_words.append({
                            'word': word,
                            'confidence': int(conf),
                            'block': data['block_num'][i],
                            'line': data['line_num'][i]
                        })

            result = {
                'text': text,
                'average_confidence': avg_confidence,
                'low_confidence_words': low_confidence_words,
                'total_words': len([w for w in data['text'] if w.strip()])
            }

            logger.info(f"Average OCR confidence: {avg_confidence:.1f}%")
            if low_confidence_words:
                logger.warning(f"Found {len(low_confidence_words)} low confidence words")

            return result

        except Exception as e:
            logger.error(f"Error extracting text with confidence: {e}")
            raise

    def _reconstruct_text_from_data(self, data: Dict) -> str:
        """
        Reconstruct text from Tesseract data dictionary.

        Args:
            data: Dictionary from pytesseract.image_to_data

        Returns:
            Reconstructed text string
        """
        lines = []
        current_block = -1
        current_line = -1
        current_line_text = []

        for i in range(len(data['text'])):
            block_num = data['block_num'][i]
            line_num = data['line_num'][i]
            text = data['text'][i]

            # New block - add extra line break
            if block_num != current_block:
                if current_line_text:
                    lines.append(' '.join(current_line_text))
                    current_line_text = []
                if current_block != -1:  # Not the first block
                    lines.append('')  # Empty line between blocks
                current_block = block_num
                current_line = line_num

            # New line
            elif line_num != current_line:
                if current_line_text:
                    lines.append(' '.join(current_line_text))
                    current_line_text = []
                current_line = line_num

            # Add word to current line
            if text.strip():
                current_line_text.append(text)

        # Add last line
        if current_line_text:
            lines.append(' '.join(current_line_text))

        return '\n'.join(lines)

    def _post_process_text(self, text: str) -> str:
        """
        Post-process OCR text to fix common errors.

        Args:
            text: Raw OCR text

        Returns:
            Cleaned text
        """
        # Remove excessive whitespace
        text = re.sub(r' +', ' ', text)

        # Remove excessive newlines (but keep paragraph breaks)
        text = re.sub(r'\n{4,}', '\n\n', text)

        # Fix common OCR errors
        text = self._fix_common_ocr_errors(text)

        # Strip leading/trailing whitespace
        text = text.strip()

        return text

    def _fix_common_ocr_errors(self, text: str) -> str:
        """
        Fix common OCR character recognition errors.

        Args:
            text: OCR text

        Returns:
            Text with common errors corrected
        """
        # Common OCR substitutions
        corrections = {
            # Number/letter confusion
            r'\b0(?=\d)': 'O',  # 0 at start of word -> O
            r'(?<=\d)O\b': '0',  # O at end of number -> 0
            r'\bl(?=\d)': '1',  # lowercase L before digit -> 1
            r'(?<=\d)l\b': '1',  # lowercase L after digit -> 1

            # Common word errors
            r'\bth e\b': 'the',
            r'\ba nd\b': 'and',
            r'\bwi th\b': 'with',
            r'\bt o\b': 'to',

            # Dollar signs
            r'\$\s+(?=\d)': '$',  # Remove space after $

            # Section symbols
            r'§\s+': '§ ',  # Normalize section symbol spacing
        }

        for pattern, replacement in corrections.items():
            text = re.sub(pattern, replacement, text)

        return text

    def extract_blocks(self, image: Image.Image) -> List[Dict]:
        """
        Extract text organized by blocks (paragraphs).

        Useful for preserving document structure.

        Args:
            image: PIL Image object

        Returns:
            List of blocks, each containing text and metadata
        """
        logger.info("Extracting text blocks")

        try:
            data = pytesseract.image_to_data(
                image,
                lang=self.language,
                config=self.custom_config,
                output_type=pytesseract.Output.DICT
            )

            blocks = {}
            for i in range(len(data['text'])):
                if data['text'][i].strip():
                    block_num = data['block_num'][i]

                    if block_num not in blocks:
                        blocks[block_num] = {
                            'block_num': block_num,
                            'text': [],
                            'confidence': [],
                            'bbox': {
                                'left': data['left'][i],
                                'top': data['top'][i],
                                'width': data['width'][i],
                                'height': data['height'][i]
                            }
                        }

                    blocks[block_num]['text'].append(data['text'][i])
                    if data['conf'][i] != '-1':
                        blocks[block_num]['confidence'].append(int(data['conf'][i]))

                    # Update bounding box
                    blocks[block_num]['bbox']['left'] = min(
                        blocks[block_num]['bbox']['left'],
                        data['left'][i]
                    )
                    blocks[block_num]['bbox']['top'] = min(
                        blocks[block_num]['bbox']['top'],
                        data['top'][i]
                    )

            # Convert to list and format
            block_list = []
            for block_num, block_data in sorted(blocks.items()):
                block_text = ' '.join(block_data['text'])
                avg_conf = sum(block_data['confidence']) / len(block_data['confidence']) \
                    if block_data['confidence'] else 0

                block_list.append({
                    'block_num': block_num,
                    'text': self._post_process_text(block_text),
                    'confidence': avg_conf,
                    'bbox': block_data['bbox']
                })

            logger.info(f"Extracted {len(block_list)} text blocks")
            return block_list

        except Exception as e:
            logger.error(f"Error extracting blocks: {e}")
            raise

    def validate_ocr_quality(self, text: str, min_confidence: float = 70.0) -> Dict:
        """
        Validate OCR quality and provide warnings.

        Args:
            text: Extracted text
            min_confidence: Minimum acceptable confidence score

        Returns:
            Dictionary with validation results
        """
        issues = []

        # Check for very short text
        if len(text.strip()) < 50:
            issues.append({
                'type': 'warning',
                'message': 'Very little text extracted. Document may be image-based or low quality.'
            })

        # Check for unusual character ratio (signs of poor OCR)
        alpha_chars = sum(c.isalpha() for c in text)
        digit_chars = sum(c.isdigit() for c in text)
        special_chars = sum(not c.isalnum() and not c.isspace() for c in text)
        total_chars = len(text.replace(' ', '').replace('\n', ''))

        if total_chars > 0:
            special_ratio = special_chars / total_chars
            if special_ratio > 0.3:
                issues.append({
                    'type': 'warning',
                    'message': 'High ratio of special characters detected. OCR quality may be poor.'
                })

        # Check for repeated characters (common OCR error)
        repeated_chars = re.findall(r'(.)\1{4,}', text)
        if repeated_chars:
            issues.append({
                'type': 'warning',
                'message': f'Repeated character sequences found: {set(repeated_chars)}. May indicate OCR errors.'
            })

        return {
            'is_valid': len(issues) == 0,
            'issues': issues,
            'stats': {
                'total_chars': total_chars,
                'alpha_chars': alpha_chars,
                'digit_chars': digit_chars,
                'special_chars': special_chars
            }
        }
