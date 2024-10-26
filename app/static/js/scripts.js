// static/js/scripts.js

$(document).ready(function () {
    console.log('Document is ready.');

    // Show spinner function
    function showSpinner() {
        $('#spinner').show();
    }

    // Hide spinner function
    function hideSpinner() {
        $('#spinner').hide();
    }

    // Variables to store selected product prices and barcodes
    var mainPrice = parseFloat($('#main-price').val()) || 0;
    var pnpPrice = 0;
    var pnpBarcode = '';
    var checkersPrice = 0;
    var checkersBarcode = '';

    // Update main price when it changes
    $('#main-price').on('input', function () {
        mainPrice = parseFloat($(this).val()) || 0;
        updatePriceDifferences();
    });

    // Function to update price differences
    function updatePriceDifferences() {
        // Update PnP Price Difference
        if (pnpPrice > 0) {
            var pnpDiffPercentage = ((mainPrice - pnpPrice) / pnpPrice) * 100;
            var pnpDiffAmount = mainPrice - pnpPrice;
            displayPriceDifference('pnp', pnpDiffPercentage, pnpDiffAmount);
        } else {
            $('#pnp-price-difference').hide();
        }

        // Update Checkers Price Difference
        if (checkersPrice > 0) {
            var checkersDiffPercentage = ((mainPrice - checkersPrice) / checkersPrice) * 100;
            var checkersDiffAmount = mainPrice - checkersPrice;
            displayPriceDifference('checkers', checkersDiffPercentage, checkersDiffAmount);
        } else {
            $('#checkers-price-difference').hide();
        }

        // Calculate and display average price if applicable
        if (pnpBarcode && checkersBarcode && pnpBarcode === checkersBarcode) {
            var averagePrice = (pnpPrice + checkersPrice) / 2;
            $('#average-price-value').text('R' + averagePrice.toFixed(2));
            $('#average-price-section').show();
        } else {
            $('#average-price-section').hide();
        }

        updateCopyButtonVisibility();
    }

    function displayPriceDifference(source, diffPercentage, diffAmount) {
        var diffElement = $('#' + source + '-price-difference');
        var diffValueElement = $('#' + source + '-price-diff-value');
        diffElement.show();

        var diffText = diffPercentage.toFixed(1) + '% (R' + diffAmount.toFixed(1) + ')';
        diffValueElement.text(diffText);

        // Color coding
        if (diffPercentage > 10) {
            diffValueElement.css('color', 'red');
        } else if (diffPercentage >= 0 && diffPercentage <= 10) {
            diffValueElement.css('color', 'orange');
        } else {
            diffValueElement.css('color', 'green');
        }
    }

    function updateCopyButtonVisibility() {
        var copyButton = $('#copy-price-btn');

        if (pnpPrice > 0 && checkersPrice > 0 && pnpBarcode === checkersBarcode) {
            copyButton.text('Copy Average').show();
        } else if ((pnpPrice > 0 || checkersPrice > 0) && !(pnpPrice > 0 && checkersPrice > 0)) {
            copyButton.text('Copy Selected').show();
        } else {
            copyButton.hide();
        }
    }

    // Initially hide the Save and Revert buttons
    $('#save-changes-btn, #revert-changes-btn').hide();

    // Function to check if any fields have been modified
    function checkForChanges() {
        const productNameChanged = $('#main-product-name').val() !== window.initialProductName;
        const descriptionChanged = $('#main-description').val() !== window.initialDescription;
        const brandChanged = $('#main-brand-name').val() !== window.initialBrandName;
        const categoryChanged = $('#main-product-category').val() !== window.initialProductCategory;
        const priceChanged = $('#main-price').val() !== window.initialPrice;
        const barcodeChanged = $('#main-barcode').val() !== '';

        if (productNameChanged || descriptionChanged || brandChanged || categoryChanged || priceChanged || barcodeChanged) {
            $('#save-changes-btn, #revert-changes-btn').show();
        } else {
            $('#save-changes-btn, #revert-changes-btn').hide();
        }
    }

    // Attach event listeners to input fields
    $('#main-product-name, #main-description, #main-brand-name, #main-product-category, #main-price, #main-barcode').on('input', function () {
        checkForChanges();
    });

    // Bind Dropdown Search Form Submission
    $('#dropdown-search-form').on('submit', function (event) {
        event.preventDefault();
        performSearch();
    });

    function performSearch() {
        const searchTerm = $('#search-term').val().trim();
        if (searchTerm === '') {
            alert('Please enter a product name to search.');
            return;
        }

        showSpinner();

        // Clear previous suggestions and product details
        $('#pnp-dropdown').empty().append('<option value="">-- Select a PnP Product --</option>');
        $('#checkers-dropdown').empty().append('<option value="">-- Select a Checkers Product --</option>');
        $('#pnp-product-details').empty();
        $('#checkers-product-details').empty();
        pnpPrice = 0;
        pnpBarcode = '';
        checkersPrice = 0;
        checkersBarcode = '';
        updatePriceDifferences();

        // Perform both PnP and Checkers searches
        const pnpSearch = $.ajax({
            url: pnpSearchUrl,
            method: 'POST',
            data: { 'search_term': searchTerm },
        });

        const checkersSearch = $.ajax({
            url: checkersSearchUrl,
            method: 'POST',
            data: { 'search_term': searchTerm },
        });

        $.when(pnpSearch, checkersSearch)
            .done(function (pnpResponse, checkersResponse) {
                hideSpinner();

                // Handle PnP response
                if (pnpResponse[0].success) {
                    populateDropdown('pnp', pnpResponse[0].products);
                } else {
                    alert(pnpResponse[0].message || 'No suggestions found from PnP.');
                }

                // Handle Checkers response
                if (checkersResponse[0].success) {
                    populateDropdown('checkers', checkersResponse[0].products);
                } else {
                    alert(checkersResponse[0].message || 'No suggestions found from Checkers.');
                }
            })
            .fail(function () {
                hideSpinner();
                alert('An error occurred while fetching suggestions.');
            });
    }

    function populateDropdown(source, products) {
        let dropdownId = '';
        if (source === 'pnp') {
            dropdownId = '#pnp-dropdown';
        } else if (source === 'checkers') {
            dropdownId = '#checkers-dropdown';
        }

        const dropdown = $(dropdownId);
        dropdown.empty();
        dropdown.append(`<option value="">-- Select a ${source.charAt(0).toUpperCase() + source.slice(1)} Product --</option>`);
        products.forEach(product => {
            if (source === 'pnp') {
                const option = `<option value="${product.code}">${escapeHtml(product.name)} - ${escapeHtml(product.price)}</option>`;
                dropdown.append(option);
            } else if (source === 'checkers') {
                const option = `<option value="${product.href}">${escapeHtml(product.name)} - R${escapeHtml(product.price)}</option>`;
                dropdown.append(option);
            }
        });
    }

    // Handle Dropdown Selection
    $('#pnp-dropdown').change(function () {
        const productCode = $(this).val();
        if (productCode) {
            displayProductDetails('pnp', productCode);
        } else {
            $('#pnp-product-details').empty();
            pnpPrice = 0;
            pnpBarcode = '';
            updatePriceDifferences();
            updateCopyButtonVisibility();
        }
    });

    $('#checkers-dropdown').change(function () {
        const productHref = $(this).val();
        if (productHref) {
            displayProductDetails('checkers', productHref);
        } else {
            $('#checkers-product-details').empty();
            checkersPrice = 0;
            checkersBarcode = '';
            updatePriceDifferences();
            updateCopyButtonVisibility();
        }
    });

    // Display Product Details Function
    function displayProductDetails(source, identifier) {
        showSpinner();
        let fetchUrl = '';
        let data = {};
        let detailsDivId = '';

        if (source === 'pnp') {
            fetchUrl = pnpFetchProductDetailsUrl;
            data = { 'product_code': identifier };
            detailsDivId = '#pnp-product-details';
        } else if (source === 'checkers') {
            fetchUrl = checkersFetchDetailsUrl;
            data = { 'href': identifier };
            detailsDivId = '#checkers-product-details';
        }

        $.ajax({
            url: fetchUrl,
            method: 'POST',
            data: data,
            success: function (response) {
                hideSpinner();
                console.log(`Response from ${source} fetch:`, response);
                if (response.success) {
                    let productInfo = {};
                    if (source === 'pnp') {
                        productInfo = response;
                        pnpPrice = parseFloat(productInfo.price_value) || 0;
                        pnpBarcode = productInfo.barcode || '';
                    } else if (source === 'checkers') {
                        productInfo = response.product_info;
                        checkersPrice = parseFloat(productInfo.product_price) || 0;
                        checkersBarcode = productInfo.barcode || '';
                    }

                    // Build product details HTML
                    let imageUrl = '';
                    if (source === 'pnp') {
                        if (productInfo.imageUrls && productInfo.imageUrls.length > 0) {
                            imageUrl = productInfo.imageUrls[0];
                        }
                    } else if (source === 'checkers') {
                        if (productInfo.product_image_url && productInfo.product_image_url !== 'N/A') {
                            imageUrl = productInfo.product_image_url;
                        }
                    }

                    let detailsHtml = `
                        ${imageUrl ? `<img src="${escapeHtml(imageUrl)}" alt="Product Image" class="product-image mb-3" data-toggle="modal" data-target="#imageModal">` : ''}
                        <h4 class="product-name">${escapeHtml(productInfo.product_name || productInfo.name || 'N/A')}
                            <span class="copy-field-btn" data-field="product_name" data-value="${escapeHtml(productInfo.product_name || productInfo.name || '')}">[Copy]</span>
                        </h4>
                        <p><strong>Price:</strong> R${escapeHtml(productInfo.product_price || productInfo.price_value || '0.00')}</p>
                        <p><strong>Barcode:</strong> ${escapeHtml(productInfo.barcode || 'N/A')}
                            <span class="copy-field-btn" data-field="barcode" data-value="${escapeHtml(productInfo.barcode || '')}">[Copy]</span>
                        </p>
                        <p><strong>Description:</strong> ${escapeHtml(productInfo.description || 'No description available.')}
                            <span class="copy-field-btn" data-field="description" data-value="${escapeHtml(productInfo.description || '')}">[Copy]</span>
                        </p>
                        <p><strong>Brand:</strong> ${escapeHtml(productInfo.brand || productInfo.product_brand || 'N/A')}
                            <span class="copy-field-btn" data-field="brand_name" data-value="${escapeHtml(productInfo.brand || productInfo.product_brand || '')}">[Copy]</span>
                        <p><strong>Category:</strong> ${escapeHtml(decodeHtml(productInfo.category || 'N/A'))}
                            <span class="copy-field-btn" data-field="product-category" data-value="${escapeHtml(productInfo.category || '')}">[Copy]</span>
                        </p>
                    `;
                    $(detailsDivId).html(detailsHtml);

                    // Attach event listeners to Copy buttons
                    $(detailsDivId).find('.copy-field-btn').click(function () {
                        const field = $(this).data('field');
                        const value = $(this).data('value');
                        $(`#main-${field}`).val(value).trigger('input');
                    });

                    updatePriceDifferences();
                    updateCopyButtonVisibility();

                } else {
                    alert(response.message || 'Failed to fetch product details.');
                }
            },
            error: function (xhr, status, error) {
                hideSpinner();
                console.error(`Error fetching ${source} product details:`, error);
                alert('An error occurred while fetching product details.');
            }
        });
    }

    // Initially hide the Copy Selected button
    $('#copy-price-btn').hide();

    function updateCopyButtonVisibility() {
        var copyButton = $('#copy-price-btn');

        if (pnpPrice > 0 && checkersPrice > 0 && pnpBarcode === checkersBarcode) {
            copyButton.text('Copy Average').show();
        } else if ((pnpPrice > 0 || checkersPrice > 0) && !(pnpPrice > 0 && checkersPrice > 0)) {
            copyButton.text('Copy Selected').show();
        } else {
            copyButton.hide();
        }
    }

    // Copy Price Button Click Handler
    $('#copy-price-btn').on('click', function () {
        var priceToCopy = null;
        if (pnpPrice > 0 && checkersPrice > 0 && pnpBarcode === checkersBarcode) {
            var averagePrice = (pnpPrice + checkersPrice) / 2;
            priceToCopy = averagePrice;
        } else if (pnpPrice > 0 && checkersPrice === 0) {
            priceToCopy = pnpPrice;
        } else if (checkersPrice > 0 && pnpPrice === 0) {
            priceToCopy = checkersPrice;
        } else {
            alert('Please select a product to copy the price from.');
            return;
        }

        // Store the price to copy for later use
        $('#percentageModal').data('priceToCopy', priceToCopy);

        // Show the modal
        $('#percentageModal').modal('show');
    });

    // Update percentage display when slider changes
    $('#percentage-slider').on('input', function () {
        var percentage = $(this).val();
        $('#percentage-value').text(percentage + '%');
    });

    // Apply the percentage adjustment
    $('#apply-percentage-btn').on('click', function () {
        var priceToCopy = $('#percentageModal').data('priceToCopy');
        var percentage = parseFloat($('#percentage-slider').val()) || 0;
        var adjustedPrice = priceToCopy * (1 + percentage / 100);
        $('#main-price').val(adjustedPrice.toFixed(2)).trigger('input');
        $('#percentageModal').modal('hide');
    });

    // Save Changes Button Click Handler
    $('#save-changes-btn').on('click', function () {
        // Update hidden form fields
        $('#form-product-name').val($('#main-product-name').val());
        $('#form-description').val($('#main-description').val());
        $('#form-brand-name').val($('#main-brand-name').val());
        $('#form-product-category').val($('#main-product-category').val());
        $('#form-price').val($('#main-price').val());
        $('#form-barcode').val($('#main-barcode').val());

        // Set action to save_changes
        $('#main-form').append('<input type="hidden" name="action" value="save_changes">');

        // Submit the form
        $('#main-form').submit();
    });

    // Revert Changes Button Click Handler
    $('#revert-changes-btn').on('click', function () {
        $('#main-product-name').val(window.initialProductName);
        $('#main-description').val(window.initialDescription);
        $('#main-brand-name').val(window.initialBrandName);
        $('#main-product-category').val(window.initialProductCategory);
        $('#main-price').val(window.initialPrice).trigger('input');
        $('#main-barcode').val('');
        updatePriceDifferences();
        checkForChanges();
    });

    // Image Modal
    $('body').on('click', '.product-image', function () {
        var src = $(this).attr('src');
        $('#modal-image').attr('src', src);
        $('#imageModal').modal('show');
    });

    // Show Top Suggestions Button Click Handler
    $('#show-top-suggestions-btn').on('click', function () {
        // Simulate selecting the top items in the dropdown list
        if ($('#pnp-dropdown option').length > 1) {
            $('#pnp-dropdown option:eq(1)').prop('selected', true).trigger('change');
        }
        if ($('#checkers-dropdown option').length > 1) {
            $('#checkers-dropdown option:eq(1)').prop('selected', true).trigger('change');
        }
    });



    // Utility function to escape HTML to prevent XSS
    function escapeHtml(text) {
        if (!text) return '';
        return String(text).replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    // Perform initial search on page load
    $('#search-term').val(window.initialProductName);
    performSearch();

    // Utility function to decode HTML entities
    function decodeHtml(text) {
        if (!text) return '';
        var txt = document.createElement("textarea");
        txt.innerHTML = text;
        return txt.value;
    }
});
