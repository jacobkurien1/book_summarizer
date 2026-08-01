"""
Unit tests for the utility functions and EPUB handlers.
"""

import os
import unittest
from unittest.mock import MagicMock, call, patch
from ebooklib import epub
import utils
from file_utils import get_book_output_folder


class TestSanitizeFilename(unittest.TestCase):
    """Test suite for filename sanitization."""

    def test_basic_sanitization(self):
        """Checks if files are correctly stripped of bad chars."""
        self.assertEqual(
            utils.sanitize_filename("file with spaces.html"), "file_with_spaces"
        )
        self.assertEqual(
            utils.sanitize_filename("another-file-with-dashes.html"),
            "another-file-with-dashes",
        )
        self.assertEqual(
            utils.sanitize_filename("file_with_special!@#$chars.html"),
            "file_with_special_chars",
        )
        self.assertEqual(
            utils.sanitize_filename("My.File.Name.txt"), "My_File_Name"
        )  # This will now be My_File_Name

    def test_leading_trailing_spaces(self):
        """Checks if leading/trailing spaces are removed."""
        self.assertEqual(
            utils.sanitize_filename("  leading and trailing  .txt"),
            "leading_and_trailing",
        )

    def test_multiple_special_chars(self):
        """Checks if multiple special characters are handled."""
        self.assertEqual(
            utils.sanitize_filename("file!!!with@@@many$$$chars.pdf"),
            "file_with_many_chars",
        )

    def test_mixed_case(self):
        """Checks if mixed case is preserved."""
        self.assertEqual(
            utils.sanitize_filename("MiXeD cAsE FiLe.JPG"), "MiXeD_cAsE_FiLe"
        )

    def test_numbers_and_special_chars(self):
        """Checks if numbers and special characters are handled."""
        self.assertEqual(
            utils.sanitize_filename("123_file-name_!@#_456.png"), "123_file-name_456"
        )

    def test_only_special_chars(self):
        """Checks fallback for filenames with only special characters."""
        self.assertEqual(utils.sanitize_filename("!!!@@@###"), "unknown_section")
        self.assertEqual(utils.sanitize_filename(" "), "unknown_section")
        self.assertEqual(utils.sanitize_filename(""), "unknown_section")


class TestChapterIdentifier(unittest.TestCase):
    """Test suite for chapter identification logic."""

    def test_chapter_numbers(self):
        """Checks if chapter numbers are correctly identified."""
        self.assertEqual(
            utils.get_chapter_identifier("text/9781400236015_Chapter13xhtml"),
            "chapter_13",
        )
        self.assertEqual(
            utils.get_chapter_identifier("text/chapter_1.xhtml"), "chapter_1"
        )
        self.assertEqual(utils.get_chapter_identifier("chapter-2.xhtml"), "chapter_2")
        self.assertEqual(utils.get_chapter_identifier("Chapter 5.html"), "chapter_5")
        self.assertEqual(utils.get_chapter_identifier("Chapter01.xhtml"), "chapter_1")
        self.assertEqual(utils.get_chapter_identifier("C-3.html"), "chapter_3")
        self.assertEqual(
            utils.get_chapter_identifier("Part_I.xhtml"), "part_i"
        )  # Corrected assertion

    def test_special_sections(self):
        """Checks if special sections like cover or nav are identified."""
        self.assertEqual(utils.get_chapter_identifier("text/cover.xhtml"), "cover")
        self.assertEqual(
            utils.get_chapter_identifier("text/titlepage.xhtml"), "titlepage"
        )
        self.assertEqual(
            utils.get_chapter_identifier("text/introduction.xhtml"), "introduction"
        )
        self.assertEqual(
            utils.get_chapter_identifier("text/conclusion.xhtml"), "conclusion"
        )
        self.assertEqual(
            utils.get_chapter_identifier("text/acknowledgments.xhtml"),
            "acknowledgments",
        )
        self.assertEqual(utils.get_chapter_identifier("text/nav.xhtml"), "navigation")
        self.assertEqual(
            utils.get_chapter_identifier("frontmatter01.xhtml"), "frontmatter"
        )

    def test_sanitization_fallback_in_identifier(self):
        """Checks fallback behavior for unidentifiable chapter names."""
        self.assertEqual(
            utils.get_chapter_identifier("some_random_file.xhtml"), "file"
        )  # Corrected assertion
        self.assertEqual(
            utils.get_chapter_identifier("another-file-with-dashes.html"),
            "another-file-with-dashes",
        )
        self.assertEqual(
            utils.get_chapter_identifier("file with spaces.html"), "file_with_spaces"
        )
        self.assertEqual(
            utils.get_chapter_identifier("file_with_special!@#$chars.html"),
            "special_chars",
        )  # Corrected assertion
        self.assertEqual(
            utils.get_chapter_identifier("text/bloo_123_some_other_section.xhtml"),
            "some_other_section",
        )  # Corrected assertion

    def test_empty_or_unidentifiable_in_identifier(self):
        """Checks behavior for empty or invalid inputs."""
        self.assertEqual(utils.get_chapter_identifier(""), "unknown_section")
        self.assertEqual(
            utils.get_chapter_identifier("just_some_text"), "text"
        )  # Corrected assertion
        self.assertEqual(utils.get_chapter_identifier(" "), "unknown_section")
        self.assertEqual(utils.get_chapter_identifier("!!!"), "unknown_section")


class TestBookOutputFolder(unittest.TestCase):
    """Test suite for determining output folder names."""

    def test_get_book_output_folder(self):
        """Checks if output folder name is derived from book metadata."""
        class MockEpubBook:
            def get_metadata(self, namespace, name):
                if namespace == "DC" and name == "title":
                    return [("My Awesome Book: A Subtitle", None)]
                return []

        mock_book = MockEpubBook()
        self.assertEqual(get_book_output_folder(mock_book), "My_Awesome_Book")

        class MockEpubBookNoSubtitle:
            def get_metadata(self, namespace, name):
                if namespace == "DC" and name == "title":
                    return [("Simple Title", None)]
                return []

        mock_book_no_subtitle = MockEpubBookNoSubtitle()
        self.assertEqual(
            get_book_output_folder(mock_book_no_subtitle), "Simple_Title"
        )

        class MockEpubBookEmptyTitle:
            def get_metadata(self, namespace, name):
                return []

        mock_book_empty_title = MockEpubBookEmptyTitle()
        self.assertEqual(
            get_book_output_folder(mock_book_empty_title), "processed_book"
        )
        self.assertEqual(
            get_book_output_folder(
                mock_book_empty_title, default_name="my_default"
            ),
            "my_default",
        )


class TestSummarizationWithBackoff(unittest.TestCase):
    """Test suite for summarization with retry logic."""

    @patch("utils.time.sleep")
    @patch("utils.genai.GenerativeModel")
    def test_summarize_text_with_gemini_with_backoff(
        self, mock_generative_model, mock_sleep
    ):
        """Checks if backoff logic works on rate limits."""
        mock_model_instance = mock_generative_model.return_value
        mock_model_instance.generate_content.side_effect = [
            Exception("429 Rate limit exceeded"),
            Exception("429 Rate limit exceeded"),
            MagicMock(text="This is a summary."),
        ]
        api_key = "fake_key"
        prompt = "This is a test prompt."

        summary = utils.summarize_text_with_gemini(prompt, api_key)

        self.assertEqual(summary, "This is a summary.")
        self.assertEqual(mock_sleep.call_count, 2)
        mock_sleep.assert_has_calls([call(60), call(60)])

    def test_is_non_chapter_content_notes(self):
        """Checks if non-chapter content is correctly identified."""
        self.assertTrue(
            utils.is_non_chapter_content(
                "<html><body>Notes<br/>1. Ref...</body></html>"
            )
        )
        self.assertTrue(
            utils.is_non_chapter_content(
                "<html><body>Endnotes<br/>1. Ref...</body></html>"
            )
        )
        self.assertTrue(
            utils.is_non_chapter_content(
                "<html><body>Further Reading<br/>...</body></html>"
            )
        )
        self.assertFalse(
            utils.is_non_chapter_content(
                "<html><body>Chapter 1<br/>Regular content...</body></html>"
            )
        )


if __name__ == "__main__":
    unittest.main()


class TestSaveSummary(unittest.TestCase):
    """Test suite for saving summaries to disk."""

    @patch("os.makedirs")
    @patch("builtins.open", new_callable=unittest.mock.mock_open)
    def test_save_summary_to_file(self, mock_open, mock_makedirs):
        """Checks if summary is saved to the correct file path."""
        summary = "This is a summary."
        item_name = "chapter1.xhtml"
        output_dir = "/fake/output/dir"

        utils.save_summary_to_file(summary, item_name, output_dir)

        mock_makedirs.assert_called_once_with(
            os.path.dirname(os.path.join(output_dir, "chapter_1.md")), exist_ok=True
        )
        mock_open.assert_called_once_with(
            os.path.join(output_dir, "chapter_1.md"), "w", encoding="utf-8"
        )
        mock_open().write.assert_called_once_with(
            f"# Chapter: {item_name}\n\n{summary}\n"
        )


class TestSummarization(unittest.TestCase):
    """Test suite for Gemini summarization."""

    @patch("utils.genai.GenerativeModel")
    def test_summarize_text_with_gemini(self, MockGenerativeModel):
        """Checks if Gemini summarization works."""
        mock_model_instance = MockGenerativeModel.return_value
        mock_model_instance.generate_content.return_value.text = "This is a summary."
        api_key = "fake_key"
        prompt = "This is the text to summarize."

        summary = utils.summarize_text_with_gemini(prompt, api_key)

        self.assertEqual(summary, "This is a summary.")
        MockGenerativeModel.assert_called_with("gemini-2.5-flash")

    @patch("utils.genai.GenerativeModel")
    def test_summarize_text_with_gemini_with_image_context(self, MockGenerativeModel):
        """Checks if Gemini summarization handles image context."""
        mock_model_instance = MockGenerativeModel.return_value
        mock_model_instance.generate_content.return_value.text = (
            "This is a summary with images."
        )
        api_key = "fake_key"
        prompt = "This is the text to summarize."

        summary = utils.summarize_text_with_gemini(prompt, api_key)

        self.assertEqual(summary, "This is a summary with images.")
        mock_model_instance.generate_content.assert_called_once_with(prompt)


class TestSummarizer(unittest.TestCase):
    """Test suite for general summarizer interface."""

    @patch("utils.requests.post")
    def test_summarize_text_with_local_llm(self, mock_post):
        """Checks if local LLM summarization works."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "response": "The capital of France is Paris."
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        system_prompt = "Test system prompt"
        prompt = "What is the capital of France?"

        summary = utils.summarize_text_with_local_llm(system_prompt, prompt)

        self.assertEqual(summary, "The capital of France is Paris.")
        mock_post.assert_called_once()

    @patch("utils.get_local_llm_system_prompt")
    @patch("utils.summarize_text_with_local_llm")
    @patch("utils.summarize_text_with_gemini")
    def test_summarize_text_calls_local_llm(
        self, mock_gemini, mock_local, mock_get_system
    ):
        """Checks if local LLM is called when requested."""
        prompt = "Test prompt"
        mock_get_system.return_value = "System prompt"
        mock_local.return_value = "Local summary"

        summary = utils.summarize_text(
            prompt, use_local_llm=True, gemini_api_key="fake_key"
        )

        mock_local.assert_called_once_with("System prompt", prompt)
        mock_gemini.assert_not_called()
        self.assertEqual(summary, "Local summary")

    @patch("utils.get_full_summary_system_prompt")
    @patch("utils.summarize_text_with_local_llm")
    @patch("utils.summarize_text_with_gemini")
    def test_summarize_text_calls_local_llm_full_summary(
        self, mock_gemini, mock_local, mock_get_system
    ):
        """Checks if local LLM is called with full summary prompt when requested."""
        prompt = "Test prompt"
        mock_get_system.return_value = "System prompt full"
        mock_local.return_value = "Local summary full"

        summary = utils.summarize_text(
            prompt, use_local_llm=True, gemini_api_key="fake_key", is_full_summary=True
        )

        expected_prompt = f"Here are the chapter summaries you are to synthesize:\n{prompt}"
        mock_local.assert_called_once_with("System prompt full", expected_prompt)
        mock_gemini.assert_not_called()
        self.assertEqual(summary, "Local summary full")

    @patch("utils.summarize_text_with_local_llm")
    @patch("utils.summarize_text_with_gemini")
    @patch("utils.create_gemini_chapter_summary_prompt")
    def test_summarize_text_calls_gemini(
        self, mock_create_prompt, mock_gemini, mock_local
    ):
        """Checks if Gemini is called when requested."""
        prompt = "Test prompt"
        full_prompt = "Full Gemini prompt"
        api_key = "fake_key"
        mock_create_prompt.return_value = full_prompt
        mock_gemini.return_value = "Gemini summary"

        summary = utils.summarize_text(
            prompt, use_local_llm=False, gemini_api_key=api_key
        )

        mock_gemini.assert_called_once_with(full_prompt, api_key)
        mock_local.assert_not_called()
        self.assertEqual(summary, "Gemini summary")

    @patch("utils.summarize_text_with_openai")
    @patch("utils.summarize_text_with_gemini")
    def test_summarize_text_calls_openai(self, mock_gemini, mock_openai):
        """Checks if OpenAI is called when requested."""
        prompt = "Test prompt"
        api_key = "openai_key"
        mock_openai.return_value = "OpenAI summary"

        summary = utils.summarize_text(prompt, openai_api_key=api_key)

        mock_openai.assert_called_once_with(prompt, api_key)
        mock_gemini.assert_not_called()
        self.assertEqual(summary, "OpenAI summary")


class TestMergeAndSplit(unittest.TestCase):
    """Test suite for merging and splitting chapters."""

    def test_get_logical_chapter_number(self):
        """Checks if chapter numbers in text are extracted properly."""
        self.assertEqual(utils.get_logical_chapter_number("one"), 1)
        self.assertEqual(utils.get_logical_chapter_number("Chapter Five"), 5)
        self.assertEqual(utils.get_logical_chapter_number("PART 12"), 12)
        self.assertEqual(utils.get_logical_chapter_number("unknown text"), None)

    def test_merge_and_split_chapters(self):
        """Checks if chapters are merged and split correctly."""
        class MockItem:
            def __init__(self, name, content, item_id=None):
                self.name = name
                self.content = content
                self.item_id = item_id or name

            def get_type(self):
                import ebooklib

                return ebooklib.ITEM_DOCUMENT

            def get_name(self):
                return self.name

            def get_content(self):
                return self.content.encode("utf-8")

            def get_id(self):
                return self.item_id

        mock_items = [
            MockItem(
                "page1.html",
                "<html><body>Chapter One<br/>This is content 1</body></html>",
            ),
            MockItem(
                "page2.html",
                "<html><body>Chapter Two<br/>This is content 2</body></html>",
            ),
        ]

        class MockBook:
            def __init__(self, items):
                self.items = items

            def get_items(self):
                return self.items

            @property
            def spine(self):
                return [(item.get_id(), "yes") for item in self.items]

        mock_book = MockBook(mock_items)
        exclude_keywords = []

        # Act
        chapters = utils.merge_and_split_chapters(mock_book, exclude_keywords)

        # Assert
        # Index 0 is Introduction (empty if no text before Chapter One, but our code might pick up something if not careful)
        # In our case, full_text starts with "Chapter One", so splits[0] is empty or whitespace.
        # Let's check the logic: pattern.split(full_text)
        # If full_text starts with a match, splits[0] is empty.

        # The result should have:
        # 1. Introduction (if any text exists before first chapter)
        # 2. Chapter One
        # 3. Chapter Two

        active_chapters = [
            c for c in chapters if c["name"] != "Introduction" or c["content"].strip()
        ]
        self.assertEqual(len(active_chapters), 2)
        self.assertEqual(active_chapters[0]["name"], "Chapter 1")
        self.assertEqual(active_chapters[0]["logical_num"], 1)
        self.assertEqual(active_chapters[1]["name"], "Chapter 2")
        self.assertEqual(active_chapters[1]["logical_num"], 2)

    def test_hybrid_chapter_detection(self):
        """Verifies chapters can be found combining structure and filename cues."""
        # Simulates "The Winner Effect" structure
        class MockItem:
            def __init__(self, name, content, item_id):
                self.name = name
                self.content = content
                self.item_id = item_id

            def get_type(self):
                import ebooklib

                return ebooklib.ITEM_DOCUMENT

            def get_name(self):
                return self.name

            def get_content(self):
                return self.content.encode("utf-8")

            def get_id(self):
                return self.item_id

        mock_items = [
            MockItem(
                "c01.html",
                "<html><body>1<br/>The Mystery of Picasso’s Son<br/>Content 1</body></html>",
                "c1",
            ),
            MockItem(
                "c02.html",
                "<html><body>2<br/>The Puzzle of the Changeling Fish<br/>Content 2</body></html>",
                "c2",
            ),
        ]

        class MockBook:
            def get_items(self):
                return mock_items

            @property
            def spine(self):
                return [("c1", "yes"), ("c2", "yes")]

        mock_book = MockBook()
        exclude_keywords = []

        # Act
        chapters = utils.merge_and_split_chapters(mock_book, exclude_keywords)

        # Assert
        active_chapters = [
            c for c in chapters if c["name"] != "Introduction" or c["content"].strip()
        ]
        self.assertEqual(len(active_chapters), 2)
        # It should detect Chapter 1 and Chapter 2 from the filenames c01.html, c02.html
        self.assertEqual(active_chapters[0]["name"], "Chapter 1")
        self.assertEqual(active_chapters[1]["name"], "Chapter 2")

    def test_duplicate_chapter_merging(self):
        """Verifies duplicate sections belonging to the same chapter merge cleanly."""
        # Simulates a case where both marker and natural header match, or multiple files have headers
        class MockItem:
            def __init__(self, name, content, item_id):
                self.name = name
                self.content = content
                self.item_id = item_id

            def get_type(self):
                import ebooklib

                return ebooklib.ITEM_DOCUMENT

            def get_name(self):
                return self.name

            def get_content(self):
                return self.content.encode("utf-8")

            def get_id(self):
                return self.item_id

        mock_items = [
            MockItem("c01.html", "<html><body>1<br/>Section 1</body></html>", "c1"),
            MockItem("c01_2.html", "<html><body>1<br/>Section 2</body></html>", "c1_2"),
            MockItem(
                "bm02.html", "<html><body>Notes<br/>1. Reference</body></html>", "bm2"
            ),
        ]

        class MockBook:
            def get_items(self):
                return mock_items

            @property
            def spine(self):
                return [("c1", "yes"), ("c1_2", "yes"), ("bm2", "yes")]

        mock_book = MockBook()
        exclude_keywords = ["bm"]

        # Act
        chapters = utils.merge_and_split_chapters(mock_book, exclude_keywords)

        # Assert
        active_chapters = [
            c for c in chapters if c["name"] != "Introduction" or c["content"].strip()
        ]
        self.assertIn("Section 1", active_chapters[0]["content"])
        self.assertIn("Section 2", active_chapters[0]["content"])

    def test_content_theft_by_page_numbers(self):
        """Verifies that standalone numbers (page numbers) do not 'steal' content from the current chapter."""
        # This test demonstrates the core issue: '2' starting a new chapter and stealing subsequent text.
        full_text = """
Chapter 1
This is the legitimate start of Chapter 1.
2
This sentence belongs to Chapter 1, but it follows a standalone page number '2'. 
Currently, the regex treats '2' as the start of 'Chapter 2', stealing this text.
Chapter 2
This is the legitimate start of Chapter 2.
"""
        chapters = utils._split_text_into_chapters(full_text)
        
        # Filter out introduction if empty
        active_chapters = [c for c in chapters if c["name"] != "Introduction" or c["content"].strip()]
        
        # We expect exactly 2 chapters.
        # If the bug exists, we will get 3 chapters (Chapter 1, Chapter 2, Chapter 2).
        self.assertEqual(len(active_chapters), 2, f"Expected 2 chapters, but got {[c['name'] for c in active_chapters]}")
        self.assertEqual(active_chapters[0]["name"], "Chapter 1")
        self.assertIn("belongs to Chapter 1", active_chapters[0]["content"])
        
        self.assertEqual(active_chapters[1]["name"], "Chapter 2")
        self.assertIn("legitimate start of Chapter 2", active_chapters[1]["content"])

    def test_monolithic_file_extraction(self):
        """Verifies that large monolithic files are not skipped due to front-matter keywords."""
        class MockItem:
            def __init__(self, name, content, item_id):
                self.name = name
                self.content = content
                self.item_id = item_id

            def get_type(self):
                import ebooklib
                return ebooklib.ITEM_DOCUMENT

            def get_name(self):
                return self.name

            def get_content(self):
                return self.content.encode("utf-8")

            def get_id(self):
                return self.item_id

        # Create a large content block that starts with a keyword like 'copyright'
        padding = " padding" * 2000  # Make it larger than 10000 chars
        content = f"<html><body>copyright notice at the top<br/>{padding}<br/>Chapter 1<br/>Chapter 1 Content<br/>Chapter 2<br/>Chapter 2 Content</body></html>"
        
        mock_items = [
            MockItem("index_split_000.html", content, "id115"),
        ]

        class MockBook:
            def get_items(self):
                return mock_items

            @property
            def spine(self):
                return [("id115", "yes")]

        mock_book = MockBook()
        # "index" is removed from exclude_keywords in main.py, but we test that the content check doesn't skip it.
        exclude_keywords = []

        chapters = utils.merge_and_split_chapters(mock_book, exclude_keywords)
        active_chapters = [c for c in chapters if c["name"] != "Introduction" or c["content"].strip()]
        
        # We expect 3 chapters (Introduction, Chapter 1, Chapter 2). 
        # Before the fix, the entire file would be skipped because of 'copyright' at the top.
        self.assertEqual(len(active_chapters), 3, f"Expected 3 chapters, got {len(active_chapters)}")
        self.assertEqual(active_chapters[0]["name"], "Introduction")
        self.assertEqual(active_chapters[1]["name"], "Chapter 1")
        self.assertIn("Chapter 1 Content", active_chapters[1]["content"])
        self.assertEqual(active_chapters[2]["name"], "Chapter 2")
        self.assertIn("Chapter 2 Content", active_chapters[2]["content"])


class TestCalibreSplitFilesHandling(unittest.TestCase):
    """
    Regression tests for EPUBs produced by Calibre that use 'index_split_XXX.html'
    filenames.  These files contain 'index' in the name but are NOT back-matter.
    The two bugs being guarded against:

      1. get_chapter_identifier() maps 'index_split_005.html' -> 'index' because
         'index' is a substring of the filename, causing those items to be skipped
         entirely during spine processing.

      2. get_logical_chapter_number() runs directly on raw HTML, matching the '1'
         inside 'xml version="1.0"' or href attributes, so every document becomes
         'chapter_1' and they are all merged into one giant undivided section.
    """

    # ------------------------------------------------------------------ helpers

    # Raw HTML that mirrors a real Calibre-produced chapter file.
    # The '1' in the XML declaration and namespace URL must NOT be used as the
    # chapter number.  The real chapter number lives in the first visible line
    # of body text: "1 It Takes More Than Performance".
    CHAPTER_1_HTML = (
        "<?xml version='1.0' encoding='utf-8'?>"
        "<!DOCTYPE html>"
        '<html xmlns="http://www.w3.org/1999/xhtml">'
        "<head/><body>"
        '<p id="filepos40506"><span>1</span></p>'
        "<p>It Takes More Than Performance</p>"
        "<p>IN 2004, the Miami-Dade County school board hired Rudy Crew.</p>"
        "</body></html>"
    )

    CHAPTER_2_HTML = (
        "<?xml version='1.0' encoding='utf-8'?>"
        "<!DOCTYPE html>"
        '<html xmlns="http://www.w3.org/1999/xhtml">'
        "<head/><body>"
        '<p id="filepos50000"><span>2</span></p>'
        "<p>The Personal Qualities That Bring Influence</p>"
        "<p>RON MEYER, the president and COO of Universal Studios, is a powerful figure.</p>"
        "</body></html>"
    )

    SEARCHABLE_TERMS_HTML = (
        "<?xml version='1.0' encoding='utf-8'?>"
        "<!DOCTYPE html>"
        '<html xmlns="http://www.w3.org/1999/xhtml">'
        "<head/><body>"
        "<p>SEARCHABLE TERMS</p>"
        "<p>The pagination of this electronic edition does not match the print edition.</p>"
        "</body></html>"
    )

    TITLE_PAGE_HTML = (
        "<?xml version='1.0' encoding='utf-8'?>"
        "<!DOCTYPE html>"
        '<html xmlns="http://www.w3.org/1999/xhtml">'
        "<head/><body>"
        "<p>Power</p>"
        "<p>Why Some People Have It—and Others Don't</p>"
        "<p>Jeffrey Pfeffer</p>"
        "</body></html>"
    )

    # ------------------------------------------------------------------ tests

    def test_index_split_not_mapped_to_index_identifier(self):
        """
        'index_split_XXX.html' filenames must NOT be mapped to the 'index'
        identifier just because the string 'index' appears in the name.
        Bug: the old code did `if key in simplified_name` which matched.
        """
        # Without content hint, the fallback cleans the name
        result = utils.get_chapter_identifier("index_split_005.html")
        self.assertNotEqual(
            result,
            "index",
            "index_split_005.html must not be classified as back-matter 'index'.",
        )

    def test_chapter_identifier_reads_number_from_html_not_xml_declaration(self):
        """
        When content is provided, get_chapter_identifier must strip the HTML
        and find the visible chapter number, not the '1' in xml version="1.0".
        Bug: the old code ran regex on raw HTML and always returned chapter_1.
        """
        result = utils.get_chapter_identifier("index_split_005.html", self.CHAPTER_1_HTML)
        self.assertEqual(
            result,
            "chapter_1",
            "index_split_005.html with Chapter 1 content should yield 'chapter_1'.",
        )

        result2 = utils.get_chapter_identifier("index_split_006.html", self.CHAPTER_2_HTML)
        self.assertEqual(
            result2,
            "chapter_2",
            "index_split_006.html with Chapter 2 content should yield 'chapter_2'.",
        )

    def test_searchable_terms_identified_as_index(self):
        """
        A file starting with 'SEARCHABLE TERMS' should be identified as back-matter
        index, not as a chapter.
        """
        result = utils.get_chapter_identifier(
            "index_split_019.html", self.SEARCHABLE_TERMS_HTML
        )
        self.assertEqual(
            result,
            "index",
            "A 'SEARCHABLE TERMS' page must be classified as 'index' back-matter.",
        )

    def test_get_logical_chapter_number_ignores_xml_declaration(self):
        """
        get_logical_chapter_number must NOT match the '1' inside the XML
        declaration or XHTML namespace URL when raw HTML is passed.
        It should return the visible chapter number from the body text.
        """
        # Chapter 2 HTML — the very first digit in raw text is '1' (xml version)
        # but the visible first line is '2'.
        result = utils.get_logical_chapter_number(self.CHAPTER_2_HTML)
        self.assertEqual(
            result,
            2,
            "get_logical_chapter_number must return 2 for Chapter 2 HTML, "
            "not 1 from the XML declaration.",
        )

    def test_calibre_spine_produces_correct_chapters(self):
        """
        End-to-end: a mock book with Calibre-style 'index_split_XXX.html'
        files must be split into individual chapters, not collapsed into one.
        """

        class MockItem:
            def __init__(self, name, content, item_id):
                self.name = name
                self.content = content
                self.item_id = item_id

            def get_type(self):
                import ebooklib
                return ebooklib.ITEM_DOCUMENT

            def get_name(self):
                return self.name

            def get_content(self):
                return self.content.encode("utf-8")

            def get_id(self):
                return self.item_id

        mock_items = [
            MockItem("titlepage.xhtml",     self.TITLE_PAGE_HTML,       "tp"),
            MockItem("index_split_005.html", self.CHAPTER_1_HTML,        "s5"),
            MockItem("index_split_006.html", self.CHAPTER_2_HTML,        "s6"),
            MockItem("index_split_019.html", self.SEARCHABLE_TERMS_HTML, "s19"),
        ]

        class MockBook:
            def get_items(self):
                return mock_items

            @property
            def spine(self):
                return [("tp", "yes"), ("s5", "yes"), ("s6", "yes"), ("s19", "yes")]

        mock_book = MockBook()
        chapters = utils.merge_and_split_chapters(mock_book, exclude_keywords=[])
        active = [c for c in chapters if c["content"].strip()]

        names = [c["name"] for c in active]
        self.assertIn(
            "Chapter 1",
            names,
            f"Expected 'Chapter 1' in chapters, got: {names}",
        )
        self.assertIn(
            "Chapter 2",
            names,
            f"Expected 'Chapter 2' in chapters, got: {names}",
        )
        # Must produce at least 2 distinct chapters, not a single merged blob
        chapter_entries = [c for c in active if c["name"].startswith("Chapter")]
        self.assertGreaterEqual(
            len(chapter_entries),
            2,
            f"Expected at least 2 chapters from Calibre split files, got: {names}",
        )

    def test_endnote_line_not_treated_as_chapter(self):
        """
        A line like '6. Patricia Robinson and Norihiko...' (endnote citation)
        must NOT be treated as chapter_6.
        Endnotes have pattern: digit + period + space + author text.
        """
        result = utils.get_logical_chapter_number(
            "6. Patricia Robinson and Norihiko Shimizu, \"Japanese Corporate Restructuring\""
        )
        self.assertIsNone(result, "Endnote citation '6. Author...' must not yield chapter 6")

    def test_endnote_ibid_not_treated_as_chapter(self):
        result = utils.get_logical_chapter_number("12. Ibid., 35.")
        self.assertIsNone(result, "Endnote 'N. Ibid.' must not yield a chapter number")

    def test_standalone_number_is_chapter(self):
        """A line that is just a number IS a valid chapter identifier."""
        result = utils.get_logical_chapter_number("6")
        self.assertEqual(result, 6)

    def test_number_then_title_is_chapter(self):
        """'6\nIt Takes More Than Performance' — number on its own line before title."""
        result = utils.get_logical_chapter_number("6\nIt Takes More Than Performance")
        self.assertEqual(result, 6)

    def test_endnote_spine_items_not_counted_as_chapters(self):
        """
        Tiny endnote files (starting with 'N. Author...') must not become chapter_N.
        get_chapter_identifier must return a non-chapter identifier for them.
        """
        ENDNOTE_HTML = (
            "<?xml version='1.0' encoding='utf-8'?>"
            '<html xmlns="http://www.w3.org/1999/xhtml"><head/><body>'
            '<p>6. Patricia Robinson and Norihiko Shimizu, '
            '"Japanese Corporate Restructuring: Capital-Market Pressures '
            'and the Transform..."</p>'
            '</body></html>'
        )
        result = utils.get_chapter_identifier("index_split_232.html", ENDNOTE_HTML)
        self.assertFalse(
            str(result).startswith("chapter_"),
            f"Endnote file should not be classified as '{result}'"
        )


class TestMonolithicTOCSplittingAndChunking(unittest.TestCase):
    """Unit tests for monolithic EPUB handling, TOC extraction, fuzzy matching, and chunking."""

    def test_ocr_normalize(self):
        self.assertEqual(utils.ocr_normalize("The Clay Tablets"), "theclaltablets")
        self.assertEqual(utils.ocr_normalize("The CI ay Tablets"), "theclaltablets")

    def test_fuzzy_match(self):
        self.assertTrue(utils.fuzzy_match("The Clay Tablets From Babylon", "The CI ay Tablets From BabylonSt. Swithin'sCollege"))
        self.assertTrue(utils.fuzzy_match("About the author", "About the author"))
        self.assertFalse(utils.fuzzy_match("Foreword", "This is some random text in the book body"))

    def test_extract_toc_titles(self):
        lines = [
            "TABLE OF CONTENTS",
            "About the author 3",
            "Foreword 5",
            "An Historical Sketch of Babylon 6",
            "The Man Who Desired Gold 9",
            "This is just normal body text.",
        ]
        toc = utils.extract_toc_titles(lines, max_search=10)
        titles = [t[1] for t in toc]
        self.assertEqual(titles, ["About the author", "Foreword", "An Historical Sketch of Babylon", "The Man Who Desired Gold"])

    def test_chunk_text(self):
        text = "Paragraph 1\nParagraph 2\nParagraph 3"
        chunks = utils.chunk_text(text, max_chars=15)
        self.assertEqual(chunks, ["Paragraph 1", "Paragraph 2", "Paragraph 3"])

        chunks_larger = utils.chunk_text(text, max_chars=25)
        self.assertEqual(chunks_larger, ["Paragraph 1\nParagraph 2", "Paragraph 3"])

    def test_split_text_into_chapters_with_toc_and_chunking(self):
        full_text = (
            "TABLE OF CONTENTS\n"
            "First Story 10\n"
            "Second Story 20\n"
            "Third Story 30\n"
            "Fourth Story 40\n"
            "Introduction\n"
            "This is the introduction text.\n"
            "First Story\n"
            "This is content for the first story. It is long.\n"
            "Second Story\n"
            "This is content for the second story. It is also long.\n"
            "Third Story\n"
            "Content 3\n"
            "Fourth Story\n"
            "Content 4"
        )
        chapters = utils._split_text_into_chapters(full_text)
        names = [c["name"] for c in chapters]
        self.assertIn("Chapter 1: First Story", names)
        self.assertIn("Chapter 2: Second Story", names)

    def test_sanitize_filename_preserves_dotted_roman_numerals(self):
        from file_utils import sanitize_filename
        self.assertEqual(sanitize_filename("Tablet No. I"), "Tablet_No_I")
        self.assertEqual(sanitize_filename("chapter_1.xhtml"), "chapter_1")
        self.assertEqual(sanitize_filename("Section 1.2"), "Section_1_2")
        self.assertEqual(sanitize_filename("Chapter 3 - Part 1"), "Chapter_3_Part_1")
        self.assertEqual(utils.get_chapter_identifier("Chapter 3 - Part 1"), "chapter_3_part_1")
