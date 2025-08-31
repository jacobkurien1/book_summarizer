import unittest
from unittest.mock import patch, MagicMock, call
import os
import sys
from main import main, filter_chapters
from utils import save_summary_to_file, summarize_text_with_gemini
import ebooklib
from ebooklib import epub

class TestMain(unittest.TestCase):

    @patch('builtins.open', new_callable=unittest.mock.mock_open, read_data='summary')
    @patch('os.listdir', return_value=['summary1.md'])
    @patch('main.create_image_map')
    @patch('main.extract_chapter_images_and_context')
    @patch('main.epub.read_epub')
    @patch('main.summarize_text_with_gemini')
    @patch('main.save_summary_to_file')
    @patch('os.makedirs')
    @patch('os.path.exists', return_value=True)
    def test_main_orchestration(self, mock_exists, mock_makedirs, mock_save_summary, mock_summarize, mock_read_epub, mock_extract_images, mock_create_image_map, mock_listdir, mock_open):
        # Arrange
        mock_book = MagicMock()
        mock_chapter_item = MagicMock()
        mock_chapter_item.get_type.return_value = ebooklib.ITEM_DOCUMENT
        mock_chapter_item.get_name.return_value = "chapter1.xhtml"
        mock_chapter_item.get_content.return_value = b"<html><body><h1>Chapter 1</h1><p>This is the content.</p></body></html>"

        mock_non_chapter_item = MagicMock()
        mock_non_chapter_item.get_type.return_value = ebooklib.ITEM_DOCUMENT
        mock_non_chapter_item.get_name.return_value = "cover.xhtml"

        mock_book.get_items.return_value = [mock_chapter_item, mock_non_chapter_item]
        mock_book.get_metadata.return_value = [('Test Book', {})]
        mock_read_epub.return_value = mock_book
        mock_summarize.return_value = "This is a summary."
        mock_create_image_map.return_value = {"image.jpg": b"fakedata"}
        mock_extract_images.return_value = []

        epub_path = "/fake/path/to/book.epub"

        # Act
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'fake_key'}):
            main(epub_path)

        # Assert
        mock_read_epub.assert_called_once_with(epub_path)
        mock_create_image_map.assert_called_once_with(mock_book)
        mock_extract_images.assert_called_once_with(mock_chapter_item, {"image.jpg": b"fakedata"}, unittest.mock.ANY, unittest.mock.ANY)
        mock_summarize.assert_called()
        mock_save_summary.assert_called_once_with("This is a summary.", "chapter1.xhtml", unittest.mock.ANY)

class TestChapterFiltering(unittest.TestCase):

    def test_filter_chapters(self):
        # Arrange
        mock_chapter_item = MagicMock()
        mock_chapter_item.get_type.return_value = ebooklib.ITEM_DOCUMENT
        mock_chapter_item.get_name.return_value = "chapter1.xhtml"

        mock_non_chapter_item = MagicMock()
        mock_non_chapter_item.get_type.return_value = ebooklib.ITEM_DOCUMENT
        mock_non_chapter_item.get_name.return_value = "cover.xhtml"

        items = [mock_chapter_item, mock_non_chapter_item]
        exclude_keywords = ["cover"]

        # Act
        chapters = filter_chapters(items, exclude_keywords)

        # Assert
        self.assertEqual(len(chapters), 1)
        self.assertEqual(chapters[0].get_name(), "chapter1.xhtml")

if __name__ == '__main__':
    unittest.main()