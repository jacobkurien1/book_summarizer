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
    @patch('main.summarize_text')
    @patch('main.save_summary_to_file')
    @patch('os.makedirs')
    @patch('os.path.exists', return_value=True)
    def test_main_orchestration(self, mock_exists, mock_makedirs, mock_save_summary, mock_summarize, mock_read_epub, mock_extract_images, mock_create_image_map, mock_listdir, mock_open):
        # Arrange
        mock_book = MagicMock()
        mock_chapter_item = MagicMock()
        mock_chapter_item.get_type.return_value = ebooklib.ITEM_DOCUMENT
        mock_chapter_item.get_name.return_value = "chapter1.xhtml"
        mock_chapter_item.get_content.return_value = b"<html><body><h1>Chapter 1</h1><p>This is the content that needs to be long enough to pass the 100 character threshold check in main.py. So let's add some more text here to be sure.</p></body></html>"

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
    @patch('builtins.open', new_callable=unittest.mock.mock_open, read_data='summary')
    @patch('os.listdir', return_value=['summary1.md'])
    @patch('main.create_image_map')
    @patch('main.extract_chapter_images_and_context')
    @patch('main.epub.read_epub')
    @patch('main.summarize_text')
    @patch('main.save_summary_to_file')
    @patch('os.makedirs')
    @patch('os.path.exists', return_value=True)
    def test_main_with_wildcard_chapters(self, mock_exists, mock_makedirs, mock_save_summary, mock_summarize, mock_read_epub, mock_extract_images, mock_create_image_map, mock_listdir, mock_open):
        # Arrange: 3 chapters
        mock_book = MagicMock()
        chapters = []
        for i in range(1, 4):
            ch = MagicMock()
            ch.get_type.return_value = ebooklib.ITEM_DOCUMENT
            ch.get_name.return_value = f"chapter{i}.xhtml"
            ch.get_content.return_value = b"Content " * 20 # > 100 chars
            chapters.append(ch)

        mock_book.get_items.return_value = chapters
        mock_book.get_metadata.return_value = [('Test Book', {})]
        mock_read_epub.return_value = mock_book
        mock_summarize.return_value = "Summary"
        mock_create_image_map.return_value = {}
        mock_extract_images.return_value = []

        # Act: "2,*" should process chapters 2 and 3
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'fake_key'}):
            main("/fake/path.epub", chapters="2,*")

        # Assert: summarize called 3 times (chapter 2, chapter 3, and final summary)
        self.assertEqual(mock_summarize.call_count, 3)
        # Verify summaries were for chapter 2 and 3
        mock_save_summary.assert_any_call("Summary", "chapter2.xhtml", unittest.mock.ANY)
        mock_save_summary.assert_any_call("Summary", "chapter3.xhtml", unittest.mock.ANY)

    @patch('builtins.open', new_callable=unittest.mock.mock_open, read_data='summary')
    @patch('os.listdir', return_value=['summary1.md'])
    @patch('main.create_image_map')
    @patch('main.extract_chapter_images_and_context')
    @patch('main.epub.read_epub')
    @patch('main.summarize_text')
    @patch('main.save_summary_to_file')
    @patch('os.makedirs')
    @patch('os.path.exists', return_value=True)
    def test_main_with_invalid_chapters_parsing(self, mock_exists, mock_makedirs, mock_save_summary, mock_summarize, mock_read_epub, mock_extract_images, mock_create_image_map, mock_listdir, mock_open):
        # Arrange: 3 chapters
        mock_book = MagicMock()
        chapters = []
        for i in range(1, 4):
            ch = MagicMock()
            ch.get_type.return_value = ebooklib.ITEM_DOCUMENT
            ch.get_name.return_value = f"chapter{i}.xhtml"
            ch.get_content.return_value = b"Content " * 20 
            chapters.append(ch)

        mock_book.get_items.return_value = chapters
        mock_book.get_metadata.return_value = [('Test Book', {})]
        mock_read_epub.return_value = mock_book
        mock_summarize.return_value = "Summary"
        mock_create_image_map.return_value = {}
        mock_extract_images.return_value = []

        # Act: "2, invalid, *" should handle "2" and "*" relative to "2"
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'fake_key'}):
            main("/fake/path.epub", chapters="2, invalid, *")

        # Assert: summary called 3 times (chapter 2, 3 and final)
        self.assertEqual(mock_summarize.call_count, 3)
        mock_save_summary.assert_any_call(unittest.mock.ANY, "chapter2.xhtml", unittest.mock.ANY)
        mock_save_summary.assert_any_call(unittest.mock.ANY, "chapter3.xhtml", unittest.mock.ANY)

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