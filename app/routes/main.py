# app/routes/main.py

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash
from ..utils.inventory import load_inventory, save_inventory, reset_stale_processing
from ..utils.api import fetch_product_suggestions
from datetime import datetime
import os
import pandas as pd

main_bp = Blueprint('main', __name__)
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

PROCESSING_TIMEOUT = 600  # 10 minutes in seconds

@main_bp.route('/', methods=['GET', 'POST'])
@auth.login_required
def index():
    try:
        # Load main inventory using the configured S3 key
        main_inventory = load_inventory(current_app.config['S3_KEY_MAIN_INVENTORY'], inventory_type='main')

        # Reset stale processing flags
        reset_stale_processing(main_inventory)

        if request.method == 'POST':
            action = request.form['action']
            sku = request.form.get('sku')

            # Find the product by SKU
            product = main_inventory[main_inventory['sku'] == sku]
            if not product.empty:
                idx = product.index[0]
                assigned_to = main_inventory.at[idx, 'assigned_to']
                current_user = session.get('user_id')

                # Ensure that only the user who is processing can perform actions
                if assigned_to != current_user:
                    current_app.logger.warning(f"User '{current_user}' attempted to modify SKU '{sku}' not assigned to them.")
                    flash("You do not have permission to modify this item.", 'danger')
                    return redirect(url_for('main.index'))

                if action == 'yes':
                    # Handle 'Yes' action
                    # Load finalized inventory
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
                        'action': 'yes',
                        'sku': sku,
                        'row_data': row_to_append.to_dict(orient='records')[0]
                    }

                    flash(f"Product '{sku}' has been finalized and moved to the finalized inventory.", 'success')

                elif action == 'no':
                    # Handle 'No' action
                    product_name = main_inventory.at[idx, 'product_name']

                    # Fetch product suggestions from Pnp
                    suggestions = fetch_product_suggestions(product_name)

                    if not suggestions:
                        flash("No suggestions found for the product.", 'warning')
                        # Proceed to mark as not matched
                        original_data = main_inventory.loc[idx].to_dict()

                        main_inventory.at[idx, 'matched_name'] = None
                        main_inventory.at[idx, 'barcode'] = None
                        main_inventory.at[idx, 'processed'] = True
                        main_inventory.at[idx, 'processing'] = False
                        main_inventory.at[idx, 'assigned_to'] = None
                        main_inventory.at[idx, 'processing_timestamp'] = pd.NaT
                        current_app.logger.info(f"Cleared matched_name and barcode for product '{sku}' and marked as processed.")

                        # Store action in session for potential undo
                        session['last_action'] = {
                            'action': 'no',
                            'sku': sku,
                            'original_data': original_data
                        }

                        flash(f"Product '{sku}' has been marked as not matched.", 'warning')
                    else:
                        # Render a template to display suggestions
                        return render_template(
                            'suggestions.html',
                            suggestions=suggestions,
                            sku=sku,
                            product_name=product_name
                        )

                elif action == 'skip':
                    # Handle 'Skip' action
                    current_app.logger.info(f"Skipped product '{sku}'.")
                    flash(f"Product '{sku}' has been skipped.", 'info')

                    # Store action in session for potential undo
                    session['last_action'] = {
                        'action': 'skip',
                        'sku': sku
                    }

                    # Reset processing flags
                    main_inventory.at[idx, 'processing'] = False
                    main_inventory.at[idx, 'assigned_to'] = None
                    main_inventory.at[idx, 'processing_timestamp'] = None

                else:
                    flash("Invalid action.", 'danger')

                # Save the updated main inventory back to S3 only if changes were made
                if action in ['yes', 'no', 'skip']:
                    save_inventory(main_inventory, current_app.config['S3_KEY_MAIN_INVENTORY'])

            return redirect(url_for('main.index'))

        # Handle GET request or after processing POST
        # Filter unprocessed and unassigned products
        unprocessed = main_inventory[
            (main_inventory['processed'] != True) & (main_inventory['processing'] != True)
        ]

        if unprocessed.empty:
            flash("All products have been processed.", 'info')
            return render_template('index.html', product=None, message="All products have been processed.")
        else:
            # Randomly select an unprocessed product
            product = unprocessed.sample(n=1).iloc[0].to_dict()

            # Assign to current user
            idx = main_inventory.index[main_inventory['sku'] == product['sku']][0]
            main_inventory.at[idx, 'processing'] = True
            main_inventory.at[idx, 'assigned_to'] = session.get('user_id')
            main_inventory.at[idx, 'processing_timestamp'] = datetime.utcnow()

            # Save the updated main inventory back to S3
            save_inventory(main_inventory, current_app.config['S3_KEY_MAIN_INVENTORY'])

            return render_template('index.html', product=product, total=len(unprocessed))

    except Exception as e:
        current_app.logger.error(f"An error occurred in main route: {str(e)}")
        flash("An unexpected error occurred. Please try again later.", 'danger')
        return redirect(url_for('main.index'))
