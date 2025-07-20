from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from .models import Customer, DeliveryDate, Order, OrderLine, Product, WeeklyDelivery


def populate():
    admin = Customer(username="admin", display_name="admin", email="admin@toto.net", is_staff=True)
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


class ActionsTests(TestCase):
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
        line = OrderLine(order=order, product=(Product.objects.get(ref="GK")), quantity=1)
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
                "levain": {"Levain froment": 170},
                "trempage": {"Graines kasha": {"dry": 80, "soaking_qty": 80, "soaking_ingredient": "Eau"}},
            },
        )
        actions = order.get_actions(self.next_monday)
        actions.finalize()
        self.assertEqual(actions["delivery"], {delivery_date: {"Semi-complet Kasha (1 kg)/GK": 1}})
        self.assertEqual(
            actions["bakery"],
            {
                "Semi-complet Kasha/GK": {
                    "ingredients": {
                        "Eau": 310,
                        "Farine blé": 600,
                        "Levain froment": 170,
                        "Sel": 11,
                        "Graines kasha (trempé)": 160,
                    },
                    "division": {"Semi-complet Kasha (1 kg)/GK": 1},
                    "weight": 1240,
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
        line = OrderLine(order=order, product=(Product.objects.get(ref="GK")), quantity=1)
        line.save()
        actions = order.get_actions(self.next_monday)
        actions.finalize()
        self.assertEqual(len(actions["delivery"]), 0)
        self.assertEqual(len(actions["bakery"]), 0)
        self.assertEqual(
            actions["preparation"],
            {
                "levain": {"Levain froment": 170},
                "trempage": {"Graines kasha": {"dry": 80, "soaking_qty": 80, "soaking_ingredient": "Eau"}},
            },
        )
        actions = order.get_actions(self.next_monday + timedelta(1))
        actions.finalize()
        self.assertEqual(len(actions["delivery"]), 0)
        self.assertEqual(
            actions["bakery"],
            {
                "Semi-complet Kasha/GK": {
                    "ingredients": {
                        "Eau": 310,
                        "Farine blé": 600,
                        "Levain froment": 170,
                        "Sel": 11,
                        "Graines kasha (trempé)": 160,
                    },
                    "division": {
                        "Semi-complet Kasha (1 kg)/GK": 1,
                    },
                    "weight": 1240,
                }
            },
        )
        self.assertEqual(len(actions["preparation"]["levain"]), 0)
        self.assertEqual(len(actions["preparation"]["trempage"]), 0)
        actions = order.get_actions(self.next_monday + timedelta(2))
        actions.finalize()
        self.assertEqual(actions["delivery"], {delivery_date: {"Semi-complet Kasha (1 kg)/GK": 1}})
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
        OrderLine(order=order, product=(Product.objects.get(ref="PSa")), quantity=5).save()
        OrderLine(order=order, product=(Product.objects.get(ref="PSe")), quantity=3).save()

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
            {"levain": {"Levain sarrasin": 400, "Levain froment": 290}, "trempage": {}},
        )
        actions = order.get_actions(self.next_monday)
        actions.finalize()
        self.assertEqual(
            actions["delivery"],
            {delivery_date: {"Sarrasin 100% (400 g)/PSa": 5, "Seigle 70% (400 g)/PSe": 3}},
        )
        self.assertEqual(
            actions["bakery"],
            {
                "Sarrasin 100%/GSa": {"ingredients": {"Eau": 1320, "Farine sarrasin": 1320, "Levain sarrasin": 400, "Sel": 26}, "division": {"Sarrasin 100% (400 g)/PSa": 6}, "weight": 3060},
                "Seigle 70%/GSe": {"ingredients": {"Eau": 680, "Farine blé": 320, "Farine seigle": 740, "Levain froment": 290, "Sel": 19}, "division": {"Seigle 70% (400 g)/PSe": 4}, "weight": 2040},
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
        OrderLine(order=order, product=(Product.objects.get(ref="GK")), quantity=4).save()
        OrderLine(order=order, product=(Product.objects.get(ref="TGK")), quantity=2).save()
        OrderLine(order=order, product=(Product.objects.get(ref="PK")), quantity=4).save()

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
                "levain": {"Levain froment": 1680.0},
                "trempage": {"Graines kasha": {"dry": 780.0, "soaking_qty": 780.0, "soaking_ingredient": "Eau"}},
            },
        )
        actions = order.get_actions(self.next_monday)
        actions.finalize()
        self.assertEqual(
            actions["delivery"],
            {
                delivery_date: {
                    "Semi-complet Kasha (1 kg)/GK": 4,
                    "Semi-complet kasha (2 kg)/TGK": 2,
                    "Semi-complet kasha (500 g)/PK": 4,
                }
            },
        )
        self.assertEqual(
            actions["bakery"],
            {
                "Semi-complet Kasha/GK": {
                    "ingredients": {
                        "Eau": 3110.0,
                        "Farine blé": 5990.0,
                        "Levain froment": 1680.0,
                        "Sel": 110.0,
                        "Graines kasha (trempé)": 1560.0,
                    },
                    "division": {"Semi-complet Kasha (1 kg)/GK": 4, "Semi-complet kasha (2 kg)/TGK": 2, "Semi-complet kasha (500 g)/PK": 4},
                    "weight": 12420,
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
        line = OrderLine(order=order, product=(Product.objects.get(ref="BR")), quantity=1)
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
                "levain": {"Levain froment": 130},
                "trempage": {
                    "Raisins secs": {"dry": 50, "soaking_qty": 50, "soaking_ingredient": "Eau"},
                    "Flocons de riz": {
                        "dry": 10,
                        "soaking_qty": 130,
                        "soaking_ingredient": "Eau",
                        "warning": "⚠ prévoir 10% de marge",
                    },
                },
            },
        )
        actions = order.get_actions(self.next_monday)
        actions.finalize()
        self.assertEqual(actions["delivery"], {delivery_date: {"Brioche raisin (500g)/BR": 1}})
        self.assertEqual(
            actions["bakery"],
            {
                "Brioche raisin/BR": {
                    "ingredients": {
                        "Eau": 0,
                        "Farine blé": 250,
                        "Huile": 20,
                        "Levain froment": 130,
                        "Sel": 3,
                        "Sucre": 30,
                        "Raisins secs (trempé)": 90,
                        "Flocons de riz (trempé)": 150,
                    },
                    "division": {"Brioche raisin (500g)/BR": 1},
                    "weight": 680,
                }
            },
        )
        self.assertEqual(len(actions["preparation"]["levain"]), 0)
        self.assertEqual(len(actions["preparation"]["trempage"]), 0)

    def test_rounding(self):
        delivery_date = DeliveryDate.objects.filter(weekly_delivery=self.context["monday_delivery"]).get(date=self.next_monday)
        order = Order(
            customer=self.context["guy"],
            delivery_date=delivery_date,
        )
        order.save()
        line = OrderLine(order=order, product=(Product.objects.get(ref="GSe")), quantity=6)
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
            {"levain": {"Levain froment": 880}, "trempage": {}},
        )
        actions = order.get_actions(self.next_monday)
        actions.finalize()
        self.assertEqual(actions["delivery"], {delivery_date: {"Seigle 70% (800 g)/GSe": 6}})
        self.assertEqual(
            actions["bakery"],
            {"Seigle 70%/GSe": {"ingredients": {"Eau": 2050, "Farine blé": 950, "Farine seigle": 2210, "Levain froment": 880, "Sel": 58}, "division": {"Seigle 70% (800 g)/GSe": 6}, "weight": 6180}},
        )
        self.assertEqual(len(actions["preparation"]["levain"]), 0)
        self.assertEqual(len(actions["preparation"]["trempage"]), 0)


class RestTests(TestCase):
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
        self.assertEqual(len(products), 21)
        for product in products:
            if product["name"] == "Semi-complet Kasha (1 kg)":
                GK = product
                self.assertEqual(product["ref"], "GK")
                self.assertEqual(product["price"], 6.5)
                self.assertAlmostEqual(product["cost_price"], Decimal(1.62))
                self.assertAlmostEqual(product["weight"], 1240)
                self.assertEqual(len(product["raw_ingredients"]), 5)
            if product["name"] == "Semi-complet kasha (2 kg)":
                self.assertEqual(product["ref"], "TGK")
                self.assertEqual(product["price"], 13)
                self.assertAlmostEqual(product["cost_price"], Decimal(3.23))
                self.assertAlmostEqual(product["weight"], 2490)
                self.assertEqual(product["orig_product"], GK["id"])
                self.assertEqual(product["coef"], 2)
                self.assertTrue(len(product["raw_ingredients"]) == 0)
            if product["name"] == "Cookie":
                self.assertAlmostEqual(product["cost_price"], Decimal(0.68))
                self.assertAlmostEqual(product["weight"], 120)

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
        self.assertAlmostEqual(sum([o["total_price"] for o in ddates[0][1]]), Decimal(188.09))
        self.assertAlmostEqual(sum([o["total_price"] for o in ddates[1][1]]), Decimal(218.69))
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
