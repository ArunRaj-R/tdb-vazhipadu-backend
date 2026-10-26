from decimal import Decimal
from django.db import models


class Temple(models.Model):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.code})"


class Offering(models.Model):
    temple = models.ForeignKey(Temple, related_name='offerings', on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} - ₹{self.price} ({'Active' if self.is_active else 'Inactive'})"


class Order(models.Model):
    class Status(models.TextChoices):
        CONFIRMED = 'CONFIRMED', 'Confirmed'
        CANCELLED = 'CANCELLED', 'Cancelled'

    temple = models.ForeignKey(Temple, related_name='orders', on_delete=models.CASCADE)
    devotee_name = models.CharField(max_length=255, help_text="Booker / devotee name")
    phone_number = models.CharField(max_length=20, help_text="Contact phone number for counter lookup")
    date = models.DateField(help_text="Ritual / Offering performance date")
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.CONFIRMED)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['temple', 'date'], name='idx_order_temple_date'),
            models.Index(fields=['temple', 'status'], name='idx_order_temple_status'),
            models.Index(fields=['temple', 'phone_number'], name='idx_order_temple_phone'),
            models.Index(fields=['phone_number'], name='idx_order_phone'),
            models.Index(fields=['temple', 'date', 'status'], name='idx_order_temple_dt_st'),
        ]

    def __str__(self):
        return f"Order #{self.id} - {self.devotee_name} ({self.date})"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    offering = models.ForeignKey(Offering, related_name='order_items', on_delete=models.PROTECT)
    devotee_name = models.CharField(max_length=255, help_text="Devotee for whom this ritual is conducted")
    nakshatra = models.CharField(max_length=100, help_text="Birth star of the devotee")
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"{self.quantity}x {self.offering.name} for {self.devotee_name} ({self.nakshatra})"
