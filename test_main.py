import unittest
from unittest.mock import patch, MagicMock, call
import os
import sys
from main import main, filter_chapters, save_summary_to_file
import ebooklib
from ebooklib import epub

class TestMain(unittest.TestCase):

    @patch('main.epub.read_epub')
    @patch('main.summarize_text_with_gemini')
    @patch('main.save_summary_to_file')
    @patch('os.makedirs')
    @patch('os.path.exists', return_value=True)
    def test_main_orchestration(self, mock_exists, mock_makedirs, mock_save_summary, mock_summarize, mock_read_epub):
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

        epub_path = "/fake/path/to/book.epub"

        # Act
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'fake_key'}):
            main(epub_path)

        # Assert
        mock_read_epub.assert_called_once_with(epub_path)
        mock_summarize.assert_called_once()
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

class TestSaveSummary(unittest.TestCase):

    @patch('os.makedirs')
    @patch('builtins.open', new_callable=unittest.mock.mock_open)
    def test_save_summary_to_file(self, mock_open, mock_makedirs):
        # Arrange
        summary = "This is a summary."
        item_name = "chapter1.xhtml"
        output_dir = "/fake/output/dir"

        # Act
        save_summary_to_file(summary, item_name, output_dir)

        # Assert
        mock_makedirs.assert_called_once_with(output_dir, exist_ok=True)
        mock_open.assert_called_once_with(os.path.join(output_dir, "chapter_1.md"), "w", encoding="utf-8")
        mock_open().write.assert_called_once_with(f"# Chapter: {item_name}\n\n{summary}\n")

if __name__ == '__main__':
    unittest.main()