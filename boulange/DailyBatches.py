class DeliveryDateDispatch:
    products: dict[str, int]

    def __init__(self, delivery_date):
        self.delivery_date = delivery_date
        self.products = {}

    def add(self, productLine):
        if productLine.product.ref not in self.products:
            self.products[productLine.product.ref] = 0
        self.products[productLine.product.ref] += productLine.quantity


class ProductBatch:
    quantity = 0
    delivery_date_dispatch: dict[int, DeliveryDateDispatch]

    def __init__(self, product):
        self.product = product
        self.delivery_date_dispatch = {}

    def add(self, productLine, deliveryDate):
        self.quantity += productLine.quantity * productLine.product.coef
        if deliveryDate.id not in self.delivery_date_dispatch:
            self.delivery_date_dispatch[deliveryDate.id] = DeliveryDateDispatch(
                deliveryDate
            )
        self.delivery_date_dispatch[deliveryDate.id].add(productLine)

    def list_ingredients(self):
        for line in self.product.productline_set.all():
            yield line.display(self.quantity)


class Preparation:
    def __init__(self, name, quantity, water_qty):
        self.name = name
        self.quantity = quantity
        self.water_qty = water_qty
        self.is_levain_froment = True if name == "Levain froment" else False
        self.is_levain_sarrasin = True if name == "Levain sarrasin" else False
        self.is_rice = True if name == "Flocons de riz" else False

    def round_quantity(self):
        quantity = self.quantity
        if self.is_levain_sarrasin:
            # including future levain chef
            quantity += 20
        if quantity % 10 == 0:
            return quantity
        return (int(quantity / 10) + 1) * 10

    def refresh_flour_water(self, initial_qty, target_qty, water_percentage):
        missing = target_qty - initial_qty
        water = missing * water_percentage / 100
        flour = missing - water
        return {"flour": flour, "water": water}

    def refresh_first(self):
        return self.refresh_flour_water(100, 300, 60)

    def refresh_first_sarrasin(self):
        return self.refresh_flour_water(20, 100, 50)

    def refresh_second(self):
        return self.refresh_flour_water(300, self.round_quantity(), 50)

    def refresh_second_sarrasin(self):
        return self.refresh_flour_water(100, self.round_quantity(), 50)


class DailyBatches:
    batches: dict[int, ProductBatch]

    def __init__(self):
        self.batches = {}

    def add(self, productLine, deliveryDate):
        base_product = productLine.product.orig_product or productLine.product
        if base_product.id not in self.batches:
            self.batches[base_product.id] = ProductBatch(base_product)
        self.batches[base_product.id].add(productLine, deliveryDate)

    def get_preparations(self):
        preparations = {}
        for batch in self.batches.values():
            for line in batch.product.productline_set.all():
                if (
                    line.ingredient.name.startswith("Levain")
                    or line.ingredient.needs_soaking
                ):
                    if line.ingredient.name not in preparations:
                        preparations[line.ingredient.name] = Preparation(
                            line.ingredient.name, 0, 0
                        )
                    preparations[line.ingredient.name].quantity += (
                        line.quantity * batch.quantity
                    )
                    preparations[line.ingredient.name].water_qty += (
                        line.quantity * batch.quantity * line.ingredient.soaking_coef
                    )

        return preparations
