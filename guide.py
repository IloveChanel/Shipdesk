"""Tell a new submitter whether the problem is their code or the App Store."""
import project_check
import store

CONFUSED = ('not sure', 'confused', "i'm stuck", 'im stuck', 'i am stuck', 'stuck',
            'how do i', 'help me', "what's wrong", 'what is wrong', 'what is broken')

def wants_guide(question):
    text = (question or '').lower()
    return any(phrase in text for phrase in CONFUSED)

def _steps(lines, title, detail, steps):
    lines.append(f'\n{title}')
    lines.append(detail)
    lines.append('How to fix:')
    lines.extend(f'{number}. {step}' for number, step in enumerate(steps, 1))

def explain(snapshot):
    """Turn a store snapshot and a local folder scan into plain steps."""
    lines = ['SHIPDESK CHECK',
             'ShipDesk reads App Store Connect and the project folder on this computer.',
             'It does not use GitHub or Visual Studio.']
    app = snapshot.get('app') or {}
    bundle = app.get('bundleId') or 'unknown'
    name = app.get('name') or 'this app'
    lines.append(f'\nApp · {name}')
    lines.append(f'App Store bundle id · {bundle}')

    code = snapshot.get('code')
    if not code:
        _steps(lines, 'NOT SURE · Your project folder is not linked.',
               'ShipDesk can see the App Store, but it cannot see your code yet.',
               ['In ShipDesk, keep this app selected.',
                'Click Link folder.',
                'Choose the folder on this PC that contains the app project.',
                'Click I\'m stuck again.'])
    else:
        lines.append(f"Project folder · {code['scanned']} files read")
        bundles = code['bundles']
        if bundle in bundles:
            lines.append(f'PASS · Your code uses the same bundle id as the App Store ({bundle}).')
        elif bundles:
            shown = ', '.join(sorted(bundles)[:4])
            _steps(lines, 'YOUR CODE · The bundle id does not match the App Store.',
                   f'This folder says {shown}. Apple has {bundle}.',
                   ['Open the project on this computer. Xcode is enough. Visual Studio is not required.',
                    f'Set the app bundle id to {bundle}, or link the folder for the app you selected.',
                    'Run I\'m stuck again.'])
        else:
            lines.append('NOT SURE · No bundle id was found in the linked folder. Link the app project, not a docs folder.')

        release = snapshot.get('release') or {}
        store_version = release.get('versionString')
        if store_version and code['versions']:
            if store_version in code['versions']:
                lines.append(f'PASS · Version {store_version} is in your code and on the App Store version you selected.')
            else:
                shown = ', '.join(sorted(code['versions'])[:4])
                _steps(lines, 'YOUR CODE · The version in the project does not match this App Store version.',
                       f'The folder says {shown}. The selected App Store version is {store_version}.',
                       [f'In the project, set the version to {store_version} before you archive.',
                        'Or select the matching release in ShipDesk and run the check again.'])

        apple_ids = set(snapshot.get('product_ids') or [])
        found = code['products']
        for item in sorted(apple_ids & found.keys()):
            lines.append(f'PASS · Subscription {item} is in the App Store and in {found[item]}.')
        missing_in_code = sorted(apple_ids - found.keys())
        extra_in_code = sorted(set(found) - apple_ids)
        if missing_in_code:
            shown = ', '.join(missing_in_code)
            _steps(lines, 'YOUR CODE · The App Store has a subscription id the project does not.',
                   f'Apple will sell {shown}. Those exact characters are not in the project folder.',
                   [f'Search the project folder for {shown}.',
                    'If the code uses a close name, such as annual instead of yearly, they are not the same id.',
                    'Change the code to the Apple id, or create that id in App Store Connect.',
                    'Save, then click I did this.'])
        if extra_in_code:
            _steps(lines, 'YOUR CODE · The project asks for subscription ids Apple did not return.',
                   'The App Store record for this app does not list: ' + ', '.join(extra_in_code),
                   ['Confirm you selected the right app in ShipDesk.',
                    'In App Store Connect, open Subscriptions and create the missing product, or fix the id in code.',
                    'The id must match character for character.'])
        if not apple_ids and not found:
            lines.append('PASS · No subscriptions in the App Store or in this folder. Fine if the app is free.')

    release = snapshot.get('release')
    if not release:
        _steps(lines, 'APP STORE · No release is selected.',
               'ShipDesk cannot check screenshots, the description, or the build until a version is selected.',
               ['Click Load releases.',
                'Select the version you want to submit.',
                'Click I\'m stuck again.'])
        lines.append('\nShipDesk cannot see agreements, tax, banking, age rating, or the privacy form. Check those in App Store Connect if submit stays disabled.')
        return '\n'.join(lines)

    state = release.get('appVersionState') or release.get('appStoreState') or 'Unknown'
    version_label = f"{release.get('platform', 'App')} {release.get('versionString', '')}".strip()
    lines.append(f'\nSelected version · {version_label} · {state}')
    build = snapshot.get('build')
    if not release.get('buildId'):
        _steps(lines, 'APP STORE · This version has no build attached.',
               'Apple cannot review a version with no build. Your source folder is not the upload.',
               ['Archive the app from Xcode on this computer.',
                'Upload it to App Store Connect and wait until the build says Valid.',
                'Open the version and select that build.',
                'Run this check again.'])
    elif build and build.get('processingState') in ('FAILED', 'INVALID'):
        _steps(lines, 'YOUR CODE · Apple rejected the uploaded build.',
               f"Processing state: {build.get('processingState')}. The store received a build and marked it unusable.",
               ['Read the email from App Store Connect. It names the signing or icon problem.',
                'Fix that in the project, archive again, and upload a new build.',
                'Select the new build on this version.'])
    elif build and build.get('processingState') == 'PROCESSING':
        lines.append('APP STORE · The build is still processing. Wait until it says Valid, then run this check again.')
    else:
        lines.append('PASS · A build is attached to this version.')

    if state in ('REJECTED', 'METADATA_REJECTED'):
        _steps(lines, 'APP STORE · Apple rejected this version.',
               'The version state is ' + state + '. The fix is in App Store Connect unless the email says the binary crashed.',
               ['Open App Store Connect → this app → the rejected version.',
                'Read Resolution Center. Follow only the items Apple listed.',
                'Reply in Resolution Center after the change.',
                'Submit again, then run this check.'])
    elif state == 'INVALID_BINARY':
        _steps(lines, 'YOUR CODE · Apple marked the binary invalid.',
               'The upload failed Apple\'s build check.',
               ['Open the email from Apple. It names the missing icon, entitlement, or signature.',
                'Fix it in the project and upload a new archive.',
                'Attach the new build to this version.'])

    for locale in snapshot.get('locales') or []:
        language = locale.get('locale') or 'a language'
        if not locale.get('description'):
            _steps(lines, f'APP STORE · {language} has no description.',
                   'Reviewers and customers need the description on the version.',
                   ['App Store Connect → this app → this version.',
                    f'Open the {language} localization.',
                    'Fill Description. Save.',
                    'Run this check again.'])
        if not locale.get('keywords'):
            lines.append(f'APP STORE · {language} keywords are empty. Open that localization and add keywords, separated by commas.')
        if not locale.get('supportUrl'):
            _steps(lines, f'APP STORE · {language} has no support URL.',
                   'Apple requires a support link before you can submit.',
                   ['Open the version localization.',
                    'Paste a real support page URL in Support URL.',
                    'Save.'])
        sets = locale.get('sets') or []
        if not sets or not any(group.get('screenshots') for group in sets):
            _steps(lines, f'APP STORE · {language} has no screenshots.',
                   'Your code does not supply store screenshots. They are uploaded in App Store Connect.',
                   ['Open this version in App Store Connect.',
                    f'Scroll to Screenshots for {language}.',
                    'Upload the iPhone size Apple shows on that page.',
                    'You can check pixel sizes in ShipDesk → Screenshot Studio first.'])
        else:
            count = sum(len(group.get('screenshots') or []) for group in sets)
            lines.append(f'PASS · {language} has {count} screenshots on the App Store.')

    review = snapshot.get('review')
    if review is None:
        _steps(lines, 'APP STORE · Review contact details are missing.',
               'Apple needs a person to call if the reviewer gets stuck.',
               ['Open the version → App Review Information.',
                'Enter your first name, last name, phone, and email.',
                'If the app needs a login, turn on demo account and enter a working username and password.',
                'Save.'])
    else:
        missing = [label for key, label in (
            ('contactFirstName', 'first name'), ('contactLastName', 'last name'),
            ('contactPhone', 'phone'), ('contactEmail', 'email'),
        ) if not (review.get(key) or '').strip()]
        if missing:
            _steps(lines, 'APP STORE · Review contact is incomplete.',
                   'Missing: ' + ', '.join(missing) + '.',
                   ['Open the version → App Review Information.',
                    'Fill ' + ', '.join(missing) + '.',
                    'Save.'])
        elif review.get('demoAccountRequired') and not (review.get('demoAccountName') or '').strip():
            _steps(lines, 'APP STORE · A demo login is required but empty.',
                   'The reviewer cannot sign in.',
                   ['Open App Review Information.',
                    'Enter a demo username and password that works.',
                    'Save.'])
        else:
            lines.append('PASS · Review contact details are filled in.')

    for product in snapshot.get('subscriptions') or []:
        state = product.get('state') or 'unknown'
        product_id = product.get('product') or 'a subscription'
        if state == 'MISSING_METADATA':
            _steps(lines, f'APP STORE · Subscription {product_id} is missing store details.',
                   'The id can be correct in your code and still be unfinished in App Store Connect.',
                   ['App Store Connect → this app → Subscriptions.',
                    f'Open {product_id}.',
                    'Fill every field marked missing, including the review screenshot and a price.',
                    'Save, then run this check again.'])
        elif product.get('price') is False:
            _steps(lines, f'APP STORE · Subscription {product_id} has no US price.',
                   'Apple will not sell it until a price is saved.',
                   ['Open the subscription.',
                    'Open Subscription Prices.',
                    'Add a price for the United States.',
                    'Save.'])

    lines.append('\nNOT SURE · Agreements, tax, banking, age rating, and the privacy form.')
    lines.append('How to fix:')
    lines.append('1. In App Store Connect, open Business and accept any agreement in red.')
    lines.append('2. Open App Privacy on this app and finish the privacy questions.')
    lines.append('3. Open the version and set the age rating if it is still empty.')
    lines.append('4. Those screens are not fully visible to this check. Look at them yourself before you submit.')
    return '\n'.join(lines)

def problems(text):
    """Split a check into one confirmable problem at a time."""
    items = []
    current = None

    def close():
        nonlocal current
        if current and current['steps']:
            items.append(current)
        current = None

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        head, _, title = line.partition(' · ')
        if head in ('YOUR CODE', 'APP STORE', 'NOT SURE') and title:
            close()
            current = {'where': head, 'title': title, 'detail': '', 'steps': []}
            continue
        if line.startswith('PASS') or line.startswith('SHIPDESK') or line.startswith('Step '):
            close()
            continue
        if current is None:
            continue
        if line.startswith('How to fix'):
            continue
        number, _, rest = line.partition('. ')
        if number.isdigit() and rest:
            current['steps'].append(rest)
        elif not current['detail']:
            current['detail'] = line
    close()
    return items

def one_step(text, index=0, help_open=False):
    items = problems(text)
    if not items:
        passed = [line for line in text.splitlines() if line.startswith('PASS')]
        body = 'Nothing to fix from this check.'
        if passed:
            body += '\n' + '\n'.join(passed)
        return body, items
    index = max(0, min(index, len(items) - 1))
    item = items[index]
    where = {
        'YOUR CODE': 'This one is your code.',
        'APP STORE': 'This one is the App Store. Your code is not the problem.',
        'NOT SURE': 'ShipDesk cannot see this screen. You have to look.',
    }[item['where']]
    lines = [f'Step {index + 1} of {len(items)}', where, item['title']]
    if item['detail']:
        lines.append(item['detail'])
    lines.extend(['', 'Do this now:', item['steps'][0]])
    if help_open:
        lines.extend(['', 'Still stuck? Do these in order:'])
        lines.extend(f'{number}. {step}' for number, step in enumerate(item['steps'], 1))
    else:
        lines.extend(['', 'When that is done, click I did this.', 'If you are lost, click I can\'t figure this out.'])
    return '\n'.join(lines), items

def diagnose(app_id, version_id, bearer, folder):
    if not app_id:
        return explain({'app': {}, 'release': None, 'code': None})
    app = store.apple_app(app_id, bearer)
    releases = store.apple_releases(app_id, bearer)
    release = next((row for row in releases if row['id'] == version_id), None)
    if release is None and releases:
        release = next((row for row in releases if 'PREPARE' in (row.get('appVersionState') or '')), releases[0])
    locales = []
    review = None
    build = None
    if release:
        locales = store.apple_version_localizations(release['id'], bearer)
        listed = {row['locale']: row for row in store.apple_listing(release['id'], bearer)}
        for locale in locales:
            locale['sets'] = (listed.get(locale['locale']) or {}).get('sets') or []
        review = store.apple_review_detail(release['id'], bearer)
        build = store.apple_build(release.get('buildId'), bearer)
    products = []
    product_ids = []
    for product, endpoint in store.apple_subscription_setup(app_id, bearer):
        attributes = product['attributes']
        product_ids.append(attributes.get('productId'))
        prices = list(store.apple_us_prices(endpoint, bearer))
        products.append({'product': attributes.get('productId'), 'state': attributes.get('state'),
                         'price': bool(prices)})
    code = project_check.scan_project(folder, [item for item in product_ids if item]) if folder else None
    return explain({
        'app': app, 'release': release, 'locales': locales, 'review': review, 'build': build,
        'subscriptions': products, 'product_ids': [item for item in product_ids if item], 'code': code,
    })
