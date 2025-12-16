# Shiprocket Pickup Scheduling Verification Checklist

## ✅ VERIFIED FLOW

### Step 1: Courier Assignment & AWB Extraction ✅
- **Line 621**: API endpoint: `POST /courier/assign/awb`
- **Line 623**: Payload: `{"shipment_id": shipment_id}` (with optional courier_company_id)
- **Lines 640-645**: AWB extraction tries multiple response paths:
  1. `courier_data.get('awb_code')`
  2. `courier_data.get('response', {}).get('data', {}).get('awb_code')`
  3. `courier_data.get('data', {}).get('awb_code')`
  4. `courier_data.get('response', {}).get('awb_code')`
- **Lines 658-673**: Fallback: If AWB not found, fetches from `/orders/show/{order_id}` shipment details
- **Line 655**: Logs AWB code for verification

### Step 2: Pickup Scheduling ✅
- **Line 676**: Only executes if `awb_code` exists
- **Line 699**: API endpoint: `POST /courier/generate/pickup`
- **Lines 702-705**: Payload format (as per your specification):
  ```json
  {
    "awb": awb_code,
    "pickup_address_id": 18928400
  }
  ```
- **Line 701**: Pickup address ID from settings: `SHIPROCKET_PICKUP_ADDRESS_ID = 18928400`
- **Lines 711-719**: On success (status 200):
  - Sets `pickup_scheduled = True`
  - Sets `pickup_status` from response
  - Stores pickup response data
  - Logs success message

### Step 3: Database Storage ✅
- **Line 768**: AWB code saved: `awb_code=awb_code`
- **Lines 771-773**: Pickup fields saved:
  - `pickup_scheduled=pickup_scheduled`
  - `pickup_status=pickup_status`
  - `pickup_data=pickup_data`

## 🔍 VERIFICATION POINTS

### What to Check in Backend Logs:
1. ✅ "✅ Courier assigned successfully! AWB Code: {awb_code}"
2. ✅ "🚚 Shiprocket: Scheduling pickup for AWB: {awb_code}"
3. ✅ "Shiprocket: Pickup payload: {...}"
4. ✅ "Shiprocket: Pickup scheduling response status: 200"
5. ✅ "✅✅✅ PICKUP SCHEDULED SUCCESSFULLY! ✅✅✅"

### Expected Behavior:
1. ✅ Order created in Shiprocket
2. ✅ Courier assigned
3. ✅ AWB code extracted (with fallback to shipment details)
4. ✅ Pickup automatically scheduled
5. ✅ Order status changes to "PICKUP SCHEDULED" in Shiprocket dashboard
6. ✅ Database stores AWB code and pickup status

## ⚠️ POTENTIAL ISSUES TO WATCH

1. **AWB Not Found**: If AWB code is None after all extraction attempts, pickup scheduling is skipped (line 727)
2. **Pickup API Failure**: If pickup API returns non-200 status, error is logged but order is still saved (line 721)
3. **Shiprocket Response Structure**: If Shiprocket changes their response format, the multiple extraction paths should handle it

## 📝 CURRENT STATUS

✅ **Code is correctly implemented according to your specifications**
✅ **Pickup address ID: 18928400 is configured**
✅ **Multiple AWB extraction paths for reliability**
✅ **Fallback mechanism to fetch AWB from shipment details**
✅ **Detailed logging at each step for debugging**

## 🚀 NEXT STEPS

When you test a new order:
1. Monitor backend logs for the verification points above
2. Check Shiprocket dashboard - order should move from "READY TO SHIP" → "PICKUP SCHEDULED"
3. Check database - `pickup_scheduled` should be `True` and `awb_code` should be populated

