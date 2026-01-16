"""
Image preprocessing module to improve OCR accuracy.

Applies various image enhancement techniques to make text clearer for Tesseract OCR.
"""

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
from typing import Tuple
import logging

logger = logging.getLogger(__name__)


class ImagePreprocessor:
    """Preprocesses images to improve OCR accuracy."""

    def __init__(self, target_dpi: int = 300):
        """
        Initialize preprocessor.

        Args:
            target_dpi: Target DPI for OCR (300 is optimal for Tesseract)
        """
        self.target_dpi = target_dpi

    def preprocess(self, image: Image.Image) -> Image.Image:
        """
        Apply full preprocessing pipeline to image.

        Args:
            image: PIL Image object

        Returns:
            Preprocessed PIL Image object
        """
        logger.info("Starting image preprocessing")

        # Convert to RGB if necessary
        if image.mode != 'RGB':
            logger.debug(f"Converting image from {image.mode} to RGB")
            image = image.convert('RGB')

        # Resize if needed for optimal DPI
        image = self._resize_for_ocr(image)

        # Convert to grayscale
        image = self._to_grayscale(image)

        # Increase contrast
        image = self._enhance_contrast(image)

        # Apply slight sharpening
        image = self._sharpen(image)

        # Denoise
        image = self._denoise(image)

        # Binarize (convert to black and white)
        image = self._binarize(image)

        # Deskew if needed
        image = self._deskew(image)

        logger.info("Image preprocessing complete")
        return image

    def _resize_for_ocr(self, image: Image.Image) -> Image.Image:
        """
        Resize image to optimal size for OCR.

        Tesseract works best with images at 300 DPI. If image is too small,
        scale it up.
        """
        width, height = image.size

        # If image is very small, scale it up
        min_height = 1000
        if height < min_height:
            scale_factor = min_height / height
            new_width = int(width * scale_factor)
            new_height = int(height * scale_factor)
            logger.debug(f"Scaling image from {width}x{height} to {new_width}x{new_height}")
            image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

        return image

    def _to_grayscale(self, image: Image.Image) -> Image.Image:
        """Convert image to grayscale."""
        return image.convert('L')

    def _enhance_contrast(self, image: Image.Image, factor: float = 1.5) -> Image.Image:
        """
        Enhance image contrast.

        Args:
            image: PIL Image
            factor: Contrast enhancement factor (1.0 = no change, >1.0 = more contrast)
        """
        enhancer = ImageEnhance.Contrast(image)
        return enhancer.enhance(factor)

    def _sharpen(self, image: Image.Image) -> Image.Image:
        """Apply sharpening filter to make text edges clearer."""
        return image.filter(ImageFilter.SHARPEN)

    def _denoise(self, image: Image.Image) -> Image.Image:
        """
        Remove noise from image.

        Uses median filter which is effective at removing salt-and-pepper noise
        while preserving edges.
        """
        return image.filter(ImageFilter.MedianFilter(size=3))

    def _binarize(self, image: Image.Image, threshold: int = 128) -> Image.Image:
        """
        Convert grayscale image to black and white using adaptive thresholding.

        Args:
            image: Grayscale PIL Image
            threshold: Threshold value for binarization

        Returns:
            Binarized image
        """
        # Convert to numpy array for processing
        img_array = np.array(image)

        # Apply Otsu's method for automatic threshold calculation
        # This finds optimal threshold by minimizing intra-class variance
        threshold = self._calculate_otsu_threshold(img_array)

        logger.debug(f"Binarization threshold: {threshold}")

        # Apply threshold
        binary_array = (img_array > threshold) * 255
        binary_image = Image.fromarray(binary_array.astype(np.uint8))

        return binary_image

    def _calculate_otsu_threshold(self, img_array: np.ndarray) -> int:
        """
        Calculate optimal threshold using Otsu's method.

        Args:
            img_array: Grayscale image as numpy array

        Returns:
            Optimal threshold value
        """
        # Calculate histogram
        histogram, bin_edges = np.histogram(img_array, bins=256, range=(0, 256))

        # Normalize histogram
        histogram = histogram.astype(float) / histogram.sum()

        # Calculate cumulative sums and means
        cum_sum = np.cumsum(histogram)
        cum_mean = np.cumsum(histogram * np.arange(256))

        # Calculate total mean
        total_mean = cum_mean[-1]

        # Calculate between-class variance for each threshold
        max_variance = 0
        optimal_threshold = 0

        for t in range(256):
            # Weight of background class
            w0 = cum_sum[t]
            # Weight of foreground class
            w1 = 1.0 - w0

            if w0 == 0 or w1 == 0:
                continue

            # Mean of background class
            mu0 = cum_mean[t] / w0 if w0 > 0 else 0
            # Mean of foreground class
            mu1 = (total_mean - cum_mean[t]) / w1 if w1 > 0 else 0

            # Between-class variance
            variance = w0 * w1 * (mu0 - mu1) ** 2

            if variance > max_variance:
                max_variance = variance
                optimal_threshold = t

        return optimal_threshold

    def _deskew(self, image: Image.Image) -> Image.Image:
        """
        Detect and correct skew in image.

        Note: This is a simplified deskew. For more robust deskewing,
        consider using OpenCV's methods.
        """
        # For now, return image as-is
        # Full deskew implementation would require detecting text lines
        # and calculating rotation angle, which is complex
        # OpenCV would be better for this, but we're keeping dependencies minimal
        return image

    def preprocess_for_layout_analysis(self, image: Image.Image) -> Image.Image:
        """
        Preprocess image for layout analysis (less aggressive than OCR preprocessing).

        Used when we need to preserve more of the original image structure.
        """
        if image.mode != 'RGB':
            image = image.convert('RGB')

        # Only resize and enhance contrast, no binarization
        image = self._resize_for_ocr(image)
        image = self._to_grayscale(image)
        image = self._enhance_contrast(image, factor=1.2)

        return image
