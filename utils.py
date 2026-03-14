import re
import os
import time
from ebooklib import epub
import google.generativeai as genai
import requests
import json
import openai
from openai import OpenAI

def sanitize_filename(name):
    # Separate base and extension first from the original name
    base, ext = os.path.splitext(name)
    
    # Sanitize the base name
    s = base.replace(' ', '_')
    s = re.sub(r'[^a-zA-Z0-9_-]', '_', s) # Replace non-alphanumeric (except _ and -) with single underscores
    s = re.sub(r'_+', '_', s) # Replace multiple underscores with single
    s = s.strip('_') # Remove leading/trailing underscores
    
    return s if s else "unknown_section"

def get_book_output_folder(book: epub.EpubBook, default_name: str = "processed_book") -> str:
    book_title_metadata = book.get_metadata('DC', 'title')
    if not book_title_metadata:
        return default_name # Use default if no title metadata is found

    book_title = book_title_metadata[0][0]
    # Extract primary part of the title for folder name
    if ":" in book_title:
        book_folder_name_raw = book_title.split(":")[0]
    else:
        book_folder_name_raw = book_title
    book_folder_name = sanitize_filename(book_folder_name_raw) # sanitize_filename no longer removes extensions
    return book_folder_name if book_folder_name else default_name

def get_chapter_identifier(chapter_name_raw):
    simplified_name = chapter_name_raw.lower()
    # Aggressively clean the name for better identifier matching
    simplified_name = simplified_name.replace('text/', '')
    simplified_name = simplified_name.replace('xhtml/', '')

    # Remove file extensions at the very beginning
    base, ext = os.path.splitext(simplified_name)
    if ext.lower() in ('.md', '.html', '.xhtml', '.jpg', '.jpeg', '.png', '.gif', '.svg', '.bmp'):
        simplified_name = base

    # More flexible chapter number extraction
    match = re.search(r'(?:chapter|c|part)[_-]?(\d+)', simplified_name)
    if match:
        return f"chapter_{int(match.group(1))}"

    # Handle Appendix
    if "appendix" in simplified_name:
        match = re.search(r'appendix[_-]?([a-z]|\d+)', simplified_name)
        if match:
            return f"appendix_{match.group(1)}"
        else:
            return "appendix"

    # Map common EPUB item names to cleaner identifiers
    name_to_identifier_map = {
        "cover": "cover",
        "titlepage": "titlepage",
        "dedication": "dedication",
        "nav": "navigation",
        "introduction": "introduction",
        "acknowledgments": "acknowledgments",
        "about_the_author": "about_the_author",
        "ba1": "back_matter_1",
        "copyright": "copyright",
        "credits": "credits",
        "publisher": "publisher_info",
        "preface": "preface",
        "foreword": "foreword",
        "epilogue": "epilogue",
        "index": "index",
        "glossary": "glossary",
        "bibliography": "bibliography",
        "conclusion": "conclusion",
        "frontmatter": "frontmatter"
    }

    for key, value in name_to_identifier_map.items():
        if key in simplified_name:
            return value

    # Fallback for other unidentifiable document items
    # Remove common prefixes and suffixes
    simplified_name = re.sub(r'^[a-z]+_.*?_', '', simplified_name) # a generic prefix remover
    simplified_name = re.sub(r'_epub3_.*?_r\d+', '', simplified_name) # Remove _epub3_..._rX patterns
    simplified_name = re.sub(r'_r\d+', '', simplified_name) # Remove _rX patterns

    return sanitize_filename(simplified_name) if simplified_name else "unknown_section"

def get_logical_chapter_number(chapter_name_raw):
    """Extracts the logical chapter number from the filename/identifier."""
    simplified_name = chapter_name_raw.lower()
    simplified_name = simplified_name.replace('text/', '').replace('xhtml/', '')
    match = re.search(r'(?:chapter|c|part)[_-]?(\d+)', simplified_name)
    if match:
        return int(match.group(1))
    return None

def is_non_chapter_content(content: str) -> bool:
    """Checks if the content is a non-chapter section."""
    non_chapter_keywords = [
        "dedication", "copyright", "acknowledgments", "title page", 
        "table of contents", "epigraph", "author's note", "publisher", "isbn",
        "frontmatter", "halftitle", "bibliography", "references",
        "footnote", "footnotes"
    ]
    
    # Check for keywords in the first 1024 characters of the content
    content_lower = content[:1024].lower()
    for keyword in non_chapter_keywords:
        if keyword in content_lower:
            return True
            
    return False

def get_chapter_title_from_content(content):
    """Extracts the chapter title from the chapter's content."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(content, 'html.parser')
    
    # Try to find the title in common heading tags
    for tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
        heading = soup.find(tag)
        if heading and heading.get_text(strip=True):
            return heading.get_text(strip=True)
    
    # Fallback to the first few lines of text if no heading is found
    lines = [line.strip() for line in soup.get_text().splitlines() if line.strip()]
    if lines:
        return lines[0]
    
    return "Untitled Chapter"

def save_summary_to_file(summary, item_name, output_dir):
    """Saves the summary to a Markdown file."""
    chapter_identifier = get_chapter_identifier(item_name)
    filename = f"{chapter_identifier}.md"
    chapter_output_path = os.path.join(output_dir, filename)
    os.makedirs(os.path.dirname(chapter_output_path), exist_ok=True)
    with open(chapter_output_path, "w", encoding="utf-8") as f:
        f.write(f"# Chapter: {item_name}\n\n{summary}\n")
    print(f"Summary for {item_name} written to {chapter_output_path}")

def get_chapter_summary_system_prompt() -> str: 
    return f"""## Role & Goal
    You are a Knowledge Distiller. Your mission is to distill the provided chapter summaries for a book into a concise, high-level overview. Your output should be a compact knowledge outline, not a detailed study guide.
    ---

    ## Formatting Instructions
    * End result should be in markdown format only.
    * Use a hierarchical structure with markdown headings (##, ###, etc.) to organize information.
    * Use nested bullet points extensively to present key details.
    * Use bolding to emphasize key terms and concepts.
    * Do not add any information outside of the provided text.

    ---

    ## Output Structure
    * Start with the book's central argument or "big idea" in a few sentences.
    * Organize the remaining content into logical sections. Use concise headings for each section.
    * Present only the most critical concepts and core advice. Keep bullet points to a minimum, focusing on the main idea of each chapter or section.

    ---
    """

def create_gemini_chapter_summary_prompt(text: str) -> str:
    return f""" {get_chapter_summary_system_prompt()}

    ## Input Summaries
    {text}
    ---
    """

def create_gemini_full_summary_prompt(text: str) -> str:
    return f"""## Role & Goal
    You are an expert analyst and synthesizer of non-fiction book. Your input is a series of my chapter summaries. Your goal is to synthesize these into a definitive, high-level analysis that captures the book's core framework, practical applications, and overall intellectual contribution. The final output should be a strategic document for a busy leader who needs to grasp the essence of the book quickly.
    ## Output Structure

    ### 1. Executive Summary
    Begin with a single, concise paragraph that captures the book's central purpose, main argument, and overall conclusion. This should serve as a high-level introduction that answers "What is this book about and why is it important?"

    ### 2. Key Themes / Sections
    Following the summary, identify the primary themes, arguments, or sections of the book. For each one, create a dedicated section with the following precise structure:

    #### [Descriptive Title]
    Create a clear and descriptive title for the theme or section. This should reflect the core content (e.g., "The Rise of the Roman Republic," "Principles of Effective Marketing," "The Discovery of Penicillin").

    **[Core Idea]**
    Immediately after the title, provide a single, bolded sentence that explains the main point or finding of this section.

    * **Key Points & Details:**
        * Under this sub-heading, create a bulleted list.
        * Extract the most important supporting information for this theme. Depending on the book's genre, this could include:
            * Key facts, statistics, or dates.
            * Core arguments or evidence presented.
            * Important examples, case studies, or anecdotes.
            * Actionable steps or methodologies described.
            * Key people, events, or discoveries mentioned.
        * Use sub-bullets to elaborate on a point where necessary.

    Create a separate section for each major theme or part of the book you identify in the source text.
    ## Input Summaries
    Here are the chapter summaries you are to synthesize:
    {text}
    """

def get_local_llm_system_prompt() -> str:
    return get_chapter_summary_system_prompt()

def summarize_text_with_gemini(prompt, api_key):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash')
    initial_delay = 10
    max_retries = 5
    delay = initial_delay
    for i in range(max_retries):
        try:
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            if "429" in str(e):
                print(f"Rate limit exceeded. Retrying in {delay} seconds...")
                time.sleep(delay)
                delay *= 2
            else:
                print(f"Error summarizing text with Gemini API: {e}")
                return None
    print("Failed to summarize text after multiple retries.")
    return None

def summarize_text_with_local_llm(system_prompt, prompt):
    url = "http://localhost:11434/api/generate"
    headers = {"Content-Type": "application/json"}
    data = {
        "model": "deepseek-r1",
        "system": system_prompt,
        "prompt": prompt,
        "stream": False
    }
    try:
        response = requests.post(url, headers=headers, json=data, timeout=120)
        response.raise_for_status()
        response_json = response.json()
        return response_json.get("response", "").strip()
    except requests.exceptions.RequestException as e:
        print(f"Error making API call to local LLM: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON response from local LLM: {e}")
        return None

def summarize_text_with_openai(prompt, api_key):
    client = OpenAI(api_key=api_key)
    initial_delay = 5
    max_retries = 5
    delay = initial_delay
    
    for i in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": get_chapter_summary_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=2048
            )
            return response.choices[0].message.content
        except Exception as e:
            if "rate_limit" in str(e).lower() or "429" in str(e):
                print(f"OpenAI Rate limit exceeded. Retrying in {delay} seconds...")
                time.sleep(delay)
                delay *= 2
            else:
                print(f"Error summarizing text with OpenAI API: {e}")
                return None
    print("Failed to summarize text with OpenAI after multiple retries.")
    return None

def summarize_text(text_content: str, use_local_llm: bool = False, gemini_api_key: str = None, openai_api_key: str = None, is_full_summary: bool = False):
    if use_local_llm:
        print("Using local LLM for summarization...")
        system_prompt = get_local_llm_system_prompt()
        return summarize_text_with_local_llm(system_prompt, text_content)
    elif openai_api_key:
        print("Using OpenAI API for summarization...")
        if is_full_summary:
            # We don't have create_openai_full_summary_prompt yet, but prompts are mostly text.
            # Reusing the existing prompt logic.
            prompt = create_gemini_full_summary_prompt(text_content)
        else:
            prompt = text_content # System prompt is already handled in summarize_text_with_openai
        return summarize_text_with_openai(prompt, openai_api_key)
    else:
        print("Using Gemini API for summarization...")
        if not gemini_api_key:
            print("Error: Neither OPENAI_API_KEY nor GEMINI_API_KEY provided.")
            return None
        if is_full_summary:
            prompt = create_gemini_full_summary_prompt(text_content)
        else:
            prompt = create_gemini_chapter_summary_prompt(text_content)
        return summarize_text_with_gemini(prompt, gemini_api_key)
