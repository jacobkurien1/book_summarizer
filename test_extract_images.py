import unittest
from unittest.mock import patch, MagicMock
import os
import sys
from extract_images import extract_images, create_image_map, extract_chapter_images_and_context
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup

class TestExtractImages(unittest.TestCase):

    @patch('extract_images.epub.read_epub')
    @patch('os.makedirs')
    @patch('builtins.open', new_callable=unittest.mock.mock_open)
    @patch('os.path.exists', return_value=True)
    def test_extract_images_flow(self, mock_exists, mock_open, mock_makedirs, mock_read_epub):
        # Arrange
        mock_book = MagicMock()
        mock_image_item = MagicMock()
        mock_image_item.get_type.return_value = ebooklib.ITEM_IMAGE
        mock_image_item.get_name.return_value = "images/test_image.jpg"
        mock_image_item.get_content.return_value = b"fake_image_data"

        mock_chapter_item = MagicMock()
        mock_chapter_item.get_type.return_value = ebooklib.ITEM_DOCUMENT
        mock_chapter_item.get_name.return_value = "chapter1.xhtml"
        mock_chapter_item.get_content.return_value = b'<html><body><img src="../images/test_image.jpg"/></body></html>'

        mock_book.get_items.return_value = [mock_image_item, mock_chapter_item]
        mock_book.get_metadata.return_value = [('Test Book', {})]
        mock_read_epub.return_value = mock_book

        epub_path = "/fake/path/to/book.epub"

        # Act
        with patch.object(sys, 'argv', ['extract_images.py', epub_path]):
            extract_images(epub_path)

        # Assert
        mock_read_epub.assert_called_once_with(epub_path)
        mock_open.assert_called_once()
        self.assertIn("chapter_1_image_1.jpg", mock_open.call_args[0][0])

class TestImageMap(unittest.TestCase):

    def test_create_image_map(self):
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

    def test_extract_chapter_images_and_context(self):
        # Arrange
        mock_chapter_item = MagicMock()
        mock_chapter_item.get_name.return_value = "chapter1.xhtml"
        mock_chapter_item.get_content.return_value = b'<html><body><img src="../images/test_image.jpg" alt="A test image"/></body></html>'

        image_map = {"images/test_image.jpg": b"fake_image_data"}
        output_dir = "/fake/output/dir"
        chapter_image_counts = {}

        # Act
        with patch('builtins.open', new_callable=unittest.mock.mock_open) as mock_open:
            image_context = extract_chapter_images_and_context(mock_chapter_item, image_map, output_dir, chapter_image_counts)

        # Assert
        self.assertEqual(len(image_context), 1)
        self.assertEqual(image_context[0]["image_path"], os.path.join(output_dir, "chapter_1_image_1.jpg"))
        self.assertEqual(image_context[0]["context_text"], "A test image")
        mock_open.assert_called_once_with(os.path.join(output_dir, "chapter_1_image_1.jpg"), "wb")

if __name__ == '__main__':
    unittest.main()