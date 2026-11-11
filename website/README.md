# ShipDesk checkout deployment

The agency site's Vercel project can host api/shipdesk.mjs and shipdesk/ at the
repository root. Add a navigation link to /shipdesk/ after testing on a preview.

Set STRIPE_SECRET_KEY, SHIPDESK_PRICE_ID, SHIPDESK_SITE_URL (the deployment
origin), and SHIPDESK_LICENSE_SECRET (32 or more random characters).
Create a USD 39.00 yearly recurring Price in Stripe, starting in test mode.
Set SHIPDESK_PRIVATE_DOWNLOAD_URL to a private origin endpoint that serves the
desktop ZIP and accepts SHIPDESK_DOWNLOAD_TOKEN if configured. The public
download handler checks active entitlement with Stripe on every request.

Desktop settings read the production domain. For checkout verification on a
preview, test its status endpoint with the license from that preview.
This implementation uses live Stripe lookups, with no webhook or automatic
license emails. A customer must keep their license or their successful Checkout
return link to retrieve it again. Desktop checks display billing status.
The protected download requires an active subscription. Desktop store checks and screenshot operations verify the license online before running.
Set SHIPDESK_STRIPE_PORTAL_URL to the Stripe-hosted customer portal login URL.
The customer uses that page to manage billing or update payment details.
ShipDesk stores the license in the current Windows user profile after verification.
A billing outage blocks gated checks until the service returns.
