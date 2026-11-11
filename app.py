"""ShipDesk desktop presentation layer."""
import asyncio
import json
import os
from pathlib import Path
from types import SimpleNamespace

import flet as ft

import ai_help
import audit
import billing
import project_check
import screenshots
import store

BG, CARD, TEXT, MUTED, ACCENT = '#0A0A0C', '#16161A', '#FFFFFF', '#B7B4AF', '#FF6B00'
EDGE = '#2D2D30'
RADIUS = 10

async def main(page: ft.Page):
    page.title = 'ShipDesk Workspace'
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = BG
    page.padding = 0
    page.window.width = 1220
    page.window.height = 750
    page.window.min_width = 780
    page.window.min_height = 620
    directory = Path(os.environ.get('LOCALAPPDATA') or Path.home()) / 'ShipDesk'

    def read(name):
        try:
            value = json.loads((directory / name).read_text(encoding='utf-8'))
            return value if isinstance(value, dict) else {}
        except (OSError, ValueError):
            return {}

    def save(name, value):
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / name
        pending = target.with_suffix('.tmp')
        pending.write_text(json.dumps(value), encoding='utf-8')
        pending.replace(target)

    saved = read('apple.json')
    links = read('projects.json')
    picker = ft.FilePicker()
    clipboard = ft.Clipboard()
    apps, versions = {}, {}
    busy = False

    input_border = {
        ft.ControlState.DEFAULT: ft.OutlineInputBorder(border_radius=RADIUS, side=ft.BorderSide(1, EDGE)),
        ft.ControlState.FOCUSED: ft.OutlineInputBorder(border_radius=RADIUS, side=ft.BorderSide(1.5, ACCENT)),
    }

    def field(label, value='', **options):
        return ft.TextField(label=label, value=value, bgcolor=CARD, border=input_border, **options)

    def dropdown(**options):
        return ft.Dropdown(bgcolor=CARD, fill_color=CARD, filled=True, border=input_border, **options)

    def label(value, size=14, color=TEXT):
        return ft.Text(value, size=size, color=color)

    def surface(content, expand=None, padding=20):
        return ft.Container(content=content, bgcolor=CARD,
                            border=ft.Border.all(1, EDGE), border_radius=RADIUS,
                            shadow=ft.BoxShadow(color='#75000000', blur_radius=14, offset=ft.Offset(0, 4)),
                            padding=padding, expand=expand)

    def card(*controls, expand=None):
        return surface(ft.Column(list(controls), spacing=12, expand=True, horizontal_alignment=ft.CrossAxisAlignment.STRETCH), expand=expand)

    def button(title, handler, primary=False):
        return ft.Button(
            content=title, on_click=handler, color=TEXT,
            bgcolor=ACCENT if primary else CARD,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=RADIUS),
                side=ft.BorderSide(1, ACCENT if primary else EDGE),
                elevation=0,
            ),
        )

    key_id = field('Apple key ID', saved.get('ASC_KEY_ID', ''))
    issuer = field('Issuer ID · team keys only', saved.get('ASC_ISSUER_ID', ''))
    key_path = field('Apple private key file', saved.get('ASC_KEY_PATH', ''))
    provider = dropdown(label='AI provider', value='Local only',
                           options=[ft.DropdownOption(name) for name in ('Local only', 'OpenAI', 'Gemini')])
    openai = field('OpenAI API key', password=True)
    gemini = field('Gemini API key', password=True)
    app = dropdown(label='App', hint_text='Select an app', expand=2)
    version = dropdown(label='Release version', hint_text='Select a release', expand=1)
    status = label('Connect your Apple account', color=MUTED)
    activity = ft.Column([label('No checks run in this session.', 12, MUTED)], spacing=8)
    recent_checks = []
    apps_total = ft.Text('—', size=29, color=ACCENT, weight=ft.FontWeight.BOLD)

    def record_check(name, success):
        recent_checks.insert(0, (name, success))
        del recent_checks[4:]
        activity.controls = [
            ft.Row([ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE if ok else ft.Icons.ERROR_OUTLINE,
                            size=15, color=ACCENT),
                    ft.Text(f'{title} · {"done" if ok else "failed"}', size=12, color=TEXT, expand=True)])
            for title, ok in recent_checks
        ]
    source = ft.Text('No source folder linked', size=13, color=MUTED, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
    prompt = field('What would you like to verify?', 'Check subscription pricing and offer codes',
                   multiline=True, min_lines=2, max_lines=3, expand=True)
    report = SimpleNamespace(value='Choose an app and run a check.')
    report_feed = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO, spacing=8)

    def render_report():
        text = report.value or ''
        blocks = []
        for line in text.splitlines():
            if not line.strip():
                continue
            marker = line.partition(' · ')[0]
            color = {'PASS': '#8EE5BC', 'REVIEW': '#FFD298', 'UNVERIFIED': '#FFD298'}.get(marker, TEXT)
            if line in ('WHAT TO DO NEXT', 'FINDINGS') or line.endswith(' EXPLANATION'):
                blocks.append(ft.Text(line, size=12, color=ACCENT, weight=ft.FontWeight.BOLD))
            else:
                blocks.append(ft.Text(line, size=14, color=color, selectable=True))
        report_feed.controls = blocks
    play_report = field('Google Play findings', multiline=True, read_only=True, expand=True)
    media_report = field('Screenshot results', multiline=True, read_only=True, expand=True)

    async def run(output, work, apply=None, name=None, licensed=True):
        nonlocal busy
        if busy:
            return
        busy = True
        output.value = 'Checking…'
        if output is report:
            render_report()
        page.update()
        try:
            if licensed:
                details = await asyncio.to_thread(billing.read_subscription, (license_input.value or '').strip())
                show_subscription(details)
                billing.require_active(details)
            result = await asyncio.to_thread(work)
            output.value = apply(result) if apply else (
                result if isinstance(result, str) else json.dumps(result, indent=2))
        except Exception as error:
            if name:
                record_check(name, False)
            output.value = f'Could not complete the check. {error}'
        else:
            if name:
                record_check(name, True)
        finally:
            busy = False
            if output is report:
                render_report()
            page.update()

    def credentials():
        path = (key_path.value or '').strip()
        key = store.apple_key_id(path) or (key_id.value or '').strip().upper()
        if not key or not path:
            raise ValueError('Choose your Apple .p8 file and enter its key ID in Settings.')
        return key, (issuer.value or '').strip(), path

    def sync_source():
        source.value = links.get(app.value, '') or 'No source folder linked'

    def select_app(event=None):
        versions.clear()
        version.options = []
        version.value = None
        sync_source()
        page.update()

    async def connect(event=None):
        if busy:
            return
        def work():
            config = credentials()
            return config, store.apple_apps(store.token(*config))

        def apply(result):
            config, rows = result
            previous_app = app.value
            apps.clear()
            apps.update((item['id'], item['attributes']) for item in rows)
            app.options = [ft.DropdownOption(key, f"{info['name']} · {info.get('bundleId', '')}")
                           for key, info in apps.items()]
            app.value = previous_app if previous_app in apps else next(iter(apps), None)
            select_app()
            status.value = f'Connected · {len(apps)} apps'
            apps_total.value = str(len(apps))
            save('apple.json', dict(zip(('ASC_KEY_ID', 'ASC_ISSUER_ID', 'ASC_KEY_PATH'), config)))
            return 'Select an app and ask ShipDesk a question.'
        status.value = 'Checking connection…'
        await run(report, work, apply, name='Apple connection', licensed=False)
        if status.value == 'Checking connection…':
            status.value = 'Connection unverified · see report'
            page.update()

    async def apple_action(kind):
        app_id, release_id = app.value, version.value
        question = prompt.value or ''
        folder = links.get(app_id)
        selected_provider = provider.value
        ai_key = (openai.value if selected_provider == 'OpenAI' else gemini.value) or ''

        def work():
            bearer = store.token(*credentials())
            if kind == 'audit':
                return audit.audit_apple(bearer)
            if not app_id:
                raise ValueError('Connect Apple and select an app first.')
            if kind == 'versions':
                return store.apple_releases(app_id, bearer)
            if kind == 'listing':
                if not release_id:
                    raise ValueError('Load and select a release first.')
                return store.apple_listing(release_id, bearer)
            if kind == 'offers':
                return store.apple_offers(app_id, bearer)
            result = audit.verify_request(question, app_id, release_id, bearer)
            explanation = ''
            if selected_provider in ('OpenAI', 'Gemini') and ai_key:
                try:
                    explanation = ai_help.explain(ai_key, question, result, selected_provider)
                except (OSError, ValueError):
                    explanation = f'{selected_provider} could not respond. Check API access and quota.'
            if folder:
                ids = [row['attributes']['productId'] for row, _ in store.apple_subscription_setup(app_id, bearer)]
                result += '\n\n' + project_check.compare_subscriptions(folder, ids)
            steps = [line.partition('·')[2].strip() for line in result.splitlines()
                     if line.startswith('Next step ·')]
            if steps:
                result = 'WHAT TO DO NEXT\n' + '\n'.join(
                    f'{i}. {step}' for i, step in enumerate(dict.fromkeys(steps), 1)) + '\n\nFINDINGS\n' + result
            return result + (f'\n\n{selected_provider.upper()} EXPLANATION\n{explanation}' if explanation else '')

        def apply(rows):
            if app.value != app_id:
                return 'The selected app changed. Load its releases to continue.'
            versions.clear()
            versions.update((row['id'], row) for row in rows)
            version.options = [ft.DropdownOption(key, f"{row['versionString']} · {row['platform']}")
                               for key, row in versions.items()]
            version.value = next(iter(versions), None)
            return f'{len(rows)} releases loaded.'

        await run(report, work, apply if kind == 'versions' else None,
                  name={'audit': 'Account audit', 'versions': 'Release lookup', 'listing': 'Screenshot inspection',
                        'offers': 'Offer codes', 'verify': 'Verification'}[kind])

    def action(kind):
        async def invoke(event):
            await apple_action(kind)
        return invoke

    async def browse_key(event):
        files = await picker.pick_files(allowed_extensions=['p8'], file_type=ft.FilePickerFileType.CUSTOM)
        if files and files[0].path:
            key_path.value = files[0].path
            key_id.value = store.apple_key_id(key_path.value) or key_id.value
            page.update()

    async def link(event):
        app_id = app.value
        if not app_id:
            report.value = 'Select an app before linking a project.'
            render_report()
        else:
            folder = await picker.get_directory_path()
            if folder:
                links[app_id] = folder
                save('projects.json', links)
                sync_source()
        page.update()

    async def unlink(event):
        if app.value in links:
            del links[app.value]
            save('projects.json', links)
            sync_source()
            page.update()

    async def paste(event):
        text = await clipboard.get()
        if text:
            prompt.value = text
            page.update()

    async def copy(event):
        await clipboard.set(report.value or '')

    async def export_report(event):
        path = await picker.save_file(file_name='ShipDesk-report.txt')
        if path:
            Path(path).write_text(report.value or '', encoding='utf-8')

    app.on_select = select_app
    def fill_prompt(question):
        def apply(event):
            prompt.value = question
            page.update()
        return apply

    apple_main = ft.Column([
        surface(ft.Column([
            ft.Row([app, version], spacing=12),
            ft.Row([button('Connect', connect), button('Load releases', action('versions')),
                    button('Screenshots', action('listing')), button('Offer codes', action('offers')),
                    button('Audit account', action('audit'))], spacing=7, wrap=True),
            status,
        ], spacing=8), padding=14),
        card(
            ft.Row([
                ft.Text('Verification report', size=18, color=TEXT, weight=ft.FontWeight.BOLD, expand=True),
                ft.Row([button('Copy', copy), button('Export', export_report)], spacing=7),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Divider(height=1, color=EDGE), report_feed,
            expand=True,
        ),
        surface(ft.Column([
            ft.Row([
                ft.Text('Ask ShipDesk', size=16, color=TEXT, weight=ft.FontWeight.BOLD),
                button('Subscriptions', fill_prompt('Check subscription pricing and offer codes')),
                button('Release assets', fill_prompt('Check release and screenshots')),
            ], spacing=7, wrap=True),
            ft.Row([prompt, button('Paste', paste), button('Run check', action('verify'), True)],
                   spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Row([ft.Icon(ft.Icons.FOLDER_OUTLINED, size=16, color=MUTED),
                    ft.Container(content=source, expand=True),
                    button('Link folder', link), button('Unlink', unlink)], spacing=8),
        ], spacing=7, horizontal_alignment=ft.CrossAxisAlignment.STRETCH), padding=14),
    ], spacing=10, expand=True, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
    insights = ft.Column([
        card(label('Connected apps', 13, MUTED), apps_total),
        card(label('Session activity', 15), activity),
    ], width=190, spacing=10)
    apple_page = ft.Row([apple_main, insights], spacing=12, expand=True,
                        vertical_alignment=ft.CrossAxisAlignment.STRETCH)

    def fit_workspace(event=None):
        insights.visible = (getattr(page, 'width', None) or page.window.width) >= 1180
        if event is not None:
            page.update()

    page.on_resize = fit_workspace
    fit_workspace()
    render_report()

    async def setup_connect(event):
        navigate('Apple workspace')
        await connect()

    license_input = field('ShipDesk license', read('license.json').get('key', ''), password=True)
    billing_status = label('Check your purchase date, plan price, and renewal or expiration date.', color=MUTED)
    manage = ft.TextButton(content='Manage billing', visible=False)
    subscribe = ft.TextButton(content='Subscribe or renew', url='https://www.thetrendsetteragency.com/shipdesk/')

    def show_subscription(details):
        billing_status.value = billing.format_subscription(details)
        portal = details.get('portal_url')
        manage.url = portal
        manage.visible = bool(portal)
        subscribe.visible = not details.get('active') and details.get('status') not in ('past_due', 'unpaid', 'incomplete')

    async def check_subscription(event):
        license_key = (license_input.value or '').strip()
        def apply(details):
            show_subscription(details)
            try:
                save('license.json', {'key': license_key})
            except OSError:
                return billing_status.value + '\nLicense could not be saved locally.'
            return billing_status.value
        await run(billing_status, lambda: billing.read_subscription(license_key), apply, licensed=False)

    settings_page = ft.Column([
        card(ft.Row([label('App Store Connect', 20), button('Get API credentials', lambda event: navigate('API setup'))], wrap=True), key_id, issuer,
             ft.Row([key_path, button('Browse', browse_key)], wrap=True),
             button('Connect and open workspace', setup_connect, True)),
        card(label('Subscription', 20), license_input,
             ft.Row([button('Verify and save license', check_subscription), manage, subscribe], wrap=True), billing_status),
        card(label('Optional AI explanations', 20), provider, openai, gemini,
             label('Provider keys are held for this session. The selected provider receives your question and store findings.', color=MUTED)),
    ], spacing=16, scroll=ft.ScrollMode.AUTO, expand=True)

    package = field('Android package name')
    play_token = field('Google Play access token', password=True)

    async def play(event):
        await run(play_report, lambda: audit.audit_google(package.value, play_token.value))

    async def read_play(event):
        await run(play_report, lambda: store.play_listing(package.value, play_token.value))

    google_page = ft.Column([card(button('Get an access token', lambda event: navigate('API setup')), package, play_token,
                                 ft.Row([button('Read listing', read_play), button('Audit listing', play, True)]),
                                 play_report, expand=True)], expand=True)

    old = field('Previous screenshots folder')
    new = field('New screenshots folder')
    slot = dropdown(label='Apple size preset', value=next(iter(screenshots.APPLE_SLOTS)),
                       options=[ft.DropdownOption(name) for name in screenshots.APPLE_SLOTS])

    def browse_folder(control):
        async def browse(event):
            path = await picker.get_directory_path()
            if path:
                control.value = path
                page.update()
        return browse

    async def compare(event):
        if not old.value or not new.value:
            media_report.value = 'Select both screenshot folders first.'
            page.update()
            return
        await run(media_report, lambda: screenshots.compare(
            screenshots.inventory(old.value), screenshots.inventory(new.value)))

    async def size(event):
        await run(media_report, lambda: screenshots.check_size(new.value, screenshots.APPLE_SLOTS[slot.value]))

    def export_screens(resize):
        async def export(event):
            if not new.value:
                media_report.value = 'Select the new screenshots folder first.'
                page.update()
                return
            target = await picker.save_file(file_name='ShipDesk-screenshots.zip')
            if target:
                await run(media_report, lambda: screenshots.resize_set(new.value, target, screenshots.APPLE_SLOTS[slot.value])
                          if resize else f'Exported {screenshots.export(new.value, target)} screenshots.')
        return export

    studio = ft.Column([card(ft.Row([old, button('Browse', browse_folder(old))]),
                             ft.Row([new, button('Browse', browse_folder(new))]), slot,
                             ft.Row([button('Compare', compare), button('Check sizes', size),
                                     button('Export ZIP', export_screens(False)),
                                     button('Resize to ZIP', export_screens(True), True)], wrap=True),
                             media_report, expand=True)], expand=True)

    def guide_step(number, title, detail):
        return ft.Row([
            ft.Container(label(str(number), 13, ACCENT), width=30, height=30,
                         alignment=ft.Alignment.CENTER, bgcolor='#38241A', border_radius=8),
            ft.Column([ft.Text(title, size=15, color=TEXT, weight=ft.FontWeight.BOLD),
                       label(detail, 13, MUTED)], spacing=4, expand=True),
        ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.START)

    def external(title, url):
        return ft.TextButton(content=title, url=url, icon=ft.Icons.OPEN_IN_NEW)

    api_setup = ft.Column([
        card(
            ft.Row([ft.Icon(ft.Icons.APPLE, color=ACCENT), label('Apple App Store Connect', 20)]),
            guide_step(1, 'Choose an individual key or a team key',
                       'For an individual key, open your profile in App Store Connect and select Generate Key under Individual API Key. '
                       'For a team key, go to Users and Access → Integrations → App Store Connect API → Team Keys. '
                       'If API access has not been enabled, the Account Holder must request access first.'),
            guide_step(2, 'Download the .p8 file',
                       'Save the private key file on your computer. Apple lets you download it once. '
                       'Copy its Key ID and, for a team key, the Issuer ID shown above the key list.'),
            guide_step(3, 'Connect in ShipDesk',
                       'Open Settings and choose the .p8 file with Browse. Enter your Key ID if it was not filled in. '
                       'Leave Issuer ID empty for an individual key. Select Connect and open workspace, then check that your apps appear.'),
            ft.Row([button('Open ShipDesk Settings', lambda event: navigate('Settings'), True),
                    external('Apple instructions', 'https://developer.apple.com/help/app-store-connect/get-started/app-store-connect-api')], wrap=True),
        ),
        card(
            ft.Row([ft.Icon(ft.Icons.ANDROID, color=ACCENT), label('Google Play Developer API', 20)]),
            guide_step(1, 'Enable the API and grant app access',
                       'Enable Google Play Android Developer API in a Google Cloud project. '
                       'The Google account you authorize needs access to the target app in Play Console.'),
            guide_step(2, 'Get a short-lived OAuth access token',
                       'For a manual connection, create a Web application OAuth client in Google Cloud. '
                       'Add https://developers.google.com/oauthplayground as a redirect URI. In Google’s OAuth Playground, '
                       'enable Use your own OAuth credentials and enter that client ID and secret. '
                       'Authorize https://www.googleapis.com/auth/androidpublisher, then exchange the authorization code for tokens.'),
            guide_step(3, 'Read your listing',
                       'In ShipDesk → Google Play, enter your Android package name and paste the Access token. '
                       'Select Read listing or Audit listing. When the token expires, get a new one.'),
            ft.Row([button('Open Google Play workspace', lambda event: navigate('Google Play'), True),
                    external('Google instructions', 'https://developers.google.com/android-publisher/getting_started'),
                    external('OAuth Playground', 'https://developers.google.com/oauthplayground')], wrap=True),
        ),
    ], spacing=14, scroll=ft.ScrollMode.AUTO, expand=True,
       horizontal_alignment=ft.CrossAxisAlignment.STRETCH)

    views = {
        'Apple workspace': ('App Store Connect', 'Verify subscriptions, releases and screenshots.', apple_page),
        'Google Play': ('Google Play', 'Review Android listing metadata.', google_page),
        'Screenshot studio': ('Screenshot Studio', 'Compare, validate and export release assets.', studio),
        'API setup': ('Connect your stores', 'Get the credentials ShipDesk needs and verify each connection.', api_setup),
        'Settings': ('Welcome to ShipDesk', 'A desktop release workspace by The Trendsetter Agency.', settings_page),
    }
    title = ft.Text('', size=27, color=TEXT, weight=ft.FontWeight.BOLD)
    subtitle = ft.Text('', size=14, color=MUTED, style=ft.TextStyle(letter_spacing=0.35))
    header = surface(ft.Row([
        ft.Container(width=3, height=43, bgcolor=ACCENT, border_radius=3),
        ft.Column([title, subtitle], spacing=4, expand=True),
        button('API setup', lambda event: navigate('API setup')),
    ], spacing=14), padding=16)
    host = ft.Container(expand=True)
    nav = ft.Column(spacing=10)
    icons = {'Apple workspace': ft.Icons.APPLE, 'Google Play': ft.Icons.ANDROID,
             'Screenshot studio': ft.Icons.PHOTO_LIBRARY_OUTLINED,
             'Settings': ft.Icons.SETTINGS_OUTLINED, 'API setup': ft.Icons.KEY_OUTLINED}

    def nav_item(name, selected):
        return ft.Container(
            content=ft.Row([ft.Container(width=3, height=20, border_radius=2,
                                         bgcolor=ACCENT if selected else CARD),
                            ft.Icon(icons[name], size=19, color=ACCENT if selected else MUTED),
                            ft.Text(name, size=13, color=ACCENT if selected else MUTED, expand=True, max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS)],
                           spacing=11, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=8, border_radius=RADIUS,
            bgcolor='#211A17' if selected else CARD,
            ink=True, on_click=lambda event: navigate(name))

    def navigate(name):
        title.value, subtitle.value, host.content = views[name]
        nav.controls = [nav_item(item, item == name) for item in views]
        page.update()

    brand = ft.Row([
        ft.Container(label('S', 21, BG), width=35, height=35,
                     alignment=ft.Alignment.CENTER, border_radius=RADIUS, bgcolor=ACCENT),
        ft.Text('ShipDesk', size=20, weight=ft.FontWeight.BOLD, color=TEXT),
    ], spacing=10)
    side = surface(ft.Column([brand, ft.Container(height=14), nav, ft.Container(expand=True),
                            label('The Trendsetter Agency', 11, MUTED)]), padding=11)
    side.width = 196
    workspace = ft.Container(content=ft.Column([header, host], spacing=10, horizontal_alignment=ft.CrossAxisAlignment.STRETCH), expand=True)
    page.add(ft.Container(
        content=ft.Row([side, workspace], spacing=10, expand=True,
                       vertical_alignment=ft.CrossAxisAlignment.STRETCH),
        padding=10, expand=True,
    ))
    navigate('Apple workspace' if saved else 'Settings')
    if saved and Path(key_path.value).is_file():
        await connect()

if __name__ == '__main__':
    ft.run(main, view=ft.AppView.FLET_APP)
