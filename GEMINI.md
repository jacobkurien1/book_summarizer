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

*   **API Integration**: Utilizes either the Google Gemini API (default, `gemini-2.5-flash`) or the OpenAI API (via `--openai` flag). API calls include an exponential backoff mechanism with up to 5 retries to handle rate limiting.
*   **Command-line Arguments**:
    *   `--full-summary-only`: Skip chapter-by-chapter summarization and only generate the consolidated full summary from existing chapter summary files.
    *   `--openai`: Use OpenAI's GPT-4o model for summarization (requires `OPENAI_API_KEY`).
    *   `--chapters 1,3,5`: Specify which chapters to process (1-indexed). Use `5,*` to process from chapter 5 to the end. Wrap in quotes if using spaces or wildcards (e.g., `--chapters "18, *"`). Useful for idempotency and debugging.
    *   `--localllm`: Use a local LLM (Ollama) for summarization. The model defaults to `gpt-oss:20b`. You can customize this by setting the `OLLAMA_MODEL` environment variable (e.g., `export OLLAMA_MODEL=deepseek-r1`).
    *   `--hybrid`: Use a local LLM for chapter-by-chapter summarization, but use Gemini (or OpenAI if `--openai` is provided) for the final consolidated full book summary.
*   **Decoupled Functionality**: Summarization and image extraction are handled by separate scripts for modularity.

## Guidelines

*   **Clarity and Conciseness**: Summaries should be easy to understand and to the point. Should not use any other sources other than the book content.
*   **Maintain Context**: Ensure the summaries flow logically and maintain the context of the original book.
*   **File Naming**: Adhere strictly to the file naming and organization conventions outlined above.
*   **Idempotency**: Use the `--chapters` flag to selectively re-run chapters without re-summarizing the entire book.
*   **Image Handling**: Images found within a chapter will be extracted and appended to the end of the chapter's summary in Markdown format (`![context description](image_path)`). The `image_path` will be relative to the summary file.