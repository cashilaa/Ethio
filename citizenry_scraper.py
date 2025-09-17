import requests
import json
import time
import logging
import os
import csv
import re
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime
from urllib.parse import urljoin, urlparse
import signal

def signal_handler(sig, frame):
    logger.warning("Script interrupted by user via SIGINT (Ctrl+C)")
    print("\nExiting due to user interrupt (Ctrl+C)...")
    os._exit(0)

signal.signal(signal.SIGINT, signal_handler)

load_dotenv()

# Create output directory
output_dir = Path("./citizenry_data")
output_dir.mkdir(exist_ok=True, parents=True)

# Create images directory
images_dir = output_dir / "images"
images_dir.mkdir(exist_ok=True, parents=True)

# Setup logging
log_file = output_dir / f"citizenry_scrape_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logger = logging.getLogger('CitizenryProductScraper')
logger.setLevel(logging.INFO)

fh = logging.FileHandler(log_file)
fh.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
logger.addHandler(fh)

ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(formatter)
logger.addHandler(ch)

API_KEY = os.getenv("FIRECRAWL_API_KEY", "")
if not API_KEY:
    logger.critical("API key not found. Please add your API key to the .env file.")
    exit(1)

FIRECRAWL_API_URL = "https://api.firecrawl.dev/v1/scrape"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
    "User-Agent": "CitizenryProductScraper/1.0"
}

BASE_URL = "https://www.the-citizenry.com"

def make_request_with_retry(url, payload, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=120)
            
            if response.status_code == 429:
                wait_time = int(response.headers.get('Retry-After', 30))
                logger.warning(f"Rate limited. Waiting {wait_time} seconds.")
                time.sleep(wait_time)
                continue
                
            if response.status_code >= 500:
                wait_time = 30 * (2 ** attempt)
                logger.warning(f"Server error {response.status_code}. Waiting {wait_time} seconds.")
                time.sleep(wait_time)
                continue
                
            return response
            
        except requests.exceptions.RequestException as e:
            wait_time = 30 * (2 ** attempt)
            logger.error(f"Request failed: {e}. Waiting {wait_time} seconds.")
            time.sleep(wait_time)
    
    return None

def discover_product_urls():
    """Discover product URLs by scraping multiple collection pages"""
    logger.info("Starting product URL discovery...")
    
    collection_urls = [
        f"{BASE_URL}/collections/all",
        f"{BASE_URL}/collections/accents",
        f"{BASE_URL}/collections/baskets",
        f"{BASE_URL}/collections/bedding",
        f"{BASE_URL}/collections/furniture",
        f"{BASE_URL}/collections/lighting",
        f"{BASE_URL}/collections/rugs",
        f"{BASE_URL}/collections/pillows",
        f"{BASE_URL}/collections/throws",
        f"{BASE_URL}/collections/tabletop",
        f"{BASE_URL}/collections/wall-art",
        f"{BASE_URL}/collections/mirrors"
    ]
    
    all_product_urls = set()
    
    for collection_url in collection_urls:
        logger.info(f"Scraping collection: {collection_url}")
        
        payload = {
            "url": collection_url,
            "formats": ["json"],
            "onlyMainContent": True,
            "jsonOptions": {
                "prompt": "Find all product links on this page. Look for URLs containing '/products/'. Return as JSON: {\"product_urls\": [\"url1\", \"url2\"]}",
                "temperature": 0.0
            }
        }
        
        response = make_request_with_retry(FIRECRAWL_API_URL, payload)
        if response and response.status_code == 200:
            try:
                data = response.json().get('data', {})
                product_data = data.get('json', {}) if 'json' in data else data
                urls = product_data.get('product_urls', [])
                
              
                for url in urls:
                    if url and isinstance(url, str):
                        if url.startswith('/'):
                            url = BASE_URL + url
                        if '/products/' in url:
                            all_product_urls.add(url)
                            
                logger.info(f"Found {len(urls)} products in {collection_url}")
                
            except Exception as e:
                logger.error(f"Error parsing collection {collection_url}: {e}")
        
        time.sleep(1)
    
    product_urls = list(all_product_urls)
    logger.info(f"Discovered {len(product_urls)} unique product URLs from all collections")
    
    if not product_urls:
        logger.warning("No products found in collections, trying fallback method")
        return discover_fallback_urls()
    
    # Remove duplicates and clean URLs
    unique_urls = set()
    for url in product_urls:
        clean_url = url.split('?')[0]  
        unique_urls.add(clean_url)
    
    final_urls = list(unique_urls)
    logger.info(f"Final count after deduplication: {len(final_urls)}")
    return final_urls

def discover_fallback_urls():
    """Fallback method to get some product URLs"""
    logger.info("Using fallback URL discovery")
    
    payload = {
        "url": BASE_URL,
        "formats": ["json"],
        "onlyMainContent": True,
        "jsonOptions": {
            "prompt": "Find all links to product pages (containing '/products/'). Return as JSON: {\"urls\": [\"url1\", \"url2\"]}",
            "temperature": 0.0
        }
    }
    
    response = make_request_with_retry(FIRECRAWL_API_URL, payload)
    if response and response.status_code == 200:
        try:
            data = response.json().get('data', {})
            product_data = data.get('json', {}) if 'json' in data else data
            urls = product_data.get('urls', [])
            
            product_urls = []
            for url in urls:
                if url and '/products/' in str(url):
                    if url.startswith('/'):
                        url = BASE_URL + url
                    product_urls.append(url)
            
            return product_urls 
        except Exception as e:
            logger.error(f"Fallback discovery failed: {e}")
    
    return []

def extract_keywords(text):
    """Extract sustainability/ethical keywords from text"""
    if not text:
        return []
    
    keywords = ['Fairtrade', 'FSC', 'Handmade', 'Artisan', 'Sustainable', 'Organic', 'Eco-friendly']
    found_keywords = []
    
    text_lower = text.lower()
    for keyword in keywords:
        if keyword.lower() in text_lower:
            found_keywords.append(keyword)
    
    return found_keywords

def clean_filename(name):
    """Clean product name for use as filename"""
    if not name:
        return "unknown_product"
    
    cleaned = re.sub(r'[^\w\s-]', '', name)
    cleaned = re.sub(r'[-\s]+', '_', cleaned)
    return cleaned[:50]  

def download_image(image_url, filename):
    """Download product image"""
    try:
        if not image_url:
            return None
        
    
        if image_url.startswith('//'):
            image_url = 'https:' + image_url
        elif image_url.startswith('/'):
            image_url = urljoin(BASE_URL, image_url)
        
        response = requests.get(image_url, timeout=30)
        if response.status_code == 200:
            parsed_url = urlparse(image_url)
            ext = os.path.splitext(parsed_url.path)[1] or '.jpg'
            
            file_path = images_dir / f"{filename}{ext}"
            with open(file_path, 'wb') as f:
                f.write(response.content)
            
            logger.info(f"Downloaded image: {file_path}")
            return str(file_path)
    except Exception as e:
        logger.error(f"Failed to download image {image_url}: {e}")
    
    return None

def scrape_product(product_url):
    """Scrape individual product data"""
    logger.info(f"Scraping product: {product_url}")
    
    payload = {
        "url": product_url,
        "formats": ["json"],
        "onlyMainContent": True,
        "jsonOptions": {
            "prompt": """
            Extract product information in JSON format:
            {
                "name": "product title/name",
                "current_price": "current price",
                "original_price": "original price if discounted, null if not",
                "description": "full product description text",
                "images": ["array of image URLs"],
                "colors_sizes": ["array of available colors/sizes/variants"],
                "upsells": ["array of related/recommended products or 'complete the set' items"],
                "sustainability_text": "any text mentioning sustainability, ethical sourcing, handmade, artisan, etc."
            }
            Return null for missing fields.
            """,
            "temperature": 0.0
        }
    }
    
    response = make_request_with_retry(FIRECRAWL_API_URL, payload)
    if not response or response.status_code != 200:
        logger.error(f"Failed to scrape {product_url}")
        return None
    
    try:
        data = response.json().get('data', {})
        if not data:
            return None
        
        # Extract product info
        product_data = data.get('json', {}) if 'json' in data else data
        
        name = product_data.get('name', 'Unknown Product')
        current_price = product_data.get('current_price', '')
        original_price = product_data.get('original_price', '')
        description = product_data.get('description', '')
        images = product_data.get('images', [])
        colors_sizes = product_data.get('colors_sizes', [])
        upsells = product_data.get('upsells', [])
        sustainability_text = product_data.get('sustainability_text', '')
        
        # Extract keywords
        full_text = f"{name} {description} {sustainability_text}"
        keywords = extract_keywords(full_text)
        
        # Format price
        price_display = current_price
        if original_price and original_price != current_price:
            price_display = f"{current_price} (was {original_price})"
        
        # Download first image
        image_path = None
        if images and len(images) > 0:
            clean_name = clean_filename(name)
            image_path = download_image(images[0], clean_name)
        
        # Format arrays as comma-separated strings
        keywords_str = ', '.join(keywords) if keywords else ''
        colors_sizes_str = ', '.join(colors_sizes) if colors_sizes else ''
        upsells_str = ', '.join(upsells) if upsells else ''
        
        return {
            'Name': name,
            'Price': price_display,
            'Description of product': description,
            'Original URL': product_url,
            'Keywords': keywords_str,
            'Stretch goals': upsells_str,
            'Alternative sizes or colors available': colors_sizes_str,
            'Image Path': image_path or ''
        }
        
    except Exception as e:
        logger.error(f"Error processing product data for {product_url}: {e}")
        return None

def save_to_csv(products, filename):
    """Save products to CSV file"""
    if not products:
        logger.warning("No products to save")
        return
    
    csv_file = output_dir / filename
    
    fieldnames = [
        'Name', 
        'Price', 
        'Description of product', 
        'Original URL', 
        'Keywords', 
        'Stretch goals', 
        'Alternative sizes or colors available'
    ]
    
    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for product in products:
            row = {field: product.get(field, '') for field in fieldnames}
            writer.writerow(row)
    
    logger.info(f"Saved {len(products)} products to {csv_file}")

def main():
    logger.info("Starting Citizenry product scraper")
    
  
    product_urls = discover_product_urls()
    
    if not product_urls:
        logger.error("No product URLs found")
        return
    
    logger.info(f"Found {len(product_urls)} products to scrape")
    
    products = []
    failed_count = 0
    
    for i, url in enumerate(product_urls, 1):
        logger.info(f"Processing product {i}/{len(product_urls)}")
        
        product_data = scrape_product(url)
        if product_data:
            products.append(product_data)
            logger.info(f"Successfully scraped: {product_data['Name']}")
        else:
            failed_count += 1
            logger.warning(f"Failed to scrape: {url}")
        
        time.sleep(2)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_filename = f"citizenry_products_{timestamp}.csv"
    save_to_csv(products, csv_filename)
    
    json_filename = f"citizenry_products_detailed_{timestamp}.json"
    json_file = output_dir / json_filename
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(products, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Scraping completed. Success: {len(products)}, Failed: {failed_count}")
    logger.info(f"Results saved to {csv_filename} and {json_filename}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.warning("Script interrupted by user")
    except Exception as e:
        logger.critical(f"Unhandled exception: {e}", exc_info=True)
