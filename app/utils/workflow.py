from flask import flash, redirect, url_for, session, current_app
from .inventory import load_inventory, save_inventory
import pandas as pd
from flask import Blueprint, redirect, url_for, flash, session
from ..utils.inventory import load_inventory, save_inventory
from ..utils.auth import auth  # Import centralized auth

undo_bp = Blueprint('undo', __name__)

def finalize_product(sku, idx, main_inventory):
    """
    Handle the 'Yes' action: finalize the product and move it to finalized inventory.
    """
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
        'brand', 'brandSellerId', 'defaultUnitOfMeasure', 'supplier_name', 'supplier_code', 'active',
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
    return redirect(url_for('main.index'))

def mark_product_as_not_matched(sku, idx, main_inventory):
    """
    Handle the 'No' action: mark the product as not matched.
    """
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

    # Save the updated main inventory back to S3
    save_inventory(main_inventory, current_app.config['S3_KEY_MAIN_INVENTORY'])

    return redirect(url_for('main.index'))

def skip_product(sku, idx, main_inventory):
    """
    Handle the 'Skip' action: skip the current product.
    """
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

    # Save the updated main inventory back to S3
    save_inventory(main_inventory, current_app.config['S3_KEY_MAIN_INVENTORY'])

    return redirect(url_for('main.index'))

# app/routes/undo.py
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
