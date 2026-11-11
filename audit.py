"""Store observations and explicit audit coverage."""
import store

def audit_apple(bearer):
    lines = ['APPLE ACCOUNT AUDIT', 'Scope: apps visible to the supplied key.',
             'Review in console: agreements, privacy declarations, account notices, and final submission readiness.']
    apps = store.apple_apps(bearer)
    lines.append(f'Apps visible: {len(apps)}')
    for app in apps:
        lines.append('\n' + app['attributes']['name'])
        try:
            releases = store.apple_releases(app['id'], bearer)
        except RuntimeError as error:
            lines.append(f'UNVERIFIED · Releases: {error}')
            releases = []
        else:
            if not releases:
                lines.append('REVIEW · No releases returned.')
        for release in releases:
            label = f"{release['platform']} {release['versionString']}"
            status = release.get('appVersionState') or release.get('appStoreState') or 'Unknown'
            lines.append(f'OBSERVED · {label}: {status}; build {release.get("buildId") or "not returned"}')
            try:
                locales = store.apple_listing(release['id'], bearer)
            except RuntimeError as error:
                lines.append(f'UNVERIFIED · {label} screenshots: {error}')
                continue
            if not locales:
                lines.append('REVIEW · No listing locales returned.')
            for locale in locales:
                groups = locale['sets']
                if not groups:
                    lines.append(f"REVIEW · {locale['locale']}: no screenshot sets returned. Check fallback assets.")
                for group in groups:
                    names = ', '.join(group['screenshots'])
                    lines.append(f"{'OBSERVED' if names else 'REVIEW'} · {locale['locale']} / {group['device']}: "
                                 f"{names or 'no files returned; check fallback assets'}")
        try:
            products = store.apple_offers(app['id'], bearer)
        except RuntimeError as error:
            lines.append(f'UNVERIFIED · Offers: {error}')
            continue
        if not products:
            lines.append('OBSERVED · No subscriptions returned.')
        for product in products:
            lines.append(f"OBSERVED · Subscription {product['product']}: {product['state'] or 'unknown state'}")
            for offer in product['offers']:
                eligibility = ', '.join(offer.get('customerEligibilities') or [])
                active = offer.get('active')
                lines.append(f"{'REVIEW' if active is False else 'OBSERVED'} · {offer.get('name', 'Offer')}: "
                             f"active={active}, mode={offer.get('offerMode')}, eligible={eligibility or 'not returned'}")
    lines.append('\nUNVERIFIED · Image content, actual code redemption, and App Review outcome.')
    return '\n'.join(lines)

def audit_google(package, bearer):
    listings = store.play_listing(package, bearer)
    lines = [f'GOOGLE PLAY AUDIT · {package}',
             'Scope: listing text returned for this package.']
    if not listings:
        lines.append('REVIEW · No listings returned.')
    for listing in listings:
        locale = listing.get('language', 'Unknown locale')
        fields = {'title': 30, 'shortDescription': 80, 'fullDescription': 4000}
        for field, limit in fields.items():
            length = len((listing.get(field) or '').strip())
            status = 'PASS' if 0 < length <= limit else 'REVIEW'
            lines.append(f'{status} · {locale} / {field}: {length}/{limit} characters')
    lines.append('UNVERIFIED · Images, tracks, offers, Data Safety, policy notices, and publishing readiness.')
    return '\n'.join(lines)


def verify_request(question, app_id, version_id, bearer):
    import re
    terms = set(re.findall(r'[a-z]+', question.lower()))
    payment = terms & {'payment', 'payments', 'subscription', 'subscriptions', 'price', 'prices', 'pricing',
                       'offer', 'offers', 'code', 'codes', 'paywall'}
    release = terms & {'release', 'build', 'builds', 'submission', 'listing', 'screenshots', 'screenshot'}
    connection = terms & {'connection', 'connect', 'connected', 'permissions', 'authentication'}
    if not (payment or release or connection):
        return 'Try “Check subscription pricing and offer codes”, “Check release and screenshots”, or “Verify connection”.'
    lines = []
    if connection:
        apps = store.apple_apps(bearer)
        lines.append(f'PASS · Apple accepted the API credentials and returned {len(apps)} apps.')
    if (payment or release) and not app_id:
        lines.append('Next step · Verify and load apps, then select the app to check.')
        return '\n'.join(lines)
    if payment:
        lines.append('Subscription and payment setup')
        products = list(store.apple_subscription_setup(app_id, bearer))
        if not products:
            lines.append('REVIEW · Apple returned no subscriptions for this app.')
        for product, endpoint in products:
            attributes = product['attributes']
            state = attributes.get('state', 'Unknown')
            lines.append(f"\n{attributes.get('productId')} · {attributes.get('subscriptionPeriod')} · {state}")
            try:
                prices = list(store.apple_us_prices(endpoint, bearer))
                for start, price, preserved in prices:
                    amount = f'${price}' if price is not None else 'price unavailable'
                    lines.append(f"OBSERVED · USA {amount}; start {start or 'unspecified'}; preserved={preserved}")
                if not prices:
                    lines.append('REVIEW · No USA price rows returned. Open Subscription Prices in App Store Connect.')
            except RuntimeError as error:
                lines.append(f'UNVERIFIED · USA price schedule: {error}')
            for relationship, label in [('subscriptionLocalizations', 'localizations'),
                                        ('appStoreReviewScreenshot', 'review screenshot')]:
                try:
                    response = store.request(store.APPLE + endpoint + '/' + relationship, bearer)
                    lines.append(f"{'OBSERVED' if response.get('data') else 'REVIEW'} · {label}: "
                                 f"{'returned' if response.get('data') else 'missing'}")
                except RuntimeError as error:
                    lines.append(f'UNVERIFIED · {label}: {error}')
            if state == 'MISSING_METADATA':
                lines.append('Next step · Open the subscription in App Store Connect and complete its flagged fields.')
        for product in store.apple_offers(app_id, bearer):
            for offer in product['offers']:
                lines.append(f"OBSERVED · {product['product']} / {offer.get('name')}: "
                             f"{offer.get('offerMode')}, eligible={offer.get('customerEligibilities')}, "
                             f"active={offer.get('active')}, production codes={offer.get('productionCodeCount')}")
                if offer.get('productionCodeCount') == 0:
                    lines.append('Next step · Open the offer and create production codes if you intend to distribute it.')
        lines.append('UNVERIFIED · Agreements, tax/banking, paywall wiring, and actual purchase or redemption. '
                     'Check agreements in Business and test the purchase flow on a device.')
    if release:
        lines.append('\nRelease setup')
        for version in store.apple_releases(app_id, bearer):
            lines.append(f"{version['platform']} {version['versionString']} · "
                         f"{version.get('appVersionState') or version.get('appStoreState') or 'Unknown'} · "
                         f"build {version.get('buildId') or 'not attached'}")
        if version_id:
            for locale in store.apple_listing(version_id, bearer):
                sets = locale['sets']
                lines.append(f"{locale['locale']}: " + (', '.join(
                    f"{group['device']} ({len(group['screenshots'])})" for group in sets) or 'no screenshot sets returned'))
        else:
            lines.append('Next step · Load releases and select one to verify screenshot inventory.')
    return '\n'.join(lines)
