# auto_finalize.py

import os
import pandas as pd
from app.utils.inventory import load_inventory, save_inventory
from flask import Flask
from app.config import Config

# auto_finalize.py

app = Flask(__name__)
app.config.from_object(Config)


# auto_finalize.py

def auto_finalize_items():
    with app.app_context():
        try:
            # Load main inventory
            main_inventory = load_inventory(app.config['S3_KEY_MAIN_INVENTORY'], inventory_type='main')
            original_main_inventory_length = len(main_inventory)
            
            # Identify items with confidence_score of 100
            items_to_finalize = main_inventory[main_inventory['confidence_score'] == 100]
            if items_to_finalize.empty:
                app.logger.info("No items with a confidence score of 100 found.")
                return

            # Load finalized inventory
            finalized_inventory = load_inventory(app.config['S3_KEY_FINALIZED_INVENTORY'], inventory_type='finalized')

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
            
            # Ensure all columns are present
            for col in COLUMNS_TO_INCLUDE:
                if col not in items_to_finalize.columns:
                    items_to_finalize[col] = None

            # Select the relevant columns
            items_to_append = items_to_finalize[COLUMNS_TO_INCLUDE]

            # Append to finalized_inventory
            if finalized_inventory.empty:
                finalized_inventory = items_to_append.copy()
                app.logger.info("Initialized finalized_inventory with auto-finalized items.")
            else:
                finalized_inventory = pd.concat([finalized_inventory, items_to_append], ignore_index=True)
                app.logger.info(f"Appended {len(items_to_append)} items to finalized_inventory.")

            # Remove items from main_inventory
            main_inventory = main_inventory[main_inventory['confidence_score'] != 100].reset_index(drop=True)
            app.logger.info(f"Removed {len(items_to_append)} items from main_inventory.")

            # Save inventories back to S3
            save_inventory(finalized_inventory, app.config['S3_KEY_FINALIZED_INVENTORY'])
            save_inventory(main_inventory, app.config['S3_KEY_MAIN_INVENTORY'])

            app.logger.info("Auto-finalization process completed successfully.")

        except Exception as e:
            app.logger.error(f"An error occurred during auto-finalization: {str(e)}")


# auto_finalize.py

if __name__ == '__main__':
    auto_finalize_items()

