import re
import os
import time
from ebooklib import epub
import google.generativeai as genai

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

def is_non_chapter_content(content: str) -> bool:
    """Checks if the content is a non-chapter section."""
    non_chapter_keywords = [
        "dedication", "copyright", "acknowledgments", "title page", 
        "table of contents", "epigraph", "author's note", "publisher", "isbn",
        "frontmatter", "halftitle"
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

import time

def summarize_text_with_gemini(prompt, api_key):
    """Summarizes text using the Gemini API with exponential backoff."""
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash')

    initial_delay = 1
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

def create_chapter_summary_prompt (text: str) -> str:
    return f"""## Role & Goal
    You are a Knowledge Architect. Your mission is to synthesize my chapter summaries for a book on [Optional: Briefly describe the book's topic, e.g., "a book about productivity and habits"] into a highly-organized and actionable study guide. The final output must be a structured knowledge outline, not a narrative report. Use a direct, instructional tone and format the information for maximum clarity and retention.

    ## Formatting Instructions
    * Use a hierarchical structure with markdown headings (##, ###).
    * Use nested bullet points and numbered lists extensively.
    * Write in concise, point-form phrases rather than full paragraphs.
    * Use **bolding** to emphasize key terms and concepts.
    * Address the reader directly as "you" where appropriate.

    ## Outline Structure to Follow. 
    * Only add the output text in this format. Dont add conversational text like "Here is your structured knowledge outline, synthesizing the provided chapter summary into a highly-organized study guide."
    * Keep the summary to a single page.

    ### 1. The Core Thesis / Big Idea
    - **Central Argument:** State the single most important argument or "big idea" of the book.
    - **Problem Solved:** What common problem, question, or misunderstanding does this book address?
    - **Core Model/Framework:** If there is a central model or equation, state it here.

    ### 2. Key Pillars / Core Concepts
    Based on the summaries, identify the 3-5 foundational pillars or main concepts that support the core thesis. For each pillar:
    - **### Pillar 1: [AI, give this a descriptive name]**
    - **Core Idea:** Briefly explain the main point of this pillar.
    - **Key Details:** Use nested bullets to list its most important supporting points, rules, or components.
    - **### Pillar 2: [AI, give this a descriptive name]**
    - **Core Idea:** Briefly explain the main point of this pillar.
    - **Key Details:** Use nested bullets to list its most important supporting points, rules, or components.
    - *(Continue for all major pillars identified)*

    ### 3. Actionable Framework & Strategies
    Distill the practical, actionable advice from the book.
    - **Key Actions:** List the main steps, techniques, or practices the author recommends for you to implement.
    - **"How-To" Steps:** Break down any complex processes into a simple, step-by-step list.

    ### 4. Underlying Mindsets & Barriers
    - **Essential Mindsets:** Identify any key mindsets, mental models, or philosophies the author encourages you to adopt.
    - **Barriers to Overcome:** List any common barriers, fears, or mistakes the author warns against.

    ### 5. Key Examples & Case Studies
    - Select 1-2 of the most powerful examples, stories, or case studies mentioned.
    - For each one, briefly describe it and explain which core concept it illustrates.

    ## Input Summaries
    Here are the chapter summaries to synthesize:
    {text}
    """

def create_full_summary_prompt(text: str) -> str: 
    return f"""## Role & Goal
    Act as a strategic consultant preparing an executive briefing on the book. Your input is a series of my chapter summaries. Your goal is to synthesize these into a definitive, high-level analysis that captures the book's core framework, practical applications, and overall intellectual contribution. The final output should be a strategic document for a busy leader who needs to grasp the essence of the book quickly.

    ## Briefing Document Structure

    ### 1. The Elevator Pitch
    In two sentences, what is this book about and why does it matter?

    ### 2. The Central Model / Framework
    Describe the core model, framework, or \"big idea\" the author presents. How does it work? What problem does it solve?

    ### 3. Key Thematic Pillars
    Instead of just themes, identify the 3-4 foundational pillars that support the book's central model. What are the main components of the author's argument?
    * **Pillar 1:** [e.g., \"The Psychology of...\"]. Briefly explain.
    * **Pillar 2:** [e.g., \"The System for...\"]. Briefly explain.
    * **Pillar 3:** [e.g., \"The Impact on...\"]. Briefly explain.

    ### 4. Argument Progression (The Journey)
    Summarize the intellectual journey the book takes the reader on. How does the argument build from the initial premise in the early chapters to the final conclusion?

    ### 5. Top 3 Most Actionable Takeaways
    Distill all the information into the three most critical, actionable pieces of advice a reader should take away from the entire book.
    1.  ...
    2.  ...
    3.  ...

    ### 6. Most Illuminating Examples
    Select the case study or examples from the summaries that best encapsulates the book's entire thesis in action. Briefly describe it and explain why it's so powerful.

    ## Input Summaries
    Here are the chapter summaries you are to synthesize:
    {text}
    """