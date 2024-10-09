class DeliveryPointDispatch:
    recipes : dict[str, int]
    def __init__(self, delivery_point):
        self.delivery_point = delivery_point
        self.recipes = {}
    def add(self, recipeLine):
        if recipeLine.recipe.ref not in self.recipes:
            self.recipes[recipeLine.recipe.ref] = 0
        self.recipes[recipeLine.recipe.ref] += recipeLine.quantity
        

class RecipeBatch:
    quantity = 0
    delivery_point_dispatch : dict[int, DeliveryPointDispatch]
    def __init__(self, recipe):
        self.recipe = recipe
        self.delivery_point_dispatch = {}
    def add(self, recipeLine, deliveryPoint):
        self.quantity += recipeLine.quantity * recipeLine.recipe.coef
        if deliveryPoint.id not in self.delivery_point_dispatch:
            self.delivery_point_dispatch[deliveryPoint.id] = DeliveryPointDispatch(deliveryPoint)
        self.delivery_point_dispatch[deliveryPoint.id].add(recipeLine)
    def list_ingredients(self):
        for line in self.recipe.recipeline_set.all():
            yield line.display(self.quantity)

class DailyBatches:
    batches: dict[int, RecipeBatch]
    def __init__(self):
        self.batches = {}
    def add(self, recipeLine, deliveryPoint):
        base_recipe = recipeLine.recipe.orig_recipe or recipeLine.recipe
        if base_recipe.id not in self.batches:
            self.batches[base_recipe.id] = RecipeBatch(base_recipe)
        self.batches[base_recipe.id].add(recipeLine, deliveryPoint)
