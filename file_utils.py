"""
String manipulation and file-saving utilities for book extraction.
"""

import os
import re

from ebooklib import epub


def sanitize_filename(name):
    """
    Sanitizes a string to be safe for file system use by removing
    illegal characters and substituting spaces for underscores.
    """
    # Separate base and extension first from the original name
    base, _ext = os.path.splitext(name)

    # Sanitize the base name
    clean_name = base.replace(" ", "_")
    clean_name = re.sub(
        r"[^a-zA-Z0-9_-]", "_", clean_name
    )  # Replace non-alphanumeric (except _ and -) with single underscores
    clean_name = re.sub(r"_+", "_", clean_name)  # Replace multiple underscores with single
    clean_name = clean_name.strip("_")  # Remove leading/trailing underscores

    return clean_name if clean_name else "unknown_section"


def get_book_output_folder(
    book: epub.EpubBook, default_name: str = "processed_book"
) -> str:
    """
    Extracts the book title from EPUB metadata to construct a safe
    output directory name. Falls back to default_name if none found.
    """
    book_title_metadata = book.get_metadata("DC", "title")
    if not book_title_metadata:
        return default_name  # Use default if no title metadata is found

    book_title = book_title_metadata[0][0]
    # Extract primary part of the title for folder name
    if ":" in book_title:
        book_folder_name_raw = book_title.split(":")[0]
    else:
        book_folder_name_raw = book_title
    book_folder_name = sanitize_filename(
        book_folder_name_raw
    )  # sanitize_filename no longer removes extensions
    return book_folder_name if book_folder_name else default_name
