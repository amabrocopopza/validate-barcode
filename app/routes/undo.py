# app/routes/undo.py

from flask import Blueprint, redirect, url_for, flash, session
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash
from ..utils.inventory import load_inventory, save_inventory
import os

undo_bp = Blueprint('undo', __name__)
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

@undo_bp.route('/undo', methods=['POST'])
@auth.login_required
def undo():
    try:
        last_action = session.get('last_action')
        if not last_action:
            flash("No action to undo.", 'warning')
            return redirect(url_for('main.index'))

        action = last_action.get('action')
        sku = last_action.get('sku')
        current_user = session.get('user_id')

        # Load main inventory
        main_inventory = load_inventory('main_inventory')  # Pass appropriate key

        # Find the product by SKU
        product = main_inventory[main_inventory['sku'] == sku]
        if not product.empty:
            idx = product.index[0]
            assigned_to = main_inventory.at[idx, 'assigned_to']

            # Ensure that only the user who is processing can undo actions
            if assigned_to != current_user:
                undo_bp.logger.warning(f"User '{current_user}' attempted to undo action on SKU '{sku}' not assigned to them.")
                flash("You do not have permission to undo this action.", 'danger')
                return redirect(url_for('main.index'))

        if action == 'yes':
            # Handle undo for 'yes' action
            # ... (similar to previous code)
            pass  # Replace with actual implementation

        elif action == 'no':
            # Handle undo for 'no' action
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
                    save_inventory(main_inventory, 'main_inventory')  # Pass appropriate key
                    undo_bp.logger.info(f"Reverted 'no' action for product '{sku}'.")
                    flash(f"Undo successful: Product '{sku}' has been reverted to its previous state.", 'success')
                else:
                    flash("Undo failed: SKU not found in main inventory.", 'danger')
            else:
                flash("Undo failed: Missing original data.", 'danger')

        elif action == 'no_with_barcode':
            # Handle undo for 'no_with_barcode' action
            barcode = last_action.get('barcode')
            sku = last_action.get('sku')
            
            if not barcode or not sku:
                flash("Invalid undo data.", 'danger')
                return redirect(url_for('main.index'))
            
            product = main_inventory[main_inventory['sku'] == sku]
            if not product.empty:
                idx = product.index[0]
                main_inventory.at[idx, 'barcode'] = None
                main_inventory.at[idx, 'processed'] = False
                main_inventory.at[idx, 'processing'] = False
                main_inventory.at[idx, 'assigned_to'] = None
                main_inventory.at[idx, 'processing_timestamp'] = None
                save_inventory(main_inventory, 'main_inventory')  # Pass appropriate key
                undo_bp.logger.info(f"Reverted 'no_with_barcode' action for product '{sku}'.")
                flash(f"Undo successful: Barcode '{barcode}' has been removed from product '{sku}'.", 'success')
            else:
                flash("Undo failed: SKU not found in main inventory.", 'danger')

        elif action == 'skip':
            # 'Skip' action does not alter data; nothing to undo
            flash("Undo not required for 'Skip' action.", 'info')

        else:
            flash("Unknown action. Cannot undo.", 'danger')

        # Clear the last_action from session after undo
        session.pop('last_action', None)

        return redirect(url_for('main.index'))

    except Exception as e:
        undo_bp.logger.error(f"An error occurred during undo: {str(e)}")
        flash("An unexpected error occurred while trying to undo. Please try again later.", 'danger')
        return redirect(url_for('main.index'))
