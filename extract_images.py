
import ebooklib
from ebooklib import epub
import os
import re
import sys
from bs4 import BeautifulSoup
from utils import sanitize_filename, get_book_output_folder, get_chapter_identifier

def create_image_map(book):
    """Creates a map of all images in the EPUB, mapping their internal paths to their content."""
    image_map = {}
    for item in book.get_items():
        is_image = False
        if item.get_type() == ebooklib.ITEM_IMAGE or item.get_type() == ebooklib.ITEM_COVER:
            is_image = True
        elif hasattr(item, 'get_media_type') and item.get_media_type() and item.get_media_type().startswith('image/'):
            is_image = True
        elif item.get_name().lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.svg', '.bmp')):
            is_image = True

        if is_image:
            image_map[item.get_name()] = item.get_content()
    return image_map

def extract_chapter_images_and_context(chapter_item, image_map, output_dir, chapter_image_counts):
    """Extracts images from a chapter, saves them, and returns their context."""
    image_context = []
    chapter_identifier = get_chapter_identifier(chapter_item.get_name())
    soup = BeautifulSoup(chapter_item.get_content(), 'html.parser')
    images_in_chapter = soup.find_all('img')

    for img_tag in images_in_chapter:
        src = img_tag.get('src')
        if src:
            cleaned_src = src.lstrip('../')
            if cleaned_src in image_map:
                chapter_image_counts[chapter_identifier] = chapter_image_counts.get(chapter_identifier, 0) + 1
                image_count_for_chapter = chapter_image_counts[chapter_identifier]
                ext = cleaned_src.split('.')[-1]
                image_filename = f"{chapter_identifier}_image_{image_count_for_chapter}.{ext}"
                image_path = os.path.join(output_dir, image_filename)

                try:
                    with open(image_path, 'wb') as img_file:
                        img_file.write(image_map[cleaned_src])
                    print(f"Extracted image: {image_filename} from {chapter_item.get_name()}")
                    image_context.append({
                        "image_path": image_path,
                        "context_text": img_tag.get('alt', '')
                    })
                except Exception as e:
                    print(f"Error extracting image {cleaned_src} from {chapter_item.get_name()}: {e}")
    return image_context

def extract_images(epub_path):
    epub_path = os.path.abspath(epub_path)
    if not os.path.exists(epub_path):
        print(f"Error: EPUB file not found at {epub_path}")
        return

    book = epub.read_epub(epub_path)

    book_folder_name = get_book_output_folder(book, default_name="extracted_images")
    output_base_dir = os.path.join(os.path.dirname(epub_path), book_folder_name)
    os.makedirs(output_base_dir, exist_ok=True)
    print(f"Images will be saved in: {output_base_dir}")

    image_map = create_image_map(book)
    print(f"Image map keys: {image_map.keys()}")

    chapter_image_counts = {}
    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            extract_chapter_images_and_context(item, image_map, output_base_dir, chapter_image_counts)

    print(f"Image extraction complete.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python extract_images.py <path_to_epub_file>")
        sys.exit(1)
    
    epub_file = sys.argv[1]
    extract_images(epub_file)
