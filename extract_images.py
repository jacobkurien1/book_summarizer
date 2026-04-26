"""
Handles extracting, mapping, and replacing images within EPUB files.
"""

import os
import re
import sys
from urllib.parse import unquote

import ebooklib
from bs4 import BeautifulSoup
from ebooklib import epub
from file_utils import get_book_output_folder


def create_image_map(book):
    """Creates a map of all images in the EPUB, mapping their internal paths to their content."""
    image_map = {}
    for item in book.get_items():
        is_image = False
        if (
            item.get_type() == ebooklib.ITEM_IMAGE
            or item.get_type() == ebooklib.ITEM_COVER
        ):
            is_image = True
        elif (
            hasattr(item, "get_media_type")
            and item.get_media_type()
            and item.get_media_type().startswith("image/")
        ):
            is_image = True
        elif (
            item.get_name()
            .lower()
            .endswith((".jpg", ".jpeg", ".png", ".gif", ".svg", ".bmp"))
        ):
            is_image = True

        if is_image:
            image_map[item.get_name()] = item.get_content()
    return image_map


def extract_and_mark_images(
    html_content, item_name, image_map, output_dir, img_counter
):
    """
    Finds all images in the HTML content, safely downloads them if they exist in the
    image map, and replaces the <img> tag with a special markdown placeholder.
    Returns the modified HTML string and the updated image counter.
    """
    if not image_map or not output_dir:
        return html_content, img_counter

    soup = BeautifulSoup(html_content, "html.parser")
    images = soup.find_all("img")

    modified = False
    image_placeholders = {}
    for img_tag in images:
        src = img_tag.get("src")
        if not src:
            continue

        decoded_src = unquote(src)
        chapter_path = os.path.dirname(item_name)
        cleaned_src = os.path.normpath(os.path.join(chapter_path, decoded_src)).lstrip(
            "/"
        )

        if cleaned_src in image_map:
            img_counter += 1
            ext = cleaned_src.split(".")[-1]
            image_filename = f"image_{img_counter}.{ext}"
            image_path = os.path.join(output_dir, image_filename)

            try:
                with open(image_path, "wb") as img_file:
                    img_file.write(image_map[cleaned_src])

                alt_text = img_tag.get("alt", "")
                # Use a specific, non-escapable marker
                img_tag.replace_with(f"MARKER_IMG_{img_counter}")
                modified = True
                image_placeholders[f"MARKER_IMG_{img_counter}"] = (
                    f"\n<<@IMAGE:{image_filename}|{alt_text}>>\n"
                )
            except Exception as err:
                print(f"Error extracting image {cleaned_src}: {err}")

    if modified:
        final_html = str(soup)
        for placeholder, actual_marker in image_placeholders.items():
            final_html = final_html.replace(placeholder, actual_marker)
        return final_html, img_counter
    return html_content, img_counter


def parse_markdown_images_from_text(text):
    """
    Finds <<@IMAGE:file|alt>> tags in text, converts them to markdown image links list,
    and returns the cleaned text along with the list of markdown links.
    """
    images = []
    image_matches = re.finditer(r'<<@IMAGE:(.*?)\|(.*?)>>', text)
    for match in image_matches:
        filename, alt = match.group(1), match.group(2)
        images.append(f"![{alt}]({filename})")

    clean_text = re.sub(r"<<@IMAGE:(.*?)>>", "", text).strip()
    return clean_text, images


def extract_images(epub_path):
    """
    CLI endpoint for extracting images independently from the summary generation.
    """
    epub_path = os.path.abspath(epub_path)
    if not os.path.exists(epub_path):
        print(f"Error: EPUB file not found at {epub_path}")
        return

    book = epub.read_epub(epub_path)

    book_folder_name = get_book_output_folder(
        book, default_name="extracted_images"
    )
    output_base_dir = os.path.join(os.path.dirname(epub_path), book_folder_name)
    os.makedirs(output_base_dir, exist_ok=True)
    print(f"Images will be saved in: {output_base_dir}")

    image_map = create_image_map(book)
    print(f"Image map keys: {image_map.keys()}")



    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            # Note: extract_images standalone script is mostly legacy since image extraction
            # is now tightly integrated into utils.merge_and_split_chapters
            html_content = item.get_content().decode("utf-8", errors="ignore")
            extract_and_mark_images(
                html_content, item.get_name(), image_map, output_base_dir, 0
            )

    print("Image extraction complete.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python extract_images.py <path_to_epub_file>")
        sys.exit(1)

    EPUB_FILE = sys.argv[1]
    extract_images(EPUB_FILE)
