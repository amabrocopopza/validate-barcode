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

        # Reset stale processing flags
        reset_stale_processing(main_inventory)

        if request.method == 'POST':
            action = request.form['action']
            sku = request.form.get('sku')

            # Redirect POST requests to barcode_bp for handling
            if action in ['yes', 'no', 'skip']:
                return redirect(url_for('barcode.handle_action', action=action, sku=sku))

            flash("Invalid action.", 'danger')
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
            current_product_record = None  # No current product
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
            search_term = product.get('product_name', '')
            suggestions = fetch_product_suggestions(search_term)
            processed_suggestions = []
            for p in suggestions:
                processed = {
                    'name': p.get('name', 'N/A'),
                    'code': p.get('code', ''),
                    'price': p.get('price', {}).get('formattedValue', 'N/A'),
                    'images': p.get('images', []),
                    'description': p.get('description', 'No description available.'),
                    'brand': p.get('brand', 'N/A'),
                    'brandSellerId': p.get('brandSellerId', 'N/A'),
                    'defaultUnitOfMeasure': p.get('defaultUnitOfMeasure', 'N/A')
                    
                    
                    
                    
                }
                processed_suggestions.append(processed)

            # Prepare current product record for the main product table
            current_product_record = {
                'sku': product.get('sku', ''),
                'product_name': product.get('product_name', 'N/A'),
                'description': product.get('description', 'No description available.'),
                'brand_name' : 'None Set' if pd.isna(product.get('brand_name', 'N/A')) else product.get('brand_name', 'N/A'),
                'retail_price': product.get('retail_price', 0.0),
                'product_category': product.get('product_category', 'N/A'),
                'supplier_name': product.get('Supplier Name', 'N/A'),        
                  
            }

        # Convert DataFrame to records for Jinja2
        # Instead of passing all main_inventory_records, pass only the current product
        if current_product_record:
            main_inventory_records = [current_product_record]
        else:
            main_inventory_records = []

        return render_template('index.html', 
                               product=product, 
                               total=len(unprocessed),
                               initial_suggestions=processed_suggestions,
                               main_inventory=main_inventory_records)

    except Exception as e:
        current_app.logger.error(f"An error occurred in index route: {str(e)}")
        return render_template('index.html', product=None, message="An error occurred.", main_inventory=[])


