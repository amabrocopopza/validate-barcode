# app/utils/api.py

import requests
from flask import current_app as app

def fetch_product_suggestions(product_name):
    """
    Fetch product suggestions based on the product name.
    """
    url = "https://www.pnp.co.za/pnphybris/v2/pnp-spa/products/suggestions"
    params = {
        'term': product_name,
        'maxSuggestions': 10,
        'maxProducts': 10,
        'storeCode': 'WC44',
        'lang': 'en',
        'curr': 'ZAR'
    }
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        return data.get('products', [])
    except requests.RequestException as e:
        app.logger.error(f"Failed to fetch product suggestions: {str(e)}")
        return []

def fetch_product_details(code):
    """
    Fetch product details based on the product code.
    """
    url = f"https://www.pnp.co.za/pnphybris/v2/pnp-spa/products/{code}"
    params = {
        'fields': 'DEFAULT,productDetailsDisplayInfoResponse,quantityType',
        'storeCode': 'WC44',
        'scope': 'list',
        'lang': 'en',
        'curr': 'ZAR'
    }
    headers = {
        'accept': 'application/json, text/plain, */*',
        'accept-language': 'en-GB,en;q=0.8',
        'priority': 'u=1, i',
        'referer': f'https://www.pnp.co.za/All-Products/Beverages/Water/Sparkling-Flavoured-Water/aquelle-watermelon-sparkling-drink-500ml/p/{code}'
    }
    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data
    except requests.RequestException as e:
        app.logger.error(f"Failed to fetch product details for code {code}: {str(e)}")
        return None
