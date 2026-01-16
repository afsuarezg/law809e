"""
Main OCR processor that orchestrates document processing pipeline.

Handles PDF conversion, image preprocessing, and text extraction.
"""

import logging
from pathlib import Path
from typing import Union, List, Dict, Optional
from PIL import Image
import pdf2image
import pypdf

from .preprocessor import ImagePreprocessor
from .extractor import TextExtractor

logger = logging.getLogger(__name__)


class OCRProcessor:
    """Main OCR processor for eviction notices."""

    # Supported file formats
    IMAGE_FORMATS = {'.png', '.jpg', '.jpeg', '.tiff', '.tif', '.bmp'}
    PDF_FORMAT = '.pdf'

    def __init__(
        self,
        preprocess: bool = True,
        language: str = 'eng',
        dpi: int = 300
    ):
        """
        Initialize OCR processor.

        Args:
            preprocess: Whether to apply image preprocessing (recommended)
            language: Language for OCR (default: English)
            dpi: DPI for PDF conversion (default: 300)
        """
        self.preprocess = preprocess
        self.dpi = dpi

        self.preprocessor = ImagePreprocessor(target_dpi=dpi) if preprocess else None
        self.extractor = TextExtractor(language=language)

        logger.info(f"OCR Processor initialized (preprocess={preprocess}, dpi={dpi})")

    def process_document(self, file_path: Union[str, Path]) -> str:
        """
        Process a document and extract text.

        Args:
            file_path: Path to PDF or image file

        Returns:
            Extracted text as string

        Raises:
            ValueError: If file format is not supported
            FileNotFoundError: If file does not exist
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        logger.info(f"Processing document: {file_path}")

        # Determine file type and process accordingly
        if file_path.suffix.lower() == self.PDF_FORMAT:
            text = self._process_pdf(file_path)
        elif file_path.suffix.lower() in self.IMAGE_FORMATS:
            text = self._process_image(file_path)
        else:
            raise ValueError(
                f"Unsupported file format: {file_path.suffix}. "
                f"Supported formats: {self.IMAGE_FORMATS | {self.PDF_FORMAT}}"
            )

        logger.info(f"Document processing complete. Extracted {len(text)} characters.")
        return text

    def process_document_with_metadata(self, file_path: Union[str, Path]) -> Dict:
        """
        Process document and return text with metadata and confidence scores.

        Args:
            file_path: Path to PDF or image file

        Returns:
            Dictionary containing text, confidence scores, and metadata
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        logger.info(f"Processing document with metadata: {file_path}")

        # Determine file type
        if file_path.suffix.lower() == self.PDF_FORMAT:
            result = self._process_pdf_with_metadata(file_path)
        elif file_path.suffix.lower() in self.IMAGE_FORMATS:
            result = self._process_image_with_metadata(file_path)
        else:
            raise ValueError(f"Unsupported file format: {file_path.suffix}")

        # Add file metadata
        result['file_info'] = {
            'filename': file_path.name,
            'file_size': file_path.stat().st_size,
            'file_type': file_path.suffix.lower()
        }

        return result

    def _process_pdf(self, pdf_path: Path) -> str:
        """
        Process PDF file by converting to images and running OCR.

        First attempts to extract text directly from PDF (for digital PDFs).
        If that yields insufficient text, falls back to OCR.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Extracted text
        """
        logger.info(f"Processing PDF: {pdf_path}")

        # Try direct text extraction first (for digital PDFs)
        direct_text = self._extract_pdf_text_directly(pdf_path)

        # If we got substantial text, use it
        if len(direct_text.strip()) > 100:  # Arbitrary threshold
            logger.info("PDF contains extractable text, using direct extraction")
            return direct_text

        # Otherwise, use OCR (for scanned PDFs)
        logger.info("PDF appears to be scanned, using OCR")
        return self._ocr_pdf(pdf_path)

    def _extract_pdf_text_directly(self, pdf_path: Path) -> str:
        """
        Try to extract text directly from PDF (for digital PDFs).

        Args:
            pdf_path: Path to PDF file

        Returns:
            Extracted text (may be empty if PDF is image-based)
        """
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = pypdf.PdfReader(file)

                text_parts = []
                for page_num, page in enumerate(pdf_reader.pages):
                    text = page.extract_text()
                    if text:
                        text_parts.append(text)
                        logger.debug(f"Extracted {len(text)} chars from page {page_num + 1}")

                return '\n\n'.join(text_parts)

        except Exception as e:
            logger.warning(f"Direct PDF text extraction failed: {e}")
            return ""

    def _ocr_pdf(self, pdf_path: Path) -> str:
        """
        OCR a PDF by converting to images.

        Args:
            pdf_path: Path to PDF file

        Returns:
            OCR extracted text
        """
        try:
            # Convert PDF pages to images
            logger.info(f"Converting PDF to images at {self.dpi} DPI")
            images = pdf2image.convert_from_path(
                pdf_path,
                dpi=self.dpi,
                fmt='png'
            )

            logger.info(f"Converted PDF to {len(images)} image(s)")

            # OCR each page
            text_parts = []
            for i, image in enumerate(images):
                logger.info(f"OCR processing page {i + 1}/{len(images)}")

                if self.preprocess:
                    image = self.preprocessor.preprocess(image)

                page_text = self.extractor.extract_text(image)
                text_parts.append(page_text)

                logger.debug(f"Page {i + 1}: extracted {len(page_text)} characters")

            # Combine all pages
            full_text = '\n\n--- PAGE BREAK ---\n\n'.join(text_parts)
            return full_text

        except Exception as e:
            logger.error(f"PDF OCR failed: {e}")
            raise

    def _process_pdf_with_metadata(self, pdf_path: Path) -> Dict:
        """Process PDF with metadata extraction."""
        # Try direct extraction first
        direct_text = self._extract_pdf_text_directly(pdf_path)

        if len(direct_text.strip()) > 100:
            return {
                'text': direct_text,
                'method': 'direct_extraction',
                'average_confidence': 100.0,  # Direct extraction is 100% accurate
                'page_count': direct_text.count('\n\n') + 1,
                'ocr_warnings': []
            }

        # Fall back to OCR
        images = pdf2image.convert_from_path(pdf_path, dpi=self.dpi)

        page_results = []
        all_warnings = []

        for i, image in enumerate(images):
            if self.preprocess:
                image = self.preprocessor.preprocess(image)

            result = self.extractor.extract_text_with_confidence(image)

            page_results.append({
                'page': i + 1,
                'text': result['text'],
                'confidence': result['average_confidence']
            })

            # Check for warnings
            validation = self.extractor.validate_ocr_quality(result['text'])
            if not validation['is_valid']:
                for issue in validation['issues']:
                    all_warnings.append(f"Page {i + 1}: {issue['message']}")

        # Combine pages
        combined_text = '\n\n--- PAGE BREAK ---\n\n'.join(
            [p['text'] for p in page_results]
        )

        avg_confidence = sum(p['confidence'] for p in page_results) / len(page_results)

        return {
            'text': combined_text,
            'method': 'ocr',
            'average_confidence': avg_confidence,
            'page_count': len(images),
            'pages': page_results,
            'ocr_warnings': all_warnings
        }

    def _process_image(self, image_path: Path) -> str:
        """
        Process a single image file.

        Args:
            image_path: Path to image file

        Returns:
            Extracted text
        """
        logger.info(f"Processing image: {image_path}")

        try:
            # Load image
            image = Image.open(image_path)

            # Preprocess if enabled
            if self.preprocess:
                image = self.preprocessor.preprocess(image)

            # Extract text
            text = self.extractor.extract_text(image)

            return text

        except Exception as e:
            logger.error(f"Image processing failed: {e}")
            raise

    def _process_image_with_metadata(self, image_path: Path) -> Dict:
        """Process image with metadata extraction."""
        image = Image.open(image_path)

        original_size = image.size

        if self.preprocess:
            image = self.preprocessor.preprocess(image)

        result = self.extractor.extract_text_with_confidence(image)
        validation = self.extractor.validate_ocr_quality(result['text'])

        return {
            'text': result['text'],
            'method': 'ocr',
            'average_confidence': result['average_confidence'],
            'page_count': 1,
            'image_size': original_size,
            'ocr_warnings': [issue['message'] for issue in validation['issues']],
            'low_confidence_words': result['low_confidence_words']
        }

    def extract_structured_blocks(self, file_path: Union[str, Path]) -> List[Dict]:
        """
        Extract text organized by blocks (useful for layout analysis).

        Args:
            file_path: Path to document

        Returns:
            List of text blocks with positioning information
        """
        file_path = Path(file_path)

        if file_path.suffix.lower() in self.IMAGE_FORMATS:
            image = Image.open(file_path)
            if self.preprocess:
                image = self.preprocessor.preprocess(image)
            return self.extractor.extract_blocks(image)

        elif file_path.suffix.lower() == self.PDF_FORMAT:
            # For PDFs, process first page only
            # (could be extended to handle multi-page)
            images = pdf2image.convert_from_path(file_path, dpi=self.dpi)
            if images:
                image = images[0]
                if self.preprocess:
                    image = self.preprocessor.preprocess(image)
                return self.extractor.extract_blocks(image)
            return []

        else:
            raise ValueError(f"Unsupported file format: {file_path.suffix}")

    @staticmethod
    def is_supported_format(file_path: Union[str, Path]) -> bool:
        """
        Check if file format is supported.

        Args:
            file_path: Path to file

        Returns:
            True if format is supported
        """
        file_path = Path(file_path)
        suffix = file_path.suffix.lower()
        return suffix in OCRProcessor.IMAGE_FORMATS or suffix == OCRProcessor.PDF_FORMAT
