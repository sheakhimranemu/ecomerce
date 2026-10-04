from django.contrib import admin
from .models import Category, Product, Order, OrderItem, Coupon, Review

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'price', 'stock', 'is_available')
    list_editable = ('price', 'stock', 'is_available')

@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ('code', 'discount_percentage', 'active')
    list_editable = ('active',)

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'phone', 'payment_method', 'transaction_id', 'total_price', 'status', 'created_at')
    list_editable = ('status',)
    inlines = [OrderItemInline]
    search_fields = ('name', 'phone', 'address', 'transaction_id')

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('product', 'name', 'rating', 'created_at')
