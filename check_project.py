"""Link a project folder and print the code check. No ShipDesk window."""
import argparse
import json
import os
import sys
from pathlib import Path

import project_check
import store

def settings_dir():
    return Path(os.environ.get('LOCALAPPDATA') or Path.home()) / 'ShipDesk'

def load_saved(directory):
    path = Path(directory) / 'apple.json'
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    key = (data.get('ASC_KEY_ID') or '').strip()
    issuer = (data.get('ASC_ISSUER_ID') or '').strip()
    file = (data.get('ASC_KEY_PATH') or '').strip()
    if not key or not file:
        return None
    return key, issuer, file

def write_link(directory, app_id, folder):
    path = Path(directory) / 'projects.json'
    try:
        saved = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(saved, dict):
            saved = {}
    except (OSError, ValueError):
        saved = {}
    saved[app_id] = str(folder)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(saved), encoding='utf-8')

def local_report(folder, bundle):
    folder = Path(folder)
    lines = []
    if not folder.is_dir():
        return [f'FAIL · Folder not found: {folder}']
    lines.append(f'PASS · Folder exists: {folder}')
    found = project_check.scan_project(folder, [])
    lines.append(f"PASS · Read {found['scanned']} files, skipped {found['skipped']}")
    bundles = sorted(found['bundles'])
    if bundle in found['bundles']:
        lines.append(f'PASS · {bundle} is in this folder')
    elif bundles:
        lines.append('YOUR CODE · This folder does not use the App Store bundle id.')
        lines.append(f'Folder says: {", ".join(bundles[:6])}')
        lines.append(f'App Store app selected in ShipDesk: {bundle}')
    else:
        lines.append('NOT SURE · No bundle id in this folder. Point the test at the app project, not a docs folder.')
    if found['versions']:
        lines.append('PASS · Versions in the folder: ' + ', '.join(sorted(found['versions'])[:6]))
    if found['products']:
        lines.append('PASS · Subscription ids in the folder: ' + ', '.join(sorted(found['products'])[:8]))
    else:
        lines.append('NOT SURE · No subscription ids were found in the folder.')
    return lines

def link_store(directory, folder, bundle):
    saved = load_saved(directory)
    if not saved:
        return ['NOT SURE · No Apple key saved yet. Open ShipDesk once and connect, then run this test again.']
    apps = store.apple_apps(store.token(*saved))
    match = next((item for item in apps if item['attributes'].get('bundleId') == bundle), None)
    if not match:
        names = ', '.join(item['attributes'].get('bundleId', '') for item in apps[:8])
        return [f'FAIL · Apple did not return {bundle}. Visible: {names or "none"}']
    write_link(directory, match['id'], folder)
    return [f"PASS · Linked {match['attributes'].get('name', bundle)} to {folder}",
            'Open ShipDesk. The folder line should show this path.']

def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--folder', default=r'D:\VERIFYLY\Verifyly')
    parser.add_argument('--bundle', default='com.verifyly.app')
    parser.add_argument('--settings', default='')
    args = parser.parse_args(argv)
    directory = Path(args.settings) if args.settings else settings_dir()
    lines = local_report(args.folder, args.bundle)
    if lines[0].startswith('PASS'):
        try:
            lines.extend(link_store(directory, args.folder, args.bundle))
        except (OSError, RuntimeError, ValueError) as error:
            lines.append(f'NOT SURE · Apple link was not written. {error}')
    print('\n'.join(lines))
    return 0 if lines[0].startswith('PASS') and not any(line.startswith('FAIL') for line in lines) else 1

if __name__ == '__main__':
    sys.exit(main())
