from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core import mail
from django.db import IntegrityError, transaction
from django.test import Client, TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .models import (
    ORDER_WINDOW_DAYS,
    Checkout,
    Customer,
    DeliveryDate,
    Ingredient,
    Order,
    OrderLine,
    Product,
    ResetAccountToken,
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

    def test_preparation_screen_shows_levain_quantities(self):
        next_monday = date.today() + timedelta(days=7 - date.today().weekday())
        delivery_date = DeliveryDate.objects.filter(weekly_delivery=self.context["monday_delivery"]).get(date=next_monday)
        order = Order.objects.create(customer=self.context["guy"], delivery_date=delivery_date)
        OrderLine.objects.create(order=order, product=Product.objects.get(ref="GK"), quantity=1)
        # For a SAME_DAY delivery, preparation happens the day before delivery.
        prep_day = next_monday - timedelta(days=1)
        response = self.client.get(f"/actions/{prep_day.year}/{prep_day.month}/{prep_day.day}/")
        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8")
        self.assertIn("Levains", body)
        self.assertInHTML("<li>Levain froment : 5 g</li>", body)


class AccessControlTests(ExtendedTestCase):
    """Covers the access-control fixes: ownership checks and staff gating."""

    fixtures = ["data/base.json"]
    next_monday = date.today() + timedelta(days=7 - date.today().weekday())

    def setUp(self):
        self.context = populate()

    def _delivery_date(self):
        return DeliveryDate.objects.filter(weekly_delivery=self.context["monday_delivery"]).get(date=self.next_monday)

    # --- #4 staff-only views must reject authenticated non-staff users ---

    def test_staff_views_forbidden_for_regular_customer(self):
        client = Client()
        client.force_login(self.context["guy"])
        for url in ("/actions/", "/products/", "/check_delivery_dates_consistency/"):
            self.assertEqual(client.get(url).status_code, 403, msg=url)

    def test_staff_views_allowed_for_staff(self):
        client = Client()
        client.force_login(self.context["admin"])
        for url in ("/actions/", "/products/", "/check_delivery_dates_consistency/"):
            self.assertEqual(client.get(url).status_code, 200, msg=url)

    def test_staff_views_redirect_anonymous_to_login(self):
        client = Client()
        response = client.get("/actions/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login", response.url)

    # --- #2 cancel_checkout ownership ---

    def test_cancel_checkout_rejects_other_customer(self):
        checkout = Checkout.objects.create(remote_id="remote-x", customer=self.context["store"])
        client = Client()
        client.force_login(self.context["guy"])
        with patch("boulange.views.requests.delete") as remote:
            response = client.post("/cancel_checkout/", {"checkout_id": checkout.id})
        self.assertEqual(response.status_code, 403)
        remote.assert_not_called()
        # checkout must still exist
        self.assertTrue(Checkout.objects.filter(id=checkout.id).exists())

    # --- #3 finalize ownership ---

    def test_finalize_rejects_other_customer(self):
        checkout = Checkout.objects.create(remote_id="remote-x", customer=self.context["store"])
        client = Client()
        client.force_login(self.context["guy"])
        with patch("boulange.views.requests.get") as remote:
            response = client.get(f"/finalize/{checkout.id}/")
        self.assertEqual(response.status_code, 403)
        # ownership is checked before any SumUp network call
        remote.assert_not_called()

    # --- #5 generate_delivery_dates API permission ---

    def test_generate_delivery_dates_requires_admin(self):
        anon = APIClient()
        self.assertEqual(anon.post("/api/generate_delivery_dates/").status_code, 403)
        regular = APIClient()
        regular.force_authenticate(user=self.context["guy"])
        self.assertEqual(regular.post("/api/generate_delivery_dates/").status_code, 403)

    # --- #13 hx_* endpoints require login ---

    def test_hx_endpoints_require_login(self):
        client = Client()
        for url in ("/hx/order_line/", "/hx/order_line_sum/", "/hx/get_dates_for_weekly_delivery/"):
            response = client.post(url, {})
            self.assertEqual(response.status_code, 302, msg=url)
            self.assertIn("/accounts/login", response.url, msg=url)

    # --- cleanup: missing objects yield 404, not 500 ---

    def test_missing_objects_return_404(self):
        client = Client()
        client.force_login(self.context["guy"])
        self.assertEqual(client.post("/delete_order/999999").status_code, 404)
        self.assertEqual(client.get("/payment/999999/").status_code, 404)


class PasswordResetTests(ExtendedTestCase):
    """Covers #6 (expiry enforced on POST), #8 (account_init) and #9 (tz-aware)."""

    def setUp(self):
        self.context = populate()
        self.client = Client()

    def test_account_init_unknown_email_does_not_leak_and_sends_nothing(self):
        response = self.client.post("/account_init", {"email": "nobody@example.com"})
        self.assertEqual(response.status_code, 200)  # same page as a known address, no 404
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(ResetAccountToken.objects.count(), 0)

    def test_account_init_missing_email_does_not_500(self):
        response = self.client.post("/account_init", {})
        self.assertEqual(response.status_code, 302)

    def test_account_init_known_email_sends_one_link(self):
        response = self.client.post("/account_init", {"email": self.context["guy"].email})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(ResetAccountToken.objects.filter(customer=self.context["guy"]).count(), 1)

    def test_account_init_is_throttled(self):
        for _ in range(3):
            self.client.post("/account_init", {"email": self.context["guy"].email})
        # repeated submissions must not create extra tokens / send extra mail
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(ResetAccountToken.objects.filter(customer=self.context["guy"]).count(), 1)

    def test_token_created_is_timezone_aware(self):
        token = ResetAccountToken.objects.create(customer=self.context["guy"])
        self.assertTrue(timezone.is_aware(token.created))

    def test_valid_token_resets_password(self):
        token = ResetAccountToken.objects.create(customer=self.context["guy"])
        response = self.client.post(f"/reset_password/{token.token}", {"newpw": "a-strong-pw"})
        self.assertEqual(response.status_code, 302)
        self.context["guy"].refresh_from_db()
        self.assertTrue(self.context["guy"].check_password("a-strong-pw"))
        self.assertFalse(ResetAccountToken.objects.filter(token=token.token).exists())

    def test_expired_token_cannot_reset_password_via_post(self):
        token = ResetAccountToken.objects.create(customer=self.context["guy"])
        token.created = timezone.now() - timedelta(days=2)
        token.save()
        response = self.client.post(f"/reset_password/{token.token}", {"newpw": "a-strong-pw"})
        self.assertContains(response, "n'est plus valide")
        self.context["guy"].refresh_from_db()
        self.assertFalse(self.context["guy"].check_password("a-strong-pw"))
        # the token is not consumed by a rejected attempt
        self.assertTrue(ResetAccountToken.objects.filter(token=token.token).exists())


class ModelBehaviourTests(ExtendedTestCase):
    """Covers #10 (unique delivery dates), #11 (guarded regen), #12 (Decimal price)."""

    fixtures = ["data/base.json"]

    def setUp(self):
        self.context = populate()

    def test_duplicate_delivery_date_is_rejected(self):
        existing = DeliveryDate.objects.filter(weekly_delivery=self.context["monday_delivery"]).first()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                DeliveryDate.objects.create(weekly_delivery=existing.weekly_delivery, date=existing.date)

    def test_save_regenerates_only_when_schedule_changes(self):
        wd = self.context["monday_delivery"]
        with patch.object(WeeklyDelivery, "generate_delivery_dates") as gen:
            wd.notes = "just a note"
            wd.save()
            gen.assert_not_called()
            wd.day_of_week = 5
            wd.save()
            gen.assert_called_once()

    def test_save_regenerates_on_reactivation(self):
        wd = self.context["monday_delivery"]
        wd.active = False
        wd.save()
        with patch.object(WeeklyDelivery, "generate_delivery_dates") as gen:
            wd.active = True
            wd.save()
            gen.assert_called_once()

    def test_professional_price_is_exact_decimal(self):
        store = self.context["store"]  # professional, 5% discount
        delivery_date = DeliveryDate.objects.filter(weekly_delivery=self.context["monday_delivery"]).first()
        order = Order.objects.create(customer=store, delivery_date=delivery_date)
        product = Product.objects.get(ref="GN")
        line = OrderLine.objects.create(order=order, product=product, quantity=3)
        gross = product.price * 3
        expected = (gross - gross * (Decimal("5.5") / 100)) * (1 - Decimal("5") / 100)
        self.assertIsInstance(line.get_price(), Decimal)
        self.assertEqual(line.get_price(), expected)

    def test_product_availability_out_of_range_is_false(self):
        product = Product.objects.get(ref="GN")
        self.assertFalse(product.is_available_on_day(7))
        self.assertFalse(product.is_available_on_day(-1))


class LazyDeliveryDateGenerationTests(ExtendedTestCase):
    """Cron-less, pure-Django self-healing of the delivery-date horizon."""

    fixtures = ["data/base.json"]

    def setUp(self):
        self.context = populate()
        self.client = Client()
        self.client.force_login(self.context["guy"])

    def _post_dates(self, weekly_delivery):
        return self.client.post(
            "/hx/get_dates_for_weekly_delivery/",
            {"weekly_delivery_id": weekly_delivery.id, "order_id": "", "event_type": "load"},
        )

    def test_ensure_is_a_noop_when_window_already_covered(self):
        # populate() already generated a full year, so nothing should be regenerated.
        wd = self.context["monday_delivery"]
        with patch.object(WeeklyDelivery, "generate_delivery_dates") as gen:
            wd.ensure_delivery_dates()
            gen.assert_not_called()

    def test_ensure_regenerates_when_horizon_falls_inside_window(self):
        wd = self.context["monday_delivery"]
        # Drop every date that is beyond the bookable window: the horizon now ends
        # inside the window, so ensure_delivery_dates() must refill it.
        cutoff = date.today() + timedelta(days=ORDER_WINDOW_DAYS)
        wd.deliverydate_set.filter(date__gt=cutoff).delete()
        self.assertFalse(wd.deliverydate_set.filter(date__gt=cutoff).exists())
        wd.ensure_delivery_dates()
        furthest = wd.deliverydate_set.order_by("-date").first().date
        self.assertGreater(furthest, cutoff)

    def test_date_picker_request_self_heals_the_horizon(self):
        wd = self.context["monday_delivery"]
        wd.deliverydate_set.all().delete()
        self.assertEqual(wd.deliverydate_set.count(), 0)
        response = self._post_dates(wd)
        self.assertEqual(response.status_code, 200)
        # the bookable window is now populated again, purely from the web request
        needed_until = date.today() + timedelta(days=ORDER_WINDOW_DAYS)
        self.assertTrue(wd.deliverydate_set.filter(date__gte=needed_until).exists())

    def test_generation_is_idempotent_and_conflict_safe(self):
        wd = self.context["monday_delivery"]
        before = wd.deliverydate_set.count()
        # a second generation (e.g. a concurrent request) must not create duplicates
        wd.generate_delivery_dates()
        self.assertEqual(wd.deliverydate_set.count(), before)

    def test_inactive_delivery_is_not_generated(self):
        wd = self.context["monday_delivery"]
        wd.deliverydate_set.all().delete()
        wd.active = False
        wd.save()
        wd.ensure_delivery_dates()
        self.assertEqual(wd.deliverydate_set.count(), 0)

    def test_new_active_delivery_generates_on_creation(self):
        # A freshly created active delivery must already cover the bookable window
        # (save() generates), so customers can order from it immediately.
        wd = WeeklyDelivery.objects.create(customer=self.context["guy"], day_of_week=4, active=True)
        needed_until = date.today() + timedelta(days=ORDER_WINDOW_DAYS)
        self.assertTrue(wd.deliverydate_set.filter(date__gte=needed_until).exists())

    def test_new_inactive_delivery_generates_nothing_until_activated(self):
        wd = WeeklyDelivery.objects.create(customer=self.context["guy"], day_of_week=5, active=False)
        self.assertEqual(wd.deliverydate_set.count(), 0)
        # activating it triggers generation
        wd.active = True
        wd.save()
        needed_until = date.today() + timedelta(days=ORDER_WINDOW_DAYS)
        self.assertTrue(wd.deliverydate_set.filter(date__gte=needed_until).exists())
