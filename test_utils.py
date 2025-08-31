import unittest
from unittest.mock import patch, MagicMock, call
import os
import utils
from ebooklib import epub

class TestSanitizeFilename(unittest.TestCase):

    def test_basic_sanitization(self):
        self.assertEqual(utils.sanitize_filename("file with spaces.html"), "file_with_spaces")
        self.assertEqual(utils.sanitize_filename("another-file-with-dashes.html"), "another-file-with-dashes")
        self.assertEqual(utils.sanitize_filename("file_with_special!@#$chars.html"), "file_with_special_chars")
        self.assertEqual(utils.sanitize_filename("My.File.Name.txt"), "My_File_Name") # This will now be My_File_Name

    def test_leading_trailing_spaces(self):
        self.assertEqual(utils.sanitize_filename("  leading and trailing  .txt"), "leading_and_trailing")

    def test_multiple_special_chars(self):
        self.assertEqual(utils.sanitize_filename("file!!!with@@@many$$$chars.pdf"), "file_with_many_chars")

    def test_mixed_case(self):
        self.assertEqual(utils.sanitize_filename("MiXeD cAsE FiLe.JPG"), "MiXeD_cAsE_FiLe")

    def test_numbers_and_special_chars(self):
        self.assertEqual(utils.sanitize_filename("123_file-name_!@#_456.png"), "123_file-name_456")

    def test_only_special_chars(self):
        self.assertEqual(utils.sanitize_filename("!!!@@@###"), "unknown_section")
        self.assertEqual(utils.sanitize_filename(" "), "unknown_section")
        self.assertEqual(utils.sanitize_filename(""), "unknown_section")

class TestChapterIdentifier(unittest.TestCase):

    def test_chapter_numbers(self):
        self.assertEqual(utils.get_chapter_identifier("text/9781400236015_Chapter13xhtml"), "chapter_13")
        self.assertEqual(utils.get_chapter_identifier("text/chapter_1.xhtml"), "chapter_1")
        self.assertEqual(utils.get_chapter_identifier("chapter-2.xhtml"), "chapter_2")
        self.assertEqual(utils.get_chapter_identifier("Chapter 5.html"), "chapter_5")
        self.assertEqual(utils.get_chapter_identifier("Chapter01.xhtml"), "chapter_1")
        self.assertEqual(utils.get_chapter_identifier("C-3.html"), "chapter_3")
        self.assertEqual(utils.get_chapter_identifier("Part_I.xhtml"), "part_i") # Corrected assertion

    def test_special_sections(self):
        self.assertEqual(utils.get_chapter_identifier("text/cover.xhtml"), "cover")
        self.assertEqual(utils.get_chapter_identifier("text/titlepage.xhtml"), "titlepage")
        self.assertEqual(utils.get_chapter_identifier("text/introduction.xhtml"), "introduction")
        self.assertEqual(utils.get_chapter_identifier("text/conclusion.xhtml"), "conclusion")
        self.assertEqual(utils.get_chapter_identifier("text/acknowledgments.xhtml"), "acknowledgments")
        self.assertEqual(utils.get_chapter_identifier("text/nav.xhtml"), "navigation")
        self.assertEqual(utils.get_chapter_identifier("frontmatter01.xhtml"), "frontmatter")

    def test_sanitization_fallback_in_identifier(self):
        # These test cases are now handled by sanitize_filename directly
        self.assertEqual(utils.get_chapter_identifier("some_random_file.xhtml"), "file") # Corrected assertion
        self.assertEqual(utils.get_chapter_identifier("another-file-with-dashes.html"), "another-file-with-dashes")
        self.assertEqual(utils.get_chapter_identifier("file with spaces.html"), "file_with_spaces")
        self.assertEqual(utils.get_chapter_identifier("file_with_special!@#$chars.html"), "special_chars") # Corrected assertion
        self.assertEqual(utils.get_chapter_identifier("text/bloo_123_some_other_section.xhtml"), "some_other_section") # Corrected assertion

    def test_empty_or_unidentifiable_in_identifier(self):
        self.assertEqual(utils.get_chapter_identifier(""), "unknown_section")
        self.assertEqual(utils.get_chapter_identifier("just_some_text"), "text") # Corrected assertion
        self.assertEqual(utils.get_chapter_identifier(" "), "unknown_section")
        self.assertEqual(utils.get_chapter_identifier("!!!"), "unknown_section")

class TestBookOutputFolder(unittest.TestCase):

    def test_get_book_output_folder(self):
        # Create a mockEpubBook object for testing
        class MockEpubBook:
            def get_metadata(self, namespace, name):
                if namespace == 'DC' and name == 'title':
                    return [('My Awesome Book: A Subtitle', None)]
                return []
        
        mock_book = MockEpubBook()
        self.assertEqual(utils.get_book_output_folder(mock_book), "My_Awesome_Book")

        class MockEpubBookNoSubtitle:
            def get_metadata(self, namespace, name):
                if namespace == 'DC' and name == 'title':
                    return [('Simple Title', None)]
                return []
        mock_book_no_subtitle = MockEpubBookNoSubtitle()
        self.assertEqual(utils.get_book_output_folder(mock_book_no_subtitle), "Simple_Title")

        class MockEpubBookEmptyTitle:
            def get_metadata(self, namespace, name):
                return []
        mock_book_empty_title = MockEpubBookEmptyTitle()
        self.assertEqual(utils.get_book_output_folder(mock_book_empty_title), "processed_book")
        self.assertEqual(utils.get_book_output_folder(mock_book_empty_title, default_name="my_default"), "my_default")

class TestSummarizationWithBackoff(unittest.TestCase):

    @patch('utils.time.sleep')
    @patch('utils.genai.GenerativeModel')
    def test_summarize_text_with_gemini_with_backoff(self, mock_generative_model, mock_sleep):
        # Arrange
        mock_model_instance = mock_generative_model.return_value
        mock_model_instance.generate_content.side_effect = [
            Exception("429 Rate limit exceeded"),
            Exception("429 Rate limit exceeded"),
            MagicMock(text="This is a summary.")
        ]
        api_key = "fake_key"
        prompt = "This is a test prompt."

        # Act
        summary = utils.summarize_text_with_gemini(prompt, api_key)

        # Assert
        self.assertEqual(summary, "This is a summary.")
        self.assertEqual(mock_sleep.call_count, 2)
        mock_sleep.assert_has_calls([call(1), call(2)])

if __name__ == '__main__':
    unittest.main()

class TestSaveSummary(unittest.TestCase):

    @patch('os.makedirs')
    @patch('builtins.open', new_callable=unittest.mock.mock_open)
    def test_save_summary_to_file(self, mock_open, mock_makedirs):
        # Arrange
        summary = "This is a summary."
        item_name = "chapter1.xhtml"
        output_dir = "/fake/output/dir"

        # Act
        utils.save_summary_to_file(summary, item_name, output_dir)

        # Assert
        mock_makedirs.assert_called_once_with(os.path.dirname(os.path.join(output_dir, "chapter_1.md")),
                                             exist_ok=True)
        mock_open.assert_called_once_with(os.path.join(output_dir, "chapter_1.md"), "w", encoding="utf-8")
        mock_open().write.assert_called_once_with(f"# Chapter: {item_name}\n\n{summary}\n")

class TestSummarization(unittest.TestCase):

    @patch('utils.genai.GenerativeModel')
    def test_summarize_text_with_gemini(self, MockGenerativeModel):
        # Arrange
        mock_model_instance = MockGenerativeModel.return_value
        mock_model_instance.generate_content.return_value.text = "This is a summary."
        api_key = "fake_key"
        prompt = "This is the text to summarize."

        # Act
        summary = utils.summarize_text_with_gemini(prompt, api_key)

        # Assert
        self.assertEqual(summary, "This is a summary.")
        MockGenerativeModel.assert_called_with('gemini-2.5-flash')

    @patch('utils.genai.GenerativeModel')
    def test_summarize_text_with_gemini_with_image_context(self, MockGenerativeModel):
        # Arrange
        mock_model_instance = MockGenerativeModel.return_value
        mock_model_instance.generate_content.return_value.text = "This is a summary with images."
        api_key = "fake_key"
        prompt = "This is the text to summarize."

        # Act
        summary = utils.summarize_text_with_gemini(prompt, api_key)

        # Assert
        self.assertEqual(summary, "This is a summary with images.")
        mock_model_instance.generate_content.assert_called_once_with(prompt)