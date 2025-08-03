# Gemini Assistant Instructions for Book Summarization

You are an AI assistant helping to process and summarize e-books. Your primary goal is to take an e-book in `.epub` format and create high-quality chapter-by-chapter summaries.

## Core Workflow

1.  **Deconstruct the E-book**: Given a new `.epub` file, your first task is to deconstruct it into its core components:
    *   Extract all text content into individual Markdown files, one for each chapter or section.
    *   Extract all images into a corresponding directory.
    *   Use the existing python scripts (`main.py`, `utils.py`, `extract_images.py`) as a reference for this process.

2.  **Organize the Content**:
    *   Create a new directory named after the book (e.g., `Book_Title/`).
    *   Place all extracted Markdown chapter files into this new directory.
    *   Place all extracted images into this same directory.

3.  **Summarize Each Chapter**:
    *   Go through each chapter's Markdown file one by one.
    *   For each chapter, create a concise, well-written summary.
    *   The summary should capture the key ideas, arguments, and narrative of the chapter.

4.  **Store the Summaries**:
    *   Create a new directory named `summaries/` if it doesn't exist.
    *   Save each chapter summary as a separate Markdown file inside the `summaries/` directory.
    *   Follow the naming convention: `summary_{book_title}_{chapter_name}.md`.

## Guidelines

*   **Clarity and Conciseness**: Summaries should be easy to understand and to the point.
*   **Maintain Context**: Ensure the summaries flow logically and maintain the context of the original book.
*   **File Naming**: Adhere strictly to the file naming and organization conventions outlined above.
*   **Handle Images**: When summarizing a chapter that includes images, note the presence of the images in the summary (e.g., "[Image: A chart showing X]"). Do not try to analyze the image content directly unless requested.
