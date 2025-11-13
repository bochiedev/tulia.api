# Tenant Onboarding Guide

## Welcome to WabotIQ!

This guide will walk you through setting up your WabotIQ account step-by-step. By the end of this guide, you'll have a fully configured WhatsApp commerce platform ready to engage with your customers.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Step 1: Create Your Account](#step-1-create-your-account)
3. [Step 2: Verify Your Email](#step-2-verify-your-email)
4. [Step 3: Connect Twilio (WhatsApp)](#step-3-connect-twilio-whatsapp)
5. [Step 4: Add Payment Method](#step-4-add-payment-method)
6. [Step 5: Configure Business Settings](#step-5-configure-business-settings)
7. [Step 6: Optional Integrations](#step-6-optional-integrations)
8. [Step 7: Generate API Keys](#step-7-generate-api-keys)
9. [Next Steps](#next-steps)
10. [Troubleshooting](#troubleshooting)

---

## Getting Started

### What You'll Need

Before you begin, make sure you have:

- ✅ A valid email address
- ✅ A Twilio account with WhatsApp enabled ([Get one here](https://www.twilio.com/whatsapp))
- ✅ A payment method (credit/debit card) for subscription billing
- ✅ (Optional) WooCommerce or Shopify store credentials
- ✅ About 15-20 minutes to complete setup

### Onboarding Progress

As you complete each step, your onboarding progress will be tracked:

- **Required Steps** (must complete): 
  - Twilio Configuration
  - Payment Method
  - Business Settings

- **Optional Steps** (enhance functionality):
  - WooCommerce Integration
  - Shopify Integration
  - Payout Method Configuration

---

## Step 1: Create Your Account

### 1.1 Navigate to Registration Page

Go to the WabotIQ registration page:
- **Development**: `http://localhost:3000/register`
- **Production**: `https://app.yourdomain.com/register`

### 1.2 Fill Out Registration Form

Enter your information:

| Field | Description | Example |
|-------|-------------|---------|
| **Email** | Your business email address | `john@acmecorp.com` |
| **Password** | Strong password (8+ characters) | `SecurePass123!` |
| **First Name** | Your first name | `John` |
| **Last Name** | Your last name | `Doe` |
| **Business Name** | Your company or business name | `Acme Corp` |


### 1.3 Submit Registration

Click the **"Create Account"** button. You'll receive:

- ✅ Immediate access to your account
- ✅ Your first tenant (business workspace) automatically created
- ✅ Owner role with full permissions
- ✅ 14-day free trial (no credit card required yet)

### 1.4 What Happens Next

After registration:
1. You're automatically logged in
2. Your first tenant is created with your business name
3. A verification email is sent to your email address
4. You're redirected to the onboarding dashboard

**📧 Check your email** for the verification link!

---

## Step 2: Verify Your Email

### 2.1 Check Your Inbox

Look for an email from `noreply@yourdomain.com` with the subject:
**"Verify Your Email Address - WabotIQ"**

### 2.2 Click Verification Link

Click the verification link in the email. This will:
- ✅ Verify your email address
- ✅ Enable full account access
- ✅ Allow you to receive important notifications

### 2.3 Troubleshooting Email Verification

**Didn't receive the email?**

1. **Check spam/junk folder** - sometimes verification emails end up there
2. **Wait a few minutes** - email delivery can take 1-5 minutes
3. **Request a new verification email** - click "Resend Verification Email" in your dashboard
4. **Check email address** - make sure you entered it correctly during registration

**Verification link expired?**

- Verification links expire after 24 hours
- Request a new verification email from your dashboard
- The new link will be valid for another 24 hours

---

## Step 3: Connect Twilio (WhatsApp)

This is the most important step - it enables WhatsApp messaging for your business.

### 3.1 Get Twilio Credentials

If you don't have a Twilio account yet:

1. Go to [Twilio.com](https://www.twilio.com)
2. Sign up for a free account
3. Navigate to **Console Dashboard**
4. Enable WhatsApp messaging (follow Twilio's WhatsApp setup guide)

You'll need these credentials:

| Credential | Where to Find It | Example |
|------------|------------------|---------|
| **Account SID** | Console Dashboard | `ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` |
| **Auth Token** | Console Dashboard (click "View") | `your-auth-token-here` |
| **WhatsApp Number** | Phone Numbers → Active Numbers | `+14155551234` |
| **Webhook Secret** | Optional, for signature verification | `your-webhook-secret` |

### 3.2 Configure Twilio in WabotIQ

1. Navigate to **Settings → Integrations → Twilio**
2. Enter your Twilio credentials:
   - Account SID
   - Auth Token
   - Webhook Secret (optional but recommended)
   - WhatsApp Number

3. Click **"Save & Validate"**

### 3.3 Validation Process

WabotIQ will:
- ✅ Test your credentials with Twilio's API
- ✅ Verify the WhatsApp number is active
- ✅ Encrypt and securely store your credentials
- ✅ Mark this onboarding step as complete

**⏱️ This usually takes 5-10 seconds**


### 3.4 Configure Twilio Webhook

To receive incoming WhatsApp messages, configure Twilio's webhook:

1. In Twilio Console, go to **Phone Numbers → Active Numbers**
2. Click on your WhatsApp number
3. Scroll to **Messaging Configuration**
4. Set **"A Message Comes In"** webhook to:
   ```
   https://api.yourdomain.com/v1/webhooks/twilio/
   ```
5. Set HTTP method to **POST**
6. Click **Save**

**🔒 Security Note**: If you provided a webhook secret, Twilio will sign all requests, and WabotIQ will verify the signature.

### 3.5 Test Your Connection

Send a test message:
1. Send "Hello" from your personal WhatsApp to your business number
2. Check the **Messages** section in WabotIQ dashboard
3. You should see the incoming message appear

**✅ Success!** Your WhatsApp integration is working!

---

## Step 4: Add Payment Method

Add a payment method to upgrade from trial to a paid subscription.

### 4.1 Navigate to Payment Settings

Go to **Settings → Billing → Payment Methods**

### 4.2 Add Credit/Debit Card

Click **"Add Payment Method"** and enter:

- Card number
- Expiration date (MM/YY)
- CVC/CVV code
- Billing ZIP code

**🔒 Security**: 
- Card details are processed by Stripe (PCI-DSS compliant)
- WabotIQ never stores your full card number
- Only the last 4 digits and expiration date are saved

### 4.3 Set as Default

If you add multiple payment methods:
- Mark one as **default** for automatic billing
- You can change the default anytime

### 4.4 What Happens Next

- ✅ Payment method is tokenized and stored securely
- ✅ You can now upgrade to a paid plan
- ✅ Automatic billing will use this method
- ✅ Onboarding step marked as complete

**💳 Trial Period**: You won't be charged until your 14-day trial ends.

---

## Step 5: Configure Business Settings

Customize how WabotIQ operates for your business.

### 5.1 Navigate to Business Settings

Go to **Settings → Business Settings**

### 5.2 Set Your Timezone

Choose your business timezone:

```
Example: America/New_York, Europe/London, Asia/Tokyo
```

**Why it matters**: 
- Scheduled messages send at the right time
- Business hours are calculated correctly
- Analytics show data in your local time

### 5.3 Configure Business Hours

Set when your business is open:

| Day | Open | Close |
|-----|------|-------|
| Monday | 09:00 AM | 05:00 PM |
| Tuesday | 09:00 AM | 05:00 PM |
| Wednesday | 09:00 AM | 05:00 PM |
| Thursday | 09:00 AM | 05:00 PM |
| Friday | 09:00 AM | 05:00 PM |
| Saturday | Closed | Closed |
| Sunday | Closed | Closed |

**Why it matters**:
- Customers see accurate availability
- Automated responses mention business hours
- Appointment booking respects your schedule


### 5.4 Set Quiet Hours

Define when NOT to send automated messages:

```
Start: 10:00 PM
End: 8:00 AM
```

**Why it matters**:
- Respects customer preferences
- Avoids sending messages at inappropriate times
- Improves customer satisfaction

### 5.5 Configure Notification Preferences

Choose how you want to be notified:

**Email Notifications:**
- ✅ New orders
- ✅ New messages
- ✅ Low wallet balance
- ✅ Failed payments
- ⬜ Daily summary

**SMS Notifications:**
- ✅ Urgent issues only
- ⬜ All notifications

### 5.6 Save Settings

Click **"Save Business Settings"**

**✅ Success!** Your business settings are configured!

---

## Step 6: Optional Integrations

These integrations enhance functionality but aren't required.

### 6.1 WooCommerce Integration (Optional)

If you have a WooCommerce store:

**Step 1: Get WooCommerce API Keys**

1. In WordPress admin, go to **WooCommerce → Settings → Advanced → REST API**
2. Click **"Add Key"**
3. Set permissions to **Read/Write**
4. Copy the **Consumer Key** and **Consumer Secret**

**Step 2: Configure in WabotIQ**

1. Go to **Settings → Integrations → WooCommerce**
2. Enter:
   - Store URL: `https://mystore.com`
   - Consumer Key: `ck_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
   - Consumer Secret: `cs_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
3. Click **"Save & Validate"**

**What You Get:**
- ✅ Automatic product sync
- ✅ Real-time inventory updates
- ✅ Order creation from WhatsApp
- ✅ Order status updates

### 6.2 Shopify Integration (Optional)

If you have a Shopify store:

**Step 1: Get Shopify Access Token**

1. In Shopify admin, go to **Apps → Develop apps**
2. Click **"Create an app"**
3. Configure Admin API scopes (read_products, write_orders, etc.)
4. Install the app and copy the **Admin API access token**

**Step 2: Configure in WabotIQ**

1. Go to **Settings → Integrations → Shopify**
2. Enter:
   - Shop Domain: `mystore.myshopify.com`
   - Access Token: `shpat_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
3. Click **"Save & Validate"**

**What You Get:**
- ✅ Automatic product sync
- ✅ Real-time inventory updates
- ✅ Order creation from WhatsApp
- ✅ Order status updates

### 6.3 Payout Method (Optional)

If you enable payment facilitation (accepting payments on behalf of customers):

**Step 1: Navigate to Payout Settings**

Go to **Settings → Finance → Payout Method**

**Step 2: Choose Payout Method**

**Option A: Bank Transfer**
- Account Number
- Routing Number
- Account Holder Name
- Bank Name

**Option B: Mobile Money**
- Phone Number
- Provider (M-Pesa, MTN, etc.)
- Account Name

**Step 3: Save & Verify**

Click **"Save Payout Method"**

**🔒 Security**: Payout details are encrypted at rest.

---

## Step 7: Generate API Keys

API keys allow external systems to integrate with your WabotIQ tenant.

### 7.1 Navigate to API Keys

Go to **Settings → API Keys**

### 7.2 Generate New Key

1. Click **"Generate New API Key"**
2. Enter a name: `Production API Key`
3. Click **"Generate"**

### 7.3 Save Your API Key

**⚠️ IMPORTANT**: The full API key is shown only once!

```
tulia_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**Copy and store it securely:**
- ✅ Password manager
- ✅ Environment variables
- ✅ Secrets management system

**❌ Never:**
- Commit to version control
- Share in emails or chat
- Store in plain text files

### 7.4 Use Your API Key

Include in API requests:

```bash
curl -X GET https://api.yourdomain.com/v1/products \
  -H "X-TENANT-ID: your-tenant-id" \
  -H "X-TENANT-API-KEY: tulia_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

### 7.5 Manage API Keys

- **View all keys**: See list with masked values
- **Revoke keys**: Immediately invalidate compromised keys
- **Track usage**: See when each key was last used

---

## Next Steps

### 🎉 Congratulations! Your onboarding is complete!

Now you can:

1. **Add Products/Services**
   - Go to **Catalog → Products** to add your offerings
   - Or sync automatically from WooCommerce/Shopify

2. **Test WhatsApp Bot**
   - Send a message to your WhatsApp number
   - Try commands like "Show products" or "Book appointment"

3. **Customize Bot Responses**
   - Go to **Bot → Intents** to customize responses
   - Add FAQs and automated replies

4. **Invite Team Members**
   - Go to **Settings → Team** to invite users
   - Assign roles (Admin, Support, etc.)

5. **View Analytics**
   - Go to **Analytics** to see performance metrics
   - Track messages, orders, and revenue

6. **Upgrade Subscription**
   - Go to **Settings → Billing** to choose a plan
   - Growth or Enterprise plans unlock more features


---

## Troubleshooting

### Common Issues and Solutions

#### Issue: "Invalid Twilio Credentials"

**Symptoms**: Error when saving Twilio settings

**Solutions**:
1. **Double-check credentials**
   - Copy Account SID and Auth Token directly from Twilio Console
   - Make sure there are no extra spaces

2. **Verify WhatsApp is enabled**
   - In Twilio Console, check that WhatsApp is activated
   - Complete Twilio's WhatsApp setup process

3. **Check account status**
   - Ensure your Twilio account is active
   - Verify you have sufficient balance (if applicable)

4. **Try test API call**
   ```bash
   curl -X GET "https://api.twilio.com/2010-04-01/Accounts/ACxxxx.json" \
     -u "ACxxxx:your-auth-token"
   ```

#### Issue: "Payment Method Declined"

**Symptoms**: Card is rejected when adding payment method

**Solutions**:
1. **Verify card details**
   - Check card number, expiration date, CVC
   - Ensure billing ZIP code matches card

2. **Check with your bank**
   - Some banks block online transactions by default
   - Enable online/international transactions

3. **Try a different card**
   - Use a different credit/debit card
   - Contact your bank if issues persist

4. **Check Stripe status**
   - Visit [status.stripe.com](https://status.stripe.com)
   - Stripe may be experiencing issues

#### Issue: "Webhook Not Receiving Messages"

**Symptoms**: Messages sent to WhatsApp don't appear in WabotIQ

**Solutions**:
1. **Verify webhook URL**
   - In Twilio Console, check webhook is set correctly
   - URL should be: `https://api.yourdomain.com/v1/webhooks/twilio/`
   - Must use HTTPS (not HTTP)

2. **Check webhook logs**
   - In Twilio Console, go to **Monitor → Logs → Webhooks**
   - Look for errors or failed requests

3. **Verify webhook secret**
   - If using webhook secret, ensure it matches in both Twilio and WabotIQ
   - Try removing webhook secret temporarily to test

4. **Test webhook manually**
   ```bash
   curl -X POST https://api.yourdomain.com/v1/webhooks/twilio/ \
     -d "From=whatsapp:+1234567890" \
     -d "To=whatsapp:+14155551234" \
     -d "Body=Test message"
   ```

#### Issue: "WooCommerce/Shopify Sync Failing"

**Symptoms**: Products not syncing from e-commerce platform

**Solutions**:
1. **Verify API credentials**
   - Re-generate API keys in WooCommerce/Shopify
   - Update credentials in WabotIQ

2. **Check API permissions**
   - WooCommerce: Ensure Read/Write permissions
   - Shopify: Verify all required scopes are granted

3. **Test API access**
   ```bash
   # WooCommerce
   curl https://mystore.com/wp-json/wc/v3/products \
     -u "consumer_key:consumer_secret"
   
   # Shopify
   curl https://mystore.myshopify.com/admin/api/2024-01/products.json \
     -H "X-Shopify-Access-Token: your-token"
   ```

4. **Check store URL**
   - Ensure URL is correct and accessible
   - Must use HTTPS
   - Don't include trailing slash

#### Issue: "Onboarding Progress Not Updating"

**Symptoms**: Completed steps not marked as done

**Solutions**:
1. **Refresh the page**
   - Sometimes the UI needs a refresh
   - Press Ctrl+F5 (or Cmd+Shift+R on Mac)

2. **Verify step completion**
   - Go to **Settings → Onboarding** to see detailed status
   - Check which specific requirements are missing

3. **Complete all required fields**
   - Some steps require all fields to be filled
   - Check for validation errors

4. **Contact support**
   - If issue persists, contact support with:
     - Your tenant ID
     - Which step is not updating
     - Screenshots of the issue

#### Issue: "Can't Access Tenant After Creation"

**Symptoms**: 403 Forbidden when accessing tenant resources

**Solutions**:
1. **Verify tenant ID**
   - Check you're using the correct tenant ID in X-TENANT-ID header
   - Get tenant ID from **Settings → Account**

2. **Verify API key**
   - Ensure API key is valid and not revoked
   - Generate a new API key if needed

3. **Check user membership**
   - Verify you have membership in the tenant
   - Go to **Settings → Team** to see your role

4. **Clear browser cache**
   - Clear cookies and local storage
   - Log out and log back in

### Getting Help

If you're still experiencing issues:

1. **Check Documentation**
   - API Guide: `docs/api/TENANT_ONBOARDING_API_GUIDE.md`
   - Deployment Guide: `docs/DEPLOYMENT.md`
   - Environment Variables: `docs/ENVIRONMENT_VARIABLES.md`

2. **Check System Status**
   - Visit status page (if available)
   - Check for known issues or maintenance

3. **Contact Support**
   - **Email**: support@yourdomain.com
   - **Live Chat**: Available in dashboard (bottom right)
   - **Phone**: +1 (555) 123-4567 (Business hours)

4. **Provide Details**
   When contacting support, include:
   - Your tenant ID
   - Steps to reproduce the issue
   - Screenshots or error messages
   - Browser and OS information

---

## Frequently Asked Questions

### General Questions

**Q: How long does onboarding take?**
A: Most users complete onboarding in 15-20 minutes. The Twilio setup is usually the longest step.

**Q: Can I skip optional steps?**
A: Yes! Optional steps (WooCommerce, Shopify, Payout Method) can be configured later.

**Q: What happens after my trial ends?**
A: You'll need to upgrade to a paid plan. Your data is preserved, but access is limited until you upgrade.

**Q: Can I change my business name later?**
A: Yes, go to **Settings → Account** to update your business name and other details.

### Twilio Questions

**Q: Do I need a Twilio account?**
A: Yes, Twilio provides the WhatsApp messaging infrastructure. WabotIQ integrates with your Twilio account.

**Q: How much does Twilio cost?**
A: Twilio charges per message sent/received. Check [Twilio's pricing](https://www.twilio.com/whatsapp/pricing) for current rates.

**Q: Can I use my existing WhatsApp Business number?**
A: You need to use a Twilio WhatsApp number. You can't use a regular WhatsApp Business number directly.

### Billing Questions

**Q: When will I be charged?**
A: You won't be charged during the 14-day trial. After that, billing is monthly based on your chosen plan.

**Q: Can I cancel anytime?**
A: Yes, you can cancel your subscription anytime. You'll have access until the end of your billing period.

**Q: What payment methods do you accept?**
A: We accept all major credit and debit cards via Stripe (Visa, Mastercard, Amex, Discover).

### Integration Questions

**Q: Do I need WooCommerce or Shopify?**
A: No, these are optional. You can manually add products in WabotIQ without an e-commerce platform.

**Q: Can I integrate both WooCommerce and Shopify?**
A: Yes, you can connect both platforms to the same tenant.

**Q: How often do products sync?**
A: Products sync automatically every hour, or you can trigger a manual sync anytime.

---

## Checklist

Use this checklist to track your onboarding progress:

### Required Steps
- [ ] Create account and verify email
- [ ] Configure Twilio credentials
- [ ] Set up Twilio webhook
- [ ] Add payment method
- [ ] Configure timezone
- [ ] Set business hours
- [ ] Configure quiet hours
- [ ] Set notification preferences

### Optional Steps
- [ ] Connect WooCommerce (if applicable)
- [ ] Connect Shopify (if applicable)
- [ ] Configure payout method (if using payment facilitation)
- [ ] Generate API keys (if using API)

### Next Steps
- [ ] Add products or sync from e-commerce
- [ ] Test WhatsApp bot
- [ ] Customize bot responses
- [ ] Invite team members
- [ ] Review analytics
- [ ] Upgrade subscription (after trial)

---

**Last Updated**: 2025-11-13
**Version**: 1.0.0

**Need Help?** Contact support@yourdomain.com or visit our [Help Center](https://help.yourdomain.com)
