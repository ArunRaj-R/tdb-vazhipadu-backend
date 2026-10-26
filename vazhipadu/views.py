import zoneinfo
from collections import defaultdict
from datetime import datetime, time
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone
from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Temple, Offering, Order, OrderItem
from .pagination import StandardResultsSetPagination
from .serializers import (
    TempleSerializer,
    OfferingSerializer,
    OrderCreateSerializer,
    OrderDetailSerializer,
)


def compute_daily_collection_report(temple, date_str):
    """
    Computes daily collection for a temple and calendar date in Indian Standard Time (IST).
    Totals strictly match to the paisa.
    Excludes cancelled orders.
    """
    ist = zoneinfo.ZoneInfo('Asia/Kolkata')
    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        raise ValidationError({"date": "Invalid date format. Expected YYYY-MM-DD."})

    # Calendar day boundaries in Indian Standard Time (00:00:00 to 23:59:59.999999 IST)
    start_dt = datetime.combine(target_date, time.min, tzinfo=ist)
    end_dt = datetime.combine(target_date, time.max, tzinfo=ist)

    # Active/confirmed orders placed on this date in IST
    confirmed_orders = Order.objects.filter(
        temple=temple,
        status=Order.Status.CONFIRMED,
        created_at__gte=start_dt,
        created_at__lte=end_dt,
    )

    items = OrderItem.objects.filter(order__in=confirmed_orders).select_related('offering')

    offering_stats = defaultdict(lambda: {'count': 0, 'total_amount': Decimal('0.00'), 'name': ''})
    for item in items:
        offering_stats[item.offering_id]['count'] += item.quantity
        offering_stats[item.offering_id]['total_amount'] += item.total_price
        offering_stats[item.offering_id]['name'] = item.offering.name

    offerings_report = [
        {
            'offering_id': oid,
            'offering_name': data['name'],
            'count': data['count'],
            'total_amount': str(data['total_amount']),
        }
        for oid, data in sorted(offering_stats.items(), key=lambda x: x[1]['name'])
    ]

    total_order_amount = confirmed_orders.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')

    return {
        'temple_id': temple.id,
        'temple_name': temple.name,
        'date': str(target_date),
        'timezone': 'Asia/Kolkata',
        'order_count': confirmed_orders.count(),
        'total_amount': str(total_order_amount),
        'offerings': offerings_report,
    }


class TempleViewSet(viewsets.ModelViewSet):
    """Manage temples."""
    queryset = Temple.objects.all()
    serializer_class = TempleSerializer

    @action(detail=True, methods=['get'], url_path='daily-collection')
    def daily_collection(self, request, pk=None):
        temple = self.get_object()
        date_str = request.query_params.get('date')
        if not date_str:
            date_str = str(timezone.localdate())
        report = compute_daily_collection_report(temple, date_str)
        return Response(report, status=status.HTTP_200_OK)


class OfferingViewSet(viewsets.ModelViewSet):
    """
    Manage offerings for a temple:
    Supports filtering by temple and active status:
    GET /api/offerings/?temple=1&is_active=true
    """
    queryset = Offering.objects.all()
    serializer_class = OfferingSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        temple_id = self.request.query_params.get('temple')
        if temple_id:
            queryset = queryset.filter(temple_id=temple_id)
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() in ['true', '1'])
        return queryset


class OrderViewSet(mixins.CreateModelMixin,
                   mixins.RetrieveModelMixin,
                   mixins.ListModelMixin,
                   viewsets.GenericViewSet):
    """
    Order management endpoints:
    - POST /api/orders/ : Place an order
    - GET /api/orders/<id>/ : Retrieve order details
    - GET /api/orders/?temple=1&date=YYYY-MM-DD&status=CONFIRMED&phone_number=... : Search and list orders with pagination
    - POST /api/orders/<id>/cancel/ : Cancel an order and release its daily limit
    """
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        queryset = Order.objects.select_related('temple').prefetch_related('items__offering')

        temple_id = self.request.query_params.get('temple')
        if temple_id:
            queryset = queryset.filter(temple_id=temple_id)

        date_param = self.request.query_params.get('date')
        if date_param:
            queryset = queryset.filter(date=date_param)

        status_param = self.request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param.upper())

        phone_param = self.request.query_params.get('phone_number') or self.request.query_params.get('phone')
        if phone_param:
            queryset = queryset.filter(phone_number=phone_param.strip())

        return queryset.order_by('-created_at', '-id')

    def get_serializer_class(self):
        if self.action == 'create':
            return OrderCreateSerializer
        return OrderDetailSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = serializer.save()
        response_serializer = OrderDetailSerializer(order)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, *args, **kwargs):
        order = self.get_object()
        serializer = OrderDetailSerializer(order)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post', 'patch'], url_path='cancel')
    def cancel(self, request, pk=None):
        """Staff cancellation of an order; frees up daily limits."""
        order = self.get_object()
        if order.status != Order.Status.CANCELLED:
            order.status = Order.Status.CANCELLED
            order.save(update_fields=['status'])

        serializer = OrderDetailSerializer(order)
        return Response(serializer.data, status=status.HTTP_200_OK)


class DailyCollectionReportView(APIView):
    """
    GET /api/reports/daily-collection/?temple=1&date=YYYY-MM-DD
    Daily collection report in Indian Standard Time (IST).
    """
    def get(self, request):
        temple_id = request.query_params.get('temple')
        if not temple_id:
            raise ValidationError({"temple": "Query parameter 'temple' is required."})

        try:
            temple = Temple.objects.get(id=temple_id)
        except Temple.DoesNotExist:
            raise ValidationError({"temple": f"Temple with ID {temple_id} does not exist."})

        date_str = request.query_params.get('date')
        if not date_str:
            date_str = str(timezone.localdate())

        report = compute_daily_collection_report(temple, date_str)
        return Response(report, status=status.HTTP_200_OK)
