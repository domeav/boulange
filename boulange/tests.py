from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

from django.core import mail
from django.db import IntegrityError, connection, transaction
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext
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
from .views import _get_start_end_command_period


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

    def test_bread_dough_weight(self):
        delivery_date = DeliveryDate.objects.filter(weekly_delivery=self.context["monday_delivery"]).get(date=self.next_monday)
        order = Order(customer=self.context["guy"], delivery_date=delivery_date)
        order.save()
        gk = Product.objects.get(ref="GK")  # bread (1251 g of dough per unit)
        foc = Product.objects.get(ref="FOC")  # focaccia: not a bread, must be excluded
        OrderLine(order=order, product=gk, quantity=1).save()
        OrderLine(order=order, product=foc, quantity=1).save()
        actions = order.get_actions(self.next_monday)
        actions.finalize()
        # both doughs are baked, but only the bread's dough is counted
        self.assertEqual(actions["bakery"].bread_dough_weight, 1251.0)
        self.assertAlmostEqual(actions["bakery"].bread_dough_kg(), 1.251)

    def test_bread_dough_weight_sums_multiple_breads(self):
        delivery_date = DeliveryDate.objects.filter(weekly_delivery=self.context["monday_delivery"]).get(date=self.next_monday)
        order = Order(customer=self.context["guy"], delivery_date=delivery_date)
        order.save()
        OrderLine(order=order, product=Product.objects.get(ref="PSa"), quantity=5).save()
        OrderLine(order=order, product=Product.objects.get(ref="PSe"), quantity=3).save()
        actions = order.get_actions(self.next_monday)
        actions.finalize()
        # matches the per-recipe weights asserted in test_small_breads_batch (3051 + 2114)
        self.assertAlmostEqual(actions["bakery"].bread_dough_weight, 5165.0)


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

    def test_nav_shows_admin_link_for_staff(self):
        response = self.client.get("/orders/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'href="/admin/"')

    def test_nav_hides_admin_link_for_non_staff(self):
        client = Client()
        client.force_login(self.context["guy"])
        response = client.get("/orders/")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'href="/admin/"')

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


class AdminTests(ExtendedTestCase):
    fixtures = ["data/base.json"]

    def setUp(self):
        self.context = populate()
        admin = self.context["admin"]
        admin.is_superuser = True
        admin.save()
        self.client = Client()
        self.client.force_login(admin)

    def test_product_change_shows_recipe_dough_weight(self):
        gk = Product.objects.get(ref="GK")
        response = self.client.get(f"/admin/boulange/product/{gk.id}/change/")
        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8")
        self.assertIn("Poids de pâte crue", body)
        # server-rendered initial value (JS keeps it live afterwards)
        self.assertIn(f"{gk.weight * gk.nb_units:.0f} g", body)

    def test_order_inline_defaults_quantity_to_one(self):
        guy = self.context["guy"]
        delivery_date = self.context["monday_delivery"].deliverydate_set.first()
        order = Order.objects.create(customer=guy, delivery_date=delivery_date)
        OrderLine.objects.create(order=order, product=Product.objects.get(ref="GK"), quantity=7)
        response = self.client.get(f"/admin/boulange/order/{order.id}/change/")
        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8")
        # existing saved line keeps its value
        self.assertRegex(body, r'name="lines-0-quantity"[^>]*value="7"')
        # new (extra) rows default to 1
        self.assertRegex(body, r'name="lines-1-quantity"[^>]*value="1"')

    def test_order_change_shows_live_price(self):
        guy = self.context["guy"]
        dd = self.context["monday_delivery"].deliverydate_set.first()
        order = Order.objects.create(customer=guy, delivery_date=dd)
        OrderLine.objects.create(order=order, product=Product.objects.get(ref="GK"), quantity=2)
        response = self.client.get(f"/admin/boulange/order/{order.id}/change/")
        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8")
        self.assertIn("Prix de la commande", body)
        self.assertIn('id="order-total-price"', body)
        self.assertIn('id="order-product-prices"', body)
        self.assertIn('id="order-customers"', body)
        self.assertIn("boulange/admin_order_price.js", body)
        # server-rendered initial total (JS keeps it live afterwards)
        self.assertIn(f"{order.total_price:.2f} €", body)

    def test_product_autocomplete_searches_code_and_name(self):
        gk = Product.objects.get(ref="GK")  # ref "GK", name "Semi-complet kasha LL (1 kg)"
        base = "/admin/autocomplete/?app_label=boulange&model_name=orderline&field_name=product&term="
        # search by a name fragment that is not in the ref
        by_name = self.client.get(base + "kasha")
        self.assertEqual(by_name.status_code, 200)
        self.assertIn(gk.id, {int(r["id"]) for r in by_name.json()["results"]})
        # search by the code/ref still works
        by_code = self.client.get(base + "GK")
        self.assertIn(gk.id, {int(r["id"]) for r in by_code.json()["results"]})

    def test_order_change_customer_is_autocomplete(self):
        guy = self.context["guy"]
        dd = self.context["monday_delivery"].deliverydate_set.first()
        order = Order.objects.create(customer=guy, delivery_date=dd)
        response = self.client.get(f"/admin/boulange/order/{order.id}/change/")
        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8")
        # the customer field uses the admin autocomplete (select2) widget
        self.assertRegex(body, r'name="customer"[^>]*class="admin-autocomplete"')

    def test_order_price_reflects_professional_discount(self):
        store = self.context["store"]  # professional, 5% discount
        dd = self.context["monday_delivery"].deliverydate_set.first()
        order = Order.objects.create(customer=store, delivery_date=dd)
        OrderLine.objects.create(order=order, product=Product.objects.get(ref="GK"), quantity=2)
        body = self.client.get(f"/admin/boulange/order/{order.id}/change/").content.decode("utf-8")
        # the displayed total is net of TVA and discounted, not the raw 6.5 x 2
        self.assertIn(f"{order.total_price:.2f} €", body)
        self.assertNotIn("13.00 €", body)

    def test_deliverydate_changelist_has_last_8_days_filter(self):
        response = self.client.get("/admin/boulange/deliverydate/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "8 jours + demain")

    def test_deliverydate_last_8_days_filter_range(self):
        wd = self.context["monday_delivery"]
        today = date.today()
        in_range = DeliveryDate.objects.create(weekly_delivery=wd, date=today - timedelta(days=3))
        out_range = DeliveryDate.objects.create(weekly_delivery=wd, date=today - timedelta(days=10))
        response = self.client.get(
            "/admin/boulange/deliverydate/",
            {"date__gte": (today - timedelta(days=7)).isoformat(), "date__lt": (today + timedelta(days=1)).isoformat()},
        )
        self.assertEqual(response.status_code, 200)
        ids = set(response.context["cl"].queryset.values_list("id", flat=True))
        self.assertIn(in_range.id, ids)
        self.assertNotIn(out_range.id, ids)

    def test_deliverydate_changelist_has_no_bulk_delete(self):
        response = self.client.get("/admin/boulange/deliverydate/")
        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8")
        self.assertNotIn('value="delete_selected"', body)
        # the custom duplicate action is still offered
        self.assertIn('value="duplicate_delivery_date_orders"', body)

    def test_deliverydate_changelist_has_single_date_picker(self):
        response = self.client.get("/admin/boulange/deliverydate/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'type="date"')
        self.assertContains(response, 'name="exact_date"')

    def test_deliverydate_single_date_filter(self):
        wd = self.context["monday_delivery"]
        today = date.today()
        target = DeliveryDate.objects.create(weekly_delivery=wd, date=today - timedelta(days=3))
        other = DeliveryDate.objects.create(weekly_delivery=wd, date=today - timedelta(days=10))
        response = self.client.get("/admin/boulange/deliverydate/", {"exact_date": (today - timedelta(days=3)).isoformat()})
        self.assertEqual(response.status_code, 200)
        results = response.context["cl"].queryset
        ids = set(results.values_list("id", flat=True))
        self.assertIn(target.id, ids)
        self.assertNotIn(other.id, ids)
        for dd in results:
            self.assertEqual(dd.date, today - timedelta(days=3))

    def test_deliverydate_filter_excludes_inactive_customers(self):
        import re

        active_cust = Customer.objects.create(username="activecust", display_name="ActiveCust", email="a@x.net", is_active=True)
        inactive_cust = Customer.objects.create(username="inactivecust", display_name="InactiveCust", email="i@x.net", is_active=False)
        WeeklyDelivery.objects.create(customer=active_cust, day_of_week=4, active=True)
        WeeklyDelivery.objects.create(customer=inactive_cust, day_of_week=5, active=True)
        response = self.client.get("/admin/boulange/deliverydate/")
        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8")
        # isolate the right-hand filter sidebar
        nav = re.search(r'id="changelist-filter".*?</nav>', body, re.S)
        self.assertIsNotNone(nav)
        nav = nav.group(0)
        self.assertIn("ActiveCust", nav)
        self.assertNotIn("InactiveCust", nav)

    def test_product_change_includes_live_update_assets(self):
        gk = Product.objects.get(ref="GK")
        response = self.client.get(f"/admin/boulange/product/{gk.id}/change/")
        body = response.content.decode("utf-8")
        # the live-update result container, the data payloads and the script must be present
        self.assertIn('id="recipe-dough-weight"', body)
        self.assertIn('id="dough-ingredient-factors"', body)
        self.assertIn('id="dough-product-raw-weights"', body)
        self.assertIn("boulange/admin_recipe_weight.js", body)
        # the ingredient-factor payload should carry a known weighable ingredient (grams -> 1)
        flour = Ingredient.objects.get(name="Farine blé")
        self.assertIn(f'"{flour.id}": 1', body)


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

    def test_deactivating_delivery_deactivates_future_dates_only(self):
        wd = self.context["monday_delivery"]
        past = DeliveryDate.objects.create(weekly_delivery=wd, date=date.today() - timedelta(days=7))
        self.assertTrue(wd.deliverydate_set.filter(date__gte=date.today(), active=True).exists())
        wd.active = False
        wd.save()
        # upcoming dates are now inactive (but still present)...
        self.assertEqual(wd.deliverydate_set.filter(date__gte=date.today(), active=True).count(), 0)
        self.assertTrue(wd.deliverydate_set.filter(date__gte=date.today()).exists())
        # ...while past dates are left untouched
        past.refresh_from_db()
        self.assertTrue(past.active)

    def test_reactivating_delivery_reactivates_future_dates(self):
        wd = self.context["monday_delivery"]
        wd.active = False
        wd.save()
        self.assertEqual(wd.deliverydate_set.filter(date__gte=date.today(), active=True).count(), 0)
        wd.active = True
        wd.save()
        self.assertFalse(wd.deliverydate_set.filter(date__gte=date.today(), active=False).exists())

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


class DuplicateDeliveryDateOrdersTests(ExtendedTestCase):
    """The 'duplicate orders' admin action: oldest selected date -> newer ones, per weekly delivery."""

    fixtures = ["data/base.json"]

    def setUp(self):
        self.context = populate()

    def _make_order(self, delivery_date, customer, items):
        order = Order.objects.create(customer=customer, delivery_date=delivery_date)
        for ref, qty in items:
            OrderLine.objects.create(order=order, product=Product.objects.get(ref=ref), quantity=qty)
        return order

    @staticmethod
    def _lines(delivery_date):
        order = delivery_date.order_set.first()
        return set(order.lines.values_list("product__ref", "quantity"))

    def test_duplicates_from_oldest_to_all_newer_single_wd(self):
        from boulange.admin import duplicate_delivery_date_orders

        m1, m2, m3 = list(self.context["monday_delivery"].deliverydate_set.order_by("date")[:3])
        self._make_order(m1, self.context["guy"], [("GK", 2), ("PN", 1)])
        qs = DeliveryDate.objects.filter(id__in=[m1.id, m2.id, m3.id])

        duplicate_delivery_date_orders(None, None, qs)

        # source untouched; both newer dates received a faithful copy
        self.assertEqual(m1.order_set.count(), 1)
        self.assertEqual(m2.order_set.count(), 1)
        self.assertEqual(m3.order_set.count(), 1)
        self.assertEqual(self._lines(m2), {("GK", 2), ("PN", 1)})
        self.assertEqual(self._lines(m3), {("GK", 2), ("PN", 1)})
        self.assertEqual(m2.order_set.first().customer, self.context["guy"])

    def test_duplicates_grouped_by_weekly_delivery(self):
        from boulange.admin import duplicate_delivery_date_orders

        m1, m2 = list(self.context["monday_delivery"].deliverydate_set.order_by("date")[:2])
        w1, w2 = list(self.context["wednesday_delivery"].deliverydate_set.order_by("date")[:2])
        self._make_order(m1, self.context["guy"], [("GK", 2)])
        self._make_order(w1, self.context["store"], [("PN", 5), ("BR", 3)])

        qs = DeliveryDate.objects.filter(id__in=[m1.id, m2.id, w1.id, w2.id])
        duplicate_delivery_date_orders(None, None, qs)

        # each newer date receives ONLY its own weekly delivery's oldest order (no cross-contamination)
        self.assertEqual(m2.order_set.count(), 1)
        self.assertEqual(self._lines(m2), {("GK", 2)})
        self.assertEqual(w2.order_set.count(), 1)
        self.assertEqual(self._lines(w2), {("PN", 5), ("BR", 3)})

    def test_oldest_is_source_and_targets_accumulate(self):
        from boulange.admin import duplicate_delivery_date_orders

        m1, m2, m3 = list(self.context["monday_delivery"].deliverydate_set.order_by("date")[:3])
        # orders exist on m1 (oldest) and m2 (middle)
        self._make_order(m1, self.context["guy"], [("GK", 1)])
        self._make_order(m2, self.context["guy"], [("PN", 9)])

        qs = DeliveryDate.objects.filter(id__in=[m1.id, m2.id, m3.id])
        duplicate_delivery_date_orders(None, None, qs)

        # the oldest (m1) is the source: m3 receives GK, NOT m2's PN
        self.assertEqual(self._lines(m3), {("GK", 1)})
        # the action APPENDS rather than replaces: m2 keeps its own order and also
        # receives a copy of m1's, ending up with both
        m2_orders = {frozenset(o.lines.values_list("product__ref", "quantity")) for o in m2.order_set.all()}
        self.assertEqual(m2_orders, {frozenset({("PN", 9)}), frozenset({("GK", 1)})})

    def test_action_is_not_idempotent(self):
        from boulange.admin import duplicate_delivery_date_orders

        m1, m2 = list(self.context["monday_delivery"].deliverydate_set.order_by("date")[:2])
        self._make_order(m1, self.context["guy"], [("GK", 1)])
        qs = DeliveryDate.objects.filter(id__in=[m1.id, m2.id])

        # running the action twice duplicates the order onto m2 twice (no dedup guard)
        duplicate_delivery_date_orders(None, None, qs)
        duplicate_delivery_date_orders(None, None, qs)
        self.assertEqual(m2.order_set.count(), 2)

    def test_action_runs_through_admin(self):
        admin = self.context["admin"]
        admin.is_superuser = True
        admin.save()
        client = Client()
        client.force_login(admin)
        m1, m2 = list(self.context["monday_delivery"].deliverydate_set.order_by("date")[:2])
        self._make_order(m1, self.context["guy"], [("GK", 1)])

        response = client.post(
            "/admin/boulange/deliverydate/",
            {"action": "duplicate_delivery_date_orders", "_selected_action": [str(m1.id), str(m2.id)]},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(m2.order_set.count(), 1)
        self.assertEqual(self._lines(m2), {("GK", 1)})


class LocalizationTests(ExtendedTestCase):
    """Guard the French labels so English can't creep back into the admin."""

    def test_model_verbose_names_are_french(self):
        self.assertEqual(Ingredient._meta.verbose_name, "Ingrédient")
        self.assertEqual(Ingredient._meta.verbose_name_plural, "Ingrédients")
        self.assertEqual(Product._meta.verbose_name, "Produit")
        self.assertEqual(WeeklyDelivery._meta.verbose_name, "Livraison hebdo")
        self.assertEqual(Order._meta.verbose_name, "Commande")
        self.assertEqual(OrderLine._meta.verbose_name, "Ligne de commande")
        from boulange.models import ProductLine

        self.assertEqual(ProductLine._meta.verbose_name, "Ligne de recette")

    def test_field_labels_are_french(self):
        self.assertEqual(Product._meta.get_field("ref").verbose_name, "Référence")
        self.assertEqual(Product._meta.get_field("nb_units").verbose_name, "Nombre d'unités")
        # validated bakery-domain terms
        self.assertEqual(Product._meta.get_field("baked_by_batch").verbose_name, "Cuit par lot entier")
        self.assertEqual(Product._meta.get_field("orig_product").verbose_name, "Produit d'origine")
        self.assertEqual(Product._meta.get_field("is_bread").verbose_name, "Produit de type pain")
        self.assertEqual(OrderLine._meta.get_field("quantity").verbose_name, "Quantité")

    def test_help_text_and_choices_are_french(self):
        self.assertEqual(Ingredient._meta.get_field("per_unit_price").help_text, "prix par kg, litre ou unité")
        self.assertEqual(WeeklyDelivery.BATCH_TARGET["SAME_DAY"], "Le jour même")
        self.assertEqual(WeeklyDelivery.BATCH_TARGET["PREVIOUS_DAY"], "La veille")

    def test_admin_action_labels_are_french(self):
        from boulange.admin import (
            cancel_checkouts,
            duplicate_delivery_date_orders,
            generate_delivery_dates,
        )

        self.assertIn("Dupliquer", duplicate_delivery_date_orders.short_description)
        self.assertIn("Générer", generate_delivery_dates.short_description)
        self.assertIn("Annuler", cancel_checkouts.short_description)


class StatsTests(ExtendedTestCase):
    """Sales statistics per product over year / quarter / month / custom range (staff only)."""

    fixtures = ["data/base.json"]

    def setUp(self):
        self.context = populate()
        self.client = Client()
        self.client.force_login(self.context["admin"])

    @staticmethod
    def _quarter(d):
        return d.year, (d.month - 1) // 3 + 1

    def _monday(self):
        return date.today() + timedelta(days=7 - date.today().weekday())

    def test_requires_staff(self):
        client = Client()
        client.force_login(self.context["guy"])
        self.assertEqual(client.get("/stats/").status_code, 403)

    def test_year_sales_aggregation(self):
        monday = self._monday()
        dd = DeliveryDate.objects.filter(weekly_delivery=self.context["monday_delivery"]).get(date=monday)
        order = Order.objects.create(customer=self.context["guy"], delivery_date=dd, validated=True)
        gk = Product.objects.get(ref="GK")  # price 6.5, non-pro customer -> 13.00
        OrderLine.objects.create(order=order, product=gk, quantity=2)
        response = self.client.get("/stats/", {"year": monday.year})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Chiffre d'affaires")
        rows = dict(response.context["rows"])
        self.assertEqual(rows[gk]["qty"], 2)
        self.assertEqual(rows[gk]["amount"], Decimal("13.00"))
        self.assertEqual(response.context["total_qty"], 2)
        self.assertEqual(response.context["nb_orders"], 1)
        self.assertEqual(response.context["total_amount"], Decimal("13.00"))

    def test_margin_calculation(self):
        monday = self._monday()
        dd = DeliveryDate.objects.filter(weekly_delivery=self.context["monday_delivery"]).get(date=monday)
        order = Order.objects.create(customer=self.context["guy"], delivery_date=dd, validated=True)
        gk = Product.objects.get(ref="GK")  # CA 13.00 (non-pro), ingredient cost < price
        OrderLine.objects.create(order=order, product=gk, quantity=2)
        response = self.client.get("/stats/", {"year": monday.year})
        rows = dict(response.context["rows"])
        expected_cost = gk.cost_price * 2
        self.assertEqual(rows[gk]["cost"], expected_cost)
        self.assertEqual(rows[gk]["margin"], Decimal("13.00") - expected_cost)
        self.assertEqual(response.context["total_cost"], expected_cost)
        self.assertEqual(response.context["total_margin"], Decimal("13.00") - expected_cost)
        self.assertGreater(response.context["total_margin_pct"], 0)
        self.assertLess(response.context["total_margin_pct"], 100)

    def test_unvalidated_orders_are_excluded(self):
        monday = self._monday()
        dd = DeliveryDate.objects.filter(weekly_delivery=self.context["monday_delivery"]).get(date=monday)
        order = Order.objects.create(customer=self.context["guy"], delivery_date=dd, validated=False)
        OrderLine.objects.create(order=order, product=Product.objects.get(ref="GK"), quantity=2)
        response = self.client.get("/stats/", {"year": monday.year})
        self.assertEqual(response.context["total_qty"], 0)
        self.assertEqual(response.context["nb_orders"], 0)

    def test_quarter_filters_out_other_quarters(self):
        mondays = list(self.context["monday_delivery"].deliverydate_set.order_by("date"))
        d1 = mondays[0]
        year, quarter = self._quarter(d1.date)
        d2 = next(dd for dd in mondays if self._quarter(dd.date) != (year, quarter))
        gk = Product.objects.get(ref="GK")
        pn = Product.objects.get(ref="PN")
        o1 = Order.objects.create(customer=self.context["guy"], delivery_date=d1, validated=True)
        OrderLine.objects.create(order=o1, product=gk, quantity=1)
        o2 = Order.objects.create(customer=self.context["guy"], delivery_date=d2, validated=True)
        OrderLine.objects.create(order=o2, product=pn, quantity=1)
        response = self.client.get("/stats/", {"year": year, "quarter": quarter})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["period_label"], f"T{quarter} {year}")
        rows = dict(response.context["rows"])
        self.assertIn(gk, rows)
        self.assertNotIn(pn, rows)

    def test_month_filters_out_other_months(self):
        mondays = list(self.context["monday_delivery"].deliverydate_set.order_by("date"))
        d1 = mondays[0]
        d2 = next(dd for dd in mondays if (dd.date.year, dd.date.month) != (d1.date.year, d1.date.month))
        gk = Product.objects.get(ref="GK")
        pn = Product.objects.get(ref="PN")
        o1 = Order.objects.create(customer=self.context["guy"], delivery_date=d1, validated=True)
        OrderLine.objects.create(order=o1, product=gk, quantity=1)
        o2 = Order.objects.create(customer=self.context["guy"], delivery_date=d2, validated=True)
        OrderLine.objects.create(order=o2, product=pn, quantity=1)
        response = self.client.get("/stats/", {"year": d1.date.year, "month": d1.date.month})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["granularity"], "month")
        rows = dict(response.context["rows"])
        self.assertIn(gk, rows)
        self.assertNotIn(pn, rows)

    def test_custom_range_is_inclusive_and_bounded(self):
        mondays = list(self.context["monday_delivery"].deliverydate_set.order_by("date"))
        d1, d2 = mondays[0], mondays[1]
        gk = Product.objects.get(ref="GK")
        pn = Product.objects.get(ref="PN")
        o1 = Order.objects.create(customer=self.context["guy"], delivery_date=d1, validated=True)
        OrderLine.objects.create(order=o1, product=gk, quantity=1)
        o2 = Order.objects.create(customer=self.context["guy"], delivery_date=d2, validated=True)
        OrderLine.objects.create(order=o2, product=pn, quantity=1)
        # range covering only d1 (end == start, inclusive)
        response = self.client.get("/stats/", {"start": d1.date.isoformat(), "end": d1.date.isoformat()})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["granularity"], "custom")
        rows = dict(response.context["rows"])
        self.assertIn(gk, rows)
        self.assertNotIn(pn, rows)
        # widening to include d2 picks up both
        response = self.client.get("/stats/", {"start": d1.date.isoformat(), "end": d2.date.isoformat()})
        rows = dict(response.context["rows"])
        self.assertIn(gk, rows)
        self.assertIn(pn, rows)


class EmailLoginTests(TestCase):
    fixtures = ["data/base.json"]

    def setUp(self):
        self.context = populate()
        self.user = self.context["guy"]
        self.user.set_password("secretpw1")
        self.user.save()

    def test_login_with_username_still_works(self):
        self.assertTrue(self.client.login(username="guy", password="secretpw1"))

    def test_login_with_email(self):
        self.assertTrue(self.client.login(username="guy@toto.net", password="secretpw1"))

    def test_login_with_email_is_case_insensitive(self):
        self.assertTrue(self.client.login(username="GUY@TOTO.NET", password="secretpw1"))

    def test_login_with_email_wrong_password_fails(self):
        self.assertFalse(self.client.login(username="guy@toto.net", password="wrong"))

    def test_login_with_unknown_email_fails(self):
        self.assertFalse(self.client.login(username="nobody@toto.net", password="secretpw1"))

    def test_ambiguous_email_is_refused(self):
        for name in ("dup1", "dup2"):
            dup = Customer(username=name, display_name=name, email="dup@toto.net")
            dup.set_password("secretpw1")
            dup.save()
        # the shared email is ambiguous, so it cannot be used to log in...
        self.assertFalse(self.client.login(username="dup@toto.net", password="secretpw1"))
        # ...but each account can still log in with its username
        self.assertTrue(self.client.login(username="dup1", password="secretpw1"))


class OrderSubmissionSecurityTests(ExtendedTestCase):
    """POST /orders/ is attacker-controlled: everything in it is re-checked server-side."""

    fixtures = ["data/base.json"]

    def setUp(self):
        self.context = populate()
        self.guy = self.context["guy"]
        self.client = Client()
        self.client.force_login(self.guy)
        self.private_delivery = WeeklyDelivery.objects.create(customer=self.context["store"], day_of_week=4, public_delivery_point=False, online_payment=False)
        self.private_delivery.generate_delivery_dates()
        self.weekly_delivery = self.context["monday_delivery"]
        self.weekly_delivery.public_delivery_point = True
        self.weekly_delivery.save()
        self.delivery_date = self.weekly_delivery.deliverydate_set.filter(date__gte=date.today() + timedelta(days=10)).first()
        self.product = Product.objects.filter(active=True, available_mondays=True).first()

    def _post_order(self, delivery_date, product, quantity=1, order_id=""):
        return self.client.post(
            "/orders/",
            {"order_id": order_id, "delivery_date": delivery_date.id, "notes": "", "product_id": [product.id], "product_qty": [str(quantity)]},
        )

    # --- delivery date must be one the customer may actually order on ---

    def test_private_delivery_point_is_refused(self):
        delivery_date = self.private_delivery.deliverydate_set.filter(date__gte=date.today() + timedelta(days=10)).first()
        self.assertEqual(self._post_order(delivery_date, self.product).status_code, 403)
        self.assertFalse(Order.objects.filter(customer=self.guy).exists())

    def test_private_delivery_point_is_allowed_once_granted(self):
        self.private_delivery.allowed_customers.add(self.guy)
        delivery_date = self.private_delivery.deliverydate_set.filter(date__gte=date.today() + timedelta(days=10)).first()
        product = Product.objects.filter(active=True, available_fridays=True).first()
        self.assertEqual(self._post_order(delivery_date, product).status_code, 302)
        self.assertTrue(Order.objects.filter(customer=self.guy, delivery_date=delivery_date).exists())

    def test_past_delivery_date_is_refused(self):
        past = DeliveryDate.objects.create(weekly_delivery=self.weekly_delivery, date=date.today() - timedelta(days=30))
        self.assertEqual(self._post_order(past, self.product).status_code, 403)
        self.assertFalse(Order.objects.filter(delivery_date=past).exists())

    def test_date_before_the_cutoff_is_refused(self):
        start, _end = _get_start_end_command_period()
        too_soon = DeliveryDate.objects.create(weekly_delivery=self.weekly_delivery, date=start - timedelta(days=1))
        self.assertEqual(self._post_order(too_soon, self.product).status_code, 403)
        self.assertFalse(Order.objects.filter(delivery_date=too_soon).exists())

    def test_date_beyond_the_order_window_is_refused(self):
        _start, end = _get_start_end_command_period()
        too_far = DeliveryDate.objects.create(weekly_delivery=self.weekly_delivery, date=end + timedelta(days=7))
        self.assertEqual(self._post_order(too_far, self.product).status_code, 403)
        self.assertFalse(Order.objects.filter(delivery_date=too_far).exists())

    def test_cancelled_delivery_date_is_refused_and_not_offered(self):
        self.delivery_date.active = False
        self.delivery_date.save()
        self.assertEqual(self._post_order(self.delivery_date, self.product).status_code, 403)
        response = self.client.post(
            "/hx/get_dates_for_weekly_delivery/",
            {"weekly_delivery_id": self.weekly_delivery.id, "order_id": "", "event_type": "load"},
        )
        self.assertNotContains(response, f'value="{self.delivery_date.id}"')

    # --- products must be on sale on that delivery ---

    def test_product_unavailable_that_weekday_is_refused(self):
        product = Product.objects.filter(active=True, available_mondays=True).exclude(id=self.product.id).first()
        product.available_mondays = False
        product.save()
        self.assertEqual(self._post_order(self.delivery_date, product).status_code, 403)

    def test_inactive_product_is_refused(self):
        product = Product.objects.filter(active=True, available_mondays=True).exclude(id=self.product.id).first()
        product.active = False
        product.save()
        self.assertEqual(self._post_order(self.delivery_date, product).status_code, 403)

    # --- quantities may never be negative ---

    def test_negative_quantity_is_dropped(self):
        self.assertEqual(self._post_order(self.delivery_date, self.product, quantity=-5).status_code, 302)
        self.assertFalse(OrderLine.objects.filter(quantity__lt=1).exists())
        self.assertFalse(Order.objects.filter(customer=self.guy).exists())

    def test_negative_line_cannot_lower_the_order_total(self):
        other = Product.objects.filter(active=True, available_mondays=True).exclude(id=self.product.id).first()
        self.client.post(
            "/orders/",
            {"order_id": "", "delivery_date": self.delivery_date.id, "notes": "", "product_id": [self.product.id, other.id], "product_qty": ["10", "-9"]},
        )
        order = Order.objects.get(customer=self.guy)
        self.assertEqual(order.lines.count(), 1)
        self.assertEqual(order.lines.first().quantity, 10)
        self.assertGreater(order.total_price, 0)

    # --- the legitimate flows still work ---

    def test_valid_order_is_created(self):
        self.assertEqual(self._post_order(self.delivery_date, self.product, quantity=3).status_code, 302)
        order = Order.objects.get(customer=self.guy)
        self.assertEqual(order.lines.first().quantity, 3)
        self.assertFalse(order.validated)

    def test_valid_edit_updates_date_notes_and_lines(self):
        self._post_order(self.delivery_date, self.product, quantity=3)
        order = Order.objects.get(customer=self.guy)
        other_date = self.weekly_delivery.deliverydate_set.filter(date__gt=self.delivery_date.date).first()
        response = self.client.post(
            "/orders/",
            {"order_id": str(order.id), "delivery_date": other_date.id, "notes": "modifiée", "product_id": [self.product.id], "product_qty": ["7"]},
        )
        self.assertEqual(response.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.notes, "modifiée")
        self.assertEqual(order.delivery_date, other_date)
        self.assertEqual(order.lines.count(), 1)
        self.assertEqual(order.lines.first().quantity, 7)

    def test_editing_another_customers_order_is_refused(self):
        other = Order.objects.create(customer=self.context["store"], delivery_date=self.delivery_date, validated=False)
        response = self.client.post(
            "/orders/",
            {"order_id": str(other.id), "delivery_date": self.delivery_date.id, "notes": "", "product_id": [self.product.id], "product_qty": ["1"]},
        )
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Order.objects.filter(id=other.id).exists())

    # --- an order without a single line is not an order ---

    def test_emptying_an_order_deletes_it(self):
        self._post_order(self.delivery_date, self.product, quantity=3)
        order = Order.objects.get(customer=self.guy)
        response = self.client.post(
            "/orders/",
            {"order_id": str(order.id), "delivery_date": self.delivery_date.id, "notes": "x", "product_id": [self.product.id], "product_qty": [""]},
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Order.objects.filter(id=order.id).exists())
        self.assertFalse(OrderLine.objects.filter(order_id=order.id).exists())


class CancelCheckoutTests(ExtendedTestCase):
    fixtures = ["data/base.json"]

    def setUp(self):
        self.context = populate()
        self.guy = self.context["guy"]
        self.client = Client()
        self.client.force_login(self.guy)
        self.checkout = Checkout.objects.create(remote_id="remote-x", customer=self.guy)
        delivery_date = self.context["monday_delivery"].deliverydate_set.filter(date__gte=date.today() + timedelta(days=10)).first()
        self.order = Order.objects.create(customer=self.guy, delivery_date=delivery_date, validated=False, checkout=self.checkout)

    def test_cancel_accepted_by_sumup_removes_the_checkout(self):
        with patch("boulange.views.requests.delete", return_value=Mock(ok=True)) as remote:
            response = self.client.post("/cancel_checkout/", {"checkout_id": self.checkout.id})
        remote.assert_called_once()
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Checkout.objects.filter(id=self.checkout.id).exists())
        self.order.refresh_from_db()
        self.assertIsNone(self.order.checkout)

    def test_cancel_refused_by_sumup_keeps_the_checkout(self):
        """SumUp refuses to delete an already-paid checkout: the payment must not be lost."""
        with patch("boulange.views.requests.delete", return_value=Mock(ok=False, status_code=409)):
            response = self.client.post("/cancel_checkout/", {"checkout_id": self.checkout.id})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f"/payment/{self.checkout.id}/")
        self.assertTrue(Checkout.objects.filter(id=self.checkout.id).exists())
        self.order.refresh_from_db()
        self.assertEqual(self.order.checkout, self.checkout)


class OrdersPagePerformanceTests(ExtendedTestCase):
    fixtures = ["data/base.json"]
    NB_ORDERS = 40

    def setUp(self):
        self.context = populate()
        self.guy = self.context["guy"]
        self.client = Client()
        self.client.force_login(self.guy)
        wd = self.context["monday_delivery"]
        wd.public_delivery_point = True
        wd.save()
        products = list(Product.objects.filter(active=True, available_mondays=True)[:5])
        for dd in list(wd.deliverydate_set.all()[: self.NB_ORDERS]):
            order = Order.objects.create(customer=self.guy, delivery_date=dd, validated=True)
            for p in products:
                OrderLine.objects.create(order=order, product=p, quantity=2)

    def test_query_count_is_flat(self):
        """The page must cost the same whether the customer has 40 past orders or 400."""
        with CaptureQueriesContext(connection) as few:
            self.client.get("/orders/")
        wd = self.context["monday_delivery"]
        products = list(Product.objects.filter(active=True, available_mondays=True)[:5])
        dates = list(wd.deliverydate_set.all())
        for i in range(360):
            order = Order.objects.create(customer=self.guy, delivery_date=dates[i % len(dates)], validated=True)
            for p in products:
                OrderLine.objects.create(order=order, product=p, quantity=2)
        self.assertGreater(Order.objects.filter(customer=self.guy).count(), 300)
        with CaptureQueriesContext(connection) as many:
            self.client.get("/orders/")
        print(f"  /orders/ queries: {len(few.captured_queries)} with 40 orders, {len(many.captured_queries)} with {Order.objects.filter(customer=self.guy).count()}")
        self.assertEqual(len(few.captured_queries), len(many.captured_queries))
        self.assertLess(len(many.captured_queries), 15)

    def test_page_size_and_nav(self):
        r = self.client.get("/orders/")
        self.assertEqual(len(r.context["validated_orders"]), 12)
        self.assertEqual(r.context["validated_orders"].paginator.num_pages, 4)
        self.assertContains(r, "Plus anciennes")
        r2 = self.client.get("/orders/?page=4")
        self.assertEqual(len(r2.context["validated_orders"]), self.NB_ORDERS - 36)
        self.assertContains(r2, "Plus récentes")

    def test_bad_page_param_does_not_500(self):
        self.assertEqual(self.client.get("/orders/?page=abc").status_code, 200)
        self.assertEqual(self.client.get("/orders/?page=99999").status_code, 200)


class HxEndpointAuthorizationTests(ExtendedTestCase):
    fixtures = ["data/base.json"]

    def setUp(self):
        self.context = populate()
        self.guy = self.context["guy"]
        self.client = Client()
        self.client.force_login(self.guy)
        self.private = WeeklyDelivery.objects.create(customer=self.context["store"], day_of_week=4, public_delivery_point=False)
        self.private.generate_delivery_dates()

    def test_private_dates_are_not_leaked(self):
        r = self.client.post("/hx/get_dates_for_weekly_delivery/", {"weekly_delivery_id": self.private.id, "order_id": "", "event_type": "load"})
        self.assertEqual(r.status_code, 404)

    def test_private_products_are_not_leaked(self):
        self.assertEqual(self.client.post("/hx/order_line/", {"weekly_delivery_id": self.private.id}).status_code, 404)

    def test_granted_customer_still_gets_them(self):
        self.private.allowed_customers.add(self.guy)
        r = self.client.post("/hx/get_dates_for_weekly_delivery/", {"weekly_delivery_id": self.private.id, "order_id": "", "event_type": "load"})
        self.assertEqual(r.status_code, 200)
        self.assertGreater(r.content.count(b"<option"), 0)
        self.assertEqual(self.client.post("/hx/order_line/", {"weekly_delivery_id": self.private.id}).status_code, 200)

    def test_public_delivery_still_works(self):
        wd = self.context["monday_delivery"]
        wd.public_delivery_point = True
        wd.save()
        r = self.client.post("/hx/get_dates_for_weekly_delivery/", {"weekly_delivery_id": wd.id, "order_id": "", "event_type": "load"})
        self.assertEqual(r.status_code, 200)
        self.assertGreater(r.content.count(b"<option"), 0)

    def test_another_customers_order_is_not_readable(self):
        wd = self.context["monday_delivery"]
        wd.public_delivery_point = True
        wd.save()
        dd = wd.deliverydate_set.first()
        other = Order.objects.create(customer=self.context["store"], delivery_date=dd)
        r = self.client.post("/hx/get_dates_for_weekly_delivery/", {"weekly_delivery_id": wd.id, "order_id": str(other.id), "event_type": "load"})
        self.assertEqual(r.status_code, 404)


class CheckoutReconciliationTests(ExtendedTestCase):
    fixtures = ["data/base.json"]

    def setUp(self):
        self.context = populate()
        self.guy = self.context["guy"]
        self.checkout = Checkout.objects.create(remote_id="remote-x", customer=self.guy)
        dd = self.context["monday_delivery"].deliverydate_set.filter(date__gte=date.today()).first()
        self.order = Order.objects.create(customer=self.guy, delivery_date=dd, validated=False, checkout=self.checkout)
        self.staff = Client()
        self.staff.force_login(self.context["admin"])

    def _sumup(self, status):
        return patch("boulange.views.requests.get", return_value=Mock(raise_for_status=Mock(), json=Mock(return_value={"status": status})))

    def test_paid_but_abandoned_checkout_is_picked_up_by_the_baker_screen(self):
        with self._sumup("PAID"):
            self.staff.get("/actions/")
        self.order.refresh_from_db()
        self.assertTrue(self.order.validated)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.guy.email, mail.outbox[0].to)

    def test_unpaid_checkout_is_left_alone(self):
        with self._sumup("PENDING"):
            self.staff.get("/actions/")
        self.order.refresh_from_db()
        self.assertFalse(self.order.validated)
        self.assertEqual(len(mail.outbox), 0)

    def test_reconciliation_is_not_repeated(self):
        with self._sumup("PAID"):
            self.staff.get("/actions/")
            self.staff.get("/actions/")
        self.assertEqual(len(mail.outbox), 1)

    def test_sumup_being_down_does_not_break_the_baker_screen(self):
        import requests as requests_lib

        with patch("boulange.views.requests.get", side_effect=requests_lib.ConnectionError("down")):
            response = self.staff.get("/actions/")
        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertFalse(self.order.validated)

    def test_old_checkouts_are_not_reconciled(self):
        stale = DeliveryDate.objects.create(weekly_delivery=self.context["wednesday_delivery"], date=date.today() - timedelta(days=60))
        self.order.delivery_date = stale
        self.order.save()
        with self._sumup("PAID") as remote:
            self.staff.get("/actions/")
        remote.assert_not_called()

    def test_finalize_reload_does_not_resend_the_email(self):
        customer = Client()
        customer.force_login(self.guy)
        with self._sumup("PAID"):
            r1 = customer.get(f"/finalize/{self.checkout.id}/")
            r2 = customer.get(f"/finalize/{self.checkout.id}/")
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)
        self.order.refresh_from_db()
        self.assertTrue(self.order.validated)
        self.assertEqual(len(mail.outbox), 1)
