from flask import Flask, render_template, request, redirect, url_for, flash, session
import pandas as pd
import boto3
from io import BytesIO
from config import Config
import os
import logging
from logging.handlers import RotatingFileHandler
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from uuid import uuid4
from datetime import datetime, timedelta

# Load environment variables from .env file
load_dotenv()

# Define columns to include in finalized_inventory.xlsx
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

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = app.config['SECRET_KEY']

# Set up logging
if not os.path.exists('logs'):
    os.mkdir('logs')

file_handler = RotatingFileHandler('logs/inventory_validation.log', maxBytes=10240, backupCount=10)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
))
file_handler.setLevel(logging.INFO)
app.logger.addHandler(file_handler)

app.logger.setLevel(logging.INFO)
app.logger.info('Inventory Validation Startup')

# Initialize S3 client
if app.config['AWS_ACCESS_KEY_ID'] and app.config['AWS_SECRET_ACCESS_KEY']:
    s3_client = boto3.client(
        's3',
        aws_access_key_id=app.config['AWS_ACCESS_KEY_ID'],
        aws_secret_access_key=app.config['AWS_SECRET_ACCESS_KEY'],
        region_name=app.config['AWS_REGION']
    )
else:
    # Assume IAM role is assigned (when deployed on AWS)
    s3_client = boto3.client(
        's3',
        region_name=app.config['AWS_REGION']
    )

# Initialize Basic Auth
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

# Define processing timeout duration
PROCESSING_TIMEOUT = timedelta(minutes=10)  # Adjust as needed

def load_inventory(key, inventory_type='main'):
    try:
        obj = s3_client.get_object(Bucket=app.config['S3_BUCKET'], Key=key)
        df = pd.read_excel(BytesIO(obj['Body'].read()))
        app.logger.info(f"Loaded {key} from S3.")
    except s3_client.exceptions.NoSuchKey:
        # Define columns based on inventory type
        if inventory_type == 'main':
            columns = [
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
        elif inventory_type == 'finalized':
            columns = COLUMNS_TO_INCLUDE  # Defined earlier
        else:
            columns = []
        
        df = pd.DataFrame(columns=columns)
        app.logger.warning(f"{key} does not exist in S3. Created a new DataFrame.")
    
    # Ensure 'processed', 'processing', 'assigned_to', and 'processing_timestamp' columns exist
    if inventory_type == 'main':
        if 'processed' not in df.columns:
            df['processed'] = False
            app.logger.info("'processed' column added with default False values.")
        if 'processing' not in df.columns:
            df['processing'] = False
            app.logger.info("'processing' column added with default False values.")
        if 'assigned_to' not in df.columns:
            df['assigned_to'] = None
            app.logger.info("'assigned_to' column added with default None values.")
        if 'processing_timestamp' not in df.columns:
            df['processing_timestamp'] = pd.NaT
            app.logger.info("'processing_timestamp' column added with default NaT values.")
        else:
            # Convert existing 'processing_timestamp' to datetime, coercing errors to NaT
            df['processing_timestamp'] = pd.to_datetime(df['processing_timestamp'], errors='coerce')
            app.logger.info("'processing_timestamp' column converted to datetime.")
    
    return df


def save_inventory(df, key):
    try:
        with BytesIO() as buffer:
            df.to_excel(buffer, index=False)
            buffer.seek(0)
            s3_client.put_object(Bucket=app.config['S3_BUCKET'], Key=key, Body=buffer.getvalue())
        app.logger.info(f"Saved {key} to S3.")
    except Exception as e:
        app.logger.error(f"Failed to save {key} to S3: {str(e)}")
        raise

def reset_stale_processing(main_inventory):
    current_time = datetime.utcnow()
    stale_items = main_inventory[
        (main_inventory['processing'] == True) &
        (main_inventory['processing_timestamp'].notna()) &
        (main_inventory['processing_timestamp'] < (current_time - PROCESSING_TIMEOUT))
    ]

    for idx in stale_items.index:
        main_inventory.at[idx, 'processing'] = False
        main_inventory.at[idx, 'assigned_to'] = None
        main_inventory.at[idx, 'processing_timestamp'] = pd.NaT
        app.logger.info(f"Reset processing flags for SKU '{main_inventory.at[idx, 'sku']}' due to timeout.")

    if not stale_items.empty:
        save_inventory(main_inventory, app.config['S3_KEY_MAIN_INVENTORY'])
        app.logger.info("Stale processing flags have been reset.")


# Initialize user ID for session
@app.before_request
def assign_user_id():
    if 'user_id' not in session:
        session['user_id'] = str(uuid4())

@app.route('/', methods=['GET', 'POST'])
@auth.login_required
def index():
    try:
        # Load main inventory
        main_inventory = load_inventory(app.config['S3_KEY_MAIN_INVENTORY'], inventory_type='main')

        # Reset stale processing flags
        if 'processing_timestamp' in main_inventory.columns:
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
                    app.logger.warning(f"User '{current_user}' attempted to modify SKU '{sku}' not assigned to them.")
                    flash("You do not have permission to modify this item.", 'danger')
                    return redirect(url_for('index'))

                if action == 'yes':
                    # Load finalized_inventory
                    finalized_inventory = load_inventory(app.config['S3_KEY_FINALIZED_INVENTORY'], inventory_type='finalized')

                    # Select the row to append as a DataFrame
                    row_to_append = main_inventory.loc[[idx]]

                    # Exclude unwanted columns
                    row_to_append = row_to_append[COLUMNS_TO_INCLUDE]

                    if finalized_inventory.empty:
                        # Initialize finalized_inventory with the row to append
                        finalized_inventory = row_to_append.copy()
                        app.logger.info("Initialized finalized_inventory with the first product.")
                    else:
                        # Concatenate the existing finalized_inventory with the new row
                        finalized_inventory = pd.concat([finalized_inventory, row_to_append], ignore_index=True)
                        app.logger.info(f"Appended product '{sku}' to finalized_inventory.")

                    # Save finalized_inventory to S3
                    save_inventory(finalized_inventory, app.config['S3_KEY_FINALIZED_INVENTORY'])

                    # Remove from main_inventory
                    main_inventory = main_inventory.drop(idx).reset_index(drop=True)
                    app.logger.info(f"Finalized and removed product '{sku}' from main inventory.")

                    # Store action in session for potential undo
                    session['last_action'] = {
                        'action': 'yes',
                        'sku': sku,
                        'row_data': row_to_append.to_dict(orient='records')[0]
                    }

                    flash(f"Product '{sku}' has been finalized and moved to the finalized inventory.", 'success')

                elif action == 'no':
                    # Clear matched_name and barcode, mark as processed
                    original_data = main_inventory.loc[idx].to_dict()

                    main_inventory.at[idx, 'matched_name'] = None
                    main_inventory.at[idx, 'barcode'] = None
                    main_inventory.at[idx, 'processed'] = True
                    main_inventory.at[idx, 'processing'] = False
                    main_inventory.at[idx, 'assigned_to'] = None
                    main_inventory.at[idx, 'processing_timestamp'] = None
                    app.logger.info(f"Cleared matched_name and barcode for product '{sku}' and marked as processed.")

                    # Store action in session for potential undo
                    session['last_action'] = {
                        'action': 'no',
                        'sku': sku,
                        'original_data': original_data
                    }

                    flash(f"Product '{sku}' has been marked as not matched.", 'warning')

                elif action == 'skip':
                    app.logger.info(f"Skipped product '{sku}'.")
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
                    save_inventory(main_inventory, app.config['S3_KEY_MAIN_INVENTORY'])

            else:
                app.logger.warning(f"SKU '{sku}' not found in main inventory.")
                flash(f"Product with SKU '{sku}' not found.", 'danger')

            return redirect(url_for('index'))

        # Filter unprocessed and unassigned products
        unprocessed = main_inventory[(main_inventory['processed'] != True) & (main_inventory['processing'] != True)]

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
            save_inventory(main_inventory, app.config['S3_KEY_MAIN_INVENTORY'])

            return render_template('index.html', product=product, total=len(unprocessed))

    except Exception as e:
        app.logger.error(f"An error occurred: {str(e)}")
        flash("An unexpected error occurred. Please try again later.", 'danger')
        return render_template('index.html', product=None, message="An error occurred.")

@app.route('/undo', methods=['POST'])
@auth.login_required
def undo():
    try:
        last_action = session.get('last_action')
        if not last_action:
            flash("No action to undo.", 'warning')
            return redirect(url_for('index'))

        action = last_action.get('action')
        sku = last_action.get('sku')
        current_user = session.get('user_id')

        # Load main inventory
        main_inventory = load_inventory(app.config['S3_KEY_MAIN_INVENTORY'], inventory_type='main')

        # Find the product by SKU
        product = main_inventory[main_inventory['sku'] == sku]
        if not product.empty:
            idx = product.index[0]
            assigned_to = main_inventory.at[idx, 'assigned_to']

            # Ensure that only the user who is processing can undo actions
            if assigned_to != current_user:
                app.logger.warning(f"User '{current_user}' attempted to undo action on SKU '{sku}' not assigned to them.")
                flash("You do not have permission to undo this action.", 'danger')
                return redirect(url_for('index'))

        if action == 'yes':
            # Load finalized_inventory
            finalized_inventory = load_inventory(app.config['S3_KEY_FINALIZED_INVENTORY'], inventory_type='finalized')

            # Remove the product from finalized_inventory
            finalized_inventory = finalized_inventory[finalized_inventory['sku'] != sku]
            save_inventory(finalized_inventory, app.config['S3_KEY_FINALIZED_INVENTORY'])
            app.logger.info(f"Removed product '{sku}' from finalized_inventory.")

            # Add the product back to main_inventory
            row_data = last_action.get('row_data')
            if row_data:
                # Convert row_data back to DataFrame
                row_df = pd.DataFrame([row_data])
                main_inventory = pd.concat([main_inventory, row_df], ignore_index=True)
                app.logger.info(f"Added product '{sku}' back to main_inventory.")
                save_inventory(main_inventory, app.config['S3_KEY_MAIN_INVENTORY'])
                flash(f"Undo successful: Product '{sku}' has been moved back to main inventory.", 'success')
            else:
                flash("Undo failed: Missing product data.", 'danger')

        elif action == 'no':
            # Revert 'no' action: Restore original data
            original_data = last_action.get('original_data')
            if original_data:
                sku = original_data.get('sku')
                product = main_inventory[main_inventory['sku'] == sku]
                if not product.empty:
                    idx = product.index[0]
                    # Restore the original data
                    for key, value in original_data.items():
                        main_inventory.at[idx, key] = value
                    # Reset processing flags
                    main_inventory.at[idx, 'processing'] = False
                    main_inventory.at[idx, 'assigned_to'] = None
                    main_inventory.at[idx, 'processing_timestamp'] = None
                    save_inventory(main_inventory, app.config['S3_KEY_MAIN_INVENTORY'])
                    app.logger.info(f"Reverted 'no' action for product '{sku}'.")
                    flash(f"Undo successful: Product '{sku}' has been reverted to its previous state.", 'success')
                else:
                    flash("Undo failed: SKU not found in main inventory.", 'danger')
            else:
                flash("Undo failed: Missing original data.", 'danger')

        elif action == 'skip':
            # 'Skip' action does not alter data; nothing to undo
            flash("Undo not required for 'Skip' action.", 'info')

        else:
            flash("Unknown action. Cannot undo.", 'danger')

        # Clear the last_action from session after undo
        session.pop('last_action', None)

        return redirect(url_for('index'))

    except Exception as e:
        app.logger.error(f"An error occurred during undo: {str(e)}")
        flash("An unexpected error occurred while trying to undo. Please try again later.", 'danger')
        return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
