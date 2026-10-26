from decimal import Decimal
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from .models import Temple, Offering, Order, OrderItem


class VazhipaduAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.temple = Temple.objects.create(name="Sree Mahadeva Temple", code="SMT-001")
        self.pushpanjali = Offering.objects.create(
            temple=self.temple,
            name="Pushpanjali",
            price=Decimal('30.00'),
            is_active=True,
        )
        self.archana = Offering.objects.create(
            temple=self.temple,
            name="Archana",
            price=Decimal('50.00'),
            is_active=True,
        )
        self.inactive_offering = Offering.objects.create(
            temple=self.temple,
            name="Special Abhishekam",
            price=Decimal('500.00'),
            is_active=False,
        )

    def test_offering_catalog_management(self):
        """Test listing and filtering offerings."""
        url = reverse('offering-list')
        response = self.client.get(url, {'temple': self.temple.id, 'is_active': 'true'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        offering_names = [item['name'] for item in response.data]
        self.assertIn("Pushpanjali", offering_names)
        self.assertIn("Archana", offering_names)
        self.assertNotIn("Special Abhishekam", offering_names)

    def test_order_total_calculation_with_multi_devotee_items(self):
        """
        Acceptance criterion:
        An order for 2 Pushpanjali at ₹30 and 1 Archana at ₹50 has a total of ₹110.
        Also tests multiple devotee names and nakshatras across order items.
        """
        url = reverse('order-list')
        payload = {
            "temple": self.temple.id,
            "devotee_name": "Arun Raj",
            "phone_number": "9876543210",
            "date": "2026-11-01",
            "items": [
                {
                    "offering_id": self.pushpanjali.id,
                    "quantity": 2,
                    "devotee_name": "Arun Raj",
                    "nakshatra": "Aswathy",
                },
                {
                    "offering_id": self.archana.id,
                    "quantity": 1,
                    "devotee_name": "Priya",
                    "nakshatra": "Rohini",
                },
            ],
        }
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Decimal(str(response.data['total_amount'])), Decimal('110.00'))
        self.assertEqual(len(response.data['items']), 2)

        # Check in DB
        order = Order.objects.get(id=response.data['id'])
        self.assertEqual(order.total_amount, Decimal('110.00'))
        self.assertEqual(order.items.count(), 2)

        # Verify individual item devotee and star details
        item1 = order.items.get(offering=self.pushpanjali)
        self.assertEqual(item1.devotee_name, "Arun Raj")
        self.assertEqual(item1.nakshatra, "Aswathy")
        self.assertEqual(item1.total_price, Decimal('60.00'))

        item2 = order.items.get(offering=self.archana)
        self.assertEqual(item2.devotee_name, "Priya")
        self.assertEqual(item2.nakshatra, "Rohini")
        self.assertEqual(item2.total_price, Decimal('50.00'))

    def test_inactive_offering_rejected_acceptance_criterion(self):
        """
        Acceptance criterion:
        An order for an inactive offering is rejected.
        """
        url = reverse('order-list')
        payload = {
            "temple": self.temple.id,
            "devotee_name": "Gopakumar",
            "phone_number": "9123456789",
            "date": "2026-11-01",
            "items": [
                {
                    "offering_id": self.inactive_offering.id,
                    "quantity": 1,
                    "devotee_name": "Gopakumar",
                    "nakshatra": "Bharani",
                }
            ],
        }
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Consistent JSON error format verification
        self.assertIn("error", response.data)
        self.assertEqual(response.data['error']['code'], 'VALIDATION_ERROR')
        self.assertIn("inactive", str(response.data['error']))

    def test_get_order_by_id(self):
        """Test retrieving an order by its ID."""
        order = Order.objects.create(
            temple=self.temple,
            devotee_name="Devan",
            phone_number="9988776655",
            date="2026-11-05",
            total_amount=Decimal('60.00'),
        )
        OrderItem.objects.create(
            order=order,
            offering=self.pushpanjali,
            devotee_name="Devan",
            nakshatra="Karthika",
            quantity=2,
            unit_price=Decimal('30.00'),
            total_price=Decimal('60.00'),
        )

        url = reverse('order-detail', kwargs={'pk': order.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], order.id)
        self.assertEqual(response.data['devotee_name'], "Devan")
        self.assertEqual(Decimal(str(response.data['total_amount'])), Decimal('60.00'))
        self.assertEqual(len(response.data['items']), 1)
        self.assertEqual(response.data['items'][0]['offering_name'], "Pushpanjali")
        self.assertEqual(response.data['items'][0]['nakshatra'], "Karthika")

    def test_item_missing_nakshatra_rejected(self):
        """Verify invalid input rejection when an offering item misses nakshatra."""
        url = reverse('order-list')
        payload = {
            "temple": self.temple.id,
            "devotee_name": "Suresh",
            "phone_number": "9812345670",
            "date": "2026-11-01",
            "items": [
                {
                    "offering_id": self.pushpanjali.id,
                    "quantity": 1,
                    # nakshatra is omitted
                }
            ],
        }
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error']['code'], 'VALIDATION_ERROR')
        self.assertIn("nakshatra", str(response.data['error']['details']))

    def test_consistent_json_error_format_on_404(self):
        """Test consistent JSON error format when an order is not found."""
        url = reverse('order-detail', kwargs={'pk': 99999})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("error", response.data)
        self.assertEqual(response.data['error']['code'], 'NOT_FOUND')

    def test_search_by_phone_number_returns_only_that_devotees_orders(self):
        """
        P2 Acceptance criterion:
        Searching by phone number returns only that devotee's orders.
        """
        target_phone = "9447012345"
        other_phone = "9847999888"

        for i in range(3):
            Order.objects.create(
                temple=self.temple,
                devotee_name=f"Devotee A{i}",
                phone_number=target_phone,
                date="2026-11-10",
                total_amount=Decimal('30.00'),
            )
        for i in range(2):
            Order.objects.create(
                temple=self.temple,
                devotee_name=f"Devotee B{i}",
                phone_number=other_phone,
                date="2026-11-10",
                total_amount=Decimal('50.00'),
            )

        url = reverse('order-list')
        response = self.client.get(url, {'phone_number': target_phone})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']
        self.assertEqual(len(results), 3)
        self.assertEqual(response.data['count'], 3)
        for order in results:
            self.assertEqual(order['phone_number'], target_phone)

    def test_pagination_page_2_no_repeats_no_gaps(self):
        """
        P2 Acceptance criterion:
        Requesting page 2 returns the next set of results, with no repeats or gaps from page 1.
        """
        created_orders = []
        for i in range(25):
            order = Order.objects.create(
                temple=self.temple,
                devotee_name=f"Pagination Devotee {i:02d}",
                phone_number="9111222333",
                date="2026-11-12",
                total_amount=Decimal('30.00'),
            )
            created_orders.append(order)

        url = reverse('order-list')
        # Page 1
        response_page1 = self.client.get(url, {'page': 1, 'page_size': 10})
        self.assertEqual(response_page1.status_code, status.HTTP_200_OK)
        page1_results = response_page1.data['results']
        self.assertEqual(len(page1_results), 10)
        self.assertEqual(response_page1.data['current_page'], 1)
        self.assertIsNotNone(response_page1.data['next'])

        # Page 2
        response_page2 = self.client.get(url, {'page': 2, 'page_size': 10})
        self.assertEqual(response_page2.status_code, status.HTTP_200_OK)
        page2_results = response_page2.data['results']
        self.assertEqual(len(page2_results), 10)
        self.assertEqual(response_page2.data['current_page'], 2)

        page1_ids = [item['id'] for item in page1_results]
        page2_ids = [item['id'] for item in page2_results]

        # No repeats between page 1 and page 2
        intersection = set(page1_ids).intersection(set(page2_ids))
        self.assertEqual(len(intersection), 0, f"Found overlapping order IDs: {intersection}")

        # No gaps: since ordered by -created_at, -id, the lowest id on page 1 is strictly greater than highest on page 2
        self.assertTrue(min(page1_ids) > max(page2_ids))

    def test_filter_by_temple_date_and_status(self):
        """Test filtering orders by temple, date, and status."""
        other_temple = Temple.objects.create(name="Sri Krishna Temple", code="SKT-002")

        o1 = Order.objects.create(
            temple=self.temple,
            devotee_name="Anand",
            phone_number="9000000001",
            date="2026-11-15",
            status=Order.Status.CONFIRMED,
            total_amount=Decimal('30.00'),
        )
        o2 = Order.objects.create(
            temple=self.temple,
            devotee_name="Bindu",
            phone_number="9000000002",
            date="2026-11-15",
            status=Order.Status.CANCELLED,
            total_amount=Decimal('50.00'),
        )
        o3 = Order.objects.create(
            temple=other_temple,
            devotee_name="Chandran",
            phone_number="9000000003",
            date="2026-11-15",
            status=Order.Status.CONFIRMED,
            total_amount=Decimal('30.00'),
        )

        url = reverse('order-list')
        response = self.client.get(url, {
            'temple': self.temple.id,
            'date': '2026-11-15',
            'status': 'CONFIRMED',
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['id'], o1.id)

