from django.test import TestCase
from django.urls import reverse

class ViewTests(TestCase):
    def test_products(self):
        response = self.client.get(reverse("products"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Semi-complet lin (2 kg)")
    def test_orders(self):
        response = self.client.get(reverse("orders"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Commandes")
    def test_actions(self):
        response = self.client.get(reverse("actions", kwargs={'year': 2024, 'month': 10, 'day': 10}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Actions pour le 10 octobre 2024")
