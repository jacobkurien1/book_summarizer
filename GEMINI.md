# Gemini Assistant Instructions for Book Summarization

You are an AI assistant helping to process and summarize e-books. Your primary goal is to take an e-book in `.epub` format and create high-quality chapter-by-chapter summaries.

## Current Implementation & Features

This project provides Python scripts to process EPUB (electronic publication) files. It can summarize book chapters and generate a consolidated full book summary using the Google Gemini API, and extract images, organizing the output into a structured folder named after the book.

### Core Workflow

1.  **Deconstruct the E-book**: Given a new `.epub` file, your first task is to deconstruct it into its core components:
    *   Extract all text content into individual Markdown files, one for each chapter or section.
    *   Extract all images into a corresponding directory.
    *   Uses existing Python scripts (`main.py`, `utils.py`, `extract_images.py`) as a reference for this process.

2.  **Intelligent Section Skipping**: Automatically skips non-chapter sections (like covers, title pages, dedications, acknowledgments, etc.) based on both filename keywords and content analysis.

3.  **Summarize Each Chapter**: Each chapter's text content is summarized into a concise, well-written Markdown file, capturing key ideas, arguments, and narratives.

4.  **Image Extraction**: Extracts images from the EPUB and saves them with descriptive names (e.g., `chapter_1_image_1.jpg`, `cover_image_1.jpg`).

5.  **Organized Output**: All generated chapter summaries and extracted images are stored in a dedicated folder named after the book's title (e.g., `Workplace_Poker`).

6.  **Consolidated Full Summary**: After individual chapter summaries are generated, a final, consolidated summary of the entire book is created by synthesizing the chapter summaries. This full summary is also saved within the book's dedicated output folder.

### Technical Details

*   **Gemini API Integration**: Utilizes the Google Gemini API (specifically `gemini-2.5-flash`) for summarization. API calls include an exponential backoff mechanism with up to 5 retries to handle rate limiting.
*   **Command-line Argument**: Supports a `--full-summary-only` argument to skip chapter-by-chapter summarization and only generate the consolidated full summary from existing chapter summary files.
*   **Decoupled Functionality**: Summarization and image extraction are handled by separate scripts for modularity.

## Guidelines

*   **Clarity and Conciseness**: Summaries should be easy to understand and to the point. Should not use any other sources other than the book content.
*   **Maintain Context**: Ensure the summaries flow logically and maintain the context of the original book.
*   **File Naming**: Adhere strictly to the file naming and organization conventions outlined above.
*   **Image Handling**: Images found within a chapter will be extracted and appended to the end of the chapter's summary in Markdown format (`![context description](image_path)`). The `image_path` will be relative to the summary file.