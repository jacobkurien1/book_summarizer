import ebooklib
from ebooklib import epub
import google.generativeai as genai
import os
import time
import re
from dotenv import load_dotenv

load_dotenv()

def sanitize_filename(name):
    # Replace spaces with underscores
    s = name.replace(' ', '_')
    # Remove characters that are not alphanumeric, underscores, or hyphens
    s = re.sub(r'[^a-zA-Z0-9_-]', '', s)
    s = s.strip()
    return s if s else "summaries_output"

def get_chapter_content(item):
    """Extracts text content from an EPUB item (chapter)."""
    if item.get_type() == ebooklib.ITEM_DOCUMENT:
        # This is a simplified extraction. For more robust parsing,
        # you might need to use BeautifulSoup to parse HTML content.
        return item.get_content().decode('utf-8')
    return None

def summarize_text_with_gemini(text, api_key):
    """Summarizes text using the Gemini API."""
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('models/gemini-2.5-flash')

    prompt = f"""Please summarize the following text, highlighting the most important points.
    Text:
    {text}
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Error summarizing text with Gemini API: {e}")
        return None

def main(epub_path):
    if not os.path.exists(epub_path):
        print(f"Error: EPUB file not found at {epub_path}")
        return

    book = epub.read_epub(epub_path)

    # Get book title and sanitize it for folder name
    book_title = book.get_metadata('DC', 'title')[0][0] if book.get_metadata('DC', 'title') else "Unknown Book"
    # Extract primary part of the title for folder name
    if ":" in book_title:
        book_folder_name_raw = book_title.split(":")[0]
    else:
        book_folder_name_raw = book_title
    book_folder_name = sanitize_filename(book_folder_name_raw)
    if not book_folder_name: # Fallback if sanitization results in empty string
        book_folder_name = "summaries_output" # A generic fallback for summaries
    output_base_dir = os.path.join(os.path.dirname(epub_path), book_folder_name)
    os.makedirs(output_base_dir, exist_ok=True)
    print(f"Summaries will be saved in: {output_base_dir}")

    
    

    # Keywords to identify non-chapter sections (case-insensitive)
    exclude_keywords = [
        "cover", "titlepage", "dedication", "nav", "introduction",
        "acknowledgments", "about_the_author", "ba1", "copyright",
        "credits", "publisher", "preface", "foreword", "epilogue",
        "appendix", "index", "glossary", "bibliography"
    ]   

    print(f"Processing EPUB: {epub_path}")

    for item in book.get_items():
        item_name_lower = item.get_name().lower()
        if any(keyword in item_name_lower for keyword in exclude_keywords):
            print(f"Skipping non-chapter section: {item.get_name()}")
            continue

        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            chapter_content = get_chapter_content(item)
            if chapter_content and len(chapter_content.strip()) > 0:
                print(f"Summarizing chapter: {item.get_name()}")
                # You might need to chunk chapter_content if it's too long for the API
                # For now, we'll send the whole chapter.
                gemini_api_key = os.getenv("GEMINI_API_KEY")
                if not gemini_api_key:
                    print("Error: GEMINI_API_KEY environment variable not set.")
                    return

                summary = summarize_text_with_gemini(chapter_content, gemini_api_key)
                time.sleep(5) # Add a delay to respect API rate limits
                if summary:
                    # Simplify item name for filename
                    simplified_name = item.get_name().lower()
                    if "chapter" in simplified_name:
                        match = re.search(r'chapter_(\d+)', simplified_name)
                        if match:
                            filename = f"chapter_{match.group(1)}.md"
                        else:
                            filename = f"chapter_{sanitize_filename(item.get_name())}.md"
                    elif "conclusion" in simplified_name:
                        filename = "conclusion.md"
                    elif "preface" in simplified_name:
                        filename = "preface.md"
                    elif "foreword" in simplified_name:
                        filename = "foreword.md"
                    elif "epilogue" in simplified_name:
                        filename = "epilogue.md"
                    elif "introduction" in simplified_name:
                        filename = "introduction.md"
                    elif "appendix" in simplified_name:
                        filename = "appendix.md"
                    elif "glossary" in simplified_name:
                        filename = "glossary.md"
                    elif "index" in simplified_name:
                        filename = "index.md"
                    else:
                        filename = f"{sanitize_filename(item.get_name())}.md"
                    
                    chapter_output_path = os.path.join(output_base_dir, filename)
                    os.makedirs(os.path.dirname(chapter_output_path), exist_ok=True)
                    with open(chapter_output_path, "w", encoding="utf-8") as f:
                        f.write(f"# Chapter: {item.get_name()}\n\n{summary}\n")
                    print(f"Summary for {item.get_name()} written to {chapter_output_path}")
                else:
                    print(f"Summarization failed for {item.get_name()}")

    

if __name__ == "__main__":
    epub_file = "Workplace Poker_ Are You Playing the Game, or Just Getting Played_ (2016, HarperBusiness) - libgen.li.epub"
    main(epub_file)
