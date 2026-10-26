import concurrent.futures
import zoneinfo
from datetime import datetime
from decimal import Decimal
from django.db import connection
from django.db.models import Sum
from django.test import TestCase, TransactionTestCase
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

    def test_daily_limit_acceptance_criterion(self):
        """
        P3 Acceptance criterion:
        With a daily limit of 5 and 4 already booked, an order for 2 is rejected
        and an order for 1 succeeds.
        """
        pooja = Offering.objects.create(
            temple=self.temple,
            name="Udayasthamana Pooja",
            price=Decimal('100.00'),
            is_active=True,
            daily_limit=5,
        )

        booking_date = "2026-11-18"
        # Book 4 already
        initial_order = Order.objects.create(
            temple=self.temple,
            devotee_name="Initial Devotee",
            phone_number="9123456780",
            date=booking_date,
            total_amount=Decimal('400.00'),
            status=Order.Status.CONFIRMED,
        )
        OrderItem.objects.create(
            order=initial_order,
            offering=pooja,
            devotee_name="Initial Devotee",
            nakshatra="Rohini",
            quantity=4,
            unit_price=Decimal('100.00'),
            total_price=Decimal('400.00'),
        )

        url = reverse('order-list')

        # Try to order 2 -> should be rejected (4 + 2 = 6 > 5)
        payload_2 = {
            "temple": self.temple.id,
            "devotee_name": "Devotee Over",
            "phone_number": "9123456781",
            "date": booking_date,
            "items": [
                {
                    "offering_id": pooja.id,
                    "quantity": 2,
                    "devotee_name": "Devotee Over",
                    "nakshatra": "Makayiram",
                }
            ],
        }
        res_2 = self.client.post(url, payload_2, format='json')
        self.assertEqual(res_2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(res_2.data['error']['code'], 'VALIDATION_ERROR')
        self.assertIn("Daily limit exceeded", str(res_2.data['error']['details']))

        # Try to order 1 -> should succeed (4 + 1 = 5 <= 5)
        payload_1 = {
            "temple": self.temple.id,
            "devotee_name": "Devotee Fit",
            "phone_number": "9123456782",
            "date": booking_date,
            "items": [
                {
                    "offering_id": pooja.id,
                    "quantity": 1,
                    "devotee_name": "Devotee Fit",
                    "nakshatra": "Thiruvathira",
                }
            ],
        }
        res_1 = self.client.post(url, payload_1, format='json')
        self.assertEqual(res_1.status_code, status.HTTP_201_CREATED)

        # Confirm 5 total booked in database
        total_booked = OrderItem.objects.filter(
            offering=pooja,
            order__date=booking_date,
            order__status=Order.Status.CONFIRMED,
        ).aggregate(total=Sum('quantity'))['total']
        self.assertEqual(total_booked, 5)

    def test_order_cancellation_frees_daily_limit_and_excludes_from_report(self):
        """
        P4 Acceptance criteria:
        - Staff can cancel an order. A cancelled order frees its daily limit.
        - A cancelled order is not counted in the report, and its daily limit becomes available again.
        """
        from django.utils import timezone

        offering = Offering.objects.create(
            temple=self.temple,
            name="Special Pooja",
            price=Decimal('100.00'),
            is_active=True,
            daily_limit=2,
        )
        booking_date = "2026-11-25"
        url = reverse('order-list')

        # Devotee 1 books 2 (reaches limit)
        res1 = self.client.post(url, {
            "temple": self.temple.id,
            "devotee_name": "Devotee 1",
            "phone_number": "9111111111",
            "date": booking_date,
            "items": [{"offering_id": offering.id, "quantity": 2, "nakshatra": "Rohini"}],
        }, format='json')
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)
        order1_id = res1.data['id']

        # Devotee 2 attempts to book 1 -> rejected due to daily limit
        res2 = self.client.post(url, {
            "temple": self.temple.id,
            "devotee_name": "Devotee 2",
            "phone_number": "9222222222",
            "date": booking_date,
            "items": [{"offering_id": offering.id, "quantity": 1, "nakshatra": "Aswathy"}],
        }, format='json')
        self.assertEqual(res2.status_code, status.HTTP_400_BAD_REQUEST)

        # Staff cancels order 1
        cancel_url = reverse('order-cancel', kwargs={'pk': order1_id})
        cancel_res = self.client.post(cancel_url)
        self.assertEqual(cancel_res.status_code, status.HTTP_200_OK)
        self.assertEqual(cancel_res.data['status'], 'CANCELLED')

        # Now Devotee 2 attempts to book 1 again -> succeeds!
        res2_retry = self.client.post(url, {
            "temple": self.temple.id,
            "devotee_name": "Devotee 2",
            "phone_number": "9222222222",
            "date": booking_date,
            "items": [{"offering_id": offering.id, "quantity": 1, "nakshatra": "Aswathy"}],
        }, format='json')
        self.assertEqual(res2_retry.status_code, status.HTTP_201_CREATED)

        # Check daily collection report: order 1 must be excluded, only order 2 counted!
        today_str = str(timezone.localdate())
        report_url = reverse('daily-collection-report')
        rep_res = self.client.get(report_url, {'temple': self.temple.id, 'date': today_str})
        self.assertEqual(rep_res.status_code, status.HTTP_200_OK)
        # Only Devotee 2's ₹100 is in the report, NOT Devotee 1's ₹200
        self.assertEqual(Decimal(rep_res.data['total_amount']), Decimal('100.00'))
        self.assertEqual(rep_res.data['order_count'], 1)

    def test_order_placed_at_0015_ist_counted_on_that_date(self):
        """
        P4 Acceptance criterion:
        An order placed at 00:15 IST on a date is counted on that date.
        """
        ist = zoneinfo.ZoneInfo('Asia/Kolkata')
        # 2026-12-01 00:15:00 IST corresponds to 2026-11-30 18:45:00 UTC
        ist_timestamp = datetime(2026, 12, 1, 0, 15, 0, tzinfo=ist)

        order = Order.objects.create(
            temple=self.temple,
            devotee_name="Early Bird Devotee",
            phone_number="9333333333",
            date="2026-12-05",
            total_amount=Decimal('80.00'),
            status=Order.Status.CONFIRMED,
        )
        OrderItem.objects.create(
            order=order,
            offering=self.archana,
            devotee_name="Early Bird Devotee",
            nakshatra="Makayiram",
            quantity=1,
            unit_price=Decimal('50.00'),
            total_price=Decimal('50.00'),
        )
        OrderItem.objects.create(
            order=order,
            offering=self.pushpanjali,
            devotee_name="Early Bird Devotee",
            nakshatra="Makayiram",
            quantity=1,
            unit_price=Decimal('30.00'),
            total_price=Decimal('30.00'),
        )

        # Explicitly set created_at to 00:15 IST
        Order.objects.filter(id=order.id).update(created_at=ist_timestamp)

        report_url = reverse('daily-collection-report')

        # Should be counted on 2026-12-01
        res_dec1 = self.client.get(report_url, {'temple': self.temple.id, 'date': '2026-12-01'})
        self.assertEqual(res_dec1.status_code, status.HTTP_200_OK)
        self.assertEqual(Decimal(res_dec1.data['total_amount']), Decimal('80.00'))
        self.assertEqual(res_dec1.data['order_count'], 1)

        # Should NOT be counted on 2026-11-30
        res_nov30 = self.client.get(report_url, {'temple': self.temple.id, 'date': '2026-11-30'})
        self.assertEqual(res_nov30.status_code, status.HTTP_200_OK)
        self.assertEqual(Decimal(res_nov30.data['total_amount']), Decimal('0.00'))
        self.assertEqual(res_nov30.data['order_count'], 0)

    def test_daily_collection_report_total_equals_sum_of_offerings_totals_to_the_paisa(self):
        """
        P4 Acceptance criterion:
        The report total equals the sum of its offerings' totals to the paisa.
        """
        o1 = Offering.objects.create(temple=self.temple, name="P1", price=Decimal('33.33'))
        o2 = Offering.objects.create(temple=self.temple, name="P2", price=Decimal('66.67'))
        o3 = Offering.objects.create(temple=self.temple, name="P3", price=Decimal('100.50'))

        order_date = "2026-12-10"
        order1 = Order.objects.create(
            temple=self.temple,
            devotee_name="D1",
            phone_number="9444444441",
            date=order_date,
            total_amount=Decimal('133.33'),
            status=Order.Status.CONFIRMED,
        )
        OrderItem.objects.create(order=order1, offering=o1, devotee_name="D1", nakshatra="Star1", quantity=2, unit_price=Decimal('33.33'), total_price=Decimal('66.66'))
        OrderItem.objects.create(order=order1, offering=o2, devotee_name="D1", nakshatra="Star1", quantity=1, unit_price=Decimal('66.67'), total_price=Decimal('66.67'))

        order2 = Order.objects.create(
            temple=self.temple,
            devotee_name="D2",
            phone_number="9444444442",
            date=order_date,
            total_amount=Decimal('201.00'),
            status=Order.Status.CONFIRMED,
        )
        OrderItem.objects.create(order=order2, offering=o3, devotee_name="D2", nakshatra="Star2", quantity=2, unit_price=Decimal('100.50'), total_price=Decimal('201.00'))

        # Set created_at to 2026-12-10 in IST
        ist = zoneinfo.ZoneInfo('Asia/Kolkata')
        ist_time = datetime(2026, 12, 10, 11, 30, 0, tzinfo=ist)
        Order.objects.filter(id__in=[order1.id, order2.id]).update(created_at=ist_time)

        report_url = reverse('daily-collection-report')
        res = self.client.get(report_url, {'temple': self.temple.id, 'date': '2026-12-10'})
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        report_total = Decimal(res.data['total_amount'])
        offerings_sum = sum(Decimal(off['total_amount']) for off in res.data['offerings'])

        self.assertEqual(report_total, offerings_sum)
        self.assertEqual(report_total, Decimal('334.33'))


class ConcurrentDailyLimitTests(TransactionTestCase):
    """
    P3 Acceptance criterion:
    An automated test fires 20 simultaneous orders for 1 each against a daily limit of 5.
    Exactly 5 succeed.
    """
    def test_20_simultaneous_orders_against_daily_limit_of_5(self):
        temple = Temple.objects.create(name="Chottanikkara Temple", code="CKT-001")
        offering = Offering.objects.create(
            temple=temple,
            name="Guruthi Pooja",
            price=Decimal('50.00'),
            is_active=True,
            daily_limit=5,
        )
        booking_date = "2026-11-20"
        url = reverse('order-list')

        def attempt_booking(worker_id):
            client = APIClient()
            payload = {
                "temple": temple.id,
                "devotee_name": f"Concurrent Devotee {worker_id}",
                "phone_number": f"90000000{worker_id:02d}",
                "date": booking_date,
                "items": [
                    {
                        "offering_id": offering.id,
                        "quantity": 1,
                        "devotee_name": f"Devotee {worker_id}",
                        "nakshatra": "Aswathy",
                    }
                ],
            }
            try:
                response = client.post(url, payload, format='json')
                return response.status_code
            finally:
                connection.close()

        # Fire 20 simultaneous requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(attempt_booking, i) for i in range(20)]
            status_codes = [f.result() for f in concurrent.futures.as_completed(futures)]

        success_count = sum(1 for sc in status_codes if sc == status.HTTP_201_CREATED)
        rejected_count = sum(1 for sc in status_codes if sc == status.HTTP_400_BAD_REQUEST)

        # Acceptance criterion: Exactly 5 succeed, and 15 are rejected
        self.assertEqual(success_count, 5, f"Expected 5 successes, but got {success_count}. Statuses: {status_codes}")
        self.assertEqual(rejected_count, 15, f"Expected 15 rejections, but got {rejected_count}. Statuses: {status_codes}")

        # Verify database integrity: Total booked quantity for date is exactly 5
        booked_qty = OrderItem.objects.filter(
            offering=offering,
            order__date=booking_date,
            order__status=Order.Status.CONFIRMED,
        ).aggregate(total=Sum('quantity'))['total']
        self.assertEqual(booked_qty, 5)


