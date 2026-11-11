import { createHmac, timingSafeEqual } from 'node:crypto';
import { Readable } from 'node:stream';

function settings(env) {
  const { STRIPE_SECRET_KEY: key, SHIPDESK_PRICE_ID: price, SHIPDESK_SITE_URL: site,
    SHIPDESK_LICENSE_SECRET: secret } = env;
  if (!key || !price || !site || !secret || secret.length < 32) {
    throw Object.assign(new Error('Billing is not configured'), { status: 503 });
  }
  return { key, price, site: new URL(site).origin, secret };
}

function sign(id, secret) {
  return id + '.' + createHmac('sha256', secret).update(id).digest('base64url');
}

function decode(token, secret) {
  const [id] = token.split('.');
  if (!/^sub_[a-zA-Z0-9]+$/.test(id)) return null;
  const expected = Buffer.from(sign(id, secret));
  const given = Buffer.from(token);
  return expected.length === given.length && timingSafeEqual(expected, given) ? id : null;
}

export function createHandler({ env = process.env, fetcher = fetch } = {}) {
  return async function handler(req, res) {
    const action = new URL(req.url, 'http://localhost').searchParams.get('action');
    res.setHeader('Cache-Control', 'no-store');
    res.setHeader('Referrer-Policy', 'no-referrer');
    try {
      const { key, price, site, secret } = settings(env);
      async function stripe(path, form) {
        const response = await fetcher('https://api.stripe.com/v1/' + path, {
          method: form ? 'POST' : 'GET',
          headers: { Authorization: 'Bearer ' + key, 'Stripe-Version': '2025-03-31.basil' },
          body: form && new URLSearchParams(form),
        });
        if (!response.ok) throw Object.assign(new Error('Stripe could not verify this request'), { status: 502 });
        return response.json();
      }

      if (action === 'checkout' && req.method === 'POST') {
        const session = await stripe('checkout/sessions', {
          mode: 'subscription', 'line_items[0][price]': price, 'line_items[0][quantity]': '1',
          'metadata[product]': 'shipdesk',
          success_url: site + '/shipdesk/?session_id={CHECKOUT_SESSION_ID}',
          cancel_url: site + '/shipdesk/',
        });
        return res.redirect(303, session.url);
      }

      let id;
      if (action === 'claim' && req.method === 'POST') {
        const sessionId = req.body?.session_id;
        if (typeof sessionId !== 'string' || !/^cs_(test|live)_[a-zA-Z0-9]+$/.test(sessionId)) {
          return res.status(400).json({ error: 'Invalid checkout session' });
        }
        const session = await stripe('checkout/sessions/' + sessionId);
        if (session.status !== 'complete' || session.payment_status !== 'paid' ||
            session.mode !== 'subscription' || session.metadata?.product !== 'shipdesk') {
          return res.status(403).json({ error: 'ShipDesk payment has not been confirmed' });
        }
        id = session.subscription;
      } else if (['status', 'download'].includes(action) && req.method === 'GET') {
        id = decode((req.headers.authorization || '').replace(/^Bearer /, ''), secret);
      } else {
        return res.status(405).json({ error: 'Unsupported billing request' });
      }

      if (!id || !/^sub_[a-zA-Z0-9]+$/.test(id)) return res.status(401).json({ error: 'Invalid license' });
      const subscription = await stripe('subscriptions/' + id);
      const item = subscription.items?.data?.find(row => row.price?.id === price);
      if (!item) return res.status(403).json({ error: 'Subscription does not contain ShipDesk' });
      const active = subscription.status === 'active' && item.current_period_end * 1000 > Date.now();
      const portal = env.SHIPDESK_STRIPE_PORTAL_URL;
      const portal_url = /^https:\/\/billing\.stripe\.com\//.test(portal || '') ? portal : null;
      const details = { active, portal_url, status: subscription.status, purchased_at: subscription.start_date,
        period_end: item.current_period_end, cancel_at_period_end: subscription.cancel_at_period_end,
        amount: item.price.unit_amount, currency: item.price.currency,
        interval: item.price.recurring?.interval };
      if (action === 'status') return res.status(200).json(details);
      if (!active) return res.status(403).json({ error: 'ShipDesk subscription is inactive' });
      if (action === 'claim') return res.status(200).json({ ...details, license: sign(id, secret) });
      if (!env.SHIPDESK_PRIVATE_DOWNLOAD_URL) return res.status(503).json({ error: 'Download is not configured' });
      const headers = env.SHIPDESK_DOWNLOAD_TOKEN
        ? { Authorization: 'Bearer ' + env.SHIPDESK_DOWNLOAD_TOKEN } : {};
      const file = await fetcher(env.SHIPDESK_PRIVATE_DOWNLOAD_URL, { headers });
      if (!file.ok || !file.body) return res.status(502).json({ error: 'Download unavailable' });
      res.setHeader('Content-Type', 'application/zip');
      res.setHeader('Content-Disposition', 'attachment; filename="ShipDesk.zip"');
      Readable.fromWeb(file.body).pipe(res);
    } catch (error) {
      return res.status(error.status || 500).json({ error: error.status ? error.message : 'Billing request failed' });
    }
  };
}

export default createHandler();
