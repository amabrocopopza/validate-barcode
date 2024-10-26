# app/utils/deeliver_data.py

import csv
import io
import boto3
import difflib
import re
from botocore.exceptions import NoCredentialsError, ClientError
import logging

class DeeliverData:
    def __init__(self, aws_access_key_id, aws_secret_access_key, aws_region, bucket_name, s3_file_key, logger=None):
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self.aws_region = aws_region
        self.bucket_name = bucket_name
        self.s3_file_key = s3_file_key
        self.products = []
        self.logger = logger or logging.getLogger(__name__)
        self.load_data_from_s3()
    
    def load_data_from_s3(self):
        s3 = boto3.client(
            's3',
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            region_name=self.aws_region
        )
        try:
            response = s3.get_object(Bucket=self.bucket_name, Key=self.s3_file_key)
            content = response['Body'].read().decode('utf-8')
            csv_file = io.StringIO(content)
            reader = csv.DictReader(csv_file)
            for row in reader:
                barcode = row.get('barcode', '').strip()
                if not barcode or len(barcode) < 6:
                    continue  # Skip rows without a valid barcode
                self.products.append({
                    'barcode': barcode,
                    'product_name': row.get('product_name', '').strip(),
                    'categories': row.get('categories', '').strip(),
                    'supplier_name': row.get('supplier_name', '').strip(),
                    'retail_price': row.get('retail_price', '0.00').strip(),
                })
            self.logger.info(f"Loaded {len(self.products)} products from s3://{self.bucket_name}/{self.s3_file_key}")
        except NoCredentialsError:
            self.logger.error("AWS credentials not available.")
        except ClientError as e:
            self.logger.error(f"ClientError: {e}")
        except Exception as e:
            self.logger.error(f"Error loading data from S3: {e}")
    
    def search_products(self, term, limit=20):
        """
        Search for products matching the given term.

        The search is performed in two steps:
        1. Exact keyword matching: Products containing all words in the search term.
        2. Fuzzy matching: Products with names similar to the search term.

        Args:
            term (str): The search term.
            limit (int): Maximum number of results to return.

        Returns:
            list: A list of matching product dictionaries.
        """
        term = term.lower()
        # Use a regular expression to find products containing all words in the term
        term_words = re.findall(r'\w+', term)
        results = []

        for product in self.products:
            product_name = product['product_name'].lower()
            if all(word in product_name for word in term_words):
                results.append(product)
                if len(results) >= limit:
                    break

        # If not enough results, fall back to difflib matching
        if len(results) < limit:
            remaining = limit - len(results)
            product_names = [product['product_name'] for product in self.products]
            matches = difflib.get_close_matches(term, product_names, n=remaining, cutoff=0.3)
            for match in matches:
                # Find the product(s) with the matching name
                matched_products = [product for product in self.products if product['product_name'] == match]
                for matched_product in matched_products:
                    if matched_product not in results:
                        results.append(matched_product)
                        if len(results) >= limit:
                            break
                if len(results) >= limit:
                    break

        return results[:limit]
