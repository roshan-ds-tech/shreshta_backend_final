"""
Management command to retroactively schedule pickups for orders that have AWB codes in Shiprocket
but haven't been scheduled for pickup yet.
"""
from django.core.management.base import BaseCommand
from accounts.models import Order
from django.conf import settings
import requests
import json
from accounts.views import get_shiprocket_token


class Command(BaseCommand):
    help = 'Schedule pickups for orders that have AWB codes but pickup not scheduled'

    def handle(self, *args, **options):
        # Get orders that have shipment_id but no AWB code or pickup not scheduled
        orders = Order.objects.filter(
            shipment_id__isnull=False,
            status='paid'
        ).exclude(
            pickup_scheduled=True
        )
        
        self.stdout.write(f"Found {orders.count()} orders to check for pickup scheduling")
        
        # Get Shiprocket token
        token, auth_error = get_shiprocket_token()
        if not token:
            self.stdout.write(self.style.ERROR(f"Failed to authenticate with Shiprocket: {auth_error}"))
            return
        
        headers = {"Authorization": f"Bearer {token}"}
        pickup_address_id = getattr(settings, 'SHIPROCKET_PICKUP_ADDRESS_ID', 18928400)
        
        for order in orders:
            try:
                # Try to get AWB code from Shiprocket
                if not order.awb_code and order.shiprocket_order_id:
                    # Fetch order details from Shiprocket
                    order_details_url = f"{settings.SHIPROCKET_API_BASE_URL}/orders/show/{order.shiprocket_order_id}"
                    response = requests.get(order_details_url, headers=headers, timeout=30)
                    
                    if response.status_code == 200:
                        data = response.json()
                        if 'data' in data:
                            shipments = data['data'].get('shipments', [])
                            if shipments and len(shipments) > 0:
                                awb_code = shipments[0].get('awb_code') or shipments[0].get('awb')
                                if awb_code:
                                    order.awb_code = awb_code
                                    order.save()
                                    self.stdout.write(f"Updated AWB for order {order.order_number}: {awb_code}")
                
                # Schedule pickup if we have AWB code
                if order.awb_code:
                    pickup_url = f"{settings.SHIPROCKET_API_BASE_URL}/courier/generate/pickup"
                    pickup_payload = {
                        "awb": order.awb_code,
                        "pickup_address_id": pickup_address_id
                    }
                    
                    pickup_response = requests.post(pickup_url, json=pickup_payload, headers=headers, timeout=30)
                    
                    if pickup_response.status_code == 200:
                        pickup_data = pickup_response.json()
                        order.pickup_scheduled = True
                        order.pickup_status = pickup_data.get('status', 'scheduled')
                        order.pickup_data = json.dumps(pickup_data)
                        order.save()
                        self.stdout.write(
                            self.style.SUCCESS(f"✅ Scheduled pickup for order {order.order_number} (AWB: {order.awb_code})")
                        )
                    else:
                        self.stdout.write(
                            self.style.WARNING(f"❌ Failed to schedule pickup for order {order.order_number}: {pickup_response.text[:200]}")
                        )
                else:
                    self.stdout.write(
                        self.style.WARNING(f"⚠️  Order {order.order_number} has no AWB code, skipping")
                    )
                    
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"Error processing order {order.order_number}: {str(e)}")
                )

