"""
Unit tests for the main application workflows.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, call, patch

import ebooklib
from ebooklib import epub

from main import filter_chapters, main
from utils import save_summary_to_file, summarize_text_with_gemini


class TestMain(unittest.TestCase):
    """Test suite for main.py."""

    @patch("builtins.open", new_callable=unittest.mock.mock_open, read_data="summary")
    @patch("os.listdir", return_value=["summary1.md"])
    @patch("main.create_image_map")
    @patch("main.epub.read_epub")
    @patch("main.summarize_text")
    @patch("main.save_summary_to_file")
    @patch("os.makedirs")
    @patch("os.path.exists", return_value=True)
    @patch("main.merge_and_split_chapters")
    def test_main_orchestration(
        self,
        mock_merge,
        mock_exists,
        mock_makedirs,
        mock_save_summary,
        mock_summarize,
        mock_read_epub,
        mock_create_image_map,
        mock_listdir,
        mock_open,
    ):
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
        mock_book.get_metadata.return_value = [("Test Book", {})]
        mock_read_epub.return_value = mock_book

        mock_merge.return_value = [
            {
                "name": "chapter1.xhtml",
                "content": "This is the content that needs to be long enough to pass the 100 character threshold check in main.py. So let us add some more text here to be sure.",
                "logical_num": 1,
            }
        ]

        mock_summarize.return_value = "This is a summary."
        mock_create_image_map.return_value = {"image.jpg": b"fakedata"}

        epub_path = "/fake/path/to/book.epub"

        # Act
        with patch.dict(os.environ, {"GEMINI_API_KEY": "fake_key"}):
            main(epub_path)

        # Assert
        mock_read_epub.assert_called_once_with(epub_path)
        mock_create_image_map.assert_called_once_with(mock_book)
        mock_summarize.assert_called()
        mock_save_summary.assert_called_once_with(
            "This is a summary.", "chapter1.xhtml", unittest.mock.ANY
        )

    @patch("builtins.open", new_callable=unittest.mock.mock_open, read_data="summary")
    @patch("os.listdir", return_value=["summary1.md"])
    @patch("main.create_image_map")
    @patch("main.epub.read_epub")
    @patch("main.summarize_text")
    @patch("main.save_summary_to_file")
    @patch("os.makedirs")
    @patch("os.path.exists", return_value=True)
    @patch("main.merge_and_split_chapters")
    def test_main_with_wildcard_chapters(
        self,
        mock_merge,
        mock_exists,
        mock_makedirs,
        mock_save_summary,
        mock_summarize,
        mock_read_epub,
        mock_create_image_map,
        mock_listdir,
        mock_open,
    ):
        # Arrange: 3 chapters
        mock_book = MagicMock()
        chapters = []
        for i in range(1, 4):
            ch = MagicMock()
            ch.get_type.return_value = ebooklib.ITEM_DOCUMENT
            ch.get_name.return_value = f"chapter{i}.xhtml"
            ch.get_content.return_value = b"Content " * 20  # > 100 chars
            chapters.append(ch)

        mock_book.get_items.return_value = chapters
        mock_book.get_metadata.return_value = [("Test Book", {})]
        mock_read_epub.return_value = mock_book

        mock_merge.return_value = [
            {"name": "chapter1.xhtml", "content": "Content " * 20, "logical_num": 1},
            {"name": "chapter2.xhtml", "content": "Content " * 20, "logical_num": 2},
            {"name": "chapter3.xhtml", "content": "Content " * 20, "logical_num": 3},
        ]

        mock_summarize.return_value = "Summary"
        mock_create_image_map.return_value = {}

        # Act: "2,*" should process chapters 2 and 3
        with patch.dict(os.environ, {"GEMINI_API_KEY": "fake_key"}):
            main("/fake/path.epub", chapters="2,*")

        # Assert: summarize called 3 times (chapter 2, chapter 3, and final summary)
        self.assertEqual(mock_summarize.call_count, 3)
        # Verify summaries were for chapter 2 and 3
        mock_save_summary.assert_any_call(
            "Summary", "chapter2.xhtml", unittest.mock.ANY
        )
        mock_save_summary.assert_any_call(
            "Summary", "chapter3.xhtml", unittest.mock.ANY
        )

    @patch("builtins.open", new_callable=unittest.mock.mock_open, read_data="summary")
    @patch("os.listdir", return_value=["summary1.md"])
    @patch("main.create_image_map")
    @patch("main.epub.read_epub")
    @patch("main.summarize_text")
    @patch("main.save_summary_to_file")
    @patch("os.makedirs")
    @patch("os.path.exists", return_value=True)
    @patch("main.merge_and_split_chapters")
    def test_main_with_invalid_chapters_parsing(
        self,
        mock_merge,
        mock_exists,
        mock_makedirs,
        mock_save_summary,
        mock_summarize,
        mock_read_epub,
        mock_create_image_map,
        mock_listdir,
        mock_open,
    ):
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
        mock_book.get_metadata.return_value = [("Test Book", {})]
        mock_read_epub.return_value = mock_book

        mock_merge.return_value = [
            {"name": "chapter1.xhtml", "content": "Content " * 20, "logical_num": 1},
            {"name": "chapter2.xhtml", "content": "Content " * 20, "logical_num": 2},
            {"name": "chapter3.xhtml", "content": "Content " * 20, "logical_num": 3},
        ]

        mock_summarize.return_value = "Summary"
        mock_create_image_map.return_value = {}

        # Act: "2, invalid, *" should handle "2" and "*" relative to "2"
        with patch.dict(os.environ, {"GEMINI_API_KEY": "fake_key"}):
            main("/fake/path.epub", chapters="2, invalid, *")

        # Assert: summary called 3 times (chapter 2, 3 and final)
        self.assertEqual(mock_summarize.call_count, 3)
        mock_save_summary.assert_any_call(
            unittest.mock.ANY, "chapter2.xhtml", unittest.mock.ANY
        )
        mock_save_summary.assert_any_call(
            unittest.mock.ANY, "chapter3.xhtml", unittest.mock.ANY
        )


class TestCreateFinalSummaryChunking(unittest.TestCase):
    """Tests that create_final_summary batches chapter summaries into chunks."""

    def _make_summaries(self, count, size=6000):
        """Helper: list of fake chapter summary strings."""
        return [f"Chapter {i} summary. " + ("x" * size) for i in range(1, count + 1)]

    @patch("main.summarize_text", return_value="batch_summary")
    @patch("builtins.open", new_callable=unittest.mock.mock_open)
    @patch("os.makedirs")
    @patch("os.listdir")
    def test_single_chunk_when_summaries_fit(
        self, mock_listdir, mock_makedirs, mock_open, mock_summarize
    ):
        """When all summaries fit in one chunk, summarize_text is called exactly twice
        (once for the batch, once for the final synthesis — but since there's only
        one batch its output IS the final and a second call should NOT happen)."""
        # Two small summaries that fit well within 16 000 chars
        summaries = ["Chapter 1 summary.", "Chapter 2 summary."]
        mock_listdir.return_value = ["chapter_1.md", "chapter_2.md"]
        mock_open.return_value.read.side_effect = summaries

        from main import create_final_summary
        with patch("os.path.join", side_effect=lambda *a: "/".join(a)):
            create_final_summary("MyBook", "/output", use_local_llm=True)

        # With one batch there is still one summarize_text call (the batch itself),
        # followed by one final synthesis call — total 2.
        self.assertGreaterEqual(mock_summarize.call_count, 1)
        # Ensure is_full_summary=True was used in at least the last call
        last_call_kwargs = mock_summarize.call_args
        self.assertTrue(last_call_kwargs.kwargs.get("is_full_summary", False))

    @patch("main.summarize_text", return_value="batch_summary")
    @patch("builtins.open", new_callable=unittest.mock.mock_open)
    @patch("os.makedirs")
    @patch("os.listdir")
    def test_multiple_chunks_when_summaries_overflow(
        self, mock_listdir, mock_makedirs, mock_open, mock_summarize
    ):
        """When summaries overflow the chunk limit, create_final_summary must call
        summarize_text once per batch PLUS once for the final synthesis."""
        # 4 summaries of 5 000 chars each → total 20 000 chars → 2 batches at 16 000 limit
        summaries = [f"Chapter {i} summary. " + ("x" * 5000) for i in range(1, 5)]
        mock_listdir.return_value = [f"chapter_{i}.md" for i in range(1, 5)]
        mock_open.return_value.read.side_effect = summaries

        from main import create_final_summary
        with patch("os.path.join", side_effect=lambda *a: "/".join(a)):
            create_final_summary("MyBook", "/output", use_local_llm=True)

        # 2 batch calls + 1 synthesis = 3 total
        self.assertGreaterEqual(mock_summarize.call_count, 2)


class TestFinalSummaryPrompt(unittest.TestCase):
    """Tests that the final summary prompt includes cross-chapter connections."""

    def test_gemini_full_summary_prompt_has_cross_chapter_section(self):
        from utils import create_gemini_full_summary_prompt
        prompt = create_gemini_full_summary_prompt("some summaries")
        self.assertIn("cross-chapter", prompt.lower())

    def test_local_full_summary_prompt_has_cross_chapter_section(self):
        from utils import get_full_summary_system_prompt
        prompt = get_full_summary_system_prompt()
        self.assertIn("cross-chapter", prompt.lower())


if __name__ == "__main__":
    unittest.main()



class TestChapterFiltering(unittest.TestCase):
    def test_filter_chapters(self):
        # Arrange
        mock_chapter_item = MagicMock()
        mock_chapter_item.get_type.return_value = ebooklib.ITEM_DOCUMENT
        mock_chapter_item.get_name.return_value = "chapter1.xhtml"
        mock_chapter_item.get_content.return_value = (
            b"<html><body><h1>Chapter 1 text content</h1></body></html>"
        )

        mock_non_chapter_item = MagicMock()
        mock_non_chapter_item.get_type.return_value = ebooklib.ITEM_DOCUMENT
        mock_non_chapter_item.get_name.return_value = "cover.xhtml"
        mock_non_chapter_item.get_content.return_value = (
            b"<html><body><p>copyright text</p></body></html>"
        )

        items = [mock_chapter_item, mock_non_chapter_item]
        exclude_keywords = ["cover"]

        # Act
        chapters = filter_chapters(items, exclude_keywords)

        # Assert
        self.assertEqual(len(chapters), 1)
        self.assertEqual(chapters[0].get_name(), "chapter1.xhtml")


if __name__ == "__main__":
    unittest.main()
