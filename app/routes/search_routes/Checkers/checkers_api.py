# app/routes/search_routes/Checkers/checkers_api.py

import requests
from bs4 import BeautifulSoup
import json
from flask import current_app as app

# Initialize the session
session = requests.Session()

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)'
                  ' Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0',
    'Cookie': 'AWSALB=8/Jk+FdAYElUmDGee3WL3nCPkzZ+0BA4ZEMJ+0p0hQF6M5AQVYXByUWQtrqodEWWHbMjQdU7/'
              'UdlK9/ru7eQW0SIdaOuQ6qKNBR+154yOHfEim6UnLGr+iOxd6GL; AWSALBCORS=8/Jk+FdAYElUmDGee3WL3nCPkzZ+0BA4ZEMJ+0p0hQF6M5AQVYXByUWQtrqodEWWHbMjQdU7/'
              'UdlK9/ru7eQW0SIdaOuQ6qKNBR+154yOHfEim6UnLGr+iOxd6GL; JSESSIONID=Y24-d171c19f-6a57-4b34-af12-c5ba193ea188; '
              'anonymous-consents=%5B%5D; checkersZA-preferredStore=57861; cookie-notification=NOT_ACCEPTED'
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

    # Extract barcode, product brand, unit of measure, product name, and price
    table = soup.find('table', class_='pdp__product-information')
    barcode, product_brand, unit_of_measure, product_name, product_price = None, None, None, None, None

    if table:
        for row in table.find_all('tr'):
            cols = row.find_all('td')
            if len(cols) >= 2:
                key = cols[0].get_text(strip=True)
                value = cols[1].get_text(strip=True)

                if key == 'Main Barcode':
                    barcode = value
                elif key == 'Product Brand':
                    product_brand = value
                elif key == 'Unit of Measure':
                    unit_of_measure = value

    # Extract product name and price
    product_name_tag = soup.find('h1', class_='pdp__name')
    if product_name_tag:
        product_name = product_name_tag.get_text(strip=True)

    product_price_tag = soup.find('span', class_='now')
    if product_price_tag:
        product_price = product_price_tag.get_text(strip=True).replace('R', '')

    # Extract description
    description = None
    description_div = soup.find('div', class_='pdp__description')
    if description_div:
        description = description_div.get_text(strip=True)

    # Extract category and product image URL from dataLayer
    category, product_image_url = None, None
    script_tag = soup.find('script', text=lambda t: t and 'dataLayer.push' in t)

    if script_tag:
        try:
            data = script_tag.string.split('dataLayer.push(')[1].split(');')[0]
            data = data.replace("'", '"')  # Convert single quotes to double quotes
            product_data = json.loads(data)['ecommerce']['detail']['products'][0]
            category = product_data.get('category', 'N/A')
            product_image_url = product_data.get('product_image_url', 'N/A')
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            app.logger.error(f"Error parsing dataLayer: {e}")

    # Return all collected product information
    product_info = {
        'barcode': barcode or 'N/A',
        'product_brand': product_brand or 'N/A',
        'unit_of_measure': unit_of_measure or 'N/A',
        'description': description or 'N/A',
        'category': category or 'N/A',
        'product_image_url': product_image_url or 'N/A',
        'product_name': product_name or 'N/A',
        'product_price': product_price or 'N/A'
    }

    return product_info
