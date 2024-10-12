class DeliveryPointDispatch:
    products: dict[str, int]

    def __init__(self, delivery_point):
        self.delivery_point = delivery_point
        self.products = {}

    def add(self, productLine):
        if productLine.product.ref not in self.products:
            self.products[productLine.product.ref] = 0
        self.products[productLine.product.ref] += productLine.quantity


class ProductBatch:
    quantity = 0
    delivery_point_dispatch: dict[int, DeliveryPointDispatch]

    def __init__(self, product):
        self.product = product
        self.delivery_point_dispatch = {}

    def add(self, productLine, deliveryPoint):
        self.quantity += productLine.quantity * productLine.product.coef
        if deliveryPoint.id not in self.delivery_point_dispatch:
            self.delivery_point_dispatch[deliveryPoint.id] = DeliveryPointDispatch(
                deliveryPoint
            )
        self.delivery_point_dispatch[deliveryPoint.id].add(productLine)

    def list_ingredients(self):
        for line in self.product.productline_set.all():
            yield line.display(self.quantity)


class Preparation:
    def __init__(self, name, quantity):
        self.name = name
        self.quantity = quantity
        self.is_levain = True if name.startswith("Levain") else False


class DailyBatches:
    batches: dict[int, ProductBatch]

    def __init__(self):
        self.batches = {}

    def add(self, productLine, deliveryPoint):
        base_product = productLine.product.orig_product or productLine.product
        if base_product.id not in self.batches:
            self.batches[base_product.id] = ProductBatch(base_product)
        self.batches[base_product.id].add(productLine, deliveryPoint)

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
                            line.ingredient.name, 0
                        )
                    preparations[line.ingredient.name].quantity += (
                        line.quantity * batch.quantity
                    )
        return preparations
