from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator

# ✅ Phone number validator (allows +, and enforces 10–15 digits)
phone_validator = RegexValidator(
    regex=r'^\+?\d{10,15}$',
    message='Enter a valid phone number with at least 10 digits.'
)

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone = models.CharField(
        max_length=15,
        validators=[phone_validator],
        blank=True
    )
    profile_image = models.ImageField(
        upload_to='profile_images/',
        blank=True,
        null=True
    )

    def __str__(self):
        return self.user.username


# Order Models
class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('processing', 'Processing'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    order_number = models.CharField(max_length=50, unique=True)
    
    # Payment details
    razorpay_order_id = models.CharField(max_length=255)
    razorpay_payment_id = models.CharField(max_length=255, blank=True, null=True)
    razorpay_signature = models.CharField(max_length=255, blank=True, null=True)
    
    # Shiprocket details
    shiprocket_order_id = models.CharField(max_length=200, blank=True, null=True)
    shipment_id = models.CharField(max_length=200, blank=True, null=True)
    awb_code = models.CharField(max_length=200, blank=True, null=True)
    courier_company = models.CharField(max_length=200, blank=True, null=True)
    tracking_url = models.CharField(max_length=500, blank=True, null=True)
    # Pickup scheduling
    pickup_scheduled = models.BooleanField(default=False)
    pickup_status = models.CharField(max_length=100, blank=True, null=True)
    pickup_data = models.TextField(blank=True, null=True)  # JSON string of pickup response
    
    # Order amounts
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    shipping_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Shipping details
    shipping_courier = models.CharField(max_length=255, blank=True, null=True)
    estimated_delivery_date = models.CharField(max_length=100, blank=True, null=True)
    estimated_delivery_days = models.CharField(max_length=50, blank=True, null=True)
    
    # Delivery address
    delivery_name = models.CharField(max_length=255)
    delivery_phone = models.CharField(max_length=15)
    delivery_address_line1 = models.CharField(max_length=255)
    delivery_city = models.CharField(max_length=100)
    delivery_state = models.CharField(max_length=100)
    delivery_pincode = models.CharField(max_length=10)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Coupon code if applied
    coupon_code = models.CharField(max_length=50, blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Order {self.order_number} - {self.user.username}"
    
    class Meta:
        ordering = ['-created_at']


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product_id = models.IntegerField()
    product_name = models.CharField(max_length=255)
    product_image = models.URLField(blank=True, null=True)
    quantity = models.IntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    
    def __str__(self):
        return f"{self.product_name} x{self.quantity} - Order {self.order.order_number}"
    
    class Meta:
        ordering = ['id']


class Product(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    price = models.CharField(max_length=50)  # e.g., "299/kg", "₹299/kg"
    image = models.CharField(max_length=500)  # Image path/URL
    category = models.CharField(max_length=100)
    weight_value = models.DecimalField(max_digits=10, decimal_places=3, blank=True, null=True)
    weight_unit = models.CharField(max_length=10, choices=[('kg', 'kg'), ('g', 'g'), ('L', 'L')], default='kg')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        ordering = ['-created_at']


class Coupon(models.Model):
    """
    Simple percentage-based coupon.
    Example: code="NITHIN10", discount_percentage=10.00
    """
    code = models.CharField(max_length=50, unique=True)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2)  # e.g. 10.00 = 10%
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.code} ({self.discount_percentage}%)"

    class Meta:
        ordering = ['-created_at']
