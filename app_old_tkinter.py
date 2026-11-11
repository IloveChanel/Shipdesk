"""ShipDesk native desktop workspace."""
import json
import os
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, ttk
from tkinter.scrolledtext import ScrolledText

import ai_help
import audit
import project_check
import screenshots
import store

BG, PANEL, INK, MUTED, ACCENT = '#0D1022', '#1B203B', '#F3F4FF', '#BFC9E4', '#6DE2F7'
RAIL, RAIL_INK, RAIL_MUTED, SELECTED = '#12162D', '#F3F6FF', '#B7C5DF', '#33395E'
BORDER, INPUT = '#49577F', '#131931'

def main():
    root = tk.Tk()
    root.title('ShipDesk')
    root.geometry('1240x800')
    root.minsize(980, 660)
    root.configure(bg=BG)
    style = ttk.Style(root)
    style.theme_use('clam')
    style.configure('.', background=PANEL, foreground=INK, fieldbackground=INPUT,
                    font=('Segoe UI', 10), bordercolor=BORDER,
                    lightcolor=PANEL, darkcolor=PANEL)
    style.configure('TButton', padding=(13, 8), relief='flat', background='#303653')
    style.map('TButton', background=[('active', '#42496D')])
    style.configure('Primary.TButton', background=ACCENT, foreground='#101A31')
    style.map('Primary.TButton', background=[('active', '#A0F0FF')])
    style.configure('Vertical.TScrollbar', background='#373E61',
                    troughcolor=INPUT, arrowcolor=MUTED)
    style.configure('Section.TLabel', font=('Segoe UI', 12, 'bold'))
    style.configure('Status.TLabel', foreground='#86EBC4')
    style.configure('TEntry', insertcolor=INK, padding=7)
    style.configure('TCombobox', padding=7, arrowcolor=ACCENT)
    style.map('TCombobox', fieldbackground=[('readonly', INPUT)],
              foreground=[('readonly', INK)], selectbackground=[('readonly', INPUT)],
              selectforeground=[('readonly', INK)])
    root.option_add('*TCombobox*Listbox.background', PANEL)
    root.option_add('*TCombobox*Listbox.foreground', INK)
    rail = tk.Frame(root, bg=RAIL, width=206)
    rail.pack(side='left', fill='y')
    rail.pack_propagate(False)
    brand = tk.Frame(rail, bg=RAIL)
    brand.pack(fill='x', padx=17, pady=(28, 33))
    tk.Label(brand, text='S', bg='#5470E8', fg='white', width=2, pady=4,
             font=('Segoe UI', 15, 'bold')).pack(side='left')
    tk.Label(brand, text='ShipDesk', fg=RAIL_INK, bg=RAIL,
             font=('Segoe UI', 19, 'bold')).pack(side='left', padx=9)
    tk.Label(rail, text='The Trendsetter Agency', fg=RAIL_MUTED, bg=RAIL,
             font=('Segoe UI', 9)).pack(side='bottom', anchor='w', padx=21, pady=18)
    workspace = tk.Frame(root, bg=BG, padx=26, pady=22)
    workspace.pack(side='left', fill='both', expand=True)
    banner = tk.Canvas(workspace, height=121, bg=BG, highlightthickness=0)
    banner.pack(fill='x', pady=(0, 12))
    heading_text = ''
    subtitle_text = ''

    def draw_banner(event=None):
        width = banner.winfo_width()
        banner.delete('all')
        for index in range(36):
            ratio = index / 35
            color = '#%02x%02x%02x' % (14 + int(26 * ratio), 18 + int(6 * ratio), 42 + int(43 * ratio))
            banner.create_rectangle(width * index / 36, 0, width * (index + 1) / 36 + 1,
                                    121, fill=color, outline='')
        edge = width - 22
        for offset in (0, 31, 63):
            x = edge - offset
            banner.create_line(x - 142, 102, x - 60, 22, x, 52,
                               fill=('#306C9A' if offset else '#765DB6'), width=1)
            banner.create_oval(x - 64, 18, x - 56, 26, fill='#6DE2F7', outline='')
        banner.create_line(edge - 198, 89, edge - 155, 89, edge - 124, 59,
                           fill='#AE5CA9', width=2)
        banner.create_text(23, 40, text=heading_text, anchor='w', fill=INK,
                           font=('Segoe UI', 28, 'bold'))
        banner.create_text(25, 87, text=subtitle_text, anchor='w', fill=MUTED,
                           font=('Segoe UI', 10), width=max(320, width - 225))

    banner.bind('<Configure>', draw_banner)
    content = tk.Frame(workspace, bg=BG)
    content.pack(fill='both', expand=True)
    content.rowconfigure(0, weight=1)
    content.columnconfigure(0, weight=1)
    output = queue.Queue()
    state = {'apps': [], 'versions': [], 'busy': False}
    navigation = []
    routes = {}
    activate_initial_pane = None

    def pane(name, heading, description):
        nonlocal activate_initial_pane
        frame = ttk.Frame(content, padding=18, relief='solid', borderwidth=1)
        frame.grid(row=0, column=0, sticky='nsew')

        def activate():
            frame.tkraise()
            nonlocal heading_text, subtitle_text
            heading_text, subtitle_text = heading, description
            draw_banner()
            for item in navigation:
                selected = item is button
                item.configure(bg=SELECTED if selected else RAIL,
                               fg=RAIL_INK if selected else RAIL_MUTED)

        button = tk.Button(rail, text=name, anchor='w', padx=15, pady=10,
                           relief='flat', borderwidth=0, bg=RAIL, fg=RAIL_MUTED,
                           activebackground=SELECTED, activeforeground=RAIL_INK,
                           font=('Segoe UI', 11), command=activate)
        button.pack(fill='x', padx=12, pady=3)
        navigation.append(button)
        routes[name] = activate
        if len(navigation) == 1:
            activate_initial_pane = activate
        return frame

    settings = Path(os.environ.get('LOCALAPPDATA') or Path.home()) / 'ShipDesk' / 'apple.json'
    try:
        saved = json.loads(settings.read_text(encoding='utf-8'))
        if not isinstance(saved, dict):
            saved = {}
    except (OSError, ValueError):
        saved = {}

    def field(parent, title, env='', secret=False, folder=False, file=False):
        row = ttk.Frame(parent)
        row.pack(fill='x', pady=3)
        ttk.Label(row, text=title, width=20).pack(side='left')
        value = tk.StringVar(value=os.environ.get(env, saved.get(env, '')) if env else '')
        ttk.Entry(row, textvariable=value, show='•' if secret else '').pack(side='left', fill='x', expand=True)
        if env in ('ASC_KEY_ID', 'ASC_ISSUER_ID'):
            def paste():
                try:
                    value.set(root.clipboard_get().strip())
                except tk.TclError:
                    root.bell()
            ttk.Button(row, text='Paste', command=paste).pack(side='left', padx=(8, 0))
        if folder or file:
            def choose():
                path = filedialog.askdirectory() if folder else filedialog.askopenfilename(filetypes=[('Apple key', '*.p8')])
                if path:
                    value.set(path)
            ttk.Button(row, text='Browse', command=choose).pack(side='left', padx=(8, 0))
        return value

    def copy_text(box, selection_only=False):
        start, end = ('sel.first', 'sel.last') if selection_only and box.tag_ranges('sel') else ('1.0', 'end-1c')
        text = box.get(start, end)
        root.clipboard_clear()
        root.clipboard_append(text)
        return 'break'

    def result(parent, empty):
        box = ScrolledText(parent, bg=INPUT, fg=INK, padx=14, pady=12, relief='flat', wrap='word', font=('Segoe UI', 11),
                           highlightthickness=1, highlightbackground=BORDER)
        box.pack(fill='both', expand=True, pady=(12, 0))
        box.configure(exportselection=False, takefocus=True)
        box.tag_configure('action', foreground=ACCENT, font=('Segoe UI', 11, 'bold'), spacing1=6)
        box.tag_configure('review', foreground='#FFD19C', spacing1=4)
        box.tag_configure('heading', foreground=INK, font=('Segoe UI', 13, 'bold'), spacing1=10, spacing3=5)
        def select_all(event):
            box.tag_add('sel', '1.0', 'end-1c')
            return 'break'

        box.bind('<Control-a>', select_all)
        box.bind('<Control-c>', lambda event: copy_text(box, selection_only=True))
        menu = tk.Menu(box, tearoff=False)
        menu.add_command(label='Copy selection', command=lambda: copy_text(box, selection_only=True))
        menu.add_command(label='Copy all', command=lambda: copy_text(box))
        def popup(event):
            box.focus_set()
            menu.tk_popup(event.x_root, event.y_root)
            return 'break'

        box.bind('<Button-3>', popup)
        box.insert('end', empty)
        box.configure(state='disabled')
        return box

    def show(box, message):
        box.configure(state='normal')
        box.delete('1.0', 'end')
        report = message if isinstance(message, str) else json.dumps(message, indent=2)
        for line in report.splitlines(keepends=True):
            clean = line.strip()
            tag = ''
            if clean.startswith('Next step'):
                tag = 'action'
            elif clean.startswith(('REVIEW', 'UNVERIFIED')):
                tag = 'review'
            elif clean in ('What to do next', 'Findings', 'Subscription and payment setup', 'Release setup'):
                tag = 'heading'
            box.insert('end', line, tag)
        box.configure(state='disabled')

    def run(box, action, update=None):
        if state['busy']:
            return
        state['busy'] = True
        show(box, 'Working…')
        def work():
            try:
                output.put((box, action(), update))
            except Exception as error:
                output.put((box, f'Could not complete the request. {error}', None))
        threading.Thread(target=work, daemon=True).start()

    def poll():
        try:
            box, data, update = output.get_nowait()
        except queue.Empty:
            pass
        else:
            state['busy'] = False
            if update:
                update(data)
            display = 'Choose an app above, then ask a question to get started.' if (
                box is apple_result and isinstance(data, list) and data
                and all(isinstance(row, dict) and 'bundle' in row for row in data)
            ) else data
            show(box, display)
        root.after(100, poll)

    apple = pane('Apple workspace', 'App Store Connect',
                 'Choose an app, run a check, and see what to fix before release.')
    scope = ttk.Frame(apple)
    scope.pack(fill='x', pady=(0, 10))
    scope.columnconfigure(0, weight=3)
    scope.columnconfigure(1, weight=2)
    ttk.Label(scope, text='App', style='Section.TLabel').grid(row=0, column=0, sticky='w')
    app_choice = ttk.Combobox(scope, state='readonly')
    app_choice.grid(row=1, column=0, sticky='ew', padx=(0, 12), pady=(4, 0))
    ttk.Label(scope, text='Release version', style='Section.TLabel').grid(row=0, column=1, sticky='w')
    version_choice = ttk.Combobox(scope, state='readonly')
    version_choice.grid(row=1, column=1, sticky='ew', pady=(4, 0))
    actions = ttk.Frame(apple)
    actions.pack(fill='x')
    columns = ttk.Panedwindow(apple, orient='horizontal')
    columns.pack(fill='both', expand=True, pady=(12, 0))
    request_card = ttk.Frame(columns, padding=(18, 16), width=335, relief='solid', borderwidth=1)
    report_card = ttk.Frame(columns, padding=(18, 16), width=480, relief='solid', borderwidth=1)
    columns.add(request_card, weight=1)
    columns.add(report_card, weight=2)
    apple_result = result(report_card, 'Connect Apple in Settings, or select an app and run a check.')

    status = tk.StringVar(value='Saved details · verify connection' if saved else 'Not connected')
    ttk.Label(apple, textvariable=status, style='Status.TLabel').pack(anchor='w', before=columns)

    def export_result():
        path = filedialog.asksaveasfilename(
            defaultextension='.txt', filetypes=[('Text report', '*.txt')],
            initialfile='ShipDesk-Apple-results.txt')
        if path:
            try:
                Path(path).write_text(apple_result.get('1.0', 'end-1c'), encoding='utf-8')
            except OSError as error:
                from tkinter import messagebox
                messagebox.showerror('Could not save results', str(error), parent=root)

    report_actions = ttk.Frame(report_card)
    report_actions.pack(fill='x', before=apple_result)
    ttk.Label(report_actions, text='Verification report', style='Section.TLabel').pack(side='left', padx=(0, 12))
    ttk.Button(report_actions, text='Copy', command=lambda: copy_text(apple_result)).pack(side='left')
    ttk.Button(report_actions, text='Export', command=export_result).pack(side='left', padx=8)

    def infer_id(*args):
        inferred = store.apple_key_id(key_path.get())
        if inferred:
            key_id.set(inferred)


    def mark_unverified(*args):
        status.set('Not connected · details changed')
        state['apps'] = []
        app_choice.set('')
        app_choice['values'] = []
        reset_versions()
        select_project()

    def apple_action(kind):
        credentials = (key_id.get().strip().upper(), issuer.get().strip(), key_path.get().strip())
        index, version = app_choice.current(), version_choice.current()
        if not credentials[0] or not credentials[2]:
            show(apple_result, 'Enter a Key ID and choose your Apple private key file.')
            return
        if (kind not in ('apps', 'audit', 'verify') and index < 0) or (kind == 'listing' and version < 0):
            show(apple_result, 'Select an app and, for screenshots, a release version.')
            return
        app_id = state['apps'][index]['id'] if index >= 0 else None
        version_id = state['versions'][version]['id'] if version >= 0 else None
        question = question_entry.get('1.0', 'end-1c').strip() if kind == 'verify' else ''
        folder = project_folder.get().strip() if kind == 'verify' else ''
        selected_ai = provider.get() if kind == 'verify' else 'Local only'
        use_ai = selected_ai != 'Local only'
        ai_key = provider_keys[selected_ai].get().strip() if use_ai else ''
        def action():
            bearer = store.token(*credentials)
            if kind == 'verify':
                report = audit.verify_request(question, app_id, version_id, bearer)
                explanation = ''
                if use_ai:
                    if not ai_key:
                        explanation = f'Enter your {selected_ai} API key in Settings.'
                    else:
                        try:
                            explanation = ai_help.explain(ai_key, question, report, selected_ai) or 'No explanation returned.'
                        except (OSError, ValueError):
                            explanation = f'{selected_ai} request failed. Check your API key, model access, and quota.'
                if folder and app_id:
                    try:
                        products = store.apple_subscription_setup(app_id, bearer)
                        ids = [row['attributes']['productId'] for row, _ in products]
                        report += '\n\n' + project_check.compare_subscriptions(folder, ids)
                    except (OSError, ValueError, RuntimeError) as error:
                        report += f'\n\nUNVERIFIED · Local project comparison: {error}'
                if not folder:
                    report += '\n\nCode comparison skipped. Link your local project to compare subscription IDs.'
                steps = [line.split('·', 1)[1].strip() for line in report.splitlines()
                         if line.startswith('Next step ·')]
                if steps:
                    checklist = '\n'.join(f'{index}. {step}' for index, step in enumerate(dict.fromkeys(steps), 1))
                    report = f'What to do next\n{checklist}\n\nFindings\n{report}'
                return report + (f'\n\n{selected_ai} explanation\n' + explanation if explanation else '')
            if kind == 'audit':
                return audit.audit_apple(bearer)
            if kind == 'apps':
                return [{'id': row['id'], 'name': row['attributes']['name'],
                         'bundle': row['attributes']['bundleId']} for row in store.apple_apps(bearer)]
            if kind == 'versions':
                return store.apple_releases(app_id, bearer)
            if kind == 'listing':
                return store.apple_listing(version_id, bearer)
            return store.apple_offers(app_id, bearer)
        def update(rows):
            if kind == 'apps':
                current = (key_id.get().strip().upper(), issuer.get().strip(), key_path.get().strip())
                if current != credentials:
                    return
                status.set(f'Connected · {len(rows)} apps available')
                try:
                    settings.parent.mkdir(parents=True, exist_ok=True)
                    temporary = settings.with_suffix('.tmp')
                    temporary.write_text(json.dumps(dict(zip(
                        ('ASC_KEY_ID', 'ASC_ISSUER_ID', 'ASC_KEY_PATH'), credentials
                    ))), encoding='utf-8')
                    temporary.replace(settings)
                except OSError:
                    status.set(f'Connected · {len(rows)} apps · could not remember details')
                state['apps'] = rows
                app_choice['values'] = [f"{row['name']} · {row['bundle']}" for row in rows]
                reset_versions()
                if rows:
                    app_choice.current(0)
                    select_project()
            if kind == 'versions':
                state['versions'] = rows
                version_choice['values'] = [f"{row['versionString']} · {row['platform']}" for row in rows]
                if rows:
                    version_choice.current(0)
        if kind == 'apps' and not state['busy']:
            mark_unverified()
        run(apple_result, action, update)

    def reset_versions(event=None):
        state['versions'] = []
        version_choice.set('')
        version_choice['values'] = []


    app_choice.bind('<<ComboboxSelected>>', lambda event: select_project())
    for label, kind in [('Verify and load apps', 'apps'), ('Load releases', 'versions'),
                        ('Inspect screenshots', 'listing'), ('Inspect offer codes', 'offers')]:
        ttk.Button(actions, text=label, style='Primary.TButton' if kind == 'apps' else 'TButton', command=lambda kind=kind: apple_action(kind)).pack(side='left', padx=(0, 6))

    ttk.Button(actions, text='Audit account', command=lambda: apple_action('audit')).pack(side='left')

    prompt_panel = ttk.Frame(request_card)
    prompt_panel.pack(fill='x')
    ttk.Label(prompt_panel, text='Ask ShipDesk', style='Section.TLabel').pack(anchor='w', pady=(0, 5))
    verification = ttk.Frame(prompt_panel)
    verification.pack(fill='x')
    question_entry = tk.Text(verification, height=6, width=24, wrap='word', bg=INPUT, fg=INK,
                             insertbackground=INK, padx=12, pady=9, relief='flat',
                             highlightthickness=1, highlightbackground=BORDER,
                             highlightcolor=ACCENT, font=('Segoe UI', 11))
    question_entry.pack(fill='x')
    question_entry.insert('1.0', 'Check subscription pricing and offer codes')

    def paste_question(event=None):
        try:
            text = root.clipboard_get()
        except tk.TclError:
            root.bell()
        else:
            if question_entry.tag_ranges('sel'):
                question_entry.delete('sel.first', 'sel.last')
            question_entry.insert('insert', text)
            question_entry.focus_set()
        return 'break'

    def run_question(event=None):
        if question_entry.get('1.0', 'end-1c').strip():
            apple_action('verify')
        return 'break'

    question_entry.bind('<Control-v>', paste_question)
    question_entry.bind('<Shift-Insert>', paste_question)
    question_entry.bind('<Control-Return>', run_question)
    composer_actions = ttk.Frame(verification)
    composer_actions.pack(fill='x', pady=(6, 0))
    ttk.Button(composer_actions, text='Run check', style='Primary.TButton',
               command=run_question).pack(side='right')
    ttk.Button(composer_actions, text='Paste', command=paste_question).pack(side='right', padx=6)
    code_status = tk.StringVar(value='No code folder linked')
    project_card = ttk.Frame(request_card)
    project_card.pack(fill='x', pady=(22, 0))
    ttk.Label(project_card, text='Project source', style='Section.TLabel').pack(anchor='w')
    ttk.Label(project_card, textvariable=code_status, wraplength=260).pack(anchor='w', pady=5)
    ttk.Button(project_card, text='Link folder', command=lambda: choose_code_folder()).pack(side='left')
    ttk.Button(project_card, text='Unlink', command=lambda: project_folder.set('')).pack(side='left', padx=6)

    def choose_code_folder():
        if not selected_app_id():
            code_status.set('Select an app before linking a folder.')
            return
        folder = filedialog.askdirectory(parent=root)
        if folder:
            project_folder.set(folder)

    options = pane('Settings', 'Welcome to ShipDesk', 'A local desktop workspace by The Trendsetter Agency.')
    ttk.Label(options, text='Check releases, subscriptions, offer codes and screenshots. '
                           'Compare subscription IDs with your local project.',
              wraplength=650).pack(anchor='w', pady=(0, 18))
    ttk.Label(options, text='Connect App Store Connect', font=('Segoe UI', 14, 'bold')).pack(anchor='w')
    key_id = field(options, 'Key ID', 'ASC_KEY_ID')
    issuer = field(options, 'Issuer ID (team key)', 'ASC_ISSUER_ID')
    key_path = field(options, 'Private key file', 'ASC_KEY_PATH', file=True)
    ttk.Label(options, text='Choose your Apple .p8 file. Leave Issuer ID blank for an individual key.',
              wraplength=650).pack(anchor='w', pady=(3, 16))
    ttk.Label(options, text='AI explanations', font=('Segoe UI', 14, 'bold')).pack(anchor='w')
    project_folder = tk.StringVar()
    links_path = settings.with_name('projects.json')
    try:
        project_links = json.loads(links_path.read_text(encoding='utf-8'))
        if not isinstance(project_links, dict):
            project_links = {}
    except (OSError, ValueError):
        project_links = {}

    def selected_app_id():
        index = app_choice.current()
        return state['apps'][index]['id'] if 0 <= index < len(state['apps']) else None

    def select_project():
        reset_versions()
        project_folder.set(project_links.get(selected_app_id(), ''))

    def save_project(folder):
        app_id = selected_app_id()
        if not app_id:
            return
        if project_links.get(app_id, '') == folder:
            return
        if folder:
            project_links[app_id] = folder
        else:
            project_links.pop(app_id, None)
        try:
            links_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = links_path.with_suffix('.tmp')
            temporary.write_text(json.dumps(project_links), encoding='utf-8')
            temporary.replace(links_path)
        except OSError:
            code_status.set('Folder linked for this session only.')
    def update_code_status(*args):
        folder = project_folder.get().strip()
        code_status.set(f'Linked: {Path(folder).name}' if folder else 'No code folder linked')
        save_project(folder)
    project_folder.trace_add('write', update_code_status)
    provider = tk.StringVar(value='Local only')
    provider_keys = {name: tk.StringVar() for name in ('OpenAI', 'Gemini')}
    ai_row = ttk.Frame(options)
    ai_row.pack(fill='x', pady=(8, 0))
    ttk.Label(ai_row, text='AI provider', width=20).pack(side='left')
    ttk.Combobox(ai_row, state='readonly', values=('Local only', *provider_keys),
                 textvariable=provider, width=16).pack(side='left')
    key_row = ttk.Frame(options)
    ttk.Label(key_row, text='API key', width=20).pack(side='left')
    provider_entry = ttk.Entry(key_row, show='•')
    provider_entry.pack(side='left', fill='x', expand=True)

    def paste_provider_key():
        try:
            provider_keys[provider.get()].set(root.clipboard_get().strip())
        except tk.TclError:
            root.bell()

    ttk.Button(key_row, text='Paste', command=paste_provider_key).pack(side='left', padx=(8, 0))
    provider_hint = tk.StringVar(value='Local checks run without an AI key.')
    hint = ttk.Label(options, textvariable=provider_hint, wraplength=640)
    hint.pack(anchor='w', pady=(6, 0))

    def update_provider(*args):
        selected = provider.get()
        if selected == 'Local only':
            key_row.pack_forget()
            provider_hint.set('Local checks run without an AI key.')
        else:
            provider_entry.configure(textvariable=provider_keys[selected])
            key_row.pack(fill='x', pady=5, before=hint)
            provider_hint.set(f'{selected} receives the question and store findings. Keys are kept for this session.')

    provider.trace_add('write', update_provider)
    key_path.trace_add('write', infer_id)
    infer_id()
    for field_value in (key_id, issuer, key_path):
        field_value.trace_add('write', mark_unverified)

    def open_workspace(connect=False):
        routes['Apple workspace']()
        if connect:
            apple_action('apps')

    setup_actions = ttk.Frame(options)
    setup_actions.pack(fill='x', pady=16)
    ttk.Button(setup_actions, text='Connect and open workspace', style='Primary.TButton',
               command=lambda: open_workspace(True)).pack(side='left')
    ttk.Button(setup_actions, text='Continue without connecting',
               command=open_workspace).pack(side='left', padx=8)

    google = pane('Google Play', 'Google Play listings',
                  'Read the current listing metadata for your Android app.')
    package = field(google, 'Package name', 'PLAY_PACKAGE')
    google_token = field(google, 'OAuth access token', 'PLAY_ACCESS_TOKEN', secret=True)
    ttk.Button(google, text='Read listings', command=lambda: google_action()).pack(anchor='w')
    ttk.Button(google, text='Audit this package', command=lambda: google_action(True)).pack(anchor='w', pady=(6, 0))
    google_result = result(google, 'Enter a package name and access token to read the listing.')
    def google_action(audit_mode=False):
        values = (package.get().strip(), google_token.get().strip())
        if not all(values):
            show(google_result, 'Enter the package name and a Google Play Developer API access token.')
            return
        run(google_result, lambda: audit.audit_google(*values) if audit_mode else store.play_listing(*values))

    media = pane('Screenshot studio', 'Screenshot comparison',
                 'Compare PNG files across releases and export the new set.')
    before = field(media, 'Previous release', folder=True)
    after = field(media, 'New release', folder=True)
    media_actions = ttk.Frame(media)
    media_actions.pack(fill='x')
    def comparison():
        if not before.get() or not after.get():
            show(media_result, 'Choose both screenshot folders.')
            return
        old, new = before.get(), after.get()
        def action():
            rows = screenshots.compare(screenshots.inventory(old), screenshots.inventory(new))
            return '\n'.join(f'{status:10} {width} × {height}   {name}'
                             for name, status, (width, height) in rows) or 'No PNG files in either folder.'
        run(media_result, action)
    def export():
        if not after.get():
            show(media_result, 'Choose the new release folder.')
            return
        target = filedialog.asksaveasfilename(defaultextension='.zip', filetypes=[('ZIP archive', '*.zip')])
        if target:
            directory = after.get()
            run(media_result, lambda: f'Exported {screenshots.export(directory, target)} screenshots to {target}')
    ttk.Button(media_actions, text='Compare folders', command=comparison).pack(side='left', padx=(0, 8))
    ttk.Button(media_actions, text='Export ZIP', command=export).pack(side='left')
    sizing = ttk.Frame(media)
    sizing.pack(fill='x', pady=(8, 0))
    slots = list(screenshots.APPLE_SLOTS)
    slot = ttk.Combobox(sizing, state='readonly', values=slots)
    slot.current(0)
    slot.pack(side='left', fill='x', expand=True)

    def size_action(resize=False):
        directory = after.get().strip()
        if not directory:
            show(media_result, 'Choose a New release folder first.')
            return
        target = screenshots.APPLE_SLOTS[slot.get()]
        if resize:
            destination = filedialog.asksaveasfilename(defaultextension='.zip', filetypes=[('ZIP archive', '*.zip')])
            if destination:
                run(media_result, lambda: screenshots.resize_set(directory, destination, target))
        else:
            run(media_result, lambda: screenshots.check_size(directory, target))

    ttk.Button(sizing, text='Check sizes', command=size_action).pack(side='left', padx=6)
    ttk.Button(sizing, text='Resize to ZIP', command=lambda: size_action(True)).pack(side='left')
    media_result = result(media, 'Choose two folders to see which screenshots changed.')
    root.after(100, poll)
    if saved and key_id.get() and Path(key_path.get()).is_file():
        activate_initial_pane()
        root.after(150, lambda: apple_action('apps'))
    else:
        routes['Settings']()
    root.mainloop()

if __name__ == '__main__':
    main()
