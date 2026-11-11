"""Read a ShipDesk license from the website billing service."""
import json
from datetime import datetime
from urllib.error import HTTPError
from urllib.request import Request, urlopen

URL = 'https://www.thetrendsetteragency.com/api/shipdesk?action=status'

def read_subscription(license_key):
    if not license_key:
        raise ValueError('Paste your ShipDesk license from the checkout confirmation.')
    try:
        with urlopen(Request(URL, headers={'Authorization': 'Bearer ' + license_key}), timeout=15) as response:
            payload = json.load(response)
    except HTTPError as error:
        if error.code in (401, 403):
            raise ValueError('This license could not be verified. Check the license from your checkout confirmation page.') from None
        raise RuntimeError('Billing service is temporarily unavailable. Try again shortly.') from None
    except OSError:
        raise RuntimeError('Could not reach billing. Check your connection and try again.') from None
    return payload

def format_subscription(payload):
    def date(key):
        value = payload.get(key)
        return datetime.fromtimestamp(value).strftime('%b %d, %Y') if value else 'Unavailable'
    price = f"{payload['amount'] / 100:.2f} {payload['currency'].upper()} / {payload['interval']}"
    renewal = 'Access expires' if payload.get('cancel_at_period_end') or not payload.get('active') else 'Next renewal'
    return '\n'.join((f"Status · {payload.get('status', 'Unknown').replace('_', ' ').title()}",
                      f"Purchased · {date('purchased_at')}", f"{renewal} · {date('period_end')}",
                      f'Plan price · {price}'))



def require_active(payload):
    if payload.get('active') is True:
        return
    if payload.get('status') in ('past_due', 'unpaid', 'incomplete'):
        raise ValueError('Payment needs attention. Open Manage billing in ShipDesk Settings, then try again.')
    raise ValueError('ShipDesk access has ended. Open Subscription in Settings to renew or enter a new license.')
