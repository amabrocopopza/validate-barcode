# app/routes/suggestions.py

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash
from ..utils.inventory import load_inventory, save_inventory
from ..utils.api import fetch_product_details
import os
import pandas as pd

suggestions_bp = Blueprint('suggestions', __name__)
auth = HTTPBasicAuth()

# Retrieve username and password from environment variables
BASIC_AUTH_USERNAME = os.getenv('BASIC_AUTH_USERNAME')
BASIC_AUTH_PASSWORD = os.getenv('BASIC_AUTH_PASSWORD')

# Ensure that username and password are set
if not BASIC_AUTH_USERNAME or not BASIC_AUTH_PASSWORD:
    raise ValueError("BASIC_AUTH_USERNAME and BASIC_AUTH_PASSWORD must be set in environment variables.")

# Create a hashed password
users = {
    BASIC_AUTH_USERNAME: generate_password_hash(BASIC_AUTH_PASSWORD)
}

@auth.verify_password
def verify_password(username, password):
    if username in users and check_password_hash(users.get(username), password):
        return username

@suggestions_bp.route('/select_suggestion', methods=['POST'])
@auth.login_required
def select_suggestion():
    try:
        selected_code = request.form.get('selected_code')
        sku = request.form.get('sku')  # Original SKU from the 'No' action
        product_name = request.form.get('product_name')  # Get the product name if passed

        if not selected_code or not sku:
            flash("Invalid selection.", 'danger')
            return redirect(url_for('main.index'))

        # Fetch product details using the selected code
        product_details = fetch_product_details(selected_code)

        if not product_details:
            flash("Failed to retrieve product details.", 'danger')
            return redirect(url_for('main.index'))

        # Extract barcode from product details
        barcode = None
        try:
            # Navigate the JSON to find the barcode
            product_info = product_details['productDetailsDisplayInfoResponse']['productDetailDisplayInfos'][0]['displayInfoFields']
            for field in product_info:
                if field['name'] == 'Barcode':
                    barcode = field['values'][0]['value']
                    break
        except (KeyError, IndexError, TypeError) as e:
            current_app.logger.error(f"Failed to extract barcode: {str(e)}")

        if not barcode:
            flash("Barcode not found for the selected product.", 'warning')
            return redirect(url_for('main.index'))

        # Update the main_inventory with the retrieved barcode
        main_inventory = load_inventory(current_app.config['S3_KEY_MAIN_INVENTORY'], inventory_type='main')
        product = main_inventory[main_inventory['sku'] == sku]
        if not product.empty:
            idx = product.index[0]
            main_inventory.at[idx, 'barcode'] = str(barcode)  # Ensure barcode is a string
            main_inventory.at[idx, 'processed'] = True
            main_inventory.at[idx, 'processing'] = False
            main_inventory.at[idx, 'assigned_to'] = None
            main_inventory.at[idx, 'processing_timestamp'] = pd.NaT
            current_app.logger.info(f"Updated barcode for SKU '{sku}' with barcode '{barcode}'.")

            # Now move the product to finalized_inventory
            finalized_inventory = load_inventory(current_app.config['S3_KEY_FINALIZED_INVENTORY'], inventory_type='finalized')

            # Select the row to append as a DataFrame
            row_to_append = main_inventory.loc[[idx]]

            # Define columns to include
            COLUMNS_TO_INCLUDE = [
                'id', 'handle', 'sku', 'composite_name', 'composite_sku', 'composite_quantity',
                'product_name', 'matched_name', 'confidence_score', 'description',
                'product_category', 'variant_option_one_name', 'variant_option_one_value',
                'variant_option_two_name', 'variant_option_two_value', 'variant_option_three_name',
                'variant_option_three_value', 'tags', 'supply_price', 'retail_price',
                'tax_name', 'tax_value', 'account_code', 'account_code_purchase',
                'brand_name', 'supplier_name', 'supplier_code', 'active',
                'track_inventory', 'inventory_main_outlet', 'reorder_point_main_outlet',
                'restock_level_main_outlet', 'barcode'
            ]
            row_to_append = row_to_append[COLUMNS_TO_INCLUDE]

            if finalized_inventory.empty:
                # Initialize finalized_inventory with the row to append
                finalized_inventory = row_to_append.copy()
                current_app.logger.info("Initialized finalized_inventory with the first product.")
            else:
                # Concatenate the existing finalized_inventory with the new row
                finalized_inventory = pd.concat([finalized_inventory, row_to_append], ignore_index=True)
                current_app.logger.info(f"Appended product '{sku}' to finalized_inventory.")

            # Remove from main_inventory
            main_inventory = main_inventory.drop(idx).reset_index(drop=True)
            current_app.logger.info(f"Finalized and removed product '{sku}' from main inventory.")

            # Save both inventories
            save_inventory(finalized_inventory, current_app.config['S3_KEY_FINALIZED_INVENTORY'])
            save_inventory(main_inventory, current_app.config['S3_KEY_MAIN_INVENTORY'])

            # Store action in session for potential undo
            session['last_action'] = {
                'action': 'select_suggestion',
                'sku': sku,
                'barcode': barcode,
                'row_data': row_to_append.to_dict(orient='records')[0]
            }

            flash(f"Product '{sku}' has been finalized with barcode '{barcode}' and moved to the finalized inventory.", 'success')
        else:
            flash(f"Product with SKU '{sku}' not found in inventory.", 'danger')

        return redirect(url_for('main.index'))

    except Exception as e:
        current_app.logger.error(f"An error occurred during suggestion selection: {str(e)}")
        flash("An unexpected error occurred. Please try again later.", 'danger')
        return redirect(url_for('main.index'))
