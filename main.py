"""
Main entry point for the EPUB book summarizer CLI tool.
Handles argument parsing, API setup, and summarization workflow.
"""

import os
import sys

import ebooklib
from dotenv import load_dotenv
from ebooklib import epub

from extract_images import create_image_map
from file_utils import get_book_output_folder
from utils import (
    is_non_chapter_content,
    merge_and_split_chapters,
    save_summary_to_file,
    summarize_text,
)

load_dotenv()


def get_chapter_content(item):
    """Extracts text content from an EPUB item (chapter)."""
    if item.get_type() == ebooklib.ITEM_DOCUMENT:
        return item.get_content().decode("utf-8")
    return None


def filter_chapters(items, exclude_keywords):
    """Filters a list of EPUB items, returning only the chapters to be summarized."""
    chapters = []
    for item in items:
        item_name_lower = item.get_name().lower()
        if any(keyword in item_name_lower for keyword in exclude_keywords):
            print(f"Skipping non-chapter section: {item.get_name()}")
            continue

        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            content = item.get_content().decode("utf-8", errors="ignore")
            if is_non_chapter_content(content):
                print(f"Skipping non-chapter content: {item.get_name()}")
                continue
            chapters.append(item)

    return chapters


def _validate_api_keys(use_local_llm, use_openai, gemini_api_key, openai_api_key):
    """Validates that necessary API keys are present based on the selected mode."""
    if use_openai and not openai_api_key:
        print("Error: OPENAI_API_KEY environment variable not set.")
        return False
    if not use_openai and not use_local_llm and not gemini_api_key:
        print(
            "Error: Neither GEMINI_API_KEY nor OPENAI_API_KEY (with --openai) set, and not using local LLM."
        )
        return False
    return True


def _filter_requested_chapters(chapters_data, chapters_arg):
    """Filters chapters_data based on a comma-separated list of chapters or wildcards (e.g. '1,3,*')."""
    if not chapters_arg:
        return chapters_data
        
    print(f"Limiting to specific chapters: {chapters_arg}")
    try:
        requested_numbers = set()
        wildcard_start = None
        last_num = 1

        for part in chapters_arg.split(","):
            part = part.strip()
            if not part:
                continue
            if "*" in part:
                start_str = part.replace("*", "")
                if not start_str:
                    wildcard_start = last_num
                else:
                    try:
                        wildcard_start = int(start_str)
                    except ValueError:
                        print(f"Warning: Skipping invalid wildcard start: {start_str}")
            else:
                try:
                    last_num = int(part)
                    requested_numbers.add(last_num)
                except ValueError:
                    print(f"Warning: Skipping invalid chapter number: {part}")

        filtered_chapters = []
        for chap in chapters_data:
            logical_num = chap["logical_num"]
            if logical_num is not None:
                is_requested = logical_num in requested_numbers
                is_in_range = wildcard_start is not None and logical_num >= wildcard_start
                if is_requested or is_in_range:
                    filtered_chapters.append(chap)
        return filtered_chapters
    except ValueError as err:
        print(f"Error parsing chapters: {chapters_arg}. Error: {err}")
        return []

def main(
    epub_path,
    full_summary_only=False,
    use_local_llm=False,
    use_openai=False,
    chapters=None,
    use_hybrid=False,
):
    """
    Primary workflow orchestrator.
    Resolves args, initializes APIs, splits the book, and runs summaries.
    """
    if not os.path.exists(epub_path):
        print(f"Error: EPUB file not found at {epub_path}")
        return

    book = epub.read_epub(epub_path)

    book_folder_name = get_book_output_folder(book)
    output_base_dir = os.path.join(os.path.dirname(epub_path), book_folder_name)
    os.makedirs(output_base_dir, exist_ok=True)
    print(f"Summaries will be saved in: {output_base_dir}")

    gemini_api_key = os.getenv("GEMINI_API_KEY")
    openai_api_key = os.getenv("OPENAI_API_KEY")

    if not _validate_api_keys(use_local_llm, use_openai, gemini_api_key, openai_api_key):
        return

    if not full_summary_only:
        exclude_keywords = [
            "cover", "titlepage", "title_page", "dedication", "nav",
            "introduction", "acknowledgments", "about_the_author", "ba1",
            "copyright", "credits", "publisher", "preface", "foreword",
            "epilogue", "appendix", "index", "glossary", "bibliography",
            "frontmatter", "footnote", "footnotes", "contents", "toc",
            "notes", "bm",
        ]

        image_map = create_image_map(book)
        chapters_data = merge_and_split_chapters(
            book, exclude_keywords, image_map=image_map, output_dir=output_base_dir
        )

        chapters_data = _filter_requested_chapters(chapters_data, chapters)
        if not chapters_data:
            return

        print(f"Processing EPUB: {epub_path}")

        for chap in chapters_data:
            chapter_name = chap["name"]
            chapter_content = chap["content"]

            if not chapter_content or len(chapter_content.strip()) < 100:
                print(f"Skipping almost empty chapter: {chapter_name}")
                continue

            print(f"Summarizing: {chapter_name}")

            summary = summarize_text(
                text_content=chapter_content,
                use_local_llm=use_local_llm or use_hybrid,
                gemini_api_key=gemini_api_key,
                openai_api_key=openai_api_key if use_openai else None,
            )

            if summary:
                # Append extracted images to the summary
                if chap.get("images"):
                    summary += "\n\n" + "\n\n".join(chap["images"])
                save_summary_to_file(summary, chapter_name, output_base_dir)
            else:
                print(f"Summarization failed for {chapter_name}")

    create_final_summary(
        book_folder_name,
        output_base_dir,
        use_local_llm=use_local_llm and not use_hybrid,
        gemini_api_key=gemini_api_key,
        openai_api_key=openai_api_key if use_openai else None,
    )


def create_final_summary(
    book_folder_name,
    output_base_dir,
    use_local_llm=False,
    gemini_api_key=None,
    openai_api_key=None,
):
    """
    Concatenates all individual chapter summaries and asks the LLM
    to generate a final full-book summary.
    """
    print("\nGenerating final summary...")

    chapter_summaries = []
    for filename in sorted(os.listdir(output_base_dir)):
        if filename.endswith(".md") and not filename.startswith(
            f"summary_{book_folder_name}_Full"
        ):
            with open(
                os.path.join(output_base_dir, filename), "r", encoding="utf-8"
            ) as f:
                chapter_summaries.append(f.read())

    if not chapter_summaries:
        print("No chapter summaries found to generate a final summary.")
        return

    full_text = "\n\n".join(chapter_summaries)

    final_summary = summarize_text(
        text_content=full_text,
        use_local_llm=use_local_llm,
        gemini_api_key=gemini_api_key,
        openai_api_key=openai_api_key,
        is_full_summary=True,
    )

    if final_summary:
        final_summary_filename = f"summary_{book_folder_name}_Full.md"
        final_summary_path = os.path.join(output_base_dir, final_summary_filename)
        with open(final_summary_path, "w", encoding="utf-8") as f:
            f.write(f"# Final Summary: {book_folder_name}\n\n{final_summary}")
        print(f"Final summary saved to {final_summary_path}")
    else:
        print("Failed to generate final summary.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(
            "Usage: python main.py <path_to_epub_file> [--full-summary-only] "
            "[--localllm] [--openai] [--chapters 1,3,5] [--hybrid]"
        )
        sys.exit(1)

    EPUB_FILE = sys.argv[1]
    EPUB_FILE = EPUB_FILE.replace("\\\\", "")
    EPUB_FILE = os.path.normpath(EPUB_FILE)

    # Use constants or rename to avoid shadowing
    CLI_FULL_SUMMARY_ONLY = "--full-summary-only" in sys.argv
    CLI_USE_LOCAL_LLM = "--localllm" in sys.argv
    CLI_USE_OPENAI = "--openai" in sys.argv
    CLI_USE_HYBRID = "--hybrid" in sys.argv

    CLI_CHAPTERS_ARG = None
    for arg_it in range(len(sys.argv)):
        if sys.argv[arg_it] == "--chapters" and arg_it + 1 < len(sys.argv):
            CLI_CHAPTERS_ARG = sys.argv[arg_it + 1]

    if CLI_USE_HYBRID:
        CLI_USE_LOCAL_LLM = True

    main(
        EPUB_FILE,
        full_summary_only=CLI_FULL_SUMMARY_ONLY,
        use_local_llm=CLI_USE_LOCAL_LLM,
        use_openai=CLI_USE_OPENAI,
        chapters=CLI_CHAPTERS_ARG,
        use_hybrid=CLI_USE_HYBRID,
    )
