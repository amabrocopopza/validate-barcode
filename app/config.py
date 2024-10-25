import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
ENVIRONMENT = os.getenv('ENVIRONMENT', 'staging').upper()  # Default to 'STAGING' if not set

class Config:
    # AWS S3 configurations
    S3_BUCKET = os.getenv('S3_BUCKET_NAME')
    S3_KEY_MAIN_INVENTORY = 'main_inventory.xlsx'
    S3_KEY_FINALIZED_INVENTORY = 'finalized_inventory.xlsx'
    
    # AWS Credentials (for local development only)
    AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
    AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')  # Default region
    
    # Flask configurations
    SECRET_KEY = os.getenv('SECRET_KEY', 'your_secret_key')  # Replace with a secure key


    # S3 Keys based on environment
    S3_KEY_MAIN_INVENTORY = os.getenv(
        f'S3_KEY_MAIN_INVENTORY_{ENVIRONMENT.upper()}',
        'main_inventory_staging.xlsx'
    )
    S3_KEY_FINALIZED_INVENTORY = os.getenv(
        f'S3_KEY_FINALIZED_INVENTORY_{ENVIRONMENT.upper()}',
        'finalized_inventory_staging.xlsx'
    )