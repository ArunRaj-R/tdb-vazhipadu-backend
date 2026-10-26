from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    TempleViewSet,
    OfferingViewSet,
    OrderViewSet,
    DailyCollectionReportView,
)

router = DefaultRouter()
router.register(r'temples', TempleViewSet, basename='temple')
router.register(r'offerings', OfferingViewSet, basename='offering')
router.register(r'orders', OrderViewSet, basename='order')

urlpatterns = [
    path('reports/daily-collection/', DailyCollectionReportView.as_view(), name='daily-collection-report'),
    path('', include(router.urls)),
]
