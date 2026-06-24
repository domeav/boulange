// Live order total, shown below the order-line inline in the admin and recomputed
// as the user edits products / quantities / customer. Mirrors OrderLine.get_price:
// a professional customer's lines are net of TVA and get the pro discount.
(function () {
    "use strict";

    function ready(fn) {
        if (document.readyState !== "loading") {
            fn();
        } else {
            document.addEventListener("DOMContentLoaded", fn);
        }
    }

    ready(function () {
        var out = document.getElementById("order-total-price");
        var pricesEl = document.getElementById("order-product-prices");
        var customersEl = document.getElementById("order-customers");
        var tvaEl = document.getElementById("order-tva");
        if (!out || !pricesEl || !customersEl || !tvaEl) {
            return;
        }
        var prices = JSON.parse(pricesEl.textContent);
        var customers = JSON.parse(customersEl.textContent);
        var tva = JSON.parse(tvaEl.textContent);

        function compute() {
            var group = document.getElementById("lines-group");
            if (!group) {
                return;
            }

            var pro = false;
            var discount = 0;
            var custSelect = document.getElementById("id_customer");
            if (custSelect && custSelect.value) {
                var customer = customers[custSelect.value];
                if (customer) {
                    pro = customer.pro;
                    discount = customer.discount;
                }
            }

            var total = 0;
            group.querySelectorAll('input[name$="-quantity"]').forEach(function (qtyInput) {
                var prefix = qtyInput.name.slice(0, -"-quantity".length);
                var productSelect = group.querySelector('[name="' + prefix + '-product"]');
                var del = group.querySelector('[name="' + prefix + '-DELETE"]');
                if (del && del.checked) {
                    return;
                }
                if (!productSelect || !productSelect.value) {
                    return;
                }
                var qty = parseFloat(qtyInput.value);
                if (isNaN(qty) || qty === 0) {
                    return;
                }
                var price = prices[productSelect.value];
                if (price === undefined || price === null) {
                    return;
                }
                var line = price * qty;
                if (pro) {
                    line = (line - (line * tva) / 100) * (1 - discount / 100);
                }
                total += line;
            });

            out.textContent = total.toFixed(2) + " €";
        }

        function isWatched(target) {
            if (!target) {
                return false;
            }
            if (target.id === "id_customer") {
                return true;
            }
            return !!(target.closest && target.closest("#lines-group"));
        }

        document.addEventListener("input", function (e) {
            if (isWatched(e.target)) {
                compute();
            }
        });
        document.addEventListener("change", function (e) {
            if (isWatched(e.target)) {
                compute();
            }
        });
        // select2 (the autocomplete widget used for customer/product) fires its change
        // through jQuery, which native listeners can miss, so also bind via django.jQuery.
        if (window.django && window.django.jQuery) {
            window.django.jQuery(document).on("change", function (e) {
                if (isWatched(e.target)) {
                    compute();
                }
            });
        }

        compute();
    });
})();
