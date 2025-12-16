# WhatsApp Business API Setup Guide (Meta/Facebook)

This guide will help you set up WhatsApp Business API to send automatic notifications when orders are cancelled.

## Prerequisites

1. A Facebook Business Account
2. A Meta Business Account
3. A verified business profile

## Step 1: Create Meta Business Account

1. Go to https://business.facebook.com/
2. Create a Business Account (if you don't have one)
3. Complete the business verification process

## Step 2: Set Up WhatsApp Business Account

1. Go to Meta Business Suite: https://business.facebook.com/
2. Navigate to **Settings** > **Business Settings**
3. Click on **WhatsApp Accounts** in the left sidebar
4. Click **Add** to create a new WhatsApp Business Account
5. Follow the setup wizard

## Step 3: Get Your Phone Number ID

1. In Meta Business Suite, go to **WhatsApp Accounts**
2. Select your WhatsApp Business Account
3. Go to **Phone Numbers** section
4. Copy the **Phone Number ID** (it's a numeric ID, not the actual phone number)

## Step 4: Get Your Access Token

1. Go to Meta for Developers: https://developers.facebook.com/
2. Go to **My Apps** > Create App (if needed)
3. Add **WhatsApp** product to your app
4. Go to **WhatsApp** > **API Setup**
5. Copy the **Temporary Access Token** (for testing)

### For Production - Get Permanent Access Token:

1. In Meta Business Suite, go to **Settings** > **Business Settings**
2. Click on **System Users** (left sidebar)
3. Create a new System User (if you don't have one)
4. Assign **WhatsApp Business Management** permissions
5. Generate a new access token with these permissions:
   - `whatsapp_business_messaging`
   - `whatsapp_business_management`
6. Copy the generated token

## Step 5: Configure Django Settings

Edit `firstbackend/settings.py`:

```python
# WhatsApp Configuration
WHATSAPP_ADMIN_NUMBER = '7996029992'  # Admin WhatsApp number

# WhatsApp Business API (Meta/Facebook)
WHATSAPP_BUSINESS_API_ENABLED = True  # Set to True to use WhatsApp Business API
WHATSAPP_PHONE_NUMBER_ID = 'your_phone_number_id_here'  # From Step 3
WHATSAPP_ACCESS_TOKEN = 'your_access_token_here'  # From Step 4
WHATSAPP_API_VERSION = 'v18.0'  # API version (usually v18.0 or latest)
```

## Step 6: Test the Integration

1. Make sure your Django server is running
2. Cancel an order from the "My Orders" page
3. Check the console logs for WhatsApp API response
4. Verify the message is received on the admin WhatsApp number

## API Endpoint Used

The implementation uses the WhatsApp Business API endpoint:
```
POST https://graph.facebook.com/{version}/{phone-number-id}/messages
```

Request body:
```json
{
  "messaging_product": "whatsapp",
  "to": "91{admin_number}",
  "type": "text",
  "text": {
    "body": "Your message content"
  }
}
```

## Troubleshooting

### Error: "Invalid OAuth access token"
- Your access token may have expired
- Generate a new access token and update settings

### Error: "Phone number not found"
- Verify your Phone Number ID is correct
- Make sure the phone number is verified in Meta Business Suite

### Error: "Permission denied"
- Check that your System User has the correct permissions
- Ensure `whatsapp_business_messaging` permission is granted

### Error: "Rate limit exceeded"
- WhatsApp Business API has rate limits
- Check your rate limits in Meta Business Suite
- Consider implementing retry logic with exponential backoff

## Rate Limits

WhatsApp Business API has rate limits based on your tier:
- **Tier 1**: 1,000 conversations per month (free)
- **Tier 2**: Higher limits (requires verification)
- **Tier 3+**: Enterprise limits (contact Meta)

## Webhooks (Optional)

For receiving message status updates, you can set up webhooks:
1. Go to Meta for Developers > Your App > WhatsApp > Configuration
2. Add webhook URL
3. Verify webhook token
4. Subscribe to message status events

## Documentation

- Official WhatsApp Business API Docs: https://developers.facebook.com/docs/whatsapp
- API Reference: https://developers.facebook.com/docs/whatsapp/cloud-api/reference

## Comparison: WhatsApp Business API vs Twilio

| Feature | WhatsApp Business API | Twilio WhatsApp |
|---------|----------------------|-----------------|
| Setup Complexity | Higher (requires Meta Business Account) | Lower (quick setup) |
| Cost | Free tier available, then pay-per-message | Pay-per-message |
| Official | ✅ Official Meta/WhatsApp API | ✅ Third-party but reliable |
| Rate Limits | Yes (based on tier) | Yes (based on account) |
| Best For | Large businesses, high volume | Small to medium businesses |

Choose the option that best fits your needs!

