# app/__init__.py

from flask import Flask, session
from .config import Config
from .routes import register_blueprints
from dotenv import load_dotenv
import os
from logging.handlers import RotatingFileHandler
import logging
from uuid import uuid4  # Ensure 'uuid4' is imported
from .utils.deeliver_data import DeeliverData


def create_app():
    app = Flask(__name__)
    
    # Load environment variables from .env file (if using dotenv)
    load_dotenv()
    
    # Load configurations
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
    
    # Initialize DeeliverData and attach to app
    app.deeliver_data = DeeliverData(
        aws_access_key_id=app.config['AWS_ACCESS_KEY_ID'],
        aws_secret_access_key=app.config['AWS_SECRET_ACCESS_KEY'],
        aws_region=app.config['AWS_REGION'],
        bucket_name=app.config['S3_BUCKET'],
        s3_file_key=app.config['S3_KEY_DEELIVER_DATA'],
        logger=app.logger  # Pass the Flask app's logger for consistent logging
    )
    
    # Register Blueprints
    register_blueprints(app)
    
    # Initialize other components like HTTPBasicAuth here if needed
    
    @app.before_request
    def assign_user_id():
        if 'user_id' not in session:
            session['user_id'] = str(uuid4())
    
    return app
