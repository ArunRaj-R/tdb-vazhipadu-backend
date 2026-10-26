from django.contrib import admin
from .models import Temple, Offering, Order, OrderItem


@admin.register(Temple)
class TempleAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'code', 'created_at')
    search_fields = ('name', 'code')


@admin.register(Offering)
class OfferingAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'temple', 'price', 'is_active', 'daily_limit', 'created_at')
    list_filter = ('temple', 'is_active')
    search_fields = ('name',)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('offering', 'devotee_name', 'nakshatra', 'quantity', 'unit_price', 'total_price')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'temple', 'devotee_name', 'phone_number', 'date', 'total_amount', 'status', 'created_at')
    list_filter = ('temple', 'status', 'date')
    search_fields = ('devotee_name', 'phone_number', 'items__devotee_name')
    inlines = [OrderItemInline]
