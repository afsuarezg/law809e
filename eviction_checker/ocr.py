"""
OCR module for extracting text from PDF and image files.
"""

import logging
from pathlib import Path
from typing import Union

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
import pytesseract
import pdf2image
import pypdf

logger = logging.getLogger(__name__)


class OCRProcessor:
    """Extracts text from PDF and image documents."""

    IMAGE_FORMATS = {'.png', '.jpg', '.jpeg', '.tiff', '.tif', '.bmp'}

    def __init__(self, dpi: int = 300):
        self.dpi = dpi

    def process(self, file_path: Union[str, Path]) -> str:
        """
        Extract text from a PDF or image file.

        Args:
            file_path: Path to the document

        Returns:
            Extracted text
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        suffix = file_path.suffix.lower()

        if suffix == '.pdf':
            return self._process_pdf(file_path)
        elif suffix in self.IMAGE_FORMATS:
            return self._process_image(file_path)
        else:
            raise ValueError(f"Unsupported format: {suffix}")

    def _process_pdf(self, pdf_path: Path) -> str:
        """Process PDF file."""
        # Try direct text extraction first (for digital PDFs)
        direct_text = self._extract_pdf_text(pdf_path)
        if len(direct_text.strip()) > 100:
            logger.info("Using direct PDF text extraction")
            return direct_text

        # Fall back to OCR for scanned PDFs
        logger.info("PDF appears scanned, using OCR")
        return self._ocr_pdf(pdf_path)

    def _extract_pdf_text(self, pdf_path: Path) -> str:
        """Extract text directly from PDF."""
        try:
            with open(pdf_path, 'rb') as f:
                reader = pypdf.PdfReader(f)
                text_parts = []
                for page in reader.pages:
                    text = page.extract_text()
                    if text:
                        text_parts.append(text)
                return '\n\n'.join(text_parts)
        except Exception as e:
            logger.warning(f"Direct PDF extraction failed: {e}")
            return ""

    def _ocr_pdf(self, pdf_path: Path) -> str:
        """OCR a PDF by converting to images."""
        images = pdf2image.convert_from_path(pdf_path, dpi=self.dpi)
        text_parts = []

        for i, image in enumerate(images):
            logger.info(f"OCR processing page {i + 1}/{len(images)}")
            processed = self._preprocess_image(image)
            text = pytesseract.image_to_string(processed, lang='eng')
            text_parts.append(text)

        return '\n\n'.join(text_parts)

    def _process_image(self, image_path: Path) -> str:
        """Process a single image file."""
        image = Image.open(image_path)
        processed = self._preprocess_image(image)
        return pytesseract.image_to_string(processed, lang='eng')

    def _preprocess_image(self, image: Image.Image) -> Image.Image:
        """Preprocess image for better OCR accuracy."""
        # Convert to RGB if needed
        if image.mode != 'RGB':
            image = image.convert('RGB')

        # Scale up small images
        width, height = image.size
        if height < 1000:
            scale = 1000 / height
            image = image.resize(
                (int(width * scale), int(height * scale)),
                Image.Resampling.LANCZOS
            )

        # Convert to grayscale
        image = image.convert('L')

        # Enhance contrast
        image = ImageEnhance.Contrast(image).enhance(1.5)

        # Sharpen
        image = image.filter(ImageFilter.SHARPEN)

        # Denoise
        image = image.filter(ImageFilter.MedianFilter(size=3))

        # Binarize using Otsu's method
        img_array = np.array(image)
        threshold = self._otsu_threshold(img_array)
        binary = (img_array > threshold) * 255
        image = Image.fromarray(binary.astype(np.uint8))

        return image

    def _otsu_threshold(self, img_array: np.ndarray) -> int:
        """Calculate optimal threshold using Otsu's method."""
        histogram, _ = np.histogram(img_array, bins=256, range=(0, 256))
        histogram = histogram.astype(float) / histogram.sum()

        cum_sum = np.cumsum(histogram)
        cum_mean = np.cumsum(histogram * np.arange(256))
        total_mean = cum_mean[-1]

        max_variance = 0
        threshold = 0

        for t in range(256):
            w0 = cum_sum[t]
            w1 = 1.0 - w0
            if w0 == 0 or w1 == 0:
                continue

            mu0 = cum_mean[t] / w0
            mu1 = (total_mean - cum_mean[t]) / w1
            variance = w0 * w1 * (mu0 - mu1) ** 2

            if variance > max_variance:
                max_variance = variance
                threshold = t

        return threshold
