# app/routes/main.py

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app, jsonify
from ..utils.inventory import load_inventory, save_inventory, reset_stale_processing
from app.routes.search_routes.PnP.pnp_api import fetch_product_suggestions
from datetime import datetime
import pandas as pd
from ..utils.auth import auth

main_bp = Blueprint('main', __name__)

@main_bp.route('/', methods=['GET', 'POST'])
@auth.login_required
def index():
    try:
        # Load main inventory using the configured S3 key
        main_inventory = load_inventory(current_app.config['S3_KEY_MAIN_INVENTORY'], inventory_type='main')

        # Load finalized inventory to count processed products
        finalized_inventory = load_inventory(current_app.config['S3_KEY_FINALIZED_INVENTORY'], inventory_type='finalized')

        # Reset stale processing flags
        reset_stale_processing(main_inventory)

        # Calculate progress indicators
        products_remaining = len(main_inventory)
        products_processed = len(finalized_inventory)
        total_products = products_remaining + products_processed

        if request.method == 'POST':
            action = request.form['action']
            sku = request.form.get('sku')
            # Check if SKU exists
            if sku not in main_inventory['sku'].values:
                flash('SKU not found in inventory.', 'danger')
                return redirect(url_for('main.index'))
            idx = main_inventory.index[main_inventory['sku'] == sku][0]

            if action == 'save_changes':
                # Update the product information with edited fields
                main_inventory.at[idx, 'product_name'] = request.form.get('product_name')
                main_inventory.at[idx, 'description'] = request.form.get('description')
                main_inventory.at[idx, 'brand_name'] = request.form.get('brand_name')
                main_inventory.at[idx, 'product_category'] = request.form.get('product_category')
                main_inventory.at[idx, 'retail_price'] = float(request.form.get('price')) if request.form.get('price') else 0.0
                main_inventory.at[idx, 'barcode'] = request.form.get('barcode')
                # Save to S3
                save_inventory(main_inventory, current_app.config['S3_KEY_MAIN_INVENTORY'])
                flash('Changes have been saved.', 'success')

            elif action == 'flag':
                main_inventory.at[idx, 'flagged'] = True  # Mark the product as flagged
                main_inventory.at[idx, 'processed'] = True  # Mark as processed
                main_inventory.at[idx, 'processing'] = False
                main_inventory.at[idx, 'assigned_to'] = None
                main_inventory.at[idx, 'processing_timestamp'] = None

                # Append to finalized inventory
                finalized_inventory = finalized_inventory.append(main_inventory.loc[idx])
                save_inventory(finalized_inventory, current_app.config['S3_KEY_FINALIZED_INVENTORY'])

                # Remove from main inventory
                main_inventory = main_inventory.drop(idx)
                save_inventory(main_inventory, current_app.config['S3_KEY_MAIN_INVENTORY'])
                flash('Product has been flagged and marked as processed.', 'warning')
                return redirect(url_for('main.index'))

            elif action == 'skip':
                # Reset processing flags so it can be reviewed again
                main_inventory.at[idx, 'processing'] = False
                main_inventory.at[idx, 'assigned_to'] = None
                main_inventory.at[idx, 'processing_timestamp'] = None
                # Save to S3
                save_inventory(main_inventory, current_app.config['S3_KEY_MAIN_INVENTORY'])
                flash('Product has been skipped and moved to the next one.', 'info')
                return redirect(url_for('main.index'))

            else:
                flash('Invalid action.', 'danger')
                return redirect(url_for('main.index'))

        # Handle GET request
        # Filter unprocessed and unassigned products
        unprocessed = main_inventory[
            (main_inventory['processed'] != True) & (main_inventory['processing'] != True)
        ]

        if unprocessed.empty:
            flash("All products have been processed.", 'info')
            product = None
            initial_suggestions = []
            # Provide default values to prevent template errors
            current_product_record = {
                'sku': '',
                'product_name': 'N/A',
                'description': 'No product selected.',
                'brand_name': 'N/A',
                'product_category': 'N/A',
                'retail_price': 0.0,
                'barcode': '',
                'image_url': 'default-image.jpg',
                # Add any additional default fields as needed
            }
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

            # Perform an initial search with the product name
            search_term = product.get('product_name', '').strip()
            if search_term:
                suggestions = fetch_product_suggestions(search_term)
                current_app.logger.info(f"Fetched {len(suggestions)} suggestions for search term '{search_term}'.")
                processed_suggestions = []
                for p in suggestions:
                    # Ensure 'price' is a dictionary to safely access 'formattedValue'
                    price_info = p.get('price', {})
                    processed = {
                        'name': p.get('name', 'N/A'),
                        'code': p.get('code', ''),
                        'price': price_info.get('formattedValue', 'N/A'),
                        # Include other fields if necessary
                    }
                    processed_suggestions.append(processed)
            else:
                suggestions = []
                current_app.logger.warning("Search term is empty.")
                processed_suggestions = []

            # Prepare current product record for the main product information
            current_product_record = {
                'sku': product.get('sku', ''),
                'product_name': product.get('product_name', 'N/A'),
                'description': product.get('description', 'No description available.'),
                'brand_name': product.get('brand_name', 'N/A'),
                'product_category': product.get('product_category', 'N/A'),
                'retail_price': float(product.get('retail_price', 0.0)),
                'barcode': product.get('barcode', ''),
                'image_url': product.get('image_url', 'default-image.jpg'),
                # Add any additional fields as needed
            }

        return render_template('index.html',
                               product=product,
                               total_products=total_products,
                               products_remaining=products_remaining,
                               products_processed=products_processed,
                               initial_suggestions=processed_suggestions,
                               current_product_record=current_product_record)
    except Exception as e:
        current_app.logger.error(f"Error in index route: {str(e)}")
        flash('An error occurred while processing your request.', 'danger')
        return redirect(url_for('main.index'))

@main_bp.route('/process_product', methods=['POST'])
@auth.login_required
def process_product():
    try:
        action = request.form.get('action')
        sku = request.form.get('sku')
        # Load main inventory
        main_inventory = load_inventory(current_app.config['S3_KEY_MAIN_INVENTORY'], inventory_type='main')
        finalized_inventory = load_inventory(current_app.config['S3_KEY_FINALIZED_INVENTORY'], inventory_type='finalized')

        # Check if SKU exists
        if sku not in main_inventory['sku'].values:
            flash('SKU not found in inventory.', 'danger')
            return redirect(url_for('main.index'))
        idx = main_inventory.index[main_inventory['sku'] == sku][0]

        if action == 'save_changes':
            # Update the product information with edited fields
            main_inventory.at[idx, 'product_name'] = request.form.get('product_name')
            main_inventory.at[idx, 'description'] = request.form.get('description')
            main_inventory.at[idx, 'brand_name'] = request.form.get('brand_name')
            main_inventory.at[idx, 'product_category'] = request.form.get('product_category')
            main_inventory.at[idx, 'retail_price'] = float(request.form.get('price')) if request.form.get('price') else 0.0
            main_inventory.at[idx, 'barcode'] = request.form.get('barcode')
            # Save to S3
            save_inventory(main_inventory, current_app.config['S3_KEY_MAIN_INVENTORY'])
            flash('Changes have been saved.', 'success')

        elif action == 'flag':
            main_inventory.at[idx, 'flagged'] = True  # Mark the product as flagged
            main_inventory.at[idx, 'processed'] = True  # Mark as processed
            main_inventory.at[idx, 'processing'] = False
            main_inventory.at[idx, 'assigned_to'] = None
            main_inventory.at[idx, 'processing_timestamp'] = None

            # Append to finalized inventory
            finalized_inventory = finalized_inventory.append(main_inventory.loc[idx])
            save_inventory(finalized_inventory, current_app.config['S3_KEY_FINALIZED_INVENTORY'])

            # Remove from main inventory
            main_inventory = main_inventory.drop(idx)
            save_inventory(main_inventory, current_app.config['S3_KEY_MAIN_INVENTORY'])
            flash('Product has been flagged and marked as processed.', 'warning')
            return redirect(url_for('main.index'))

        elif action == 'skip':
            # Reset processing flags so it can be reviewed again
            main_inventory.at[idx, 'processing'] = False
            main_inventory.at[idx, 'assigned_to'] = None
            main_inventory.at[idx, 'processing_timestamp'] = None
            # Save to S3
            save_inventory(main_inventory, current_app.config['S3_KEY_MAIN_INVENTORY'])
            flash('Product has been skipped and moved to the next one.', 'info')
            return redirect(url_for('main.index'))

        else:
            flash('Invalid action.', 'danger')
            return redirect(url_for('main.index'))

        return redirect(url_for('main.index'))
    except Exception as e:
        current_app.logger.error(f"Error in process_product route: {str(e)}")
        flash('An error occurred while processing your request.', 'danger')
        return redirect(url_for('main.index'))

@main_bp.route('/search_main_inventory', methods=['POST'])
@auth.login_required
def search_main_inventory():
    try:
        search_term = request.form.get('search_term', '').strip()
        if not search_term:
            return jsonify({'success': False, 'message': 'No search term provided.'}), 400

        # Implement the search logic for main inventory
        main_inventory = load_inventory(current_app.config['S3_KEY_MAIN_INVENTORY'], inventory_type='main')
        filtered_inventory = main_inventory[main_inventory['product_name'].str.contains(search_term, case=False, na=False)].copy()

        if filtered_inventory.empty:
            return jsonify({'success': False, 'message': 'No products found in Main Inventory.'}), 404

        # Convert data types to JSON serializable types
        for column in filtered_inventory.columns:
            if pd.api.types.is_float_dtype(filtered_inventory[column]):
                filtered_inventory[column] = filtered_inventory[column].astype(float)
            elif pd.api.types.is_integer_dtype(filtered_inventory[column]):
                filtered_inventory[column] = filtered_inventory[column].astype(int)
            elif pd.api.types.is_datetime64_any_dtype(filtered_inventory[column]):
                filtered_inventory[column] = filtered_inventory[column].astype(str)
            else:
                # Convert all other types to string to ensure JSON serializability
                filtered_inventory[column] = filtered_inventory[column].astype(str)

        # Replace NaN with None for JSON serialization
        results = filtered_inventory.where(pd.notnull(filtered_inventory), None).to_dict(orient='records')

        return jsonify({'success': True, 'products': results}), 200
    except Exception as e:
        current_app.logger.error(f"Error in search_main_inventory route: {str(e)}")
        return jsonify({'success': False, 'message': 'An error occurred while searching the inventory.'}), 500
