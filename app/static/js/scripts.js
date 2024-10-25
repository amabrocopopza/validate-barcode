
function showSpinner() {
    document.getElementById('spinner').style.display = 'flex';
}

function hideSpinner() {
    document.getElementById('spinner').style.display = 'none';
}

// Perform Search Function
function performSearch(event) {
    if (event) {
        event.preventDefault();
    }
    const searchTerm = $('#search-term').val().trim();
    if (searchTerm === '') {
        alert('Please enter a product name to search.');
        return;
    }

    showSpinner();

    $.ajax({
        url: "{{ url_for('main.search') }}",
        method: 'POST',
        data: { 'search_term': searchTerm },
        success: function (response) {
            hideSpinner();
            if (response.success) {
                populateSuggestions(response.products);
            } else {
                alert(response.message || 'No suggestions found.');
                $('.suggestions-section').hide();
                $('.selected-product-section').hide();
            }
        },
        error: function () {
            hideSpinner();
            alert('An error occurred while fetching suggestions.');
        }
    });
}

// Populate Suggestions Dropdown
function populateSuggestions(products) {
    const dropdown = $('#suggestions-dropdown');
    dropdown.empty();
    dropdown.append('<option value="">-- Select a Product --</option>');
    products.forEach(product => {
        const option = `
            <option value="${product.code}">
                ${escapeHtml(product.name)} - ${escapeHtml(product.price)}
            </option>
        `;
        dropdown.append(option);
    });
    $('.suggestions-section').show();
    $('.selected-product-section').hide();
}

// Display Selected Product Details
function displaySelectedProduct() {
    const selectedOption = $('#suggestions-dropdown').find(':selected');
    const sku = selectedOption.val();
    if (sku === '') {
        $('.selected-product-section').hide();
        return;
    }

    // Set the SKU in the hidden input field
    $('#action-sku').val(sku);

    // Show spinner while fetching barcode and details
    showSpinner();

    // Fetch barcode and other details via AJAX
    $.ajax({
        url: "{{ url_for('barcode.fetch_barcode') }}",
        method: 'POST',
        data: { 'product_code': sku },
        success: function (response) {
            hideSpinner();
            if (response.success) {
                // Update fields with response data
                $('#selected-product-name').text(response.product_name || 'N/A');
                $('#price-display').text(response.price_formatted || 'R0.00');

                // Retrieve retail_price from the main product table
                const mainProductRow = $(`#main-product-${sku}`);
                const retailPriceText = mainProductRow.find('td').eq(3).text(); // 4th column is retail_price
                const retailPrice = parseFloat(retailPriceText.replace('R', '')) || 0;

                // priceValue from AJAX response
                const priceValue = parseFloat(response.price_value) || 0;
                const difference = priceValue - retailPrice;

                if (difference < 0) {
                    $('#price-difference').html(`<span class="difference-negative">-${formatCurrency(Math.abs(difference))}</span>`);
                } else if (difference > 0) {
                    $('#price-difference').html(`<span class="difference-positive">+${formatCurrency(difference)}</span>`);
                } else {
                    $('#price-difference').text('R0.00');
                }

                $('#barcode-display').text(response.barcode || 'N/A');
                $('#description-display').text(response.description || 'No description available.');
                $('#brand-display').text(response.brand || 'N/A');
                $('#brand-seller-id-display').text(response.brandSellerId || 'N/A');
                $('#unit-of-measure-display').text(response.defaultUnitOfMeasure || 'N/A');

                // Handle Images Carousel
                if (response.imageUrls && response.imageUrls.length > 0) {
                    let carouselItems = '';
                    response.imageUrls.forEach((url, index) => {
                        carouselItems += `
                            <div class="carousel-item ${index === 0 ? 'active' : ''}">
                                <img src="${escapeHtml(url)}" class="d-block w-100" alt="Product Image">
                            </div>
                        `;
                    });

                    const carouselHtml = `
                        <div id="productImagesCarousel" class="carousel slide" data-ride="carousel" data-interval="false">
                            <div class="carousel-inner">
                                ${carouselItems}
                            </div>
                            <a class="carousel-control-prev" href="#productImagesCarousel" role="button" data-slide="prev">
                                <span class="carousel-control-prev-icon" aria-hidden="true"></span>
                                <span class="sr-only">Previous</span>
                            </a>
                            <a class="carousel-control-next" href="#productImagesCarousel" role="button" data-slide="next">
                                <span class="carousel-control-next-icon" aria-hidden="true"></span>
                                <span class="sr-only">Next</span>
                            </a>
                        </div>
                    `;
                    $('#image-carousel').html(carouselHtml);
                } else {
                    $('#image-carousel').text('No image available.');
                }

                $('.selected-product-section').show();
            } else {
                // If fetching details failed, show error and hide details section
                alert(response.message || 'Failed to fetch product details.');
                $('.selected-product-section').hide();
            }
        },
        error: function () {
            hideSpinner();
            alert('An error occurred while fetching product details.');
            $('.selected-product-section').hide();
        }
    });
}

// Function to format currency
function formatCurrency(amount) {
    return 'R' + amount.toFixed(2);
}

// Utility function to escape HTML to prevent XSS
function escapeHtml(text) {
    if (!text) return '';
    return text.replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// Perform an initial search on page load
$(document).ready(function () {
    const initialSearchTerm = "{{ product['product_name'] if product else '' }}";
    if (initialSearchTerm) {
        $('#search-term').val(initialSearchTerm);
        performSearch();  // Call without event
    }

    // Attach event listener to the suggestions dropdown
    $('#suggestions-dropdown').change(function () {
        displaySelectedProduct();
    });
});
