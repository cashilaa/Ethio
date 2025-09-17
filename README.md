# The Citizenry Product Scraper

This script scrapes product data from https://www.the-citizenry.com/ using FireCrawl API.

## Features

- **Product Discovery**: Automatically discovers all product URLs on the website
- **Data Extraction**: Extracts product name, price, description, images, and variants
- **Keyword Detection**: Identifies sustainability/ethical keywords (Fairtrade, FSC, Handmade, etc.)
- **Image Download**: Downloads product images with clean filenames
- **CSV Output**: Saves results in CSV format with required headers
- **Error Handling**: Robust retry logic and error handling

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create a `.env` file with your FireCrawl API key:
```
FIRECRAWL_API_KEY=your_api_key_here
```

## Usage

Run the scraper:
```bash
python citizenry_scraper.py
```

## Output

The scraper creates:
- `citizenry_data/` directory with all output files
- `citizenry_products_detailed_YYYYMMDD_HHMMSS.json` - Detailed JSON data
- `images/` subdirectory with downloaded product images
- Log file with scraping details

## CSV Columns

- Name
- Price (includes original price if discounted)
- Description of product
- Original URL
- Keywords (sustainability/ethical tags)
- Stretch goals (upsells/recommendations)
- Alternative sizes or colors available

## Rate Limiting

The scraper includes built-in rate limiting (2-second delays) to be respectful to the website.