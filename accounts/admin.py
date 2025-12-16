from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import UserProfile, Order, OrderItem, Product

# Inline profile inside the User admin page
class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'profile'
    fk_name = 'user'

# Extend the default UserAdmin to include the profile inline and show email
class CustomUserAdmin(DjangoUserAdmin):
    inlines = (UserProfileInline,)
    # columns shown on the user list page in admin
    list_display = ('username', 'email', 'is_staff', 'is_active', 'is_superuser')
    list_select_related = ('userprofile',)

    def phone(self, obj):
        # safe access to related profile
        return getattr(obj.userprofile, 'phone', '')
    phone.short_description = 'Phone'

    # If you want the phone to appear in the list_display, uncomment:
    list_display = ('username', 'email', 'phone', 'is_staff', 'is_active', 'is_superuser')

# Unregister the default User admin and register our extended one
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)

# Also register UserProfile separately (optional)
@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone')
    search_fields = ('user__username', 'phone', 'user__email')


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product_id', 'product_name', 'quantity', 'price', 'total_price')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_number', 'user', 'total', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('order_number', 'user__username', 'razorpay_order_id', 'razorpay_payment_id')
    readonly_fields = ('order_number', 'razorpay_order_id', 'razorpay_payment_id', 'razorpay_signature', 'created_at', 'updated_at')
    inlines = [OrderItemInline]
    
    fieldsets = (
        ('Order Information', {
            'fields': ('order_number', 'user', 'status', 'created_at', 'updated_at')
        }),
        ('Payment Details', {
            'fields': ('razorpay_order_id', 'razorpay_payment_id', 'razorpay_signature')
        }),
        ('Amounts', {
            'fields': ('subtotal', 'shipping_charge', 'discount', 'total', 'coupon_code')
        }),
        ('Shipping Details', {
            'fields': ('shipping_courier', 'estimated_delivery_date', 'estimated_delivery_days')
        }),
        ('Delivery Address', {
            'fields': ('delivery_name', 'delivery_phone', 'delivery_address_line1', 'delivery_city', 'delivery_state', 'delivery_pincode')
        }),
    )


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price', 'created_at')
    list_filter = ('category', 'created_at')
    search_fields = ('name', 'description', 'category')
    readonly_fields = ('created_at', 'updated_at')