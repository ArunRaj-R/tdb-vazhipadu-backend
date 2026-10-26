from rest_framework import viewsets, mixins, status
from rest_framework.response import Response

from .models import Temple, Offering, Order
from .pagination import StandardResultsSetPagination
from .serializers import (
    TempleSerializer,
    OfferingSerializer,
    OrderCreateSerializer,
    OrderDetailSerializer,
)


class TempleViewSet(viewsets.ModelViewSet):
    """Manage temples."""
    queryset = Temple.objects.all()
    serializer_class = TempleSerializer


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
