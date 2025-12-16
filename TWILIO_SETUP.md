# Twilio WhatsApp Setup Guide

## Step 1: Install Twilio Package

```bash
pip install twilio
```

Or if you have a requirements.txt:
```bash
pip install -r requirements.txt
```

## Step 2: Get Twilio Account Credentials

1. Sign up for a Twilio account at https://www.twilio.com/try-twilio
2. Go to the Twilio Console: https://console.twilio.com
3. You'll find your **Account SID** and **Auth Token** on the dashboard

## Step 3: Set Up WhatsApp Sandbox (for testing)

1. Go to https://console.twilio.com/us1/develop/sms/try-it-out/whatsapp-learn
2. Follow the instructions to join the WhatsApp Sandbox
3. The default sandbox number is: `whatsapp:+14155238886`
4. You'll need to send a message with the join code to activate

## Step 4: Configure Settings

Edit `firstbackend/settings.py` and add your Twilio credentials:

```python
# WhatsApp Configuration (Twilio)
WHATSAPP_ADMIN_NUMBER = '7996029992'  # Your admin WhatsApp number
TWILIO_ACCOUNT_SID = 'your_account_sid_here'  # From Twilio Console
TWILIO_AUTH_TOKEN = 'your_auth_token_here'  # From Twilio Console
TWILIO_WHATSAPP_FROM = 'whatsapp:+14155238886'  # Sandbox number (default)
```

## Step 5: For Production (Optional)

When you're ready for production:

1. Request a WhatsApp-enabled phone number from Twilio
2. Update `TWILIO_WHATSAPP_FROM` with your production number
3. Update `WHATSAPP_ADMIN_NUMBER` if needed

## Testing

Once configured, when an order is cancelled:
- The system will automatically send a WhatsApp message to the admin number
- The message includes all order details (order ID, customer info, items, totals, etc.)
- Check the console logs to see the message status

## Troubleshooting

- If you see "Twilio credentials not configured": Make sure you've added the credentials to settings.py
- If you see "ImportError": Run `pip install twilio`
- For sandbox testing, make sure you've joined the WhatsApp Sandbox first
- Check Twilio Console logs for any API errors: https://console.twilio.com/us1/monitor/logs

