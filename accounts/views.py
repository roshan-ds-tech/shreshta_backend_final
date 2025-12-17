from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from .models import UserProfile, Order, OrderItem, Product
from  rest_framework import status
from django.contrib.auth import authenticate
from django.conf import settings
from django.core.cache import cache
from datetime import datetime, timedelta
import os
import requests
import json
import razorpay
import hashlib
import hmac
import re
from datetime import date

@api_view(['GET', 'POST'])
def signup_view(request):
    if request.method == 'GET':
        return Response({'info': 'Signup endpoint ready'})

    data = request.data
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    phone = data.get('phone')

    if not username or not email or not password or not phone:
        return Response({'error': 'All fields are required'}, status=400)

    if User.objects.filter(username=username).exists():
        return Response({'error': 'Username already exists'}, status=400)

    if User.objects.filter(email=email).exists():
        return Response({'error': 'Email already registered'}, status=400)

    # Create new user
    user = User.objects.create(
        username=username,
        email=email,
        password=make_password(password)
    )

    # Create or update profile safely
    profile, created = UserProfile.objects.get_or_create(user=user)
    profile.phone = phone
    profile.save()

    return Response({'message': 'User registered successfully!'})


@api_view(['POST'])
def login_view(request):
    username = request.data.get('username')
    password = request.data.get('password')

    user = authenticate(username=username, password=password)

    if user is not None:
        profile_image_url = None
        phone = None
        try:
            profile = user.userprofile
            phone = profile.phone
            if profile.profile_image:
                profile_image_url = request.build_absolute_uri(profile.profile_image.url)
        except UserProfile.DoesNotExist:
            pass
        
        return Response({
            'message': 'Login successful',
            'username': user.username,
            'email': user.email,
            'phone': phone,
            'profile_image': profile_image_url
        }, status=status.HTTP_200_OK)
    else:
        return Response({'error': 'Invalid username or password'}, status=status.HTTP_401_UNAUTHORIZED)


@api_view(['GET', 'PUT'])
def profile_view(request):
    """Get or update user profile"""
    if request.method == 'GET':
        # GET: Get user profile by username
        username = request.query_params.get('username')
        
        if not username:
            return Response({'error': 'Username parameter is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            user = User.objects.get(username=username)
            profile, created = UserProfile.objects.get_or_create(user=user)
            
            profile_image_url = None
            if profile.profile_image:
                profile_image_url = request.build_absolute_uri(profile.profile_image.url)
            
            return Response({
                'username': user.username,
                'email': user.email,
                'phone': profile.phone,
                'profile_image': profile_image_url
            }, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
    
    elif request.method == 'PUT':
        # PUT: Update user profile
        username = request.data.get('username')
        
        if not username:
            return Response({'error': 'Username is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            user = User.objects.get(username=username)
            profile, created = UserProfile.objects.get_or_create(user=user)
            
            # Update email if provided
            if 'email' in request.data:
                user.email = request.data['email']
                user.save()
            
            # Update phone if provided
            if 'phone' in request.data:
                profile.phone = request.data['phone']
                profile.save()
            
            profile_image_url = None
            if profile.profile_image:
                profile_image_url = request.build_absolute_uri(profile.profile_image.url)
            
            return Response({
                'username': user.username,
                'email': user.email,
                'phone': profile.phone,
                'profile_image': profile_image_url
            }, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
def upload_profile_image_view(request):
    """Upload profile image"""
    username = request.data.get('username')
    
    if not username:
        return Response({'error': 'Username is required'}, status=status.HTTP_400_BAD_REQUEST)
    
    if 'profile_image' not in request.FILES:
        return Response({'error': 'Profile image file is required'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        user = User.objects.get(username=username)
        profile, created = UserProfile.objects.get_or_create(user=user)
        
        # Delete old image if exists
        if profile.profile_image:
            old_image_path = profile.profile_image.path
            if os.path.exists(old_image_path):
                os.remove(old_image_path)
        
        # Save new image
        profile.profile_image = request.FILES['profile_image']
        profile.save()
        
        profile_image_url = request.build_absolute_uri(profile.profile_image.url)
        
        return Response({
            'message': 'Profile image uploaded successfully',
            'profile_image': profile_image_url
        }, status=status.HTTP_200_OK)
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Shiprocket Integration
# Token cache with expiration (cleared when credentials change)
token_cache = {"token": None, "expires_at": None}

def get_shiprocket_token():
    """
    Get Shiprocket access token from cache or generate new one
    Returns: (token, error_message) tuple
    """
    # Check if cached token is still valid
    if token_cache["token"] and token_cache["expires_at"] and token_cache["expires_at"] > datetime.now():
        print("Shiprocket: Using cached token")
        return token_cache["token"], None
    
    # Generate new token
    try:
        login_url = f"{settings.SHIPROCKET_API_BASE_URL}/auth/login"
        print(f"Shiprocket: Attempting login to {login_url}")
        
        response = requests.post(
            login_url,
            json={
                'email': settings.SHIPROCKET_EMAIL,
                'password': settings.SHIPROCKET_PASSWORD
            },
            headers={'Content-Type': 'application/json'},
            timeout=30  # Increased timeout to handle slow connections
        )
        
        print(f"Shiprocket: Login response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Shiprocket: Login response data: {data}")
            # Token might be in 'token' or 'data.token' field
            token = data.get('token')
            if token:
                # Cache token for 24 hours
                token_cache["token"] = token
                token_cache["expires_at"] = datetime.now() + timedelta(hours=24)
                print("Shiprocket: Token cached successfully")
                return token, None
            else:
                error_msg = f"No token in response. Response: {data}"
                print(f"Shiprocket login error: {error_msg}")
                return None, error_msg
        elif response.status_code == 400:
            # Handle blocked account or invalid credentials
            try:
                error_data = response.json()
                error_msg = error_data.get('message', 'Authentication failed')
                if 'blocked' in error_msg.lower() or 'too many' in error_msg.lower():
                    error_msg = f"Shiprocket account temporarily blocked: {error_msg}. Please wait 15-30 minutes or contact Shiprocket support."
            except:
                error_msg = f"Authentication failed: {response.text[:200]}"
            print(f"Shiprocket login error: {error_msg}")
            return None, error_msg
        elif response.status_code == 403:
            # Handle forbidden/access denied
            try:
                error_data = response.json()
                error_msg = error_data.get('message', error_data.get('error', 'Access forbidden'))
            except:
                error_msg = f"Access forbidden: {response.text[:200]}"
            full_error = f"Status 403: {error_msg}. This usually means: 1) Account lacks API permissions, 2) IP not whitelisted, 3) API access not enabled, or 4) Invalid credentials."
            print(f"Shiprocket login error: {full_error}")
            return None, full_error
        else:
            try:
                error_data = response.json()
                error_msg = f"Status {response.status_code}: {error_data.get('message', error_data.get('error', str(error_data)))}"
            except:
                error_msg = f"Status {response.status_code}: {response.text[:200]}"
            print(f"Shiprocket login error: {error_msg}")
            return None, error_msg
    except requests.exceptions.RequestException as e:
        error_msg = f"Network error: {str(e)}"
        print(f"Shiprocket login error: {error_msg}")
        return None, error_msg
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        print(f"Shiprocket login error: {error_msg}")
        return None, error_msg


@api_view(['OPTIONS', 'POST'])
def shipping_quote(request):
    """
    Get shipping quote from Shiprocket
    Expected body:
    {
        "weight": 1.0,  # in kg
        "pickup_pincode": "560001",
        "delivery_pincode": "629174",
        "cod": false  # boolean
    }
    """
    # Handle CORS preflight requests explicitly to avoid browser CORS/network errors
    if request.method == 'OPTIONS':
        return Response(status=status.HTTP_200_OK)

    try:
        weight = request.data.get('weight', 0.5)
        pickup_pincode = request.data.get('pickup_pincode', settings.SHIPROCKET_PICKUP_PINCODE)
        delivery_pincode = request.data.get('delivery_pincode')
        cod = request.data.get('cod', False)
        
        if not delivery_pincode:
            return Response({'error': 'Delivery pincode is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Get Shiprocket token
        token, auth_error = get_shiprocket_token()
        if not token:
            error_message = auth_error or 'Failed to authenticate with Shiprocket'
            print(f"Shipping quote failed: {error_message}")
            return Response({
                'error': 'Failed to authenticate with Shiprocket',
                'details': error_message
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        
        # Call Shiprocket serviceability API using GET method
        serviceability_url = f"{settings.SHIPROCKET_API_BASE_URL}/courier/serviceability/"
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        
        params = {
            'pickup_postcode': pickup_pincode,
            'delivery_postcode': delivery_pincode,
            'weight': weight,
            'cod': 1 if cod else 0
        }
        
        print(f"Shiprocket: Calling serviceability API with params: {params}")
        response = requests.get(serviceability_url, params=params, headers=headers, timeout=30)
        
        print(f"Shiprocket: Serviceability response status: {response.status_code}")
        print(f"Shiprocket: Serviceability response: {response.text[:500]}")
        
        if response.status_code == 200:
            data = response.json()
            available_couriers = data.get('data', {}).get('available_courier_companies', [])
            
            if available_couriers:
                # Choose cheapest courier
                best = min(available_couriers, key=lambda x: x.get('rate', float('inf')))
                
                result = {
                    'success': True,
                    'courier_name': best.get('courier_name', 'Standard'),
                    'courier_company_id': best.get('courier_company_id') or best.get('courier_id'),  # Store for courier assignment
                    'rate': best.get('rate', 0),
                    'estimated_days': best.get('estimated_delivery_days', best.get('etd', 'N/A')),
                    'expected_delivery_date': best.get('etd', 'N/A'),
                    'cod_available': best.get('cod', False),
                    'tracking': best.get('realtime_tracking', False),
                    'freight_charge': best.get('freight_charge', 0)
                }
                
                return Response(result, status=status.HTTP_200_OK)
            else:
                return Response({
                    'success': False,
                    'message': 'No courier service available for this pincode'
                }, status=status.HTTP_200_OK)
        elif response.status_code == 403:
            try:
                error_data = response.json()
                error_msg = error_data.get('message', error_data.get('error', 'Access forbidden'))
            except:
                error_msg = f"Access forbidden: {response.text[:200]}"
            print(f"Shiprocket serviceability error: {error_msg}")
            return Response({
                'error': 'Access forbidden by Shiprocket',
                'details': error_msg
            }, status=status.HTTP_403_FORBIDDEN)
        else:
            try:
                error_data = response.json()
                error_msg = error_data.get('message', error_data.get('error', 'Failed to get shipping quote'))
            except:
                error_msg = f'HTTP {response.status_code}: {response.text[:200]}'
            print(f"Shiprocket serviceability error: {error_msg}")
            return Response({'error': error_msg}, status=response.status_code)
            
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        print(f"Shipping quote exception: {error_msg}")
        return Response({'error': error_msg}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Keep old endpoint for backward compatibility
@api_view(['POST'])
def calculate_shipping_view(request):
    """
    Legacy endpoint - redirects to shipping_quote
    """
    return shipping_quote(request)


# Razorpay Integration
@api_view(['POST'])
def create_razorpay_order_view(request):
    """
    Create a Razorpay order
    Expected body:
    {
        "amount": 793.00  # in rupees
    }
    """
    try:
        amount = request.data.get('amount')
        
        if not amount:
            return Response({'error': 'Amount is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            amount_float = float(amount)
            if amount_float <= 0:
                return Response({'error': 'Amount must be greater than 0'}, status=status.HTTP_400_BAD_REQUEST)
        except (ValueError, TypeError):
            return Response({'error': 'Invalid amount format'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Convert to paise (Razorpay requires amount in smallest currency unit)
        amount_paise = int(amount_float * 100)
        
        # Initialize Razorpay client
        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        
        # Create order
        order_data = {
            'amount': amount_paise,
            'currency': 'INR',
            'payment_capture': 1  # Auto-capture payment
        }
        
        order = client.order.create(order_data)
        
        return Response({
            'order_id': order['id'],
            'amount': amount_float,
            'key': settings.RAZORPAY_KEY_ID
        }, status=status.HTTP_200_OK)
        
    except razorpay.errors.BadRequestError as e:
        error_msg = str(e)
        print(f"Razorpay BadRequest error: {error_msg}")
        return Response({'error': f'Razorpay error: {error_msg}'}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        error_msg = f"Failed to create Razorpay order: {str(e)}"
        print(f"Razorpay order creation error: {error_msg}")
        return Response({'error': error_msg}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def verify_payment_and_save_order_view(request):
    """
    Verify Razorpay payment signature and save order to database
    Expected body:
    {
        "razorpay_order_id": "order_xxx",
        "razorpay_payment_id": "pay_xxx",
        "razorpay_signature": "signature_xxx",
        "order_details": {
            "cart_items": [...],
            "subtotal": 648.00,
            "shipping_charge": 145.00,
            "discount": 0,
            "total": 793.00,
            "shipping_details": {...},
            "delivery_address": {...},
            "coupon_code": "DISCOUNT10" (optional)
        },
        "username": "user123"
    }
    """
    try:
        # Get payment details
        razorpay_order_id = request.data.get('razorpay_order_id')
        razorpay_payment_id = request.data.get('razorpay_payment_id')
        razorpay_signature = request.data.get('razorpay_signature')
        order_details = request.data.get('order_details', {})
        username = request.data.get('username')
        
        # Validate required fields
        if not all([razorpay_order_id, razorpay_payment_id, razorpay_signature, username]):
            return Response({'error': 'Missing required fields'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Get user
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Verify payment signature (manual verification) - matches Razorpay spec exactly
        def verify_payment_signature(order_id, payment_id, signature):
            body = f"{order_id}|{payment_id}"
            expected_signature = hmac.new(
                settings.RAZORPAY_SECRET.encode(),
                body.encode(),
                hashlib.sha256
            ).hexdigest()
            return expected_signature == signature
        
        if not verify_payment_signature(razorpay_order_id, razorpay_payment_id, razorpay_signature):
            return Response({'error': 'Payment signature verification failed'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Extract order details
        cart_items = order_details.get('cart_items', [])
        subtotal = float(order_details.get('subtotal', 0))
        shipping_charge = float(order_details.get('shipping_charge', 0))
        discount = float(order_details.get('discount', 0))
        total = float(order_details.get('total', 0))
        shipping_details = order_details.get('shipping_details', {})
        delivery_address = order_details.get('delivery_address', {})
        coupon_code = order_details.get('coupon_code', '')
        
        # Generate unique order number
        import time
        order_number = f"ORD{int(time.time())}{user.id}"
        
        # Helper function to calculate total weight from cart items
        def calculate_total_weight(items):
            """
            Calculate total weight in kg from cart items
            Parses weight from priceDisplay format like "₹1/100g", "₹299/1kg", or "₹70/1L"
            """
            total_weight_kg = 0.0
            
            for item in items:
                quantity = item.get('quantity', 1)
                price_display = item.get('priceDisplay', '') or item.get('price', '')
                
                # Parse format like "₹1/100g", "₹299/1kg", or "₹70/1L"
                try:
                    # Remove ₹ symbol and split by "/"
                    price_without_symbol = str(price_display).replace('₹', '').strip()
                    parts = price_without_symbol.split('/')
                    
                    if len(parts) >= 2:
                        weight_part = parts[1].strip().lower()
                        
                        # Extract numeric value and unit (kg, g, L)
                        weight_match = re.search(r'([\d.]+)\s*(kg|g|gm|grams?|l|litre|liters?)', weight_part)
                        
                        if weight_match:
                            weight_value = float(weight_match.group(1))
                            unit = weight_match.group(2).lower()
                            
                            # Convert to kg
                            if unit in ['g', 'gm', 'gram', 'grams']:
                                weight_kg = weight_value / 1000  # Convert grams to kg
                            elif unit in ['l', 'litre', 'liter', 'liters']:
                                # Convert litres to kg (1L ≈ 1kg for most liquids)
                                weight_kg = weight_value
                            else:  # kg
                                weight_kg = weight_value
                            
                            # Multiply by quantity and add to total
                            total_weight_kg += weight_kg * quantity
                            continue
                except Exception as e:
                    print(f"Error parsing weight from priceDisplay '{price_display}': {str(e)}")
                
                # Fallback: assume 0.5kg per item if parsing fails
                total_weight_kg += 0.5 * quantity
            
            # Ensure minimum weight of 0.5kg
            return max(0.5, total_weight_kg)
        
        # ========================================
        # CREATE SHIPROCKET ORDER
        # ========================================
        # get_shiprocket_token now returns (token, error_message)
        shiprocket_token, shiprocket_auth_error = get_shiprocket_token()
        awb_code = None
        courier_company = None
        tracking_url = None
        shipment_id = None
        sr_order_id = None
        pickup_scheduled = False
        pickup_status = None
        pickup_data = None
        
        # Only attempt Shiprocket order creation if we have a valid token
        if shiprocket_token:
            # Build Shiprocket order payload - matching exact format requirements
            calculated_weight = calculate_total_weight(cart_items)
            # Ensure minimum dimensions: length ≥ 10, breadth ≥ 10, height ≥ 1
            # Using 12 × 10 × 10 cm as specified for jaggery orders
            shiprocket_order_payload = {
                "order_id": razorpay_order_id,
                "order_date": date.today().strftime("%Y-%m-%d"),
                "pickup_location": "Home",
                "billing_customer_name": delivery_address.get('recipient', ''),
                "billing_last_name": "",
                "billing_address": delivery_address.get('line1', ''),
                "billing_address_2": "",
                "billing_city": delivery_address.get('city', ''),
                "billing_pincode": delivery_address.get('pincode', ''),
                "billing_state": delivery_address.get('state', ''),
                "billing_country": "India",
                "billing_email": user.email if user.email else delivery_address.get('phone', '') + '@temp.com',
                "billing_phone": delivery_address.get('phone', ''),
                "shipping_is_billing": True,
                "order_items": [
                    {
                        "name": item.get('name', ''),
                        "sku": f"PROD{item.get('id')}",
                        "units": item.get('quantity', 1),
                        "selling_price": float(item.get('price', 0)),
                        "discount": 0,
                        "tax": 0,
                        "hsn": "0409"  # HSN code for jaggery
                    }
                    for item in cart_items
                ],
                "payment_method": "Prepaid",
                "sub_total": subtotal,
                "length": 12,  # Minimum 10, using 12 for jaggery
                "breadth": 10,  # Minimum 10
                "height": 10,   # Minimum 1, using 10 for jaggery
                "weight": max(0.5, calculated_weight)  # Shiprocket minimum 0.5kg (500g slab)
            }
            
            if shipping_charge > 0:
                shiprocket_order_payload["shipping_charges"] = shipping_charge
            
            # Create Shiprocket order
            try:
                shiprocket_order_url = f"{settings.SHIPROCKET_API_BASE_URL}/orders/create/adhoc"
                shiprocket_headers = {"Authorization": f"Bearer {shiprocket_token}"}
                sr_response = requests.post(shiprocket_order_url, json=shiprocket_order_payload, headers=shiprocket_headers, timeout=30)
                
                if sr_response.status_code == 200:
                    sr_data = sr_response.json()
                    shipment_id = sr_data.get('shipment_id')
                    sr_order_id = sr_data.get('order_id')
                    
                    print(f"✅ Shiprocket order created successfully! Order ID: {sr_order_id}, Shipment ID: {shipment_id}")
                    
                    # Assign courier and get AWB (REQUIRED before pickup scheduling)
                    if shipment_id:
                        try:
                            assign_courier_url = f"{settings.SHIPROCKET_API_BASE_URL}/courier/assign/awb"
                            # Build courier assignment payload - include courier_company_id if available
                            courier_payload = {"shipment_id": shipment_id}
                            # If courier_company_id is available from shipping_details, include it for assignment
                            courier_company_id = shipping_details.get('courier_company_id')
                            if courier_company_id:
                                courier_payload["courier_company_id"] = courier_company_id
                            
                            print(f"Shiprocket: Assigning courier with payload: {courier_payload}")
                            courier_response = requests.post(assign_courier_url, json=courier_payload, headers=shiprocket_headers, timeout=30)
                            
                            print(f"Shiprocket: Courier assignment response status: {courier_response.status_code}")
                            print(f"Shiprocket: Courier assignment response: {courier_response.text[:500]}")
                            
                            if courier_response.status_code == 200:
                                courier_data = courier_response.json()
                                print(f"Shiprocket: Full courier assignment response: {json.dumps(courier_data, indent=2)}")
                                
                                # Try multiple possible paths for AWB code
                                awb_code = (
                                    courier_data.get('awb_code') or
                                    courier_data.get('response', {}).get('data', {}).get('awb_code') or
                                    courier_data.get('data', {}).get('awb_code') or
                                    courier_data.get('response', {}).get('awb_code')
                                )
                                
                                # Try multiple possible paths for courier company
                                courier_company = (
                                    courier_data.get('courier_name') or
                                    courier_data.get('response', {}).get('data', {}).get('courier_name') or
                                    courier_data.get('data', {}).get('courier_name') or
                                    courier_data.get('response', {}).get('courier_name')
                                )
                                
                                print(f"✅ Courier assigned successfully! AWB Code: {awb_code}, Courier: {courier_company}")
                                
                                # If AWB is still not found, try to get it from shipment details
                                if not awb_code and shipment_id:
                                    try:
                                        print(f"Shiprocket: AWB not in courier response, trying to fetch from shipment details...")
                                        shipment_details_url = f"{settings.SHIPROCKET_API_BASE_URL}/orders/show/{sr_order_id}"
                                        shipment_details_response = requests.get(shipment_details_url, headers=shiprocket_headers, timeout=30)
                                        if shipment_details_response.status_code == 200:
                                            shipment_details_data = shipment_details_response.json()
                                            print(f"Shiprocket: Shipment details response: {json.dumps(shipment_details_data, indent=2)}")
                                            # Try to extract AWB from shipment data
                                            if 'data' in shipment_details_data:
                                                shipments = shipment_details_data['data'].get('shipments', [])
                                                if shipments and len(shipments) > 0:
                                                    awb_code = shipments[0].get('awb_code') or shipments[0].get('awb')
                                                    print(f"Shiprocket: Extracted AWB from shipment details: {awb_code}")
                                    except Exception as e:
                                        print(f"Error fetching AWB from shipment details: {str(e)}")
                                
                                # Get tracking details (optional - for tracking URL)
                                if awb_code:
                                    try:
                                        tracking_url_api = f"{settings.SHIPROCKET_API_BASE_URL}/courier/track/awb/{awb_code}"
                                        tracking_response = requests.get(tracking_url_api, headers=shiprocket_headers, timeout=30)
                                        if tracking_response.status_code == 200:
                                            tracking_data = tracking_response.json()
                                            tracking_url = tracking_data.get('tracking_url') or tracking_data.get('track_url')
                                            print(f"Shiprocket: Tracking URL: {tracking_url}")
                                    except Exception as e:
                                        print(f"Error fetching tracking details: {str(e)}")
                                    
                                    # ========================================
                                    # 5️⃣ AUTO-SCHEDULE PICKUP (AFTER ORDER CREATION SUCCESS)
                                    # ========================================
                                    # This MUST happen after:
                                    # ✅ 1. Shiprocket order is created
                                    # ✅ 2. Courier is assigned
                                    # ✅ 3. AWB code is generated
                                    # This moves the order to "PICKUP SCHEDULED" status
                                    # and notifies the courier partner to collect the package
                                    # ========================================
                                    try:
                                        print(f"🚚 Shiprocket: Scheduling pickup for AWB: {awb_code}, Shipment ID: {shipment_id} (Order created successfully)")
                                        pickup_url = f"{settings.SHIPROCKET_API_BASE_URL}/courier/generate/pickup"
                                        pickup_address_id = getattr(settings, 'SHIPROCKET_PICKUP_ADDRESS_ID', 18928400)
                                        
                                        # Shiprocket API standard format: requires shipment_id as array
                                        pickup_payload = {
                                            "shipment_id": [shipment_id]  # Shiprocket expects array of shipment IDs
                                        }
                                        print(f"Shiprocket: Pickup payload (using shipment_id): {json.dumps(pickup_payload, indent=2)}")
                                        pickup_response = requests.post(pickup_url, json=pickup_payload, headers=shiprocket_headers, timeout=30)
                                        print(f"Shiprocket: Pickup scheduling response status: {pickup_response.status_code}")
                                        print(f"Shiprocket: Pickup scheduling response: {pickup_response.text}")
                                        
                                        # If first attempt fails, try alternative format with awb
                                        if pickup_response.status_code != 200:
                                            print(f"Shiprocket: First attempt failed, trying alternative format with awb...")
                                            pickup_payload_alt = {
                                                "awb": awb_code,
                                                "pickup_address_id": pickup_address_id
                                            }
                                            print(f"Shiprocket: Pickup payload (alternative - awb): {json.dumps(pickup_payload_alt, indent=2)}")
                                            pickup_response = requests.post(pickup_url, json=pickup_payload_alt, headers=shiprocket_headers, timeout=30)
                                            print(f"Shiprocket: Pickup scheduling response status (alternative): {pickup_response.status_code}")
                                            print(f"Shiprocket: Pickup scheduling response (alternative): {pickup_response.text}")
                                        
                                        if pickup_response.status_code == 200:
                                            pickup_response_data = pickup_response.json()
                                            pickup_scheduled = True
                                            pickup_status = pickup_response_data.get('status', 'scheduled')
                                            pickup_data = json.dumps(pickup_response_data)  # Store as JSON string
                                            print(f"✅✅✅ PICKUP SCHEDULED SUCCESSFULLY! ✅✅✅")
                                            print(f"   Order status in Shiprocket: 'PICKUP SCHEDULED'")
                                            print(f"   Courier partner will be notified to collect the package")
                                            print(f"   Shipment ID: {shipment_id}, AWB: {awb_code}")
                                        else:
                                            print(f"❌ Warning: Pickup scheduling failed with status {pickup_response.status_code}: {pickup_response.text[:200]}")
                                            pickup_status = f"Failed ({pickup_response.status_code})"
                                    except Exception as e:
                                        print(f"❌ Error scheduling pickup: {str(e)}")
                                        import traceback
                                        traceback.print_exc()
                                else:
                                    print("Warning: Courier assignment succeeded but no AWB code in response")
                            else:
                                print(f"Warning: Courier assignment failed with status {courier_response.status_code}: {courier_response.text[:200]}")
                        except Exception as e:
                            print(f"Error assigning courier: {str(e)}")
                            import traceback
                            traceback.print_exc()
                else:
                    print(f"Shiprocket order creation failed: {sr_response.text}")
            except Exception as e:
                print(f"Error creating Shiprocket order: {str(e)}")
        else:
            # Log Shiprocket auth error but DO NOT fail the whole order
            print(f"Skipping Shiprocket order creation, auth error: {shiprocket_auth_error}")
        
        # Create order
        order = Order.objects.create(
            user=user,
            order_number=order_number,
            razorpay_order_id=razorpay_order_id,
            razorpay_payment_id=razorpay_payment_id,
            razorpay_signature=razorpay_signature,
            subtotal=subtotal,
            shipping_charge=shipping_charge,
            discount=discount,
            total=total,
            shipping_courier=shipping_details.get('courier_name'),
            estimated_delivery_date=shipping_details.get('expected_delivery_date'),
            estimated_delivery_days=shipping_details.get('estimated_days'),
            delivery_name=delivery_address.get('recipient', ''),
            delivery_phone=delivery_address.get('phone', ''),
            delivery_address_line1=delivery_address.get('line1', ''),
            delivery_city=delivery_address.get('city', ''),
            delivery_state=delivery_address.get('state', ''),
            delivery_pincode=delivery_address.get('pincode', ''),
            coupon_code=coupon_code if coupon_code else None,
            status='paid',
            # Shiprocket fields
            shiprocket_order_id=sr_order_id,
            shipment_id=shipment_id,
            awb_code=awb_code,
            courier_company=courier_company,
            tracking_url=tracking_url,
            # Pickup scheduling fields
            pickup_scheduled=pickup_scheduled,
            pickup_status=pickup_status,
            pickup_data=pickup_data
        )
        
        # Create order items
        for item in cart_items:
            OrderItem.objects.create(
                order=order,
                product_id=item.get('id'),
                product_name=item.get('name', ''),
                product_image=item.get('image', ''),
                quantity=item.get('quantity', 1),
                price=float(item.get('price', 0)),
                total_price=float(item.get('price', 0)) * item.get('quantity', 1)
            )
        
        return Response({
            'success': True,
            'message': 'Order saved successfully',
            'order_number': order_number,
            'order_id': order.id,
            'shiprocket_order_id': sr_order_id,
            'shipment_id': shipment_id,
            'awb_code': awb_code,
            'courier_company': courier_company,
            'tracking_url': tracking_url
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        error_msg = f"Failed to save order: {str(e)}"
        print(f"Order save error: {error_msg}")
        return Response({'error': error_msg}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_user_orders_view(request):
    """
    Get all orders for a specific user
    Query params: username
    """
    try:
        username = request.query_params.get('username')
        
        print(f"Get orders request - username: {username}")
        
        if not username:
            return Response({'error': 'Username parameter is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            user = User.objects.get(username=username)
            print(f"User found: {user.username} (ID: {user.id})")
        except User.DoesNotExist:
            print(f"User not found: {username}")
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Get all orders for this user
        orders = Order.objects.filter(user=user).order_by('-created_at')
        print(f"Found {orders.count()} orders for user {username}")
        
        orders_data = []
        for order in orders:
            order_items = []
            for item in order.items.all():
                order_items.append({
                    'product_id': item.product_id,
                    'product_name': item.product_name,
                    'product_image': item.product_image,
                    'quantity': item.quantity,
                    'price': float(item.price),
                    'total_price': float(item.total_price)
                })
            
            orders_data.append({
                'order_id': order.id,
                'order_number': order.order_number,
                'razorpay_order_id': order.razorpay_order_id,
                'total': float(order.total),
                'subtotal': float(order.subtotal),
                'shipping_charge': float(order.shipping_charge),
                'discount': float(order.discount),
                'status': order.status,
                'courier_company': order.courier_company or order.shipping_courier,
                'awb_code': order.awb_code,
                'tracking_url': order.tracking_url,
                'estimated_delivery_date': order.estimated_delivery_date,
                'estimated_delivery_days': order.estimated_delivery_days,
                'shipment_id': order.shipment_id,
                'shiprocket_order_id': order.shiprocket_order_id,
                'delivery_address': {
                    'name': order.delivery_name,
                    'phone': order.delivery_phone,
                    'address': order.delivery_address_line1,
                    'city': order.delivery_city,
                    'state': order.delivery_state,
                    'pincode': order.delivery_pincode
                },
                'items': order_items,
                'created_at': order.created_at.isoformat(),
                'coupon_code': order.coupon_code
            })
        
        return Response({
            'success': True,
            'orders': orders_data,
            'count': len(orders_data)
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        error_msg = f"Failed to fetch orders: {str(e)}"
        print(f"Get orders error: {error_msg}")
        return Response({'error': error_msg}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_order_tracking_view(request, order_id):
    """
    Get real-time tracking status from Shiprocket for a specific order
    """
    try:
        print(f"Tracking request received for order ID: {order_id}")
        # Get order
        try:
            order = Order.objects.get(id=order_id)
            print(f"Order found: {order.order_number}, AWB: {order.awb_code}, Status: {order.status}")
        except Order.DoesNotExist:
            print(f"Order {order_id} not found")
            return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Get Shiprocket token first (we need it to fetch AWB if missing)
        shiprocket_token, auth_error = get_shiprocket_token()
        if not shiprocket_token:
            return Response({
                'success': False,
                'error': 'Failed to authenticate with Shiprocket',
                'details': auth_error
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        
        # If no AWB code, try to get it from shipment ID using Shiprocket API
        awb_to_use = order.awb_code
        if not awb_to_use and order.shipment_id:
            print(f"No AWB code found, trying to get shipment details for shipment_id: {order.shipment_id}")
            try:
                # Try to get shipment details to retrieve AWB
                shipment_url = f"{settings.SHIPROCKET_API_BASE_URL}/orders/show/{order.shiprocket_order_id}"
                shiprocket_headers = {"Authorization": f"Bearer {shiprocket_token}"}
                shipment_response = requests.get(shipment_url, headers=shiprocket_headers, timeout=30)
                if shipment_response.status_code == 200:
                    shipment_data = shipment_response.json()
                    # Try to extract AWB from shipment data
                    if 'data' in shipment_data:
                        shipments = shipment_data['data'].get('shipments', [])
                        if shipments and len(shipments) > 0:
                            awb_to_use = shipments[0].get('awb_code')
                            if awb_to_use:
                                print(f"Found AWB code from shipment details: {awb_to_use}")
                                order.awb_code = awb_to_use
                                order.save()
            except Exception as e:
                print(f"Error fetching shipment details: {str(e)}")
        
        # Check if we have AWB code now
        if not awb_to_use:
            print(f"Tracking request for order {order_id}: No AWB code found after trying to fetch")
            return Response({
                'success': False,
                'error': 'Tracking information not available yet',
                'message': 'AWB code not available. Courier may not have been assigned yet.',
                'order_status': order.status,
                'has_shiprocket_order_id': bool(order.shiprocket_order_id),
                'has_shipment_id': bool(order.shipment_id)
            }, status=status.HTTP_200_OK)  # Return 200 with success:false instead of 400
        
        # Fetch tracking details from Shiprocket using the AWB we found (or existing one)
        try:
            tracking_url_api = f"{settings.SHIPROCKET_API_BASE_URL}/courier/track/awb/{awb_to_use}"
            shiprocket_headers = {"Authorization": f"Bearer {shiprocket_token}"}
            print(f"Fetching tracking from Shiprocket for AWB: {awb_to_use}")
            tracking_response = requests.get(tracking_url_api, headers=shiprocket_headers, timeout=30)
            print(f"Shiprocket tracking response status: {tracking_response.status_code}")
            
            if tracking_response.status_code == 200:
                tracking_data = tracking_response.json()
                tracking_info_data = tracking_data.get('tracking_data', {})
                
                # Extract tracking information
                current_status = tracking_info_data.get('current_status', '')
                status_code = tracking_info_data.get('status_code', '')
                
                # Map Shiprocket status to our status system
                status_mapping = {
                    'ORDER_PLACED': 'Pending',
                    'CONFIRMED': 'Confirmed',
                    'PICKED_UP': 'Processing',
                    'IN_TRANSIT': 'Shipped',
                    'OUT_FOR_DELIVERY': 'Out for Delivery',
                    'DELIVERED': 'Delivered',
                    'CANCELLED': 'Cancelled',
                }
                
                # Find matching status
                mapped_status = None
                for key, value in status_mapping.items():
                    if key in current_status.upper() or key in str(status_code).upper():
                        mapped_status = value
                        break
                
                tracking_info = {
                    'awb_code': awb_to_use or order.awb_code,
                    'current_status': current_status,
                    'status_code': status_code,
                    'status': tracking_info_data.get('status', ''),
                    'estimated_delivery_date': tracking_info_data.get('etd', '') or order.estimated_delivery_date,
                    'tracking_url': tracking_info_data.get('track_url') or order.tracking_url,
                    'shipment_track': tracking_info_data.get('shipment_track', []),
                    'shipment_track_activities': tracking_info_data.get('shipment_track_activities', []),
                    'mapped_status': mapped_status or order.status,
                }
                
                # Update order status if different (optional - you may want to keep this)
                if mapped_status and order.status != mapped_status.lower():
                    # Only update if the new status is more advanced
                    status_order = ['pending', 'paid', 'processing', 'shipped', 'delivered']
                    current_index = status_order.index(order.status) if order.status in status_order else 0
                    new_index = status_order.index(mapped_status.lower()) if mapped_status.lower() in status_order else current_index
                    
                    if new_index > current_index:
                        order.status = mapped_status.lower()
                        order.save()
                        tracking_info['status_updated'] = True
                
                return Response({
                    'success': True,
                    'tracking': tracking_info,
                    'order_status': order.status
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'success': False,
                    'error': 'Failed to fetch tracking from Shiprocket',
                    'details': tracking_response.text[:200]
                }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except requests.exceptions.RequestException as e:
            return Response({
                'success': False,
                'error': 'Network error while fetching tracking',
                'details': str(e)
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except Exception as e:
        error_msg = f"Failed to fetch tracking: {str(e)}"
        print(f"Tracking fetch error: {error_msg}")
        return Response({'success': False, 'error': error_msg}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def send_whatsapp_cancellation_notification(order):
    """
    Send WhatsApp notification to admin when an order is cancelled
    Includes all order details and order ID
    """
    try:
        admin_number = getattr(settings, 'WHATSAPP_ADMIN_NUMBER', '7996029992')
        
        # Build order items list
        order_items_list = []
        for item in order.items.all():
            order_items_list.append(f"  • {item.product_name} (Qty: {item.quantity}) - ₹{float(item.price):.2f}")
        order_items_text = "\n".join(order_items_list) if order_items_list else "  No items found"
        
        # Format cancellation message with all order details
        message = f"""🚫 *ORDER CANCELLATION ALERT*

*Order Information:*
Order Number: {order.order_number}
Order ID: {order.id}

*Customer Details:*
Name: {order.delivery_name}
Phone: {order.delivery_phone}
Email: {order.user.email if order.user.email else 'N/A'}
Username: {order.user.username}

*Order Items:*
{order_items_text}

*Order Summary:*
Subtotal: ₹{float(order.subtotal):.2f}
Shipping Charge: ₹{float(order.shipping_charge):.2f}
Discount: ₹{float(order.discount):.2f}
*Total: ₹{float(order.total):.2f}*

*Delivery Address:*
{order.delivery_address_line1}
{order.delivery_city}, {order.delivery_state} - {order.delivery_pincode}

*Payment & Shipping Info:*
Payment ID: {order.razorpay_payment_id or 'N/A'}
Shiprocket Order ID: {order.shiprocket_order_id or 'N/A'}
AWB Code: {order.awb_code or 'N/A'}
Courier: {order.courier_company or 'N/A'}
Status: {order.status}
Coupon Code: {order.coupon_code or 'None'}

*Cancellation Time:*
{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        # For actual WhatsApp sending, you can use:
        # 1. Twilio WhatsApp API (recommended for production)
        # 2. WhatsApp Business API
        # 3. WhatsApp API gateway services
        
        # Currently, we'll log the message and create a clickable URL
        # You can integrate with your preferred WhatsApp service
        
        # Check which WhatsApp service to use
        whatsapp_business_enabled = getattr(settings, 'WHATSAPP_BUSINESS_API_ENABLED', False)
        whatsapp_phone_number_id = getattr(settings, 'WHATSAPP_PHONE_NUMBER_ID', '')
        whatsapp_access_token = getattr(settings, 'WHATSAPP_ACCESS_TOKEN', '')
        whatsapp_api_version = getattr(settings, 'WHATSAPP_API_VERSION', 'v18.0')
        
        twilio_account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
        twilio_auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
        twilio_whatsapp_from = getattr(settings, 'TWILIO_WHATSAPP_FROM', 'whatsapp:+14155238886')
        
        whatsapp_url = f"https://wa.me/91{admin_number}?text={requests.utils.quote(message)}"
        
        # Option 1: Try WhatsApp Business API (Meta/Facebook) if enabled
        if whatsapp_business_enabled and whatsapp_phone_number_id and whatsapp_access_token:
            try:
                whatsapp_business_url = f"https://graph.facebook.com/{whatsapp_api_version}/{whatsapp_phone_number_id}/messages"
                whatsapp_headers = {
                    'Authorization': f'Bearer {whatsapp_access_token}',
                    'Content-Type': 'application/json'
                }
                whatsapp_payload = {
                    'messaging_product': 'whatsapp',
                    'to': f'91{admin_number}',
                    'type': 'text',
                    'text': {
                        'body': message
                    }
                }
                
                print(f"\n{'='*60}")
                print(f"📱 SENDING WHATSAPP NOTIFICATION VIA WHATSAPP BUSINESS API")
                print(f"{'='*60}")
                print(f"API URL: {whatsapp_business_url}")
                print(f"To: +91{admin_number}")
                print(f"Order: {order.order_number}")
                
                whatsapp_response = requests.post(
                    whatsapp_business_url,
                    headers=whatsapp_headers,
                    json=whatsapp_payload,
                    timeout=30
                )
                
                if whatsapp_response.status_code == 200:
                    response_data = whatsapp_response.json()
                    print(f"✅ WhatsApp message sent successfully via Business API!")
                    print(f"   Message ID: {response_data.get('messages', [{}])[0].get('id', 'N/A')}")
                    print(f"{'='*60}\n")
                else:
                    error_data = whatsapp_response.json() if whatsapp_response.text else {}
                    print(f"❌ WhatsApp Business API error: {whatsapp_response.status_code}")
                    print(f"   Error: {error_data}")
                    print(f"   Falling back to URL generation...")
                    print(f"   WhatsApp URL: {whatsapp_url}")
                    print(f"{'='*60}\n")
                    
            except Exception as whatsapp_api_error:
                print(f"⚠️  WhatsApp Business API error: {str(whatsapp_api_error)}")
                print(f"   Falling back to URL generation...")
                print(f"   WhatsApp URL: {whatsapp_url}")
        
        # Option 2: Try Twilio WhatsApp API if credentials are configured and Business API is not enabled
        elif not whatsapp_business_enabled and twilio_account_sid and twilio_auth_token:
            try:
                from twilio.rest import Client
                
                twilio_client = Client(twilio_account_sid, twilio_auth_token)
                whatsapp_to = f'whatsapp:+91{admin_number}'
                
                print(f"\n{'='*60}")
                print(f"📱 SENDING WHATSAPP NOTIFICATION VIA TWILIO")
                print(f"{'='*60}")
                print(f"From: {twilio_whatsapp_from}")
                print(f"To: {whatsapp_to}")
                print(f"Order: {order.order_number}")
                
                # Check if Content Template SID is provided (for templated messages)
                twilio_content_sid = getattr(settings, 'TWILIO_CONTENT_SID', '')
                
                if twilio_content_sid:
                    # Use Content Template with variables
                    # Format content_variables as JSON string for template placeholders
                    content_variables_json = json.dumps({
                        "1": order.order_number,
                        "2": f"₹{float(order.total):.2f}",
                        "3": order.delivery_name,
                        "4": order.delivery_phone,
                        # Add more variables as needed based on your template
                    })
                    
                    print(f"Using Content Template: {twilio_content_sid}")
                    
                    twilio_message = twilio_client.messages.create(
                        from_=twilio_whatsapp_from,
                        content_sid=twilio_content_sid,
                        content_variables=content_variables_json,
                        to=whatsapp_to
                    )
                else:
                    # Use plain text message with all order details
                    print(f"Using plain text message")
                    twilio_message = twilio_client.messages.create(
                        from_=twilio_whatsapp_from,
                        body=message,
                        to=whatsapp_to
                    )
                
                print(f"✅ WhatsApp message sent successfully via Twilio!")
                print(f"   Message SID: {twilio_message.sid}")
                print(f"   Status: {twilio_message.status}")
                print(f"{'='*60}\n")
                
            except ImportError as import_err:
                error_msg = f"⚠️  Twilio package not installed. Install it with: pip install twilio"
                print(error_msg)
                print(f"   Import Error Details: {str(import_err)}")
                print(f"   Falling back to URL generation...")
                print(f"   WhatsApp URL: {whatsapp_url}")
                # Re-raise so it's visible in logs
                raise Exception(f"Twilio not installed: {str(import_err)}")
            except Exception as twilio_error:
                error_msg = f"⚠️  Twilio API error: {str(twilio_error)}"
                print(error_msg)
                print(f"   Error Type: {type(twilio_error).__name__}")
                import traceback
                print(f"   Traceback: {traceback.format_exc()}")
                print(f"   Falling back to URL generation...")
                print(f"   WhatsApp URL: {whatsapp_url}")
                # Re-raise so caller knows it failed
                raise Exception(f"Twilio API error: {str(twilio_error)}")
        else:
            # No WhatsApp API configured, fallback to URL
            print(f"\n{'='*60}")
            print(f"📱 WHATSAPP CANCELLATION NOTIFICATION")
            print(f"{'='*60}")
            print(f"⚠️  WhatsApp API not configured in settings.py")
            print(f"\nTo enable automatic sending, choose one:")
            print(f"\nOption 1 - WhatsApp Business API (Meta):")
            print(f"   - WHATSAPP_BUSINESS_API_ENABLED = True")
            print(f"   - WHATSAPP_PHONE_NUMBER_ID = 'your_phone_number_id'")
            print(f"   - WHATSAPP_ACCESS_TOKEN = 'your_access_token'")
            print(f"\nOption 2 - Twilio WhatsApp API:")
            print(f"   - TWILIO_ACCOUNT_SID = 'your_account_sid'")
            print(f"   - TWILIO_AUTH_TOKEN = 'your_auth_token'")
            print(f"   - TWILIO_WHATSAPP_FROM = 'whatsapp:+14155238886' (optional)")
            print(f"\nTo: +91{admin_number}")
            print(f"Order: {order.order_number}")
            print(f"\nWhatsApp URL (manual send): {whatsapp_url}")
            print(f"{'='*60}\n")
        
    except Exception as e:
        error_msg = f"Failed to send WhatsApp notification: {str(e)}"
        print(f"❌ {error_msg}")
        import traceback
        traceback.print_exc()
        raise


@api_view(['GET', 'POST'])
def products_view(request):
    """
    GET: List all products
    POST: Create a new product
    """
    if request.method == 'GET':
        products = Product.objects.all()
        products_data = []
        for product in products:
            products_data.append({
                'id': product.id,
                'name': product.name,
                'description': product.description,
                'price': product.price,
                'image': product.image,
                'category': product.category,
                'weight_value': float(product.weight_value) if product.weight_value else None,
                'weight_unit': product.weight_unit,
                'created_at': product.created_at.isoformat() if product.created_at else None,
            })
        return Response({'products': products_data}, status=status.HTTP_200_OK)
    
    elif request.method == 'POST':
        data = request.data
        name = data.get('name')
        description = data.get('description')
        price = data.get('price')
        image = data.get('image')
        category = data.get('category')
        weight_value = data.get('weight_value')
        weight_unit = data.get('weight_unit', 'kg')
        
        if not all([name, description, price, image, category]):
            return Response({'error': 'Missing required fields'}, status=status.HTTP_400_BAD_REQUEST)
        
        product = Product.objects.create(
            name=name,
            description=description,
            price=price,
            image=image,
            category=category,
            weight_value=weight_value,
            weight_unit=weight_unit,
        )
        
        return Response({
            'id': product.id,
            'name': product.name,
            'description': product.description,
            'price': product.price,
            'image': product.image,
            'category': product.category,
            'weight_value': float(product.weight_value) if product.weight_value else None,
            'weight_unit': product.weight_unit,
            'created_at': product.created_at.isoformat() if product.created_at else None,
        }, status=status.HTTP_201_CREATED)


def calculate_price_for_weight(base_price_str, selected_weight_value, selected_weight_unit):
    """
    Calculate price for a selected weight based on base price.
    
    Args:
        base_price_str: Base price string like "399/kg" or "₹399/kg"
        selected_weight_value: Selected weight value (e.g., 0.5 for 500g)
        selected_weight_unit: Selected weight unit ('kg', 'g', 'L')
    
    Returns:
        dict with 'price', 'priceDisplay', 'weight_value', 'weight_unit'
    """
    try:
        # Remove currency symbols and whitespace
        price_clean = str(base_price_str).replace('₹', '').replace('Rs', '').replace('rs', '').strip()
        
        # Split by "/" to get price and base weight
        parts = price_clean.split('/')
        if len(parts) < 2:
            # If no "/" found, assume price per kg
            base_price = float(price_clean)
            base_weight_value = 1.0
            base_weight_unit = 'kg'
        else:
            base_price = float(parts[0].strip())
            weight_part = parts[1].strip().lower()
            
            # Extract base weight value and unit
            weight_match = re.search(r'([\d.]+)\s*(kg|g|gm|grams?|l|litre|liters?)', weight_part)
            if weight_match:
                base_weight_value = float(weight_match.group(1))
                base_weight_unit = weight_match.group(2).lower()
                # Normalize unit
                if base_weight_unit in ['g', 'gm', 'gram', 'grams']:
                    base_weight_unit = 'g'
                elif base_weight_unit in ['l', 'litre', 'liter', 'liters']:
                    base_weight_unit = 'L'
                else:
                    base_weight_unit = 'kg'
            else:
                # Default to 1kg if can't parse
                base_weight_value = 1.0
                base_weight_unit = 'kg'
        
        # Convert base weight to kg for calculation
        if base_weight_unit == 'g':
            base_weight_kg = base_weight_value / 1000
        elif base_weight_unit == 'L':
            base_weight_kg = base_weight_value  # 1L ≈ 1kg
        else:  # kg
            base_weight_kg = base_weight_value
        
        # Convert selected weight to kg
        if selected_weight_unit == 'g':
            selected_weight_kg = selected_weight_value / 1000
        elif selected_weight_unit == 'L':
            selected_weight_kg = selected_weight_value
        else:  # kg
            selected_weight_kg = selected_weight_value
        
        # Calculate price per kg first
        price_per_kg = base_price / base_weight_kg
        
        # Calculate price for selected weight
        calculated_price = price_per_kg * selected_weight_kg
        
        # Format price display
        if selected_weight_unit == 'g':
            price_display = f"₹{calculated_price:.2f}/{int(selected_weight_value)}g"
        elif selected_weight_unit == 'L':
            price_display = f"₹{calculated_price:.2f}/{selected_weight_value}L"
        else:  # kg
            if selected_weight_value == 1.0:
                price_display = f"₹{calculated_price:.2f}/1kg"
            else:
                price_display = f"₹{calculated_price:.2f}/{selected_weight_value}kg"
        
        return {
            'price': round(calculated_price, 2),
            'priceDisplay': price_display,
            'weight_value': selected_weight_value,
            'weight_unit': selected_weight_unit
        }
    except Exception as e:
        print(f"Error calculating price: {str(e)}")
        # Return original price as fallback
        return {
            'price': 0.0,
            'priceDisplay': base_price_str,
            'weight_value': selected_weight_value,
            'weight_unit': selected_weight_unit
        }


@api_view(['GET', 'PUT', 'DELETE'])
def product_detail_view(request, product_id):
    """
    GET: Get product details, optionally with calculated price for selected weight
    Query params: weight_value (float), weight_unit ('kg', 'g', 'L')
    PUT: Update a product
    DELETE: Delete a product
    """
    try:
        product = Product.objects.get(id=product_id)
    except Product.DoesNotExist:
        return Response({'error': 'Product not found'}, status=status.HTTP_404_NOT_FOUND)
    
    if request.method == 'GET':
        # Get base product data
        product_data = {
            'id': product.id,
            'name': product.name,
            'description': product.description,
            'price': product.price,
            'image': product.image,
            'category': product.category,
            'weight_value': float(product.weight_value) if product.weight_value else None,
            'weight_unit': product.weight_unit,
            'created_at': product.created_at.isoformat() if product.created_at else None,
        }
        
        # If weight selection is provided, calculate price
        selected_weight_value = request.query_params.get('weight_value')
        selected_weight_unit = request.query_params.get('weight_unit', 'kg')
        
        if selected_weight_value:
            try:
                selected_weight_value = float(selected_weight_value)
                calculated = calculate_price_for_weight(
                    product.price,
                    selected_weight_value,
                    selected_weight_unit
                )
                # Update the main price field to show calculated price
                product_data['price'] = calculated['priceDisplay']
                # Also keep original price for reference
                product_data['original_price'] = product.price
                # Add calculated price info
                product_data['calculated_price'] = calculated['price']
                product_data['calculated_priceDisplay'] = calculated['priceDisplay']
                product_data['selected_weight_value'] = calculated['weight_value']
                product_data['selected_weight_unit'] = calculated['weight_unit']
            except ValueError:
                pass  # Invalid weight_value, return base product data
        
        return Response(product_data, status=status.HTTP_200_OK)
    
    elif request.method == 'PUT':
        data = request.data
        product.name = data.get('name', product.name)
        product.description = data.get('description', product.description)
        product.price = data.get('price', product.price)
        product.image = data.get('image', product.image)
        product.category = data.get('category', product.category)
        if 'weight_value' in data:
            product.weight_value = data.get('weight_value')
        if 'weight_unit' in data:
            product.weight_unit = data.get('weight_unit', product.weight_unit)
        product.save()
        
        return Response({
            'id': product.id,
            'name': product.name,
            'description': product.description,
            'price': product.price,
            'image': product.image,
            'category': product.category,
            'weight_value': float(product.weight_value) if product.weight_value else None,
            'weight_unit': product.weight_unit,
            'created_at': product.created_at.isoformat() if product.created_at else None,
        }, status=status.HTTP_200_OK)
    
    elif request.method == 'DELETE':
        product.delete()
        return Response({'message': 'Product deleted successfully'}, status=status.HTTP_200_OK)


@api_view(['POST'])
def cancel_order_view(request, order_id):
    """
    Cancel an order - cancels in Shiprocket and updates database
    """
    try:
        print(f"Cancel order request for order ID: {order_id}")
        
        # Get order from database
        try:
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            return Response({'success': False, 'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Check if order can be cancelled (not already shipped/delivered)
        if order.status in ['shipped', 'delivered', 'cancelled']:
            return Response({
                'success': False,
                'error': f'Order cannot be cancelled. Current status: {order.status}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Cancel in Shiprocket if order has Shiprocket order ID
        if order.shiprocket_order_id:
            try:
                # Get Shiprocket token
                shiprocket_token, auth_error = get_shiprocket_token()
                if not shiprocket_token:
                    return Response({
                        'success': False,
                        'error': 'Failed to authenticate with Shiprocket',
                        'details': auth_error
                    }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
                
                # Cancel order in Shiprocket
                cancel_url = f"{settings.SHIPROCKET_API_BASE_URL}/orders/cancel"
                cancel_payload = {
                    "ids": [int(order.shiprocket_order_id)]  # Shiprocket expects array of order IDs
                }
                headers = {"Authorization": f"Bearer {shiprocket_token}"}
                
                print(f"Shiprocket: Cancelling order {order.shiprocket_order_id} in Shiprocket")
                print(f"Shiprocket: Cancel payload: {json.dumps(cancel_payload, indent=2)}")
                
                cancel_response = requests.post(cancel_url, json=cancel_payload, headers=headers, timeout=30)
                print(f"Shiprocket: Cancel response status: {cancel_response.status_code}")
                print(f"Shiprocket: Cancel response: {cancel_response.text}")
                
                if cancel_response.status_code == 200:
                    cancel_data = cancel_response.json()
                    print(f"✅ Order cancelled successfully in Shiprocket: {cancel_data}")
                    
                    # Update order status in database
                    order.status = 'cancelled'
                    order.save()
                    
                    # Send WhatsApp notification to admin
                    try:
                        print(f"\n📱 Attempting to send WhatsApp notification for order {order.order_number}...")
                        send_whatsapp_cancellation_notification(order)
                        print(f"✅ WhatsApp notification sent successfully\n")
                    except Exception as whatsapp_error:
                        error_details = f"❌ Failed to send WhatsApp notification: {str(whatsapp_error)}"
                        print(error_details)
                        import traceback
                        print(f"   Traceback: {traceback.format_exc()}")
                        # Don't fail the cancellation if WhatsApp fails, but log it clearly
                    
                    return Response({
                        'success': True,
                        'message': 'Order cancelled successfully in Shiprocket',
                        'order_id': order.id,
                        'order_number': order.order_number,
                        'shiprocket_response': cancel_data
                    }, status=status.HTTP_200_OK)
                else:
                    # Even if Shiprocket cancellation fails, update database if order status allows
                    error_msg = cancel_response.text[:200]
                    print(f"❌ Warning: Shiprocket cancellation failed: {error_msg}")
                    
                    # Check if order can still be cancelled in our system
                    if order.status not in ['shipped', 'delivered']:
                        order.status = 'cancelled'
                        order.save()
                        return Response({
                            'success': True,
                            'message': 'Order cancelled in database. Shiprocket cancellation failed.',
                            'warning': error_msg,
                            'order_id': order.id
                        }, status=status.HTTP_200_OK)
                    else:
                        return Response({
                            'success': False,
                            'error': f'Shiprocket cancellation failed: {error_msg}'
                        }, status=status.HTTP_400_BAD_REQUEST)
                    
            except Exception as e:
                print(f"Error cancelling order in Shiprocket: {str(e)}")
                import traceback
                traceback.print_exc()
                # Update database even if Shiprocket fails
                if order.status not in ['shipped', 'delivered']:
                    order.status = 'cancelled'
                    order.save()
                    
                    # Send WhatsApp notification to admin
                    try:
                        send_whatsapp_cancellation_notification(order)
                    except Exception as whatsapp_error:
                        print(f"Warning: Failed to send WhatsApp notification: {str(whatsapp_error)}")
                    
                    return Response({
                        'success': True,
                        'message': 'Order cancelled in database. Shiprocket cancellation error occurred.',
                        'warning': str(e),
                        'order_id': order.id
                    }, status=status.HTTP_200_OK)
                else:
                    return Response({
                        'success': False,
                        'error': f'Failed to cancel order in Shiprocket: {str(e)}'
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            # Order doesn't have Shiprocket order ID, just update database
            order.status = 'cancelled'
            order.save()
            
            # Send WhatsApp notification to admin
            try:
                print(f"\n📱 Attempting to send WhatsApp notification for order {order.order_number}...")
                send_whatsapp_cancellation_notification(order)
                print(f"✅ WhatsApp notification sent successfully\n")
            except Exception as whatsapp_error:
                error_details = f"❌ Failed to send WhatsApp notification: {str(whatsapp_error)}"
                print(error_details)
                import traceback
                print(f"   Traceback: {traceback.format_exc()}")
            
            return Response({
                'success': True,
                'message': 'Order cancelled in database (no Shiprocket order)',
                'order_id': order.id
            }, status=status.HTTP_200_OK)
            
    except Exception as e:
        error_msg = f"Failed to cancel order: {str(e)}"
        print(f"Cancel order error: {error_msg}")
        import traceback
        traceback.print_exc()
        return Response({'success': False, 'error': error_msg}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
#
