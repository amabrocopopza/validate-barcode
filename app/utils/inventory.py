# app/utils/inventory.py

import os
import pandas as pd
import boto3
from io import BytesIO
from filelock import FileLock
from flask import current_app as app
from datetime import datetime, timedelta

# Define a directory for lock files
LOCK_DIR = os.path.join(os.getcwd(), 'locks')  # Create a 'locks' directory in the current working directory

# Ensure the directory exists
if not os.path.exists(LOCK_DIR):
    os.makedirs(LOCK_DIR)

LOCK_PATH = os.path.join(LOCK_DIR, 'inventory.lock')

def load_inventory(key, inventory_type='main'):
    lock = FileLock(LOCK_PATH)
    with lock:
        try:
            s3_client = boto3.client(
                's3',
                aws_access_key_id=app.config['AWS_ACCESS_KEY_ID'],
                aws_secret_access_key=app.config['AWS_SECRET_ACCESS_KEY'],
                region_name=app.config['AWS_REGION']
            )
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
                    'restock_level_main_outlet', 'barcode',
                    'processed', 'processing', 'assigned_to', 'processing_timestamp'
                ]
            elif inventory_type == 'finalized':
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
            else:
                columns = []
            df = pd.DataFrame(columns=columns)
            app.logger.warning(f"{key} does not exist in S3. Created a new DataFrame.")

        # Ensure necessary columns exist
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
            if 'barcode' in df.columns:
                df['barcode'] = df['barcode'].astype(str)
        return df

def save_inventory(df, key):
    lock = FileLock(LOCK_PATH)
    with lock:
        try:
            s3_client = boto3.client(
                's3',
                aws_access_key_id=app.config['AWS_ACCESS_KEY_ID'],
                aws_secret_access_key=app.config['AWS_SECRET_ACCESS_KEY'],
                region_name=app.config['AWS_REGION']
            )
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
    PROCESSING_TIMEOUT = timedelta(minutes=10)  # Adjust as needed
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
