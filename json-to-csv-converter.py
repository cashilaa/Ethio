import json
import csv
import os
import glob
from pathlib import Path
from datetime import datetime

def clean_description(description):
    """
    Clean product description by removing reviews, shipping info, and other unnecessary content
    """
    if not description:
        return ''
    
    sections_to_remove = [
        '### Story',
        '### Product Details', 
        '### Care',
        '### Shipping',
        '### Returns',
        'Customer Reviews',
        'Write a Review',
        'Shipping',
        'Returns',
        'Easy 30 Day Returns',
        'In stock. Ready to ship.',
        'Translation missing:',
        'Add To Bag',
        'Your email address',
        'Want early access',
        'Ships ',
        'Most in-stock items',
        'Exchanges and returns',
        'White glove delivery',
        'For more information',
        'Customer Photos',
        'Ask a Question',
        'Based on',
        'Reviews',
        'Was this helpful?',
        'United States',
        'Loading more...',
        'Filter Reviews:',
        'Sort'
    ]
    
    # Find the first occurrence of any section marker
    clean_desc = description
    for marker in sections_to_remove:
        if marker in clean_desc:
            clean_desc = clean_desc.split(marker)[0]
    
    clean_desc = clean_desc.replace('\n\n', ' ').replace('\n', ' ')
    clean_desc = ' '.join(clean_desc.split()) 
    
    return clean_desc.strip()

def clean_price(price):
    """
    Clean price format
    """
    if not price:
        return ''
    return price.replace(' (was null)', '')

def convert_citizenry_json_to_csv(json_file_path, output_csv_path=None):
    """
    Convert citizenry_products_detailed_{timestamp}.json to CSV format
    """
    if not output_csv_path:
        json_path = Path(json_file_path)
        output_csv_path = json_path.parent / f"{json_path.stem}_cleaned.csv"
    
    try:
        # Read JSON file
        with open(json_file_path, 'r', encoding='utf-8') as f:
            products = json.load(f)
        
        if not products:
            print("No products found in JSON file")
            return
        
        # Define CSV headers
        fieldnames = [
            'Name',
            'Price', 
            'Description of product',
            'Original URL',
            'Keywords',
            'Stretch goals',
            'Alternative sizes or colors available'
        ]
        
        # Write to CSV
        with open(output_csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for product in products:
                row = {
                    'Name': product.get('Name', ''),
                    'Price': clean_price(product.get('Price', '')),
                    'Description of product': clean_description(product.get('Description of product', '')),
                    'Original URL': product.get('Original URL', ''),
                    'Keywords': product.get('Keywords', ''),
                    'Stretch goals': product.get('Stretch goals', ''),
                    'Alternative sizes or colors available': product.get('Alternative sizes or colors available', '')
                }
                writer.writerow(row)
        
        print(f"Successfully converted {len(products)} products to CSV: {output_csv_path}")
        
    except Exception as e:
        print(f"Error converting JSON to CSV: {e}")

def main():
    print("Citizenry Products JSON to CSV Converter")
    print("-" * 50)
    
    json_files = glob.glob("citizenry_products_detailed_*.json")
    json_files.extend(glob.glob("citizenry_data/citizenry_products_detailed_*.json"))
    
    if not json_files:
        json_file = input("Enter path to citizenry_products_detailed_*.json file: ").strip()
        if not os.path.exists(json_file):
            print(f"File not found: {json_file}")
            return
        json_files = [json_file]
    
    for json_file in json_files:
        print(f"Processing: {json_file}")
        convert_citizenry_json_to_csv(json_file)

if __name__ == "__main__":
    main()