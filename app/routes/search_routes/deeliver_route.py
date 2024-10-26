# app/routes/search_routes/deeliver_route.py

from flask import Blueprint, request, jsonify, current_app
from flask import current_app
from ...utils.auth import auth

deeliver_bp = Blueprint('deeliver', __name__, url_prefix='/deeliver')

@deeliver_bp.route('/search', methods=['POST'])
@auth.login_required
def search():
    term = request.form.get('search_term', '').strip()
    if not term:
        return jsonify({'success': False, 'message': 'No search term provided.'}), 400

    # Use the DeeliverData instance attached to the app
    results = current_app.deeliver_data.search_products(term, limit=20)
    if not results:
        return jsonify({'success': False, 'message': 'No products found.'}), 200  # Return 200 instead of 404

    return jsonify({'success': True, 'products': results}), 200



@deeliver_bp.route('/fetch_details', methods=['POST'])
@auth.login_required
def fetch_details():
    barcode = request.form.get('barcode', '').strip()
    if not barcode:
        return jsonify({'success': False, 'message': 'No barcode provided.'}), 400

    # Use the DeeliverData instance attached to the app
    product = next((p for p in current_app.deeliver_data.products if p['barcode'] == barcode), None)
    if not product:
        return jsonify({'success': False, 'message': 'Product not found.'}), 404

    return jsonify({'success': True, 'product_info': product}), 200