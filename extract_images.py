import ebooklib
from ebooklib import epub
import os
import re
import sys
from bs4 import BeautifulSoup
from utils import sanitize_filename, get_book_output_folder, get_chapter_identifier



def extract_images(epub_path):
    epub_path = sys.argv[1]
    epub_path = epub_path.replace('\\', '') # Remove literal backslashes
    print(f"Raw epub_path from sys.argv[1]: {epub_path}")
    epub_path = os.path.abspath(epub_path)
    epub_path = os.path.normpath(epub_path)
    if not os.path.exists(epub_path):
        print(f"Error: EPUB file not found at {epub_path}")
        return

    book = epub.read_epub(epub_path)

    book_folder_name = get_book_output_folder(book, default_name="extracted_images")
    output_base_dir = os.path.join(os.path.dirname(epub_path), book_folder_name)
    os.makedirs(output_base_dir, exist_ok=True)
    print(f"Images will be saved in: {output_base_dir}")

    chapter_image_counts = {}
    image_map = {}

    # First pass: Identify all images and store their content
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
    print(f"Image map keys: {image_map.keys()}")

    # Second pass: Iterate through document items (chapters) to associate images
    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            chapter_name = item.get_name()
            # Aggressively clean the name for better identifier matching
            simplified_name = chapter_name.lower()
            simplified_name = simplified_name.replace('text/', '')
            simplified_name = simplified_name.replace('xhtml/', '')
            simplified_name = simplified_name.replace('.xhtml', '')
            simplified_name = re.sub(r'_epub3_.*_r\d+', '', simplified_name) # Remove _epub3_..._rX patterns
            simplified_name = re.sub(r'_r\d+', '', simplified_name) # Remove _rX patterns
            simplified_name = re.sub(r'^bloo_\d+_', '', simplified_name) # Remove bloo_..._ prefixes
            
            chapter_identifier = get_chapter_identifier(chapter_name)

            chapter_image_counts[chapter_identifier] = chapter_image_counts.get(chapter_identifier, 0)
            
            soup = BeautifulSoup(item.get_content(), 'html.parser')
            images_in_chapter = soup.find_all('img')
            
            for img_tag in images_in_chapter:
                src = img_tag.get('src')
                if src:
                    # Clean up src to match item names (remove leading ../)
                    cleaned_src = src.lstrip('../')
                    
                    if cleaned_src in image_map:
                        chapter_image_counts[chapter_identifier] = chapter_image_counts.get(chapter_identifier, 0) + 1
                        image_count_for_chapter = chapter_image_counts[chapter_identifier]
                        
                        ext = cleaned_src.split('.')[-1]
                        image_filename = f"{chapter_identifier}_image_{image_count_for_chapter}.{ext}"
                        image_path = os.path.join(output_base_dir, image_filename)
                        
                        try:
                            with open(image_path, 'wb') as img_file:
                                img_file.write(image_map[cleaned_src])
                            print(f"Extracted image: {image_filename} from {chapter_name}")
                        except Exception as e:
                            print(f"Error extracting image {cleaned_src} from {chapter_name}: {e}")

    print(f"Image extraction complete.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python extract_images.py <path_to_epub_file>")
        sys.exit(1)
    
    epub_file = sys.argv[1]
    extract_images(epub_file)