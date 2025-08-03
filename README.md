# EPUB Book Processor

This project provides Python scripts to process EPUB (electronic publication) files. It can summarize book chapters using the Google Gemini API and extract images, organizing the output into a structured folder named after the book.

It also includes a `utils.py` file with helper functions for robust filename sanitization and chapter identification.

## Features

*   **Chapter Summarization**: Summarizes each chapter of an EPUB book into a separate Markdown file.
*   **Intelligent Section Skipping**: Automatically skips non-chapter sections like covers, title pages, dedications, acknowledgments, etc.
*   **Gemini API Integration**: Utilizes the Google Gemini API (specifically `gemini-2.5-flash`) for summarization.
*   **Image Extraction**: Extracts images from the EPUB and saves them with descriptive names (e.g., `chapter_1_image_1.jpg`, `cover_image_1.jpg`).
*   **Organized Output**: All generated summaries and extracted images are stored in a dedicated folder named after the book's title (e.g., `Workplace_Poker`).
*   **Decoupled Functionality**: Summarization and image extraction are handled by separate scripts for modularity.

## Project Structure

*   `main.py`: The main script for summarizing EPUB chapters.
*   `extract_images.py`: A separate script for extracting images from EPUBs.
*   `utils.py`: Contains helper functions for filename sanitization and chapter identification.
*   `test_utils.py`: Unit tests for the `utils.py` helper functions.
*   `requirements.txt`: Lists the Python dependencies.
*   `.env`: (Optional) Stores your Gemini API key.
*   `README.md`: This file.

## Setup

1.  **Install Dependencies**:
    The project requires Python 3 and the libraries listed in `requirements.txt`.
    ```bash
    pip install -r requirements.txt
    ```

2.  **Set up Gemini API Key**:
    You need a Google Gemini API key. You can obtain one from the [Google AI Studio](https://aistudio.google.com/app/apikey).
    Create a file named `.env` in the root of your project directory (the same directory as `main.py`, `extract_images.py`, and `utils.py`) and add your API key to it in the following format:
    ```
    GEMINI_API_KEY=YOUR_ACTUAL_GEMINI_API_KEY_HERE
    ```
    Replace `YOUR_ACTUAL_GEMINI_API_KEY_HERE` with your actual API key.

## Usage

Place your EPUB book file in the same directory as the scripts.

### 1. Summarize Chapters

To summarize the chapters of your EPUB book:

```bash
python main.py "Your_Book_Name.epub"
```

Replace `"Your_Book_Name.epub"` with the actual filename of your EPUB book.

The script will:
*   Read the EPUB file provided as an argument.
*   Create a folder named after the book's title (e.g., `Workplace_Poker`).
*   Generate Markdown files for each chapter summary (e.g., `chapter_1.md`, `conclusion.md`) inside the book's folder.

**Note on API Quotas**: The Gemini API has usage quotas. If you encounter `429 You exceeded your current quota` errors, you may need to wait for your quota to reset or check your Google Cloud project's billing and quota settings. A 5-second delay is included between API calls to help mitigate rate limits.

### 2. Extract Images

To extract images from your EPUB book:

```bash
python extract_images.py "Your_Book_Name.epub"
```

Replace `"Your_Book_Name.epub"` with the actual filename of your EPUB book.

The script will:
*   Create or use the existing folder named after the book's title (e.g., `Workplace_Poker`).
*   Extract all images and save them within this folder.
*   Images will be named descriptively, associating them with chapters where possible (e.g., `chapter_1_image_1.jpg`, `cover_image_1.jpg`).

## Customization

*   **EPUB File**: Both `main.py` and `extract_images.py` now accept the EPUB file path as a command-line argument.
*   **Excluded Sections**: Adjust the `exclude_keywords` list in `main.py` to customize which sections are skipped during summarization.
*   **Gemini Model**: The `summarize_text_with_gemini` function in `main.py` uses `models/gemini-2.5-flash`. You can change this to another available Gemini model if desired.
*   **API Call Delay**: The `time.sleep(5)` call in `main.py` can be adjusted to change the delay between Gemini API requests.
