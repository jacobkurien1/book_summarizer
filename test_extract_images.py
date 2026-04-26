"""
Unit tests for extracting images.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

import ebooklib
from ebooklib import epub


from extract_images import (
    create_image_map,
    extract_and_mark_images,
    extract_images,
)


class TestExtractImages(unittest.TestCase):
    """Test suite for the extract_images utilities."""

    @patch("extract_images.epub.read_epub")
    @patch("os.makedirs")
    @patch("builtins.open", new_callable=unittest.mock.mock_open)
    @patch("os.path.exists", return_value=True)
    def test_extract_images_flow(
        self, _mock_exists, mock_open, _mock_makedirs, mock_read_epub
    ):
        """Verifies the full extraction flow from epub to local files."""
        # Arrange
        mock_book = MagicMock()
        mock_image_item = MagicMock()
        mock_image_item.get_type.return_value = ebooklib.ITEM_IMAGE
        mock_image_item.get_name.return_value = "images/test_image.jpg"
        mock_image_item.get_content.return_value = b"fake_image_data"

        mock_chapter_item = MagicMock()
        mock_chapter_item.get_type.return_value = ebooklib.ITEM_DOCUMENT
        mock_chapter_item.get_name.return_value = "xhtml/chapter1.xhtml"
        mock_chapter_item.get_content.return_value = (
            b'<html><body><img src="../images/test_image.jpg"/></body></html>'
        )

        mock_book.get_items.return_value = [mock_image_item, mock_chapter_item]
        mock_book.get_metadata.return_value = [("Test Book", {})]
        mock_read_epub.return_value = mock_book

        epub_path = "/fake/path/to/book.epub"

        # Act
        with patch.object(sys, "argv", ["extract_images.py", epub_path]):
            extract_images(epub_path)

        # Assert
        mock_read_epub.assert_called_once_with(epub_path)
        mock_open.assert_called()
        self.assertIn("image_1.jpg", mock_open.call_args[0][0])


class TestImageMap(unittest.TestCase):
    """Test suite for image mapping."""

    def test_create_image_map(self):
        """Verifies images are properly mapped from EPUB."""
        # Arrange
        mock_book = MagicMock()
        mock_image_item = MagicMock()
        mock_image_item.get_type.return_value = ebooklib.ITEM_IMAGE
        mock_image_item.get_name.return_value = "images/test_image.jpg"
        mock_image_item.get_content.return_value = b"fake_image_data"

        mock_book.get_items.return_value = [mock_image_item]

        # Act
        image_map = create_image_map(mock_book)

        # Assert
        self.assertEqual(len(image_map), 1)
        self.assertIn("images/test_image.jpg", image_map)
        self.assertEqual(image_map["images/test_image.jpg"], b"fake_image_data")


class TestChapterImageExtraction(unittest.TestCase):
    """Test suite for chapter image extracting."""

    def test_extract_and_mark_images(self):
        """Verifies context near images is extracted correctly."""
        # Arrange
        item_name = "xhtml/chapter1.xhtml"
        html_content = '<html><body><img src="../images/test_image.jpg" alt="A test image"/></body></html>'

        image_map = {"images/test_image.jpg": b"fake_image_data"}
        output_dir = "/fake/output/dir"
        img_counter = 0

        # Act
        with patch("builtins.open", new_callable=unittest.mock.mock_open) as mock_open:
            result_html, new_counter = extract_and_mark_images(
                html_content, item_name, image_map, output_dir, img_counter
            )

        # Assert
        self.assertEqual(new_counter, 1)
        self.assertIn("<<@IMAGE:image_1.jpg|A test image>>", result_html)
        mock_open.assert_called_once_with(
            os.path.join(output_dir, "image_1.jpg"), "wb"
        )

    def test_extract_images_with_url_encoded_path(self):
        """Verifies images with URL encoded paths are processed successfully."""
        # Arrange
        item_name = "xhtml/chapter1.xhtml"
        html_content = '<html><body><img src="../images/image%20with%20space.jpg" alt="Image with space"/></body></html>'

        image_map = {"images/image with space.jpg": b"fake_image_data"}
        output_dir = "/fake/output/dir"
        img_counter = 0

        # Act
        with patch("builtins.open", new_callable=unittest.mock.mock_open) as mock_open:
            result_html, new_counter = extract_and_mark_images(
                html_content, item_name, image_map, output_dir, img_counter
            )

        # Assert
        self.assertEqual(new_counter, 1, "Should find 1 image")
        self.assertIn("<<@IMAGE:image_1.jpg|Image with space>>", result_html)


if __name__ == "__main__":
    unittest.main()
