"""
Core utilities for text processing, EPUB structuring, and LLM API integrations.
"""
import html
import json
import os
import re
import time

import requests
from bs4 import BeautifulSoup
import ebooklib
import google.generativeai as genai
from openai import OpenAI

from extract_images import extract_and_mark_images, parse_markdown_images_from_text
from file_utils import sanitize_filename

def unescape(text):
    """Unescapes HTML entities in text."""
    return html.unescape(text)

def get_chapter_identifier(chapter_name_raw, item_content=None):
    """
    Given a raw EPUB manifest name or HTML content, derives a clean,
    standardized logical chapter name (e.g. 'chapter_1').
    """
    simplified_name = chapter_name_raw.lower()
    # Aggressively clean the name for better identifier matching
    simplified_name = simplified_name.replace("text/", "")
    simplified_name = simplified_name.replace("xhtml/", "")

    # Remove file extensions at the very beginning
    base, ext = os.path.splitext(simplified_name)
    if ext.lower() in (
        ".md",
        ".html",
        ".xhtml",
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".svg",
        ".bmp",
    ):
        simplified_name = base

    # More flexible chapter number extraction
    match = re.search(r"(?:chapter|c|part)[_-]?(\d+)", simplified_name)
    if match:
        base_id = f"chapter_{int(match.group(1))}"
        part_match = re.search(r"part[_-]?(\d+)", chapter_name_raw.lower())
        if part_match:
            return f"{base_id}_part_{int(part_match.group(1))}"
        return base_id

    # Handle Appendix
    if "appendix" in simplified_name:
        match = re.search(r"appendix[_-]?([a-z]|\d+)", simplified_name)
        if match:
            return f"appendix_{match.group(1)}"
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
        "frontmatter": "frontmatter",
    }

    for key, value in name_to_identifier_map.items():
        # Skip 'index' substring match for Calibre-style 'index_split_XXX' filenames
        if key == "index" and "index_split" in simplified_name:
            continue
        # Use word-boundary match, but also allow key as a prefix
        # (e.g. 'frontmatter' matches 'frontmatter01').
        if re.search(rf"\b{re.escape(key)}", simplified_name):
            return value

    # Content fallback: check heading/first-line for back/front matter before
    # trying to extract a chapter number from the body text.
    # Only apply back/front-matter heading check for small files; large files
    # are monolithic EPUBs that may start with a copyright/notes blurb but
    # actually contain multiple chapters inside and must not be discarded.
    if item_content and len(item_content) < 10000:
        try:
            from bs4 import BeautifulSoup as _BS
            _soup = _BS(item_content, "html.parser")
            _heading_text = ""
            for _tag in ["h1", "h2", "h3", "h4", "h5", "h6"]:
                _h = _soup.find(_tag)
                if _h and _h.get_text(strip=True):
                    _heading_text = _h.get_text(strip=True).lower()
                    break
            if not _heading_text:
                _lines = [l.strip() for l in _soup.get_text(separator="\n").splitlines() if l.strip()]
                if _lines:
                    _heading_text = _lines[0].lower()
            _heading_to_id = {
                "searchable terms": "index",
                "index": "index",
                "bibliography": "bibliography",
                "notes": "notes",
                "acknowledgments": "acknowledgments",
                "about the author": "about_the_author",
                "author bio": "about_the_author",
            }
            for _key, _val in _heading_to_id.items():
                if _key in _heading_text:
                    return _val
        except Exception:
            pass

    # Chapter number extraction:
    # We can extract chapter numbers for files of any size, because chapter classifications
    # are never skipped. However, we avoid extracting chapter numbers if the content is identified
    # as front/back matter (non-chapter content) to prevent monolithic files starting with
    # copyright blurbs from being misclassified.
    if item_content and not is_non_chapter_content(item_content):
        num = get_logical_chapter_number(item_content)
        if num is not None:
            return f"chapter_{num}"

    # Fallback for other unidentifiable document items
    # Remove common prefixes and suffixes
    simplified_name = re.sub(
        r"^[a-z]+_.*?_", "", simplified_name
    )  # a generic prefix remover
    simplified_name = re.sub(
        r"_epub3_.*?_r\d+", "", simplified_name
    )  # Remove _epub3_..._rX patterns
    simplified_name = re.sub(r"_r\d+", "", simplified_name)  # Remove _rX patterns

    return sanitize_filename(simplified_name) if simplified_name else "unknown_section"


def get_logical_chapter_number(text):
    """Extracts a logical chapter number from chapter text or titles.

    When `text` is raw HTML (e.g. from an EPUB item), the HTML is stripped
    first using BeautifulSoup so that digits inside XML declarations, namespace
    URLs, or href attributes do not produce false positives.

    A number is accepted only if it:
      - Appears at the very start of a heading or one of the first body lines,
        optionally preceded by 'Chapter / Part / C', OR
      - Is explicitly preceded by 'Chapter / Part / C' anywhere in those lines.

    This prevents mid-sentence words like "one of the best" or years like
    "2004" from being mistaken for chapter numbers.
    """
    word_to_num = {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
        "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
        "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
        "nineteen": 19, "twenty": 20,
    }
    _word_alts = "|".join(word_to_num.keys())

    # Strip HTML to get clean visible text, preserving line/word boundaries.
    if "</" in text or "<html" in text or "<body" in text:
        try:
            from bs4 import BeautifulSoup as _BS
            _soup = _BS(text, "html.parser")
            headings = [
                h.get_text(separator=" ", strip=True)
                for tag in ["h1", "h2", "h3", "h4", "h5", "h6"]
                for h in _soup.find_all(tag)
            ]
            paragraphs = _soup.find_all(["p", "div", "li"])
            if paragraphs:
                body_lines = []
                for p in paragraphs:
                    txt = p.get_text(separator=" ", strip=True)
                    if txt:
                        body_lines.append(txt)
            else:
                body_lines = [
                    l.strip()
                    for l in _soup.get_text(separator="\n").splitlines()
                    if l.strip()
                ]
            search_items = headings + body_lines[:3]
        except Exception:
            search_items = [text]
    else:
        search_items = [text]

    # Pattern A: line/heading starts with an optional chapter indicator then
    # a digit or spelled-out number (≤ 100 for digits).
    pat_start = re.compile(
        rf"^\s*(?:chapter|part|c)?\s*"
        rf"(\d+|{_word_alts})\b",
        re.IGNORECASE,
    )
    # Pattern B: explicit chapter/part indicator ANYWHERE in the line.
    pat_explicit = re.compile(
        rf"\b(?:chapter|part|c)[_\- ]?\s*"
        rf"(\d+|{_word_alts})\b",
        re.IGNORECASE,
    )

    for item in search_items:
        # Skip endnote/footnote citation lines
        if re.match(r"^\s*\d+\.\s+", item):
            item_lower = item.lower()
            if (
                "ibid" in item_lower
                or "see" in item_lower
                or "http" in item_lower
                or "www" in item_lower
                or ("," in item and ('"' in item or '“' in item or '”' in item))
                or item.count(",") >= 2
            ):
                continue

        for pat in (pat_start, pat_explicit):
            m = pat.match(item) if pat is pat_start else pat.search(item)
            if m:
                val = m.group(1).lower()
                if val.isdigit():
                    n = int(val)
                    if n <= 100:
                        return n
                elif val in word_to_num:
                    return word_to_num[val]

    return None


def _process_spine_items(book, exclude_keywords, image_map, output_dir):
    """Iterates over the book's spine, extracts HTML, handles images, and concatenates text."""
    full_text = ""
    global_img_counter = 0
    items_by_id = {item.get_id(): item for item in book.get_items()}
    current_chapter_id = None

    for spine_item in book.spine:
        item = items_by_id.get(spine_item[0])
        if not item:
            continue
        if item.get_type() != ebooklib.ITEM_DOCUMENT:
            continue

        name = item.get_name()
        if any(kw in name.lower() for kw in exclude_keywords):
            continue

        content = item.get_content().decode("utf-8", errors="ignore")
        if len(content) < 10000 and is_non_chapter_content(content):
            continue

        new_id = get_chapter_identifier(name, content)
        if new_id and new_id.startswith("chapter_") and new_id != current_chapter_id:
            match = re.search(r"\d+", new_id)
            if match:
                full_text += f"\n<<@CHAPTER:{match.group()}>>\n"
            current_chapter_id = new_id

        if image_map and output_dir:
            content, global_img_counter = extract_and_mark_images(
                html_content=content,
                item_name=name,
                image_map=image_map,
                output_dir=output_dir,
                img_counter=global_img_counter,
            )

        soup = BeautifulSoup(content, "html.parser")
        full_text += soup.get_text(separator="\n") + "\n"
        
    return full_text

def ocr_normalize(s):
    """Standardize string for matching, resilient to common OCR confusions."""
    s = s.lower()
    s = re.sub(r'\W+', '', s)
    s = s.replace('cl', 'cl').replace('ci', 'cl').replace('cy', 'cl').replace('1', 'l').replace('i', 'l').replace('y', 'l')
    return s

def fuzzy_match(title, text):
    """Fuzzy matching to compare TOC titles with text paragraphs resiliently."""
    title_clean = ocr_normalize(title)
    text_clean = ocr_normalize(text)
    if not title_clean:
        return False
    if len(title_clean) < 8:
        return title_clean == text_clean
    if title_clean in text_clean and len(text_clean) < len(title_clean) + 35:
        return True
    return False

def extract_toc_titles(lines, max_search=200):
    """Scans the beginning lines to find a Table of Contents. Returns list of (line_idx, title)."""
    toc_pattern = re.compile(r"^(.*?)\s+(?:\.|\s)*\s*(\d+)$")
    consecutive_matches = []
    for idx, line in enumerate(lines[:max_search]):
        match = toc_pattern.match(line)
        if match:
            title = match.group(1).strip()
            title = re.sub(r"\.+$", "", title).strip()
            consecutive_matches.append((idx, title))
        else:
            if len(consecutive_matches) >= 4:
                break
            if idx - (consecutive_matches[0][0] if consecutive_matches else idx) > 5:
                consecutive_matches = []
                
    if len(consecutive_matches) >= 4:
        return consecutive_matches
    return []

def chunk_text(text, max_chars=25000):
    """Split text into smaller chunks at paragraph boundaries (newline)."""
    paragraphs = text.split('\n')
    chunks = []
    current_chunk = []
    current_len = 0
    for p in paragraphs:
        p_len = len(p) + 1
        if current_len + p_len > max_chars and current_chunk:
            chunks.append("\n".join(current_chunk))
            current_chunk = [p]
            current_len = p_len
        else:
            current_chunk.append(p)
            current_len += p_len
    if current_chunk:
        chunks.append("\n".join(current_chunk))
    return chunks

def _split_text_into_chapters(full_text):
    """Splits unified text into chapters and extracts markdown image links."""
    # Mandatory keyword (chapter|c|part) to prevent page numbers from starting chapters.
    # The internal <<@CHAPTER:n>> marker remains the ultimate truth.
    pattern = re.compile(
        r"(?im)^\s*(?:(?:(chapter|c|part)\s+)(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|\d+)|<<@CHAPTER:(\d+)>>)\s*$"
    )
    splits = pattern.split(full_text)
    
    use_fallback = False
    if len(splits) <= 1:
        use_fallback = True
        
    final_chapters = []
    
    if not use_fallback:
        chapters_map = {}
        order = []
        if splits[0].strip():
            intro_content, intro_images = parse_markdown_images_from_text(splits[0].strip())
            chapters_map[0] = {
                "name": "Introduction",
                "content": intro_content,
                "logical_num": 0,
                "images": intro_images
            }
            order.append(0)

        for i in range(1, len(splits), 4):
            chap_type = splits[i]
            chap_num_str = splits[i + 1]
            marker_num = splits[i + 2]
            chap_content = splits[i + 3].strip()

            if marker_num:
                logical_num = int(marker_num)
                name = f"Chapter {logical_num}"
            else:
                logical_num = get_logical_chapter_number(chap_num_str)
                name_prefix = chap_type.capitalize() if chap_type else "Chapter"
                name = f"{name_prefix} {chap_num_str.capitalize()}"

            chap_content_clean, chap_images = parse_markdown_images_from_text(chap_content)

            if logical_num in chapters_map:
                chapters_map[logical_num]["images"].extend(chap_images)
                if chap_content_clean:
                    if chapters_map[logical_num]["content"]:
                        chapters_map[logical_num]["content"] += "\n\n" + chap_content_clean
                    else:
                        chapters_map[logical_num]["content"] = chap_content_clean
            else:
                chapters_map[logical_num] = {
                    "name": name,
                    "content": chap_content_clean,
                    "logical_num": logical_num,
                    "images": chap_images,
                }
                order.append(logical_num)

        if order or 0 in chapters_map:
            last_logical_num = order[-1] if order else 0
            last_chap = chapters_map[last_logical_num]
            backmatter_keywords = [
                "notes", "index", "bibliography", "acknowledgments", "epilogue",
                "conclusion", "afterword", "about the author", "author bio",
                "illustration credits", "credits"
            ]
            backmatter_pattern = re.compile(rf"(?im)^\s*({'|'.join(backmatter_keywords)})\s*$")
            bm_splits = backmatter_pattern.split(last_chap["content"])
            
            if len(bm_splits) > 1:
                first_part_content, first_part_images = parse_markdown_images_from_text(bm_splits[0].strip())
                last_chap["content"] = first_part_content
                last_chap["images"] = first_part_images
                
                bm_counter = 900
                for j in range(1, len(bm_splits), 2):
                    bm_name = bm_splits[j].strip().capitalize()
                    bm_content = bm_splits[j+1].strip()
                    bm_content_clean, bm_images = parse_markdown_images_from_text(bm_content)
                    
                    chapters_map[bm_counter] = {
                        "name": bm_name,
                        "content": bm_content_clean,
                        "logical_num": bm_counter,
                        "images": bm_images
                    }
                    order.append(bm_counter)
                    bm_counter += 1

        for num in order:
            chap = chapters_map[num]
            if chap["content"].strip() or chap["images"] or chap["logical_num"] == 0:
                final_chapters.append(chap)
                
        if len(final_chapters) <= 1:
            use_fallback = True

    if use_fallback:
        final_chapters = []
        lines = [line.strip() for line in full_text.split('\n') if line.strip()]
        toc_info = extract_toc_titles(lines)
        if toc_info:
            toc_end_idx = toc_info[-1][0]
            titles = [item[1] for item in toc_info if len(item[1]) > 3]
            
            title_locations = []
            current_search_idx = toc_end_idx + 1
            for title in titles:
                found_idx = None
                for idx in range(current_search_idx, len(lines)):
                    if fuzzy_match(title, lines[idx]):
                        found_idx = idx
                        break
                if found_idx is not None:
                    title_locations.append((found_idx, title))
                    current_search_idx = found_idx + 1
                    
            if title_locations:
                intro_content = "\n".join(lines[toc_end_idx + 1:title_locations[0][0]])
                intro_content_clean, intro_images = parse_markdown_images_from_text(intro_content)
                if intro_content_clean.strip() or intro_images:
                    final_chapters.append({
                        "name": "Introduction",
                        "content": intro_content_clean,
                        "logical_num": 0,
                        "images": intro_images
                    })
                for i in range(len(title_locations)):
                    start_line = title_locations[i][0]
                    end_line = title_locations[i+1][0] if i + 1 < len(title_locations) else len(lines)
                    chap_name = f"Chapter {i + 1}: {title_locations[i][1]}"
                    chap_content = "\n".join(lines[start_line:end_line])
                    chap_content_clean, chap_images = parse_markdown_images_from_text(chap_content)
                    final_chapters.append({
                        "name": chap_name,
                        "content": chap_content_clean,
                        "logical_num": i + 1,
                        "images": chap_images
                    })
        
        if not final_chapters:
            full_clean, full_images = parse_markdown_images_from_text(full_text)
            final_chapters.append({
                "name": "Full Book Content",
                "content": full_clean,
                "logical_num": 1,
                "images": full_images
            })
            
    chunked_chapters = []
    for chap in final_chapters:
        content = chap["content"]
        if len(content) > 25000:
            sub_chunks = chunk_text(content, max_chars=25000)
            if len(sub_chunks) > 1:
                for idx, chunk in enumerate(sub_chunks):
                    sub_name = f"{chap['name']} - Part {idx + 1}"
                    sub_images = chap.get("images", []) if idx == len(sub_chunks) - 1 else []
                    chunked_chapters.append({
                        "name": sub_name,
                        "content": chunk,
                        "logical_num": chap["logical_num"],
                        "images": sub_images
                    })
                continue
        chunked_chapters.append(chap)
        
    return chunked_chapters

def merge_and_split_chapters(book, exclude_keywords, image_map=None, output_dir=None):
    """
    Merges document items from the spine and splits them by chapter headers/markers.
    Returns a list of dicts: {'name': str, 'content': str, 'logical_num': int, 'images': list}
    """
    full_text = _process_spine_items(book, exclude_keywords, image_map, output_dir)
    return _split_text_into_chapters(full_text)



def is_non_chapter_content(content: str) -> bool:
    """Checks if the content is a non-chapter section."""
    non_chapter_keywords = [
        "dedication",
        "copyright",
        "acknowledgments",
        "title page",
        "table of contents",
        "epigraph",
        "author's note",
        "publisher",
        "isbn",
        "frontmatter",
        "halftitle",
        "bibliography",
        "references",
        "footnote",
        "footnotes",
        "notes",
        "endnotes",
        "further reading",
    ]

    soup = BeautifulSoup(content, "html.parser")
    text_content = soup.get_text(separator=" ", strip=True)

    # Check for keywords in the first 1024 characters of the visible text
    content_lower = text_content[:1024].lower()
    for keyword in non_chapter_keywords:
        if re.search(rf"\b{re.escape(keyword)}\b", content_lower):
            return True

    return False


def get_chapter_title_from_content(content):
    """Extracts the chapter title from the chapter's content prioritizing header tags."""
    soup = BeautifulSoup(content, "html.parser")

    # Try to find the title in common heading tags
    for tag in ["h1", "h2", "h3", "h4", "h5", "h6"]:
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
    with open(chapter_output_path, "w", encoding="utf-8") as summ_file:
        summ_file.write("# Chapter: " + item_name + "\n\n" + summary + "\n")
    print(f"Summary for {item_name} written to {chapter_output_path}")


def get_chapter_summary_system_prompt() -> str:
    """Returns the shared system prompt for chapter summarization."""
    return f"""## Role & Goal
You are an Expert Book Summarizer and Cognitive Distiller. Your goal is to analyze the raw text of a single book chapter and produce a highly engaging, beautifully structured, and comprehensive chapter summary in Markdown.

Your summary must avoid dry academic structures and instead read like a premium, narrative-driven breakdown. It must be dense with key ideas, arguments, and actionable takeaways, focusing heavily on the "WHY" and "HOW" (the underlying causal mechanics), using everyday metaphors, true systemic ASCII diagrams, and structured inline labels.

---

## Cognitive Processing (Chain of Thought)
Before generating the final summary, perform an internal analysis within a <thought> block:
1. Logical Decomposition: Identify the chapter's central conclusion. Map the explicit premises and evidence chains the author uses to reach that conclusion.
2. Completeness Audit: Scan the text for every key claim, counter-argument, and data point.
3. Causal Mapping: Identify the underlying mechanics. Determine the exact sequence of events, incentives, or dependencies (e.g., "Because X happened, Y was incentivized to do Z"). **You must explicitly use this causal map to write the paragraphs in your final output.**
4. Constraint Verification: Ensure the summary adheres to the "no meta-talk" rule, uses zero standard bullet points for concept explanations, and ensures the ASCII diagram is a true systemic loop, not just a list in a box.

---

## Key Guidelines for High-Quality Summaries

1. **Direct, Punchy Hook (No Metadata Headers):**
   - Start your response immediately with a highly engaging introductory hook (2-3 sentences max).
   - Do NOT include any titles or metadata headers at the very top (e.g., do NOT start with `# Chapter Name`). Start directly with the hook text.
   - Format the hook using this template structure:
     "This chapter gets to the absolute core of [idea]. It shifts the perspective of [core subject] from a simple [common superficial misconception] to a [profound, unexpected, or biological/structural truth]."

2. **Engaging Numbered Headings:**
   - Divide the chapter into logical themes/concepts using numbered Markdown headings (e.g., `## 1. [Theme/Concept Name]` or `## 1. [A punchy title that grabs attention and summarizes the essence of the section].`

3. **Visual Systems Diagrams (Mechanics, Not Lists):**
   - Whenever the chapter describes a process, cycle, or relationship, you MUST include a clean, simple text-based ASCII diagram (in a code block). 
   - **CRITICAL:** Do NOT just put lists of words inside boxes. You must show the *engine* of the concept using arrows to demonstrate feedback loops, bottlenecks, or cause-and-effect (e.g., `[Action] --> causes --> [Consequence] --> leads to --> [Result]`).

4. **Narrative Flow & The "Why":**
   - Write in flowing, punchy paragraphs. Every time you introduce a concept using a **bold inline label**, you must immediately explain the *underlying mechanism*.
   - Use causal phrasing like "Because [X] happens, [Y] is forced to adapt..." or "This works by [mechanism]..." Do not just state *what* happened; explain *why* the system required it to happen and *how* it impacted the larger structure.

5. **Strict Fidelity (No Meta-Talk):**
   - Ground everything strictly in the text.
   - Avoid conversational filler or meta-talk (do not write "the author argues," "in this chapter," or "the text describes"). Write directly about the concepts as objective reality.

---

## Expected Structure:

[Hook Paragraph - 2-3 sentences following the exact template]

Here is a breakdown of how this system works, using the book's core concepts.

## 1. [Engaging Title]
**[Bold Concept Label]:** [Flowing paragraph explaining the WHAT, HOW, and WHY. Explain the mechanics and incentives driving this concept using causal language. No bulleted lists here.]
**[Bold Concept Label]:** [Flowing paragraph continuing the narrative...]

```text
[ASCII Diagram demonstrating a cause-and-effect system, using arrows and loops]
    """


def create_gemini_chapter_summary_prompt(text: str) -> str:
    """Wraps text in the chapter summary structure for Gemini."""
    return f""" {get_chapter_summary_system_prompt()}

    ## Input Summaries
    {text}
    ---
    """


def create_gemini_full_summary_prompt(text: str) -> str:
    """Returns the final synthesis prompt combining multiple chapter summaries."""
    return f"""## Role & Goal
    You are a Master Information Architect. Your goal is to transform long-form chapter summaries into a Single-Page Schematic Framework. Prioritize high-density information, tabular comparisons, and "Practical Cues" over narrative analysis. Eliminate all conversational filler and introductory meta-talk.

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

    ### 3. Cross-Chapter Connections & Thematic Synthesis
    Identify and analyze the core connections, dependencies, and logical transitions between the major themes of the book. Explain how concepts introduced in early sections build the foundation for later concepts. Highlight any recurring threads, contradictions, or overarching principles that bind the chapters together. Use a short dependency chain or arrow diagram (ASCII) where helpful.

    ## Input Summaries
    Here are the chapter summaries you are to synthesize:
    {text}
    """


def get_local_llm_system_prompt() -> str:
    """Returns the system prompt for local LLMs."""
    return get_chapter_summary_system_prompt()


def get_full_summary_system_prompt() -> str:
    """Returns the system prompt for full book summarization/synthesis using local LLMs."""
    return """## Role & Goal
    You are a Master Information Architect. Your goal is to transform long-form chapter summaries into a Single-Page Schematic Framework. Prioritize high-density information, tabular comparisons, and "Practical Cues" over narrative analysis. Eliminate all conversational filler and introductory meta-talk.

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

    ### 3. Cross-Chapter Connections & Thematic Synthesis
    Identify and analyze the core connections, dependencies, and logical transitions between the major themes of the book. Explain how concepts introduced in early sections build the foundation for later concepts. Highlight any recurring threads, contradictions, or overarching principles that bind the chapters together. Use a short dependency chain or arrow diagram (ASCII) where helpful.
    """



def summarize_text_with_gemini(prompt, api_key):
    """Uses the Gemini SDK to summarize the given prompt (with exponential backoff)."""
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-flash")
    delay = 60  # Wait exactly 60 seconds for 1-minute quota limits to reset
    max_retries = 10
    for _ in range(max_retries):
        try:
            response = model.generate_content(prompt)
            return response.text
        except Exception as err:
            error_str = str(err)
            if "429" in error_str:
                wait_time = delay
                match = re.search(r"Please retry in (\d+\.?\d*)s", error_str)
                if match:
                    parsed_time = float(match.group(1)) + 2.0
                    wait_time = max(delay, parsed_time)  # Enforce minimum 60s wait

                print(
                    f"Rate limit exceeded. Waiting {wait_time:.1f} seconds for quota reset..."
                )
                time.sleep(wait_time)
            else:
                print(f"Error summarizing text with Gemini API: {err}")
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
    except Exception as err:
        print(f"Could not automatically detect running Ollama model: {err}")
    return None


def summarize_text_with_local_llm(system_prompt, prompt):
    """Uses the local Ollama API to summarize utilizing the configured local LLM."""
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
        "stream": False,
    }
    # Configure timeout (default to 600s, check OLLAMA_TIMEOUT env var)
    try:
        timeout_val = int(os.getenv("OLLAMA_TIMEOUT", "600"))
    except ValueError:
        timeout_val = 600

    try:
        response = requests.post(url, headers=headers, json=data, timeout=timeout_val)
        response.raise_for_status()
        response_json = response.json()
        return response_json.get("response", "").strip()
    except requests.exceptions.RequestException as err:
        print(f"Error making API call to local LLM: {err}")
        return None
    except json.JSONDecodeError as err:
        print(f"Error decoding JSON response from local LLM: {err}")
        return None


def summarize_text_with_openai(prompt, api_key):
    """Uses the OpenAI SDK to summarize the given prompt (with rate limit handling)."""
    client = OpenAI(api_key=api_key)
    delay = 60  # Wait exactly 60 seconds for 1-minute quota limits to reset
    max_retries = 10

    for _ in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": get_chapter_summary_system_prompt()},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=2048,
            )
            return response.choices[0].message.content
        except Exception as err:
            if "rate_limit" in str(err).lower() or "429" in str(err):
                print(
                    f"OpenAI Rate limit exceeded. Waiting {delay} seconds for quota reset..."
                )
                time.sleep(delay)
            else:
                print(f"Error summarizing text with OpenAI API: {err}")
                return None
    print("Failed to summarize text with OpenAI after multiple retries.")
    return None


def summarize_text(
    text_content: str,
    use_local_llm: bool = False,
    gemini_api_key: str = None,
    openai_api_key: str = None,
    is_full_summary: bool = False,
):
    """
    High-level facade to route text summarization to the chosen
    language model backend (Gemini, OpenAI, or Local).
    """
    if use_local_llm:
        print("Using local LLM for summarization...")
        if is_full_summary:
            system_prompt = get_full_summary_system_prompt()
            prompt = f"Here are the chapter summaries you are to synthesize:\n{text_content}"
        else:
            system_prompt = get_local_llm_system_prompt()
            prompt = text_content
        return summarize_text_with_local_llm(system_prompt, prompt)

    if openai_api_key:
        print("Using OpenAI API for summarization...")
        if is_full_summary:
            # We don't have create_openai_full_summary_prompt yet, but prompts are mostly text.
            # Reusing the existing prompt logic.
            prompt = create_gemini_full_summary_prompt(text_content)
        else:
            prompt = text_content  # System prompt is already handled in summarize_text_with_openai
        return summarize_text_with_openai(prompt, openai_api_key)

    print("Using Gemini API for summarization...")
    if not gemini_api_key:
        print("Error: Neither OPENAI_API_KEY nor GEMINI_API_KEY provided.")
        return None
    if is_full_summary:
        prompt = create_gemini_full_summary_prompt(text_content)
    else:
        prompt = create_gemini_chapter_summary_prompt(text_content)
    return summarize_text_with_gemini(prompt, gemini_api_key)
