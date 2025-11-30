from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from django.test import Client, TestCase
from rest_framework.test import APIClient

from .models import (
    Customer,
    DeliveryDate,
    Ingredient,
    Order,
    OrderLine,
    Product,
    WeeklyDelivery,
)


class ExtendedTestCase(TestCase):
    def assertAlmostEqual(self, o1, o2, msg=None, places=3):
        if isinstance(o1, dict) and isinstance(o2, dict):
            self.assertEqual(o1.keys(), o2.keys())
            for key, value in o1.items():
                self.assertAlmostEqual(o1[key], o2[key], msg=msg, places=places)
        else:
            super().assertAlmostEqual(o1, o2, msg=msg, places=places)


def populate():
    admin = Customer(username="admin", display_name="admin", email="admin@toto.net", is_staff=True)
    admin.save()
    store = Customer(
        username="store",
        display_name="store",
        email="store@toto.net",
        is_professional=True,
        pro_discount_percentage=5,
        address="the store address",
    )
    store.save()
    monday_delivery = WeeklyDelivery(customer=store, batch_target="SAME_DAY", day_of_week=0)
    monday_delivery.save()
    monday_delivery.generate_delivery_dates()
    wednesday_delivery = WeeklyDelivery(customer=store, batch_target="PREVIOUS_DAY", day_of_week=2)
    wednesday_delivery.save()
    wednesday_delivery.generate_delivery_dates()
    count = DeliveryDate.objects.count()
    monday_delivery.generate_delivery_dates()
    wednesday_delivery.generate_delivery_dates()
    assert count == DeliveryDate.objects.count()

    guy = Customer(
        username="guy",
        display_name="guy the client",
        email="guy@toto.net",
        is_professional=False,
    )
    guy.save()
    return {
        "monday_delivery": monday_delivery,
        "wednesday_delivery": wednesday_delivery,
        "store": store,
        "guy": guy,
        "admin": admin,
    }


class ActionsTests(ExtendedTestCase):
    fixtures = ["data/base.json"]
    next_monday = date.today() + timedelta(days=7 - date.today().weekday())

    def setUp(self):
        self.context = populate()

    def test_GK(self):
        delivery_date = DeliveryDate.objects.filter(weekly_delivery=self.context["monday_delivery"]).get(date=self.next_monday)
        order = Order(
            customer=self.context["guy"],
            delivery_date=delivery_date,
        )
        order.save()
        gk = Product.objects.get(ref="GK")
        line = OrderLine(order=order, product=(gk), quantity=1)
        line.save()
        actions = order.get_actions(self.next_monday - timedelta(2))
        actions.finalize()
        self.assertEqual(len(actions["delivery"]), 0)
        self.assertEqual(len(actions["bakery"]), 0)
        self.assertEqual(len(actions["preparation"]["levain"]), 0)
        self.assertEqual(len(actions["preparation"]["trempage"]), 0)
        actions = order.get_actions(self.next_monday - timedelta(1))
        actions.finalize()
        self.assertEqual(len(actions["delivery"]), 0)
        self.assertEqual(len(actions["bakery"]), 0)
        self.assertEqual(
            actions["preparation"],
            {
                "levain": {Ingredient.objects.get(name="Levain froment"): 5.0},
                "trempage": {Ingredient.objects.get(name="Graines kasha"): {"dry": 75.0, "soaking_qty": 75.0, "soaking_ingredient": Ingredient.objects.get(name="Eau")}},
            },
        )
        actions = order.get_actions(self.next_monday)
        actions.finalize()
        self.assertEqual(actions["delivery"], {delivery_date: {gk: 1}})
        self.assertEqual(
            actions["bakery"],
            {
                gk: {
                    "ingredients": {
                        Ingredient.objects.get(name="Eau"): 421.0,
                        Ingredient.objects.get(name="Farine blé"): 663.0,
                        Ingredient.objects.get(name="Graines kasha"): 150.0,
                        Ingredient.objects.get(name="Levain froment"): 5.0,
                        Ingredient.objects.get(name="Sel"): 12.0,
                    },
                    "division": {gk: 1},
                    "weight": 1251.0,
                }
            },
        )
        self.assertEqual(len(actions["preparation"]["trempage"]), 0)
        self.assertEqual(len(actions["preparation"]["levain"]), 0)

    def test_GK_previous_day(self):
        delivery_date = DeliveryDate.objects.filter(weekly_delivery=self.context["wednesday_delivery"]).get(date=self.next_monday + timedelta(2))
        order = Order(
            customer=self.context["guy"],
            delivery_date=delivery_date,
        )
        order.save()
        gk = Product.objects.get(ref="GK")
        line = OrderLine(order=order, product=(gk), quantity=1)
        line.save()
        actions = order.get_actions(self.next_monday)
        actions.finalize()
        self.assertEqual(len(actions["delivery"]), 0)
        self.assertEqual(len(actions["bakery"]), 0)
        self.assertEqual(
            actions["preparation"],
            {
                "levain": {Ingredient.objects.get(name="Levain froment"): 5.0},
                "trempage": {Ingredient.objects.get(name="Graines kasha"): {"dry": 75.0, "soaking_qty": 75.0, "soaking_ingredient": Ingredient.objects.get(name="Eau")}},
            },
        )
        actions = order.get_actions(self.next_monday + timedelta(1))
        actions.finalize()
        self.assertEqual(len(actions["delivery"]), 0)
        self.assertEqual(
            actions["bakery"],
            {
                gk: {
                    "ingredients": {
                        Ingredient.objects.get(name="Eau"): 421.0,
                        Ingredient.objects.get(name="Farine blé"): 663.0,
                        Ingredient.objects.get(name="Graines kasha"): 150.0,
                        Ingredient.objects.get(name="Levain froment"): 5.0,
                        Ingredient.objects.get(name="Sel"): 12.0,
                    },
                    "division": {
                        gk: 1,
                    },
                    "weight": 1251.0,
                }
            },
        )
        self.assertEqual(len(actions["preparation"]["levain"]), 0)
        self.assertEqual(len(actions["preparation"]["trempage"]), 0)
        actions = order.get_actions(self.next_monday + timedelta(2))
        actions.finalize()
        self.assertEqual(actions["delivery"], {delivery_date: {gk: 1}})
        self.assertEqual(len(actions["bakery"]), 0)
        self.assertEqual(len(actions["preparation"]["levain"]), 0)
        self.assertEqual(len(actions["preparation"]["trempage"]), 0)

    def test_small_breads_batch(self):
        delivery_date = DeliveryDate.objects.filter(weekly_delivery=self.context["monday_delivery"]).get(date=self.next_monday)
        order = Order(
            customer=self.context["guy"],
            delivery_date=delivery_date,
        )
        order.save()
        gsa = Product.objects.get(ref="GSa")
        gse = Product.objects.get(ref="GSe")
        psa = Product.objects.get(ref="PSa")
        pse = Product.objects.get(ref="PSe")
        OrderLine(order=order, product=(psa), quantity=5).save()
        OrderLine(order=order, product=(pse), quantity=3).save()

        actions = order.get_actions(self.next_monday - timedelta(2))
        actions.finalize()
        self.assertEqual(len(actions["delivery"]), 0)
        self.assertEqual(len(actions["bakery"]), 0)
        self.assertEqual(len(actions["preparation"]["levain"]), 0)
        self.assertEqual(len(actions["preparation"]["trempage"]), 0)
        actions = order.get_actions(self.next_monday - timedelta(1))
        actions.finalize()
        self.assertEqual(len(actions["delivery"]), 0)
        self.assertEqual(len(actions["bakery"]), 0)
        self.assertEqual(
            actions["preparation"],
            {"levain": {Ingredient.objects.get(name="Levain sarrasin"): 15.0, Ingredient.objects.get(name="Levain froment"): 10.0}, "trempage": {}},
        )
        actions = order.get_actions(self.next_monday)
        actions.finalize()
        self.assertEqual(
            actions["delivery"],
            {delivery_date: {psa: 5, pse: 3}},
        )
        self.assertAlmostEqual(
            actions["bakery"],
            {
                gsa: {
                    "ingredients": {
                        Ingredient.objects.get(name="Eau"): 1458.0,
                        Ingredient.objects.get(name="Farine sarrasin"): 1548.0,
                        Ingredient.objects.get(name="Levain sarrasin"): 15.0,
                        Ingredient.objects.get(name="Sel"): 30.0,
                    },
                    "division": {psa: 6},
                    "weight": 3051.0,
                },
                gse: {
                    "ingredients": {
                        Ingredient.objects.get(name="Eau"): 826.0,
                        Ingredient.objects.get(name="Farine blé"): 320,
                        Ingredient.objects.get(name="Farine seigle"): 938,
                        Ingredient.objects.get(name="Levain froment"): 10,
                        Ingredient.objects.get(name="Sel"): 20,
                    },
                    "division": {pse: 4},
                    "weight": 2114,
                },
            },
        )
        self.assertEqual(len(actions["preparation"]["levain"]), 0)
        self.assertEqual(len(actions["preparation"]["trempage"]), 0)

    def test_GK_batch(self):
        delivery_date = DeliveryDate.objects.filter(weekly_delivery=self.context["monday_delivery"]).get(date=self.next_monday)
        order = Order(
            customer=self.context["guy"],
            delivery_date=delivery_date,
        )
        order.save()
        gk = Product.objects.get(ref="GK")
        tgk = Product.objects.get(ref="TGK")
        pk = Product.objects.get(ref="PK")
        OrderLine(order=order, product=(gk), quantity=4).save()
        OrderLine(order=order, product=(tgk), quantity=2).save()
        OrderLine(order=order, product=(pk), quantity=4).save()

        actions = order.get_actions(self.next_monday - timedelta(2))
        actions.finalize()
        self.assertEqual(len(actions["delivery"]), 0)
        self.assertEqual(len(actions["bakery"]), 0)
        self.assertEqual(len(actions["preparation"]["levain"]), 0)
        self.assertEqual(len(actions["preparation"]["trempage"]), 0)
        actions = order.get_actions(self.next_monday - timedelta(1))
        actions.finalize()
        self.assertEqual(len(actions["delivery"]), 0)
        self.assertEqual(len(actions["bakery"]), 0)
        self.assertEqual(
            actions["preparation"],
            {
                "levain": {Ingredient.objects.get(name="Levain froment"): 50.0},
                "trempage": {Ingredient.objects.get(name="Graines kasha"): {"dry": 750.0, "soaking_qty": 750.0, "soaking_ingredient": Ingredient.objects.get(name="Eau")}},
            },
        )
        actions = order.get_actions(self.next_monday)
        actions.finalize()
        self.assertEqual(
            actions["delivery"],
            {
                delivery_date: {
                    gk: 4,
                    tgk: 2,
                    pk: 4,
                }
            },
        )
        self.assertAlmostEqual(
            actions["bakery"],
            {
                gk: {
                    "ingredients": {
                        Ingredient.objects.get(name="Eau"): 4210.0,
                        Ingredient.objects.get(name="Farine blé"): 6630.0,
                        Ingredient.objects.get(name="Graines kasha"): 1500.0,
                        Ingredient.objects.get(name="Levain froment"): 50.0,
                        Ingredient.objects.get(name="Sel"): 120.0,
                    },
                    "division": {gk: 4, tgk: 2, pk: 4},
                    "weight": 12510.0,
                }
            },
        )
        self.assertEqual(len(actions["preparation"]["levain"]), 0)
        self.assertEqual(len(actions["preparation"]["trempage"]), 0)

    def test_BR(self):
        delivery_date = DeliveryDate.objects.filter(weekly_delivery=self.context["monday_delivery"]).get(date=self.next_monday)
        order = Order(
            customer=self.context["guy"],
            delivery_date=delivery_date,
        )
        order.save()
        br = Product.objects.get(ref="BR")
        line = OrderLine(order=order, product=(br), quantity=1)
        line.save()
        actions = order.get_actions(self.next_monday - timedelta(2))
        actions.finalize()
        self.assertEqual(len(actions["delivery"]), 0)
        self.assertEqual(len(actions["bakery"]), 0)
        self.assertEqual(len(actions["preparation"]["levain"]), 0)
        self.assertEqual(len(actions["preparation"]["trempage"]), 0)
        actions = order.get_actions(self.next_monday - timedelta(1))
        actions.finalize()
        self.assertEqual(len(actions["delivery"]), 0)
        self.assertEqual(len(actions["bakery"]), 0)
        self.assertEqual(
            actions["preparation"],
            {
                "levain": {Ingredient.objects.get(name="Levain froment"): 6.0},
                "trempage": {
                    Ingredient.objects.get(name="Flocons de riz"): {
                        "dry": 15.0,
                        "soaking_qty": 150.0,
                        "soaking_ingredient": Ingredient.objects.get(name="Eau"),
                        "warning": "⚠ prévoir 10% de marge",
                    },
                    Ingredient.objects.get(name="Raisins secs"): {"dry": 45.0, "soaking_qty": 45.0, "soaking_ingredient": Ingredient.objects.get(name="Eau")},
                },
            },
        )
        actions = order.get_actions(self.next_monday)
        actions.finalize()
        self.assertEqual(actions["delivery"], {delivery_date: {br: 1}})
        self.assertEqual(
            actions["bakery"],
            {
                br: {
                    "ingredients": {
                        Ingredient.objects.get(name="Eau"): 8.0,
                        Ingredient.objects.get(name="Farine blé"): 324.0,
                        Ingredient.objects.get(name="Flocons de riz"): 165.0,
                        Ingredient.objects.get(name="Huile"): 25.0,
                        Ingredient.objects.get(name="Levain froment"): 6.0,
                        Ingredient.objects.get(name="Raisins secs"): 90.0,
                        Ingredient.objects.get(name="Sel"): 6.0,
                        Ingredient.objects.get(name="Sucre"): 35.0,
                    },
                    "division": {br: 1},
                    "weight": 659.0,
                }
            },
        )
        self.assertEqual(len(actions["preparation"]["levain"]), 0)
        self.assertEqual(len(actions["preparation"]["trempage"]), 0)

    def test_FOC(self):
        delivery_date = DeliveryDate.objects.filter(weekly_delivery=self.context["monday_delivery"]).get(date=self.next_monday)
        order = Order(
            customer=self.context["guy"],
            delivery_date=delivery_date,
        )
        order.save()
        foc = Product.objects.get(ref="FOC")
        line = OrderLine(order=order, product=(foc), quantity=1)
        line.save()
        actions = order.get_actions(self.next_monday - timedelta(2))
        actions.finalize()
        self.assertEqual(len(actions["delivery"]), 0)
        self.assertEqual(len(actions["bakery"]), 0)
        self.assertEqual(len(actions["preparation"]["levain"]), 0)
        self.assertEqual(len(actions["preparation"]["trempage"]), 0)
        actions = order.get_actions(self.next_monday - timedelta(1))
        actions.finalize()
        self.assertEqual(len(actions["delivery"]), 0)
        self.assertEqual(len(actions["bakery"]), 0)
        self.assertEqual(
            actions["preparation"],
            {
                "levain": {Ingredient.objects.get(name="Levain froment"): 12.5},
                "trempage": {Ingredient.objects.get(name="Tomates séchées"): {"dry": 100.0, "soaking_qty": 150.0, "soaking_ingredient": Ingredient.objects.get(name="Huile olive")}},
            },
        )
        actions = order.get_actions(self.next_monday)
        actions.finalize()
        self.assertEqual(actions["delivery"], {delivery_date: {foc: 1}})
        self.assertEqual(
            actions["bakery"],
            {
                foc.orig_product: {
                    "ingredients": {
                        Ingredient.objects.get(name="Eau"): 1240.0,
                        Ingredient.objects.get(name="Farine blé"): 1870.0,
                        Ingredient.objects.get(name="Levain froment"): 12.5,
                        Ingredient.objects.get(name="Sel"): 30.0,
                    },
                    "division": {foc: 24},
                    "weight": 3152.5,
                }
            },
        )
        self.assertEqual(len(actions["preparation"]["levain"]), 0)
        self.assertEqual(len(actions["preparation"]["trempage"]), 0)
        self.assertAlmostEqual(
            actions["bakery"].sub_batches[foc.orig_product],
            {
                foc: {
                    Ingredient.objects.get(name="Huile olive"): 0.0,
                    Ingredient.objects.get(name="Tomates séchées"): 250.0,
                    Ingredient.objects.get(name="Herbes de provence"): 10.0,
                    Ingredient.objects.get(name="Olives"): 200.0,
                    "pâton": 3152.5,
                }
            },
        )

    def test_BB500g(self):
        delivery_date = DeliveryDate.objects.filter(weekly_delivery=self.context["monday_delivery"]).get(date=self.next_monday)
        order = Order(
            customer=self.context["guy"],
            delivery_date=delivery_date,
        )
        order.save()
        bb = Product.objects.get(ref="BB500g")
        line = OrderLine(order=order, product=(bb), quantity=1)
        line.save()
        actions = order.get_actions(self.next_monday - timedelta(2))
        actions.finalize()
        self.assertEqual(len(actions["delivery"]), 0)
        self.assertEqual(len(actions["bakery"]), 0)
        self.assertEqual(len(actions["preparation"]["levain"]), 0)
        self.assertEqual(len(actions["preparation"]["trempage"]), 0)
        actions = order.get_actions(self.next_monday - timedelta(1))
        actions.finalize()
        self.assertEqual(len(actions["delivery"]), 0)
        self.assertEqual(len(actions["bakery"]), 0)
        self.assertEqual(
            actions["preparation"],
            {"levain": {Ingredient.objects.get(name="Levain froment"): 50.0}, "trempage": {}},
        )
        actions = order.get_actions(self.next_monday)
        actions.finalize()
        self.assertEqual(actions["delivery"], {delivery_date: {bb: 1}})
        self.assertEqual(
            actions["bakery"],
            {
                bb: {
                    "ingredients": {
                        Ingredient.objects.get(name="Beurre"): 62.5,
                        Ingredient.objects.get(name="Farine blé"): 250.0,
                        Ingredient.objects.get(name="Lait"): 47.5,
                        Ingredient.objects.get(name="Levain froment"): 50.0,
                        Ingredient.objects.get(name="Oeufs"): 1.5,
                        Ingredient.objects.get(name="Sel"): 2.5,
                        Ingredient.objects.get(name="Sucre"): 50.0,
                    },
                    "division": {bb: 1},
                    "weight": 552.5,
                }
            },
        )
        self.assertEqual(len(actions["preparation"]["levain"]), 0)
        self.assertEqual(len(actions["preparation"]["trempage"]), 0)
        self.assertEqual(len(actions["bakery"].sub_batches), 0)

    def test_rounding(self):
        delivery_date = DeliveryDate.objects.filter(weekly_delivery=self.context["monday_delivery"]).get(date=self.next_monday)
        order = Order(
            customer=self.context["guy"],
            delivery_date=delivery_date,
        )
        order.save()
        gse = Product.objects.get(ref="GSe")
        line = OrderLine(order=order, product=(gse), quantity=6)
        line.save()
        actions = order.get_actions(self.next_monday - timedelta(2))
        actions.finalize()
        self.assertEqual(len(actions["delivery"]), 0)
        self.assertEqual(len(actions["bakery"]), 0)
        self.assertEqual(len(actions["preparation"]["levain"]), 0)
        self.assertEqual(len(actions["preparation"]["trempage"]), 0)
        actions = order.get_actions(self.next_monday - timedelta(1))
        actions.finalize()
        self.assertEqual(len(actions["delivery"]), 0)
        self.assertEqual(len(actions["bakery"]), 0)
        self.assertAlmostEqual(
            actions["preparation"],
            {"levain": {Ingredient.objects.get(name="Levain froment"): 30.0}, "trempage": {}},
        )
        actions = order.get_actions(self.next_monday)
        actions.finalize()
        self.assertEqual(actions["delivery"], {delivery_date: {gse: 6}})
        self.assertAlmostEqual(
            actions["bakery"],
            {
                gse: {
                    "ingredients": {
                        Ingredient.objects.get(name="Eau"): 2478.0,
                        Ingredient.objects.get(name="Farine blé"): 960.0,
                        Ingredient.objects.get(name="Farine seigle"): 2814.0,
                        Ingredient.objects.get(name="Levain froment"): 30.0,
                        Ingredient.objects.get(name="Sel"): 60.0,
                    },
                    "division": {gse: 6},
                    "weight": 6342.0,
                }
            },
        )
        self.assertEqual(len(actions["preparation"]["levain"]), 0)
        self.assertEqual(len(actions["preparation"]["trempage"]), 0)


class RestTests(ExtendedTestCase):
    fixtures = ["data/base.json"]
    next_monday = date.today() + timedelta(days=7 - date.today().weekday())

    def test_generate_delivery_dates(self):
        count = DeliveryDate.objects.count()
        response = self.client.post("/api/generate_delivery_dates/")
        self.assertEqual(response.data, {"message": "Delivery dates generated!"})
        self.assertEqual(response.status_code, 200)
        assert count == DeliveryDate.objects.count()

    def setUp(self):
        self.context = populate()
        self.client = APIClient()
        self.client.force_authenticate(user=self.context["admin"])
        for monday in DeliveryDate.objects.filter(weekly_delivery=self.context["monday_delivery"]):
            recurring_order = Order(customer=self.context["store"], delivery_date=monday)
            recurring_order.save()
            for product, qty in (
                (Product.objects.get(ref="GN"), 5),
                (Product.objects.get(ref="TGN"), 3),
                (Product.objects.get(ref="PK"), 5),
                (Product.objects.get(ref="BR"), 8),
                (Product.objects.get(ref="COOKIE"), 20),
                (Product.objects.get(ref="GSe"), 5),
            ):
                line = OrderLine(order=recurring_order, product=product, quantity=qty)
                line.save()
        for wednesday in DeliveryDate.objects.filter(weekly_delivery=self.context["wednesday_delivery"]):
            recurring_order2 = Order(customer=self.context["store"], delivery_date=wednesday)
            recurring_order2.save()
            for product, qty in (
                (Product.objects.get(ref="FAR"), 5),
                (Product.objects.get(ref="GK"), 5),
                (Product.objects.get(ref="GL"), 5),
                (Product.objects.get(ref="PN"), 8),
                (Product.objects.get(ref="BC"), 10),
                (Product.objects.get(ref="GSe"), 5),
            ):
                line = OrderLine(order=recurring_order2, product=product, quantity=qty)
                line.save()
        simple_order = Order(
            customer=self.context["guy"],
            delivery_date=DeliveryDate.objects.filter(weekly_delivery=self.context["monday_delivery"]).get(date=self.next_monday),
        )
        simple_order.save()
        for product, qty in (
            (Product.objects.get(ref="COOKIE"), 6),
            (Product.objects.get(ref="BR"), 1),
            (Product.objects.get(ref="PN"), 1),
            (Product.objects.get(ref="GSe"), 1),
            (Product.objects.get(ref="GSa"), 1),
        ):
            line = OrderLine(order=simple_order, product=product, quantity=qty)
            line.save()

    def test_products(self):
        response = self.client.get("/api/products/")
        self.assertEqual(response.status_code, 200)
        products = response.data
        self.assertEqual(len(products), 49)
        for product in products:
            if product["name"] == "Semi-complet kasha (1 kg)":
                GK = product
                self.assertEqual(product["ref"], "GK")
                self.assertEqual(product["price"], 6.5)
                self.assertAlmostEqual(product["cost_price"], Decimal(1.6351))
                self.assertAlmostEqual(product["weight"], 1305.98)
                self.assertEqual(len(product["raw_ingredients"]), 5)
            if product["name"] == "Semi-complet kasha (2 kg)":
                self.assertEqual(product["ref"], "TGK")
                self.assertEqual(product["price"], 13)
                self.assertAlmostEqual(product["cost_price"], Decimal(3.27))
                self.assertAlmostEqual(product["weight"], 2611.96)
                self.assertEqual(product["orig_product"], GK["id"])
                self.assertEqual(product["coef"], 2)
                self.assertTrue(len(product["raw_ingredients"]) == 0)
            if product["name"] == "Cookie":
                self.assertAlmostEqual(product["cost_price"], Decimal(0.6552))
                self.assertAlmostEqual(product["weight"], 122.5)

    def test_orders(self):
        response = self.client.get(
            "/api/orders/",
            query_params={
                "min_date": self.next_monday,
                "max_date": self.next_monday + timedelta(days=6),
            },
        )
        self.assertEqual(response.status_code, 200)
        orders = response.data
        self.assertEqual(list(orders[0]["lines"][0].keys()), ["product", "quantity"])
        ddates = defaultdict(list)
        for order in orders:
            ddates[order["delivery_date"]].append(order)
        ddates = [(ddate, ddates[ddate]) for ddate in ddates]
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(ddates), 2)
        self.assertEqual(self.next_monday, DeliveryDate.objects.filter(id=ddates[0][0]).first().date)
        self.assertAlmostEqual(sum([o["total_price"] for o in ddates[0][1]]), Decimal(192.88702))
        self.assertAlmostEqual(sum([o["total_price"] for o in ddates[1][1]]), Decimal(218.692))
        self.assertEqual(
            self.next_monday + timedelta(days=2),
            DeliveryDate.objects.filter(id=ddates[1][0]).first().date,
        )

    def test_permission(self):
        client = APIClient()
        client.force_authenticate(user=self.context["guy"])
        response = client.get("/api/products/")
        self.assertEqual(response.status_code, 403)

    def test_new_order(self):
        response = self.client.post(
            "/api/orders/",
            {
                "customer": self.context["guy"].id,
                "delivery_date": self.context["monday_delivery"].deliverydate_set.first().id,
                "lines": [
                    {"product": "GN", "quantity": 3},
                    {"product": "PN", "quantity": 3},
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertAlmostEqual(response.data["total_price"], Decimal(23.10))


class ViewTests(ExtendedTestCase):
    fixtures = ["data/base.json"]

    def setUp(self):
        self.client = Client()
        self.context = populate()
        self.client.force_login(self.context["admin"])

    def test_focaccia_recipe(self):
        response = self.client.get("/products/")
        self.assertEqual(response.status_code, 200)
        self.assertInHTML(
            """
            <article class="card">
            <header>
            <h3>FOC</h3>
            <br>
            <b>Focaccia (part)</b>
            </header>
            <ul>
            <li>Identique à <b>GN</b> avec un coef 2,5 pour 24 unités</li>
            <li>Herbes de provence : 10,00 g</li>
            <li>Huile olive : 150,00 g</li>
            <li>Olives : 200,00 g</li>
            <li>Tomates séchées : 100,00 g</li>
            </ul>
            <p>
            Prix de vente : 2,20€
            <br>
            Prix de revient : 0,31€
            <br>
            Poids pâte : 150,52g
            </p>
            </article>
            """,
            response.content.decode("utf-8"),
        )
