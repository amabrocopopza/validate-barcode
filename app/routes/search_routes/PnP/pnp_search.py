# app/routes/search_routes/PnP/pnp_search.py

from flask import Blueprint, request, jsonify, current_app, flash, redirect

from .pnp_api import fetch_product_details, fetch_product_suggestions
from ....utils.workflow import finalize_product, mark_product_as_not_matched, skip_product
from ....utils.inventory import load_inventory, save_inventory



from ....utils.auth import auth  # Import centralized auth

pnp_bp = Blueprint('pnp', __name__, url_prefix='/pnp')

@pnp_bp.route('/handle_action', methods=['GET'])
@auth.login_required
def handle_action():
    """
    Handle actions ('yes', 'no', 'skip') specific to PNP search.
    """
    try:
        action = request.args.get('action')
        sku = request.args.get('sku')

        if not action or not sku:
            flash("Missing action or SKU.", 'danger')
            return redirect(url_for('main.index'))

        # Load main inventory
        main_inventory = load_inventory(current_app.config['S3_KEY_MAIN_INVENTORY'], inventory_type='main')

        # Find the product by SKU
        product = main_inventory[main_inventory['sku'] == sku]
        if product.empty:
            flash(f"Product with SKU '{sku}' not found in inventory.", 'danger')
            return redirect(url_for('main.index'))

        idx = product.index[0]
        assigned_to = main_inventory.at[idx, 'assigned_to']
        current_user = session.get('user_id')

        # Ensure that only the user who is processing can perform actions
        if assigned_to != current_user:
            current_app.logger.warning(f"User '{current_user}' attempted to modify SKU '{sku}' not assigned to them.")
            flash("You do not have permission to modify this item.", 'danger')
            return redirect(url_for('main.index'))

        # Delegate actions to workflow functions
        if action == 'yes':
            return finalize_product(sku, idx, main_inventory)
        elif action == 'no':
            return mark_product_as_not_matched(sku, idx, main_inventory)
        elif action == 'skip':
            return skip_product(sku, idx, main_inventory)
        else:
            flash("Invalid action.", 'danger')
            return redirect(url_for('main.index'))

    except Exception as e:
        current_app.logger.error(f"An error occurred in handle_action: {str(e)}")
        flash("An unexpected error occurred. Please try again later.", 'danger')
        return redirect(url_for('main.index'))

@pnp_bp.route('/fetch_barcode', methods=['POST'])
@auth.login_required
def fetch_barcode():
    """
    Fetch barcode for a given product code and return additional details specific to PNP.
    """
    try:
        product_code = request.form.get('product_code')
        if not product_code:
            current_app.logger.warning("No product code provided in fetch_barcode request.")
            return jsonify({'success': False, 'message': 'No product code provided.'}), 400

        current_app.logger.info(f"Fetching details for product_code: {product_code}")
        product_details = fetch_product_details(product_code)
        if not product_details:
            current_app.logger.error(f"Failed to fetch product details for product_code: {product_code}")
            return jsonify({'success': False, 'message': 'Failed to fetch product details.'}), 500

        # Extract fields from top-level
        description = product_details.get('description', 'No description available.')
        brand = product_details.get('brand', 'N/A')
        brandSellerId = product_details.get('brandSellerId', 'N/A')
        defaultUnitOfMeasure = product_details.get('defaultUnitOfMeasure', 'N/A')
        barcode = product_details.get('barcode', None)
        product_name = product_details.get('name', 'N/A')  # Ensure 'name' field exists

        if not barcode:
            # Attempt to extract barcode from nested fields if top-level is missing
            display_info = product_details.get('productDetailsDisplayInfoResponse', {}).get('productDetailDisplayInfos', [])
            if display_info:
                for info in display_info:
                    for field in info.get('displayInfoFields', []):
                        if field.get('name') == 'Barcode':
                            barcode = field.get('values', [{}])[0].get('value', None)
                            break
            if not barcode:
                current_app.logger.warning(f"Barcode not found for product_code: {product_code}")
                return jsonify({'success': False, 'message': 'Barcode not found.'}), 404

        # Extract all images matching "format": "zoom" and "imageType": "PRIMARY"
        image_urls = []
        images = product_details.get('images', [])
        if isinstance(images, list):
            for img in images:
                if isinstance(img, dict):
                    url = img.get('url')
                    if url:
                        image_urls.append(url)
                elif isinstance(img, str):
                    image_urls.append(img)
        elif isinstance(images, str):
            image_urls.append(images)

        # Load main inventory to get Retail Price
        main_inventory = load_inventory(current_app.config['S3_KEY_MAIN_INVENTORY'])
        # Assuming 'sku' is the identifier in main_inventory and 'retail_price' is the column name
        sku = product_details.get('sku') or product_code  # Adjust based on actual data structure
        retail_price = main_inventory.loc[main_inventory['sku'] == sku, 'retail_price'].values
        if len(retail_price) > 0:
            retail_price = float(retail_price[0])
        else:
            retail_price = 0.0  # Default value if not found



        # Extract formatted price from product_details
        price_formatted = product_details.get('price', {}).get('formattedValue', 'R0.00')
        # Extract numerical price for calculation
        price_value = product_details.get('price', {}).get('value', 0.0)
        price_value = float(price_value) if price_value else 0.0

        return jsonify({
            'success': True,
            'barcode': barcode,
            'description': description,
            'brand': brand,
            'brandSellerId': brandSellerId,
            'defaultUnitOfMeasure': defaultUnitOfMeasure,
            'imageUrls': image_urls,
            'product_name': product_name,
            'price_formatted': price_formatted,
            'price_value': price_value,
        }), 200

    except Exception as e:
        current_app.logger.error(f"An error occurred while fetching barcode for product_code={product_code}: {str(e)}")
        return jsonify({'success': False, 'message': 'An error occurred while fetching barcode.'}), 500
    
    
@pnp_bp.route('/search', methods=['POST'])
@auth.login_required
def search():
    """
    Handle AJAX search requests and return product suggestions.
    """
    try:
        search_term = request.form.get('search_term', '').strip()
        current_app.logger.debug(f"Search term received: {search_term}")

        if not search_term:
            current_app.logger.warning("No search term provided.")
            return jsonify({'success': False, 'message': 'No search term provided.'}), 400

        suggestions = fetch_product_suggestions(search_term)
        current_app.logger.debug(f"Suggestions fetched: {suggestions}")

        if not suggestions:
            current_app.logger.info("No suggestions found.")
            return jsonify({'success': False, 'message': 'No suggestions found.'}), 404

        # Process suggestions
        processed_suggestions = []        
        for p in suggestions:
            processed = {
                'name': p.get('name', 'N/A'),
                'code': p.get('code', ''),
                'price': p.get('price', {}).get('formattedValue', 'N/A'),
                'images': p.get('images', []),
                'description': p.get('description', ''),

            }
            processed_suggestions.append(processed)
            current_app.logger.debug(f"Processed suggestion: {processed}")

        return jsonify({'success': True, 'products': processed_suggestions}), 200

    except Exception as e:
        current_app.logger.error(f"An error occurred in search route: {str(e)}")
        return jsonify({'success': False, 'message': 'An internal error occurred.'}), 500    