# Book Summarizer

This project provides a suite of Python scripts to process and summarize e-books. It leverages the Google Gemini API to create high-quality, chapter-by-chapter summaries, extracts images, and organizes all content into a structured output directory.

## Features

*   **Chapter-by-Chapter Summarization**: Generates detailed summaries for each chapter of an EPUB book.
*   **Full Book Summary**: Creates a consolidated summary of the entire book from the chapter summaries.
*   **Image Extraction**: Extracts images from the EPUB and intelligently names them based on their chapter context.
*   **Intelligent Section Skipping**: Automatically identifies and skips non-chapter sections such as covers, title pages, dedications, and tables of contents.
*   **Organized Output**: Creates a dedicated folder for each book, containing all the generated summaries and extracted images.
*   **Flexible Usage**: Supports generating a full summary from existing chapter summaries without re-processing the entire book.

## Workflow

1.  **Deconstruct E-book**: The system first deconstructs the input `.epub` file into its core components: text content (as HTML) and images.
2.  **Filter Chapters**: It then filters out non-chapter sections based on a combination of filename keywords and content analysis.
3.  **Summarize Chapters**: Each chapter's text content is sent to the Google Gemini API to generate a concise summary.
4.  **Extract and Link Images**: Any images within a chapter are extracted, saved, and linked at the end of the corresponding chapter summary.
5.  **Generate Full Summary**: Finally, all the individual chapter summaries are synthesized to create a comprehensive summary of the entire book.

## Project Structure

```
.
├── main.py               # Main script for generating summaries
├── utils.py              # Helper functions for text processing and API calls
├── extract_images.py     # Script for image extraction
├── requirements.txt      # Project dependencies
├── pdf_support.md        # Design doc for future PDF support
└── ...
```

## Installation

1.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

2.  **Set up your API Key:**
    You need a Google Gemini API key. You can obtain one from the [Google AI Studio](https://aistudio.google.com/app/apikey).
    Create a file named `.env` in the root of your project directory (the same directory as `main.py`, `extract_images.py`, and `utils.py`) and add your API key to it in the following format:
    ```
    GEMINI_API_KEY=YOUR_ACTUAL_GEMINI_API_KEY_HERE
    ```
    Replace `YOUR_ACTUAL_GEMINI_API_KEY_HERE` with your actual API key.

## Usage

To generate chapter summaries and a full book summary:
```bash
python main.py "path/to/your/book.epub"
```

To generate only the full book summary from existing chapter summaries:
```bash
python main.py "path/to/your/book.epub" --full-summary-only
```

The output will be saved in a new directory named after the book's title.

## Future Work

*   **PDF Support:** We plan to add support for processing and summarizing PDF files. The design for this feature is detailed in `pdf_support.md`.