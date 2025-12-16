# WhatsApp Notification Troubleshooting Guide

## Issue: Admin not receiving WhatsApp messages when order is cancelled

### Step 1: Check Backend Logs

When you cancel an order, check your Django backend console/terminal for these messages:

1. Look for: `📱 Attempting to send WhatsApp notification for order...`
2. Look for: `🔍 WhatsApp Configuration Check`
3. Look for any error messages starting with `❌` or `⚠️`

### Step 2: Verify Twilio Setup

#### Check Twilio Package Installation
```bash
pip show twilio
```
If not installed, run:
```bash
pip install twilio
```

#### Check Settings Configuration
In `settings.py`, verify these are set:
```python
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')  # Set in environment variables
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')  # Set in environment variables
TWILIO_WHATSAPP_FROM = os.getenv('TWILIO_WHATSAPP_FROM', 'whatsapp:+14155238886')
WHATSAPP_ADMIN_NUMBER = os.getenv('WHATSAPP_ADMIN_NUMBER', '7996029992')
```

### Step 3: Join Twilio WhatsApp Sandbox (IMPORTANT!)

**This is the most common issue!** For testing with Twilio, you MUST join the WhatsApp Sandbox first:

1. **Send a WhatsApp message** from your phone (+917996029992) to: `+1 415 523 8886`
2. **Send this exact message**: `join <code>` (where `<code>` is the code shown in Twilio Console)
3. You'll receive a confirmation message from Twilio
4. Now messages can be sent to your number

**To find your join code:**
- Go to: https://console.twilio.com/us1/develop/sms/try-it-out/whatsapp-learn
- Look for "Join Code" section
- Send that code from your WhatsApp

### Step 4: Test Twilio Connection

You can test if Twilio is working by running this Python script:

```python
from twilio.rest import Client
import os

account_sid = os.getenv('TWILIO_ACCOUNT_SID')  # Set in environment variables
auth_token = os.getenv('TWILIO_AUTH_TOKEN')  # Set in environment variables
client = Client(account_sid, auth_token)

message = client.messages.create(
    from_='whatsapp:+14155238886',
    body='Test message from Shreshta',
    to='whatsapp:+917996029992'
)

print(f"Message SID: {message.sid}")
print(f"Status: {message.status}")
```

If this works, the integration should work in your app too.

### Step 5: Common Error Messages and Solutions

#### Error: "The number +917996029992 is not a valid WhatsApp number"
**Solution:** Make sure you've joined the Twilio WhatsApp Sandbox (Step 3)

#### Error: "Invalid Account SID or Auth Token"
**Solution:** 
- Check your credentials in `settings.py`
- Verify them in Twilio Console: https://console.twilio.com/

#### Error: "ModuleNotFoundError: No module named 'twilio'"
**Solution:** 
```bash
pip install twilio
```

#### Error: "Unable to create record: The number +917996029992 is not opted in"
**Solution:** You need to join the sandbox. See Step 3.

### Step 6: Check Message Status in Twilio Console

1. Go to: https://console.twilio.com/us1/monitor/logs/sms
2. Look for your message attempts
3. Check the status:
   - `delivered` = Message sent successfully ✅
   - `failed` = Check the error code
   - `queued` = Message is waiting to be sent
   - `sent` = Message sent but not yet delivered

### Step 7: For Production

When ready for production:
1. Request a WhatsApp-enabled phone number from Twilio
2. Update `TWILIO_WHATSAPP_FROM` to your production number
3. No need for sandbox join code in production

### Still Not Working?

1. **Check backend logs** when cancelling an order - they now show detailed error messages
2. **Verify the order was actually cancelled** - WhatsApp is only sent after successful cancellation
3. **Test with a simple script** (Step 4) to isolate the issue
4. **Check Twilio account status** - make sure your account is active and has credits

### Quick Test Command

After joining the sandbox, test immediately:
```bash
# Make sure TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN are set in your environment
python -c "from twilio.rest import Client; import os; c = Client(os.getenv('TWILIO_ACCOUNT_SID'), os.getenv('TWILIO_AUTH_TOKEN')); m = c.messages.create(from_='whatsapp:+14155238886', body='Test', to='whatsapp:+917996029992'); print('SID:', m.sid)"
```

If this works, your app should work too!

