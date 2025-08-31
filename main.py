import ebooklib
from ebooklib import epub
import google.generativeai as genai
import os
import time
import re
import sys
from dotenv import load_dotenv
from utils import (
    sanitize_filename, 
    get_chapter_identifier, 
    get_book_output_folder, 
    save_summary_to_file, 
    summarize_text_with_gemini,
    create_chapter_summary_prompt,
    create_full_summary_prompt,
    is_non_chapter_content
)
from extract_images import create_image_map, extract_chapter_images_and_context

load_dotenv()

def get_chapter_content(item):
    """Extracts text content from an EPUB item (chapter)."""
    if item.get_type() == ebooklib.ITEM_DOCUMENT:
        return item.get_content().decode('utf-8')
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
            content = item.get_content().decode('utf-8', errors='ignore')
            if is_non_chapter_content(content):
                print(f"Skipping non-chapter content: {item.get_name()}")
                continue
            chapters.append(item)
            
    return chapters



def main(epub_path, full_summary_only=False):
    if not os.path.exists(epub_path):
        print(f"Error: EPUB file not found at {epub_path}")
        return

    book = epub.read_epub(epub_path)

    book_folder_name = get_book_output_folder(book, default_name="summaries_output")
    output_base_dir = os.path.join(os.path.dirname(epub_path), book_folder_name)
    os.makedirs(output_base_dir, exist_ok=True)
    print(f"Summaries will be saved in: {output_base_dir}")

    if not full_summary_only:
        exclude_keywords = [
            "cover", "titlepage", "dedication", "nav", "introduction",
            "acknowledgments", "about_the_author", "ba1", "copyright",
            "credits", "publisher", "preface", "foreword", "epilogue",
            "appendix", "index", "glossary", "bibliography", "frontmatter"
        ]   

        image_map = create_image_map(book)
        chapters_to_summarize = filter_chapters(book.get_items(), exclude_keywords)
        chapter_image_counts = {}

        print(f"Processing EPUB: {epub_path}")

        for item in chapters_to_summarize:
            chapter_content = get_chapter_content(item)
            if not chapter_content or len(chapter_content.strip()) < 100:
                print(f"Skipping almost empty chapter: {item.get_name()}")
                continue

            print(f"Summarizing chapter: {item.get_name()}") 
            print(f"***** {chapter_content}")
            gemini_api_key = os.getenv("GEMINI_API_KEY")
            if not gemini_api_key:
                print("Error: GEMINI_API_KEY environment variable not set.")
                return

            image_context = extract_chapter_images_and_context(item, image_map, output_base_dir, chapter_image_counts)
            
            summary = summarize_text_with_gemini(create_chapter_summary_prompt(chapter_content), gemini_api_key)
            
            if summary:
                # Append image links to the summary
                if image_context:
                    summary += "\n\n### Images\n\n"
                    for img_info in image_context:
                        # Ensure image_path is relative to the summary file
                        relative_image_path = os.path.relpath(img_info["image_path"], os.path.dirname(os.path.join(output_base_dir, get_chapter_identifier(item.get_name()) + ".md")))
                        summary += f"![{img_info['context_text']}]({relative_image_path})\n"

                save_summary_to_file(summary, item.get_name(), output_base_dir)
            else:
                print(f"Summarization failed for {item.get_name()}")

    create_final_summary(book_folder_name, output_base_dir)

def create_final_summary(book_folder_name, output_base_dir):
    print("\nGenerating final summary...")

    chapter_summaries = []
    for filename in os.listdir(output_base_dir):
        if filename.endswith(".md"):
            with open(os.path.join(output_base_dir, filename), "r", encoding="utf-8") as f:
                chapter_summaries.append(f.read())

    if not chapter_summaries:
        print("No chapter summaries found to generate a final summary.")
        return

    full_text = "\n\n".join(chapter_summaries)
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        print("Error: GEMINI_API_KEY environment variable not set.")
        return

    final_summary = summarize_text_with_gemini(create_full_summary_prompt(full_text), gemini_api_key)

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
        print("Usage: python main.py <path_to_epub_file> [--full-summary-only]")
        sys.exit(1)
    
    epub_file = sys.argv[1]
    epub_file = epub_file.replace('\\', '')
    epub_file = os.path.normpath(epub_file)

    full_summary_only = "--full-summary-only" in sys.argv

    main(epub_file, full_summary_only)
