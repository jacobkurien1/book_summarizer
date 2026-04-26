import re
import os
import time
from ebooklib import epub
import google.generativeai as genai
import requests
import json
import openai
import ebooklib
from extract_images import extract_and_mark_images, parse_markdown_images_from_text
from bs4 import BeautifulSoup
from openai import OpenAI

from urllib.parse import unquote
import html

def unescape(text):
    return html.unescape(text)

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

def get_chapter_identifier(chapter_name_raw, item_content=None):
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

    # NEW: Content fallback
    if item_content:
        # Pass only content to extract logical number
        num = get_logical_chapter_number(item_content)
        if num is not None:
            return f"chapter_{num}"

    # Fallback for other unidentifiable document items
    # Remove common prefixes and suffixes
    simplified_name = re.sub(r'^[a-z]+_.*?_', '', simplified_name) # a generic prefix remover
    simplified_name = re.sub(r'_epub3_.*?_r\d+', '', simplified_name) # Remove _epub3_..._rX patterns
    simplified_name = re.sub(r'_r\d+', '', simplified_name) # Remove _rX patterns

    return sanitize_filename(simplified_name) if simplified_name else "unknown_section"

def get_logical_chapter_number(text):
    """Extracts a logical number from chapter text or titles."""
    word_to_num = {
        'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
        'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
        'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14,
        'fifteen': 15, 'sixteen': 16, 'seventeen': 17, 'eighteen': 18,
        'nineteen': 19, 'twenty': 20
    }
    
    # Try digit first
    digit_match = re.search(r'\b(\d+)\b', text)
    if digit_match:
        return int(digit_match.group(1))
        
    # Try word
    lower_text = text.lower()
    for word, num in word_to_num.items():
        if word in lower_text:
            return num
            
    return None

def merge_and_split_chapters(book, exclude_keywords, image_map=None, output_dir=None):
    """
    Merges document items from the spine and splits them by chapter headers/markers.
    Returns a list of dicts: {'name': str, 'content': str, 'logical_num': int, 'images': list}
    """
    full_text = ""
    global_img_counter = 0
    
    # Get items by ID for spine lookup to ensure correct order
    items_by_id = {item.get_id(): item for item in book.get_items()}
    
    current_chapter_id = None
    
    for spine_item in book.spine:
        item_id = spine_item[0]
        item = items_by_id.get(item_id)
        if not item or item.get_type() != ebooklib.ITEM_DOCUMENT:
            continue
            
        name = item.get_name()
        if any(kw in name.lower() for kw in exclude_keywords):
            continue
            
        content = item.get_content().decode('utf-8', errors='ignore')
        
        # NEW: Content-based filtering to skip non-chapter sections during merge
        if is_non_chapter_content(content):
            continue
        
        # Step 1: Spine-based detection (Preferred)
        # Check if this file identifies as a new chapter
        new_id = get_chapter_identifier(name, content)
        if new_id and new_id.startswith('chapter_') and new_id != current_chapter_id:
            match = re.search(r'\d+', new_id)
            if match:
                num = match.group()
                # Insert a unique marker to avoid double-splitting with natural text
                full_text += f"\n<<@CHAPTER:{num}>>\n"
            current_chapter_id = new_id
        
        if image_map and output_dir:
            content, global_img_counter = extract_and_mark_images(
                html_content=content, 
                item_name=name, 
                image_map=image_map, 
                output_dir=output_dir, 
                img_counter=global_img_counter
            )

        soup = BeautifulSoup(content, 'html.parser')
        full_text += soup.get_text(separator='\n') + "\n"

    # Pattern for natural headers OR our inserted markers
    # Group 1: Prefix (Chapter/Part), Group 2: Number/Word, Group 3: Marker Number
    pattern = re.compile(r'(?im)^\s*(?:(?:(chapter|c|part)\s+)?(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|\d+)|<<@CHAPTER:(\d+)>>)\s*$')

    splits = pattern.split(full_text)
    chapters = []
    
    if len(splits) <= 1:
        # Fallback: if no chapters found, return the whole thing as one chapter
        
        # Extract images from full_text
        full_text_clean, images = parse_markdown_images_from_text(full_text)
        
        chapters.append({
            'name': 'Full Book Content',
            'content': full_text_clean,
            'logical_num': 1,
            'images': images
        })
        return chapters

    # splits[0] is the intro/pre-chapter text
    if splits[0].strip():
        chapters.append({
            'name': 'Introduction',
            'content': splits[0].strip(),
            'logical_num': 0
        })

    # pattern.split with 3 capturing groups gives: [pre, group1, group2, group3, post, ...]
    for i in range(1, len(splits), 4):
        chap_type = splits[i]
        chap_num_str = splits[i+1]
        marker_num = splits[i+2]
        chap_content = splits[i+3].strip()
        
        if marker_num:
            # Marker split
            logical_num = int(marker_num)
            name = f"Chapter {logical_num}"
        else:
            # Natural header split
            logical_num = get_logical_chapter_number(chap_num_str)
            name_prefix = chap_type.capitalize() if chap_type else "Chapter"
            name = f"{name_prefix} {chap_num_str.capitalize()}"
        
        # Extract images from this chapter's chunk
        chap_content_clean, chap_images = parse_markdown_images_from_text(chap_content)

        # Merge logic: if this chapter seems to be a continuation or duplicate of the last one
        if chapters and chapters[-1]['logical_num'] == logical_num:
            chapters[-1]['images'].extend(chap_images)
            if chap_content_clean:
                if chapters[-1]['content']:
                    chapters[-1]['content'] += "\n\n" + chap_content_clean
                else:
                    chapters[-1]['content'] = chap_content_clean
        else:
            chapters.append({
                'name': name,
                'content': chap_content_clean,
                'logical_num': logical_num,
                'images': chap_images
            })
        
    # Final pass: remove almost empty chapters that might have been created by stray numbers
    return [c for c in chapters if c['content'].strip() or c['images'] or c['logical_num'] == 0]

def is_non_chapter_content(content: str) -> bool:
    """Checks if the content is a non-chapter section."""
    non_chapter_keywords = [
        "dedication", "copyright", "acknowledgments", "title page", 
        "table of contents", "epigraph", "author's note", "publisher", "isbn",
        "frontmatter", "halftitle", "bibliography", "references",
        "footnote", "footnotes", "notes", "endnotes", "further reading"
    ]
    
    soup = BeautifulSoup(content, 'html.parser')
    text_content = soup.get_text(separator=' ', strip=True)
    
    # Check for keywords in the first 1024 characters of the visible text
    content_lower = text_content[:1024].lower()
    for keyword in non_chapter_keywords:
        if keyword in content_lower:
            return True
            
    return False

def get_chapter_title_from_content(content):
    """Extracts the chapter title from the chapter's content."""
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

def save_summary_to_file(summary, item_name, output_dir, item_content=None):
    """Saves the summary to a Markdown file."""
    chapter_identifier = get_chapter_identifier(item_name, item_content)
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
    delay = 60 # Wait exactly 60 seconds for 1-minute quota limits to reset
    max_retries = 10
    for i in range(max_retries):
        try:
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            error_str = str(e)
            if "429" in error_str:
                wait_time = delay
                match = re.search(r'Please retry in (\d+\.?\d*)s', error_str)
                if match:
                    parsed_time = float(match.group(1)) + 2.0
                    wait_time = max(delay, parsed_time) # Enforce minimum 60s wait
                
                print(f"Rate limit exceeded. Waiting {wait_time:.1f} seconds for quota reset...")
                time.sleep(wait_time)
            else:
                print(f"Error summarizing text with Gemini API: {e}")
                return None
    print("Failed to summarize text after multiple retries.")
    return None

def get_running_ollama_model():
    """Queries the local Ollama API to find the currently running/loaded model."""
    try:
        response = requests.get("http://localhost:11434/api/ps", timeout=2)
        response.raise_for_status()
        data = response.json()
        if data.get("models") and len(data["models"]) > 0:
            return data["models"][0]["name"]
    except Exception as e:
        print(f"Could not automatically detect running Ollama model: {e}")
    return None

def summarize_text_with_local_llm(system_prompt, prompt):
    url = "http://localhost:11434/api/generate"
    headers = {"Content-Type": "application/json"}
    
    # Auto-detect running model or fallback to env var / default
    ollama_model = os.getenv("OLLAMA_MODEL")
    if not ollama_model:
        detected_model = get_running_ollama_model()
        ollama_model = detected_model if detected_model else "gpt-oss:20b"
    
    print(f"Local LLM: Using model '{ollama_model}'")
    
    data = {
        "model": ollama_model,
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
    delay = 60 # Wait exactly 60 seconds for 1-minute quota limits to reset
    max_retries = 10
    
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
                print(f"OpenAI Rate limit exceeded. Waiting {delay} seconds for quota reset...")
                time.sleep(delay)
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
