from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import TempleViewSet, OfferingViewSet, OrderViewSet

router = DefaultRouter()
router.register(r'temples', TempleViewSet, basename='temple')
router.register(r'offerings', OfferingViewSet, basename='offering')
router.register(r'orders', OrderViewSet, basename='order')

urlpatterns = [
    path('', include(router.urls)),
]
