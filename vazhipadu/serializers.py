from decimal import Decimal
from django.db import transaction
from rest_framework import serializers

from .models import Temple, Offering, Order, OrderItem


class TempleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Temple
        fields = ['id', 'name', 'code', 'created_at']


class OfferingSerializer(serializers.ModelSerializer):
    temple_name = serializers.ReadOnlyField(source='temple.name')

    class Meta:
        model = Offering
        fields = ['id', 'temple', 'temple_name', 'name', 'price', 'is_active', 'created_at']

    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Offering price must be greater than zero.")
        return value


class OrderItemInputSerializer(serializers.Serializer):
    offering_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)
    devotee_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    nakshatra = serializers.CharField(max_length=100, required=True)


class OrderItemDetailSerializer(serializers.ModelSerializer):
    offering_name = serializers.ReadOnlyField(source='offering.name')

    class Meta:
        model = OrderItem
        fields = [
            'id',
            'offering_id',
            'offering_name',
            'quantity',
            'unit_price',
            'total_price',
            'devotee_name',
            'nakshatra',
        ]


class OrderCreateSerializer(serializers.Serializer):
    temple = serializers.PrimaryKeyRelatedField(queryset=Temple.objects.all())
    devotee_name = serializers.CharField(max_length=255, help_text="Booker / Primary contact name")
    phone_number = serializers.CharField(max_length=20, help_text="Contact phone number")
    date = serializers.DateField()
    items = OrderItemInputSerializer(many=True)

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("An order must contain at least one offering item.")
        return value

    def create(self, validated_data):
        temple = validated_data['temple']
        devotee_name = validated_data['devotee_name']
        phone_number = validated_data['phone_number']
        booking_date = validated_data['date']
        items_data = validated_data['items']

        with transaction.atomic():
            offering_ids = [item['offering_id'] for item in items_data]
            offerings = {
                o.id: o
                for o in Offering.objects.filter(id__in=offering_ids, temple=temple)
            }

            # Check for invalid offering IDs
            missing_ids = set(offering_ids) - set(offerings.keys())
            if missing_ids:
                raise serializers.ValidationError({
                    "items": f"Offerings with IDs {list(missing_ids)} do not exist for this temple."
                })

            # Check for inactive offerings
            for item_input in items_data:
                offering = offerings[item_input['offering_id']]
                if not offering.is_active:
                    raise serializers.ValidationError({
                        "items": f"Offering '{offering.name}' is currently inactive and cannot be booked."
                    })

            # Server computes order total
            total_amount = Decimal('0.00')
            order_items_to_create = []

            order = Order.objects.create(
                temple=temple,
                devotee_name=devotee_name,
                phone_number=phone_number,
                date=booking_date,
                total_amount=Decimal('0.00'),
            )

            for item_input in items_data:
                offering = offerings[item_input['offering_id']]
                quantity = item_input['quantity']
                unit_price = offering.price
                item_total = unit_price * quantity
                total_amount += item_total

                # Devotee name for this ritual item defaults to the booker if not specified
                item_devotee = item_input.get('devotee_name') or devotee_name
                item_nakshatra = item_input['nakshatra']

                order_items_to_create.append(
                    OrderItem(
                        order=order,
                        offering=offering,
                        quantity=quantity,
                        unit_price=unit_price,
                        total_price=item_total,
                        devotee_name=item_devotee,
                        nakshatra=item_nakshatra,
                    )
                )

            OrderItem.objects.bulk_create(order_items_to_create)
            order.total_amount = total_amount
            order.save(update_fields=['total_amount'])

            return order


class OrderDetailSerializer(serializers.ModelSerializer):
    temple_name = serializers.ReadOnlyField(source='temple.name')
    items = OrderItemDetailSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            'id',
            'temple',
            'temple_name',
            'devotee_name',
            'phone_number',
            'date',
            'total_amount',
            'status',
            'created_at',
            'items',
        ]
