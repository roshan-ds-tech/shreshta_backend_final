from django.urls import path
from . import views

urlpatterns = [
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/upload-image/', views.upload_profile_image_view, name='upload_profile_image'),
    path('shipping/quote/', views.shipping_quote, name='shipping_quote'),
    path('shipping/calculate/', views.calculate_shipping_view, name='calculate_shipping'),  # Legacy endpoint
    path('create-razorpay-order/', views.create_razorpay_order_view, name='create_razorpay_order'),
    path('verify-payment-save-order/', views.verify_payment_and_save_order_view, name='verify_payment_save_order'),
    path('orders/', views.get_user_orders_view, name='get_user_orders'),
    path('orders/<int:order_id>/tracking/', views.get_order_tracking_view, name='get_order_tracking'),
    path('orders/<int:order_id>/cancel/', views.cancel_order_view, name='cancel_order'),
    path('products/', views.products_view, name='products'),
    path('products/<int:product_id>/', views.product_detail_view, name='product_detail'),
    # Coupon management
    path('coupons/', views.coupons_view, name='coupons'),
    path('coupons/<int:coupon_id>/', views.coupon_detail_view, name='coupon_detail'),
]