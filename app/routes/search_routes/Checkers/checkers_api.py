# app/routes/search_routes/Checkers/checkers_api.py

import requests
from bs4 import BeautifulSoup
import json
from flask import current_app as app

# Initialize the session
session = requests.Session()

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
    'Accept-Language': 'en-US,en;q=0.9',
    # Include any necessary cookies or other headers
}

BASE_URL = 'https://www.checkers.co.za'

def fetch_product_suggestions(term):
    # Initial request to get cookies
    try:
        session.get(BASE_URL, headers=HEADERS)
    except requests.RequestException as e:
        app.logger.error(f"Failed to perform initial request to Checkers: {str(e)}")
        return []

    search_url = f"{BASE_URL}/search/all?q={term}"
    try:
        response = session.get(search_url, headers=HEADERS)
        response.raise_for_status()
    except requests.RequestException as e:
        app.logger.error(f"Failed to fetch search results from Checkers: {str(e)}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    products = soup.find_all('div', class_='product-frame', limit=10)

    results = []
    for product in products:
        data = product.get('data-product-ga', '{}')
        try:
            product_data = json.loads(data)
            name = product_data.get('name')
            price = product_data.get('price')
            href = product.find('a', href=True)['href']
            results.append({'name': name, 'price': price, 'href': href})
        except json.JSONDecodeError:
            continue
        except Exception:
            continue
    return results

def fetch_product_details(href):
    product_url = f"{BASE_URL}{href}"
    try:
        response = session.get(product_url, headers=HEADERS)
        response.raise_for_status()
    except requests.RequestException as e:
        app.logger.error(f"Failed to fetch product details from Checkers: {str(e)}")
        return None

    soup = BeautifulSoup(response.text, 'html.parser')

    product_info = {}

    # Extract product details
    table = soup.find('table', class_='pdp__product-information')
    if table:
        for row in table.find_all('tr'):
            cols = row.find_all('td')
            if len(cols) >= 2:
                key = cols[0].get_text(strip=True)
                value = cols[1].get_text(strip=True)
                if key == 'Main Barcode':
                    product_info['barcode'] = value
                elif key == 'Product Brand':
                    product_info['product_brand'] = value
                elif key == 'Unit of Measure':
                    product_info['unit_of_measure'] = value

    # Extract product name
    product_name_tag = soup.find('h1', class_='pdp__name')
    if product_name_tag:
        product_info['product_name'] = product_name_tag.get_text(strip=True)

    # Extract product price
    product_price_tag = soup.find('span', class_='now')
    if product_price_tag:
        product_info['product_price'] = product_price_tag.get_text(strip=True).replace('R', '')

    # Extract description
    description_div = soup.find('div', class_='pdp__description')
    if description_div:
        product_info['description'] = description_div.get_text(strip=True)

    # Extract image URL and category from dataLayer
    script_tags = soup.find_all('script', text=lambda t: t and 'dataLayer.push' in t)
    for script_tag in script_tags:
        try:
            script_content = script_tag.string
            # Extract the content inside dataLayer.push(...)
            data_layer_content = script_content.split('dataLayer.push(')[1].split(');')[0]
            # Replace single quotes with double quotes
            data_layer_content = data_layer_content.replace("'", '"')
            # Remove trailing commas (invalid in JSON)
            data_layer_content = data_layer_content.replace(',}', '}').replace(',]', ']')
            # Parse the JSON
            data_layer_json = json.loads(data_layer_content)
            ecommerce_detail = data_layer_json.get('ecommerce', {}).get('detail', {})
            products = ecommerce_detail.get('products', [])
            if products:
                product_data = products[0]
                product_info['category'] = product_data.get('category', 'N/A')
                product_info['product_image_url'] = product_data.get('product_image_url', 'N/A')
                break  # Found the data, no need to continue
        except Exception as e:
            app.logger.error(f"Error parsing dataLayer in Checkers product page: {str(e)}")
            continue

    # If still no image, try to extract from meta tags
    if 'product_image_url' not in product_info or product_info['product_image_url'] == 'N/A':
        meta_image = soup.find('meta', property='og:image')
        if meta_image and meta_image.get('content'):
            product_info['product_image_url'] = meta_image['content']

    return product_info
