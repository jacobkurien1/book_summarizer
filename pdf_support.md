# PDF Support Design Proposal

## 1. Core Concept: A Separate PDF Processing Pipeline

We'll treat PDF processing as a distinct workflow from the existing EPUB one. The main script (`main.py`) will first detect the file type and then delegate to the appropriate processing pipeline (EPUB or PDF).

## 2. Key Challenges with PDFs

Unlike EPUBs, PDFs are designed for fixed layouts, not for reflowable content. This presents two main challenges:
*   **No Standard Structure:** PDFs don't have a built-in, machine-readable concept of chapters or sections. We will have to infer the structure.
*   **Complex Content Extraction:** Extracting text and images in the correct reading order can be difficult.

## 3. Proposed Design: A Heuristic-Based Approach

To overcome these challenges, we'll use a heuristic-based approach to identify chapters and extract content. This will be handled by a new set of functions, likely in a new `pdf_processor.py` file.

Here is the proposed workflow for processing a PDF:

**Step 1: PDF Text and Structure Extraction**
*   Use a Python library like `pdfplumber` to open the PDF and extract the content of each page. `pdfplumber` is excellent for this because it can provide detailed information about the text, such as font size, font name, and position on the page, which is crucial for our heuristics.

**Step 2: Chapter Detection (The Core Logic)**
This is the most critical part of the design. We'll use a multi-pass approach to identify chapters:

*   **Pass 1: Table of Contents (ToC) Parsing:**
    *   First, the system will try to find a ToC within the first few pages of the PDF.
    *   It will look for lines that match common ToC patterns (e.g., "Chapter 1 ....... 5", "Introduction .... 1").
    *   If a ToC is found, we can extract the chapter titles and their corresponding page numbers. This is the most reliable method for splitting the book into chapters.

*   **Pass 2: Layout and Style Analysis (If no ToC is found):**
    *   If a ToC is not available, the system will fall back to analyzing the document's layout.
    *   It will iterate through each page and analyze the font sizes of the text. A significant increase in font size usually indicates a chapter title.
    *   It will also look for specific keywords like "Chapter" or "Part" at the beginning of a line, combined with a larger font size.

**Step 3: Content Aggregation**
*   Once the chapter start pages are identified (either from the ToC or layout analysis), the system will group the pages by chapter.
*   The text from all pages belonging to a chapter will be concatenated to form the full chapter content.

**Step 4: Image Extraction**
*   While processing each page, the system will also use `pdfplumber` (or a more performant library like `PyMuPDF` if needed) to detect and extract any images.
*   The extracted images will be saved to the book's output folder, named according to the chapter they belong to (e.g., `chapter_1_image_1.png`).

**Step 5: Summarization**
*   Once the text and images for each chapter are extracted, they will be passed to the existing summarization logic (`summarize_text_with_gemini`).
*   The extracted images will be linked at the end of each chapter summary, just like in the EPUB workflow.
*   Finally, a full book summary will be generated from the individual chapter summaries.

## 4. Recommended Library

*   **`pdfplumber`**: This library is the top choice for this task. It's powerful, well-documented, and provides the detailed text and layout information needed for our chapter detection heuristics. It can also extract images.
