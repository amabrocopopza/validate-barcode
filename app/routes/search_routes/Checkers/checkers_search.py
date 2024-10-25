# app/routes/search_routes/Checkers/checkers_search.py

from flask import Blueprint, request, jsonify, current_app
from .checkers_api import fetch_product_suggestions, fetch_product_details
from ....utils.auth import auth  # Import centralized auth

checkers_bp = Blueprint('checkers', __name__, url_prefix='/checkers')

@checkers_bp.route('/search', methods=['POST'])
@auth.login_required
def search():
    term = request.form.get('search_term', '').strip()
    if not term:
        return jsonify({'success': False, 'message': 'No search term provided.'}), 400

    suggestions = fetch_product_suggestions(term)
    if not suggestions:
        return jsonify({'success': False, 'message': 'No products found from Checkers.'}), 404

    return jsonify({'success': True, 'products': suggestions}), 200

@checkers_bp.route('/fetch_details', methods=['POST'])
@auth.login_required
def fetch_details():
    href = request.form.get('href', '').strip()
    if not href:
        return jsonify({'success': False, 'message': 'No product href provided.'}), 400

    product_info = fetch_product_details(href)
    if not product_info:
        return jsonify({'success': False, 'message': 'Failed to fetch product details from Checkers.'}), 500

    return jsonify({'success': True, 'product_info': product_info}), 200
