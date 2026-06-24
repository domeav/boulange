// Live "raw dough weight" for the product recipe, shown below the ingredient inline
// in the admin and recomputed as the user edits quantities / coef / nb_units / base product.
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
        var out = document.getElementById("recipe-dough-weight");
        var factorsEl = document.getElementById("dough-ingredient-factors");
        var weightsEl = document.getElementById("dough-product-raw-weights");
        if (!out || !factorsEl || !weightsEl) {
            return;
        }
        var factors = JSON.parse(factorsEl.textContent);
        var productRawWeights = JSON.parse(weightsEl.textContent);

        function numValue(id) {
            var el = document.getElementById(id);
            if (!el) {
                return 0;
            }
            var v = parseFloat(el.value);
            return isNaN(v) ? 0 : v;
        }

        function compute() {
            var group = document.getElementById("raw_ingredients-group");
            if (!group) {
                return;
            }
            var notWeighable = false;
            var directSum = 0;

            group.querySelectorAll('input[name$="-quantity"]').forEach(function (qtyInput) {
                var prefix = qtyInput.name.slice(0, -"-quantity".length);
                var select = group.querySelector('[name="' + prefix + '-ingredient"]');
                var del = group.querySelector('[name="' + prefix + '-DELETE"]');
                if (del && del.checked) {
                    return;
                }
                if (!select || !select.value) {
                    return;
                }
                var qty = parseFloat(qtyInput.value);
                if (isNaN(qty) || qty === 0) {
                    return;
                }
                var factor = factors[select.value];
                if (factor === null || factor === undefined) {
                    notWeighable = true;
                    return;
                }
                directSum += qty * factor;
            });

            // orig_product (base dough) contribution, scaled by coef
            var base = 0;
            var origSelect = document.getElementById("id_orig_product");
            if (origSelect && origSelect.value) {
                var baseRaw = productRawWeights[origSelect.value];
                if (baseRaw === null || baseRaw === undefined) {
                    notWeighable = true;
                } else {
                    base = baseRaw * numValue("id_coef");
                }
            }

            if (notWeighable) {
                out.textContent = "non calculable (ingrédient non pesable)";
                return;
            }

            var total = directSum + base;
            var nbUnits = numValue("id_nb_units") || 1;
            var perUnit = total / nbUnits;
            out.textContent =
                Math.round(total) + " g (recette pour " + nbUnits + " u. — " + Math.round(perUnit) + " g/u.)";
        }

        var watchedIds = ["id_coef", "id_nb_units", "id_orig_product"];
        function isWatched(target) {
            if (!target) {
                return false;
            }
            if (watchedIds.indexOf(target.id) >= 0) {
                return true;
            }
            return !!(target.closest && target.closest("#raw_ingredients-group"));
        }

        document.addEventListener("input", function (e) {
            if (isWatched(e.target)) {
                compute();
            }
        });
        // covers <select> changes (ingredient / orig_product) and inline row add/delete
        document.addEventListener("change", function (e) {
            if (isWatched(e.target)) {
                compute();
            }
        });

        compute();
    });
})();
