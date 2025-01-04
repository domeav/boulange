from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from .models import Customer, WeeklyDelivery, DeliveryDate, Order, OrderLine, Product
from datetime import date, timedelta
import json

class ViewTests(TestCase):

    next_monday = date.today() + timedelta(days=7-date.today().weekday())
    
    def setUp(self):
        assert(self.next_monday.weekday()==0)
        store = User(username='store', first_name="a", last_name="store", email="store@toto.net")
        store.save()
        store_customer = Customer(user=store,
                                  is_professional=True,
                                  pro_discount_percentage=5,
                                  address="the store address")
        store_customer.save()
        guy = User(username='guy', first_name="a", last_name="guy", email="guy@toto.net")
        guy.save()
        guy_customer = Customer(user=guy,
                                  is_professional=False)
        guy_customer.save()
        monday_delivery = WeeklyDelivery(customer=store.customer,
                                      batch_target="SAME_DAY",
                                      day_of_week=0)
        monday_delivery.save()
        monday_delivery.generate_delivery_dates()
        wednesday_delivery = WeeklyDelivery(customer=store.customer,
                                         batch_target="PREVIOUS_DAY",
                                         day_of_week=2)
        wednesday_delivery.save()
        wednesday_delivery.generate_delivery_dates()
        count = DeliveryDate.objects.count()
        monday_delivery.generate_delivery_dates()
        wednesday_delivery.generate_delivery_dates()
        assert(count == DeliveryDate.objects.count())

        for monday in DeliveryDate.objects.filter(weekly_delivery=monday_delivery):
            recurring_order = Order(customer=store_customer,
                                    delivery_date=monday)
            recurring_order.save()
            for product, qty in ((Product.objects.get(ref='GN'), 5),
                                 (Product.objects.get(ref='TGN'), 3),
                                 (Product.objects.get(ref='PK'), 5),
                                 (Product.objects.get(ref='BR'), 8),
                                 (Product.objects.get(ref='COOKIE'), 20),
                                 (Product.objects.get(ref='GSe'), 5)):
                line = OrderLine(order=recurring_order,
                                 product=product,
                                 quantity=qty)
                line.save()
        for wednesday in DeliveryDate.objects.filter(weekly_delivery=wednesday_delivery):
            recurring_order2 = Order(customer=store_customer,
                                    delivery_date=wednesday)
            recurring_order2.save()
            for product, qty in ((Product.objects.get(ref='FAR'), 5),
                                 (Product.objects.get(ref='GK'), 5),
                                 (Product.objects.get(ref='GL'), 5),
                                 (Product.objects.get(ref='PN'), 8),
                                 (Product.objects.get(ref='BC'), 10),
                                 (Product.objects.get(ref='GSe'), 5)):
                line = OrderLine(order=recurring_order2,
                                 product=product,
                                 quantity=qty)
                line.save()
        simple_order = Order(customer=guy_customer,
                             delivery_date=DeliveryDate.objects.filter(weekly_delivery=monday_delivery).get(date=self.next_monday))
        simple_order.save()
        for product, qty in ((Product.objects.get(ref='COOKIE'), 6),
                             (Product.objects.get(ref='BR'), 1),
                             (Product.objects.get(ref='PN'), 1),
                             (Product.objects.get(ref='GSe'), 1),
                             (Product.objects.get(ref='GSa'), 1)):
            line = OrderLine(order=simple_order,
                             product=product,
                             quantity=qty)
            line.save()
        
        
        
    
    def test_products(self):
        response = self.client.get(reverse("boulange:products"), query_params={'json': True})
        self.assertEqual(response.status_code, 200)
        products = json.loads(response.getvalue().decode('utf-8'))
        self.assertEqual(len(products), 21)
        for product in products:
            if product['name'] == "Semi-complet Kasha (1 kg)":
                self.assertEqual(product['ref'], "GK")
                self.assertEqual(product['price'], 6.5)
                self.assertEqual(product['cost_price'], 1.62)
                self.assertEqual(len(product['ingredients']), 5)
            if product['name'] == "Semi-complet kasha (2 kg)":
                self.assertEqual(product['ref'], "TGK")
                self.assertEqual(product['price'], 13)
                self.assertEqual(product['cost_price'], 3.23)
                self.assertEqual(product['orig_product'], 'GK')
                self.assertEqual(product['coef'], 2)
                self.assertTrue('ingredients' not in product)
        

    def test_orders(self):
        response = self.client.get(
            reverse(
                "boulange:orders",
                kwargs={"year": self.next_monday.year, "month": self.next_monday.month, "day": self.next_monday.day, "span": "week"},                
            ), query_params={'json': True}
        )
        self.assertEqual(response.status_code, 200)
        ddates = json.loads(response.getvalue().decode('utf-8'))
        print(ddates)
        self.assertEqual(len(ddates), 2)
        self.assertEqual(ddates[0]['date'], self.next_monday.isoformat())
        self.assertEqual(sum([o["price"] for o in ddates[0]['orders']]), 188)
        self.assertEqual(sum([o["price"] for o in ddates[1]['orders']]), 219)
        self.assertEqual(ddates[1]['date'], (self.next_monday + timedelta(days=2)).isoformat())

    def test_monthly_receipt(self):
        user = User.objects.get(email='store@toto.net')
        response = self.client.get(
            reverse(
                "boulange:monthly_receipt",
                kwargs={"customer_id": user.customer.id, "year": self.next_monday.year, "month": self.next_monday.month},                
            ), query_params={'json': True}
        )
        self.assertEqual(response.status_code, 200)
        receipt = json.loads(response.getvalue().decode('utf-8'))

    def test_actions(self):
        dimanche = self.next_monday - timedelta(days=1)
        lundi = self.next_monday
        mardi = lundi + timedelta(days=1)
        mercredi = lundi + timedelta(days=2)
        dimanche_out = self.client.get(
            reverse("boulange:actions", kwargs={"year": dimanche.year, "month": dimanche.month, "day": dimanche.day})
        )
        self.assertEqual(dimanche_out.status_code, 200)
        self.assertContains(dimanche_out, "Actions pour le dimanche")
        lundi_out = self.client.get(
            reverse("boulange:actions", kwargs={"year": lundi.year, "month": lundi.month, "day": lundi.day})
        )
        self.assertEqual(lundi_out.status_code, 200)
        self.assertContains(lundi_out, "Actions pour le lundi")
        mardi_out = self.client.get(
            reverse("boulange:actions", kwargs={"year": mardi.year, "month": mardi.month, "day": mardi.day})
        )
        self.assertEqual(mardi_out.status_code, 200)
        self.assertContains(mardi_out, "Actions pour le mardi")
        mercredi_out = self.client.get(
            reverse("boulange:actions", kwargs={"year": mercredi.year, "month": mercredi.month, "day": mercredi.day})
        )
        self.assertEqual(mercredi_out.status_code, 200)
        self.assertContains(mercredi_out, "Actions pour le mercredi")
        with open('tmp.html', 'w') as out:
            out.write(lundi_out.getvalue().decode('utf-8'))
        with open('tmp-1.html', 'w') as out:
            out.write(dimanche_out.getvalue().decode('utf-8'))
        with open('tmp+1.html', 'w') as out:
            out.write(mardi_out.getvalue().decode('utf-8'))
        with open('tmp+2.html', 'w') as out:
            out.write(mercredi_out.getvalue().decode('utf-8'))

