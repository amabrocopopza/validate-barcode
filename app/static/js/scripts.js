// static/js/scripts.js

$(document).ready(function () {
    console.log('Document is ready.');
    hideSpinner();
    // Show spinner function
    function showSpinner() {
        $('#spinner').show();
    }

    // Hide spinner function
    function hideSpinner() {
        $('#spinner').hide();
    }

    function decodeHtmlEntities(text) {
        var txt = document.createElement("textarea");
        txt.innerHTML = text;
        return txt.value;
    }

    // Variables to store selected product prices and barcodes
    var mainPrice = parseFloat($('#main-price').val()) || 0;
    var pnpPrice = 0;
    var pnpBarcode = '';
    var checkersPrice = 0;
    var checkersBarcode = '';
    var deeliverPrice = 0;
    var deeliverBarcode = '';

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

        // Update Deeliver Price Difference
        if (deeliverPrice > 0) {
            var deeliverDiffPercentage = ((mainPrice - deeliverPrice) / deeliverPrice) * 100;
            var deeliverDiffAmount = mainPrice - deeliverPrice;
            displayPriceDifference('deeliver', deeliverDiffPercentage, deeliverDiffAmount);
        } else {
            $('#deeliver-price-difference').hide();
        }

        // Update Copy Button Visibility
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

    // Perform initial search on page load
    $('#search-term').val(decodeHtmlEntities(window.initialProductName));
    performSearch();

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
        // Clear previous suggestions and product details
        $('#pnp-dropdown').empty().append('<option value="">-- Select a PnP Product --</option>');
        $('#checkers-dropdown').empty().append('<option value="">-- Select a Checkers Product --</option>');
        $('#deeliver-dropdown').empty().append('<option value="">-- Select a Deeliver Product --</option>');
        $('#pnp-product-details').empty();
        $('#checkers-product-details').empty();
        $('#deeliver-product-details').empty();

        // Perform searches
        const pnpRequest = $.ajax({
            url: pnpSearchUrl,
            method: 'POST',
            data: { 'search_term': searchTerm },
            dataType: 'json'
        });

        const checkersRequest = $.ajax({
            url: checkersSearchUrl,
            method: 'POST',
            data: { 'search_term': searchTerm },
            dataType: 'json'
        });

        const deeliverRequest = $.ajax({
            url: deeliverSearchUrl,
            method: 'POST',
            data: { 'search_term': searchTerm },
            dataType: 'json'
        });

        // Handle PnP response
        pnpRequest.done(function (data) {
            if (data.success) {
                populateDropdown('pnp', data.products);
            } else {
                // Update the dropdown to show no products found
                $('#pnp-dropdown').empty().append('<option value="">-- No PnP Products Found --</option>');
                $('#pnp-product-details').empty();
            }
        }).fail(function () {
            alert('An error occurred while fetching suggestions from PnP.');
        });

        // Handle Checkers response
        checkersRequest.done(function (data) {
            if (data.success) {
                populateDropdown('checkers', data.products);
            } else {
                $('#checkers-dropdown').empty().append('<option value="">-- No Checkers Products Found --</option>');
                $('#checkers-product-details').empty();
            }
        }).fail(function () {
            alert('An error occurred while fetching suggestions from Checkers.');
        });

        // Handle Deeliver response
        deeliverRequest.done(function (data) {
            if (data.success) {
                populateDropdown('deeliver', data.products);
            } else {
                $('#deeliver-dropdown').empty().append('<option value="">-- No Deeliver Products Found --</option>');
                $('#deeliver-product-details').empty();
            }
        }).fail(function () {
            alert('An error occurred while fetching suggestions from Deeliver.');
        });
    }


    function populateDropdown(source, products) {
        let dropdownId = '';
        if (source === 'pnp') {
            dropdownId = '#pnp-dropdown';
        } else if (source === 'checkers') {
            dropdownId = '#checkers-dropdown';
        } else if (source === 'deeliver') {
            dropdownId = '#deeliver-dropdown';
        }

        const dropdown = $(dropdownId);
        dropdown.empty();

        if (products.length > 0) {
            dropdown.append(`<option value="">-- Select a ${source.charAt(0).toUpperCase() + source.slice(1)} Product --</option>`);
            products.forEach(product => {
                if (source === 'pnp') {
                    const option = `<option value="${product.code}">${escapeHtml(product.name)} - ${escapeHtml(product.price)}</option>`;
                    dropdown.append(option);
                } else if (source === 'checkers') {
                    const option = `<option value="${product.href}">${escapeHtml(product.name)} - R${escapeHtml(product.price)}</option>`;
                    dropdown.append(option);
                } else if (source === 'deeliver') {
                    const option = `<option value="${product.barcode}">${escapeHtml(product.product_name)} - R${escapeHtml(product.retail_price)}</option>`;
                    dropdown.append(option);
                }
            });
        } else {
            dropdown.append(`<option value="">-- No ${source.charAt(0).toUpperCase() + source.slice(1)} Products Found --</option>`);
        }
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

    $('#deeliver-dropdown').change(function () {
        const barcode = $(this).val();
        if (barcode) {
            displayProductDetails('deeliver', barcode);
        } else {
            $('#deeliver-product-details').empty();
            deeliverPrice = 0;
            deeliverBarcode = '';
            updatePriceDifferences();
            updateCopyButtonVisibility();
        }
    });

    // Display Product Details Function
    function displayProductDetails(source, identifier) {
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
        } else if (source === 'deeliver') {
            fetchUrl = deeliverFetchDetailsUrl;
            data = { 'barcode': identifier };
            detailsDivId = '#deeliver-product-details';
        }

        // Show spinner in the specific product details div
        $(`${detailsDivId} .product-spinner`).show();

        $.ajax({
            url: fetchUrl,
            method: 'POST',
            data: data,
            dataType: 'json',
            success: function (response) {
                $(`${detailsDivId} .product-spinner`).hide();
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
                    } else if (source === 'deeliver') {
                        productInfo = response.product_info;
                        deeliverPrice = parseFloat(productInfo.retail_price) || 0;
                        deeliverBarcode = productInfo.barcode || '';
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
                    // Deeliver products may not have images

                    let detailsHtml = `
                        ${imageUrl ? `<img src="${escapeHtml(imageUrl)}" alt="Product Image" class="product-image mb-3" data-toggle="modal" data-target="#imageModal">` : ''}
                        <h4 class="product-name">${escapeHtml(decodeHtml(productInfo.product_name || productInfo.name || 'N/A'))}
                            <span class="copy-field-btn" data-field="product_name" data-value="${escapeHtml(productInfo.product_name || productInfo.name || '')}">[Copy]</span>
                        </h4>
                        <p><strong>Price:</strong> R${escapeHtml(productInfo.product_price || productInfo.price_value || productInfo.retail_price || '0.00')}
                            <span class="copy-price-btn" data-price="${escapeHtml(productInfo.product_price || productInfo.price_value || productInfo.retail_price || '0.00')}">[Copy Price]</span>
                        </p>
                        <p><strong>Barcode:</strong> ${escapeHtml(productInfo.barcode || 'N/A')}
                            <span class="copy-field-btn" data-field="barcode" data-value="${escapeHtml(productInfo.barcode || '')}">[Copy]</span>
                        </p>
                        <p><strong>Description:</strong> ${escapeHtml(decodeHtml(productInfo.description || 'No description available.'))}
                            <span class="copy-field-btn" data-field="description" data-value="${escapeHtml(productInfo.description || '')}">[Copy]</span>
                        </p>
                        <p><strong>Supplier:</strong> ${escapeHtml(productInfo.brand || productInfo.product_brand || productInfo.supplier_name || 'N/A')}
                            <span class="copy-field-btn" data-field="brand_name" data-value="${escapeHtml(productInfo.brand || productInfo.product_brand || productInfo.supplier_name || '')}">[Copy]</span>
                        </p>
                        ${source !== 'pnp' ? `
                        <p><strong>Category:</strong> ${escapeHtml(decodeHtml(productInfo.category || productInfo.categories || 'N/A'))}
                            <span class="copy-field-btn" data-field="product_category" data-value="${escapeHtml(productInfo.category || productInfo.categories || '')}">[Copy]</span>
                        </p>
                        ` : ''}
                        <p><strong>Unit of Measure:</strong> ${escapeHtml(productInfo.unit_of_measure || 'N/A')}</p>
                    `;
                    $(detailsDivId).html(detailsHtml);

                    // Attach event listeners to Copy buttons (move this inside the success callback)
                    $(detailsDivId).find('.copy-field-btn').click(function () {
                        const field = $(this).data('field');
                        const value = $(this).data('value');
                        const fieldId = `#main-${field.replace(/_/g, '-')}`; // Replace underscores with hyphens
                        $(fieldId).val(value).trigger('input');
                    });

                    // Attach event listener to Copy Price button
                    $(detailsDivId).find('.copy-price-btn').click(function () {
                        const price = parseFloat($(this).data('price')) || 0;
                        if (price > 0) {
                            // Store the price to copy
                            $('#percentageModal').data('priceToCopy', price);
                            // Show the modal
                            $('#percentageModal').modal('show');
                        } else {
                            alert('Invalid price to copy.');
                        }
                    });

                    updatePriceDifferences();
                    updateCopyButtonVisibility();

                } else {
                    alert(response.message || 'Failed to fetch product details.');
                }
            },
            error: function (xhr, status, error) {
                $(`${detailsDivId} .product-spinner`).hide();
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
        } else if ((pnpPrice > 0 || checkersPrice > 0 || deeliverPrice > 0) && !(pnpPrice > 0 && checkersPrice > 0 && deeliverPrice > 0)) {
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
        } else if (pnpPrice > 0 && checkersPrice === 0 && deeliverPrice === 0) {
            priceToCopy = pnpPrice;
        } else if (checkersPrice > 0 && pnpPrice === 0 && deeliverPrice === 0) {
            priceToCopy = checkersPrice;
        } else if (deeliverPrice > 0 && pnpPrice === 0 && checkersPrice === 0) {
            priceToCopy = deeliverPrice;
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
    $('#save-changes-btn').on('click', function (e) {
        e.preventDefault();
        // Update hidden form fields
        $('#form-product-name').val($('#main-product-name').val());
        $('#form-description').val($('#main-description').val());
        $('#form-brand-name').val($('#main-brand-name').val());
        $('#form-product-category').val($('#main-product-category').val());
        $('#form-price').val($('#main-price').val());
        $('#form-barcode').val($('#main-barcode').val());

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
        if ($('#deeliver-dropdown option').length > 1) {
            $('#deeliver-dropdown option:eq(1)').prop('selected', true).trigger('change');
        }
    });

    // Utility function to decode HTML entities
    function decodeHtml(text) {
        if (!text) return '';
        var txt = document.createElement("textarea");
        txt.innerHTML = text;
        return txt.value;
    }

    // Utility function to escape HTML to prevent XSS
    function escapeHtml(text) {
        if (!text) return '';
        return String(text).replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }
});
