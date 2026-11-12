"""Find bundle ids, versions, and subscription ids in a local project folder."""
import os
import re
from pathlib import Path

SOURCE_TYPES = {'.swift', '.m', '.mm', '.kt', '.java', '.dart', '.ts', '.tsx', '.js', '.jsx', '.cs', '.storekit'}
EXTRA_TYPES = {'.plist', '.gradle', '.pbxproj', '.json', '.xml'}
SKIP = {'.git', 'node_modules', 'build', 'dist', 'Pods', 'vendor', 'DerivedData'}
PRODUCT = re.compile(r"""["']([A-Za-z0-9][A-Za-z0-9_.-]*(?:monthly|annual|yearly|weekly)[A-Za-z0-9_.-]*)["']""", re.I)
BUNDLE = re.compile(
    r"""['"]?(?:PRODUCT_BUNDLE_IDENTIFIER|bundleIdentifier|applicationId|package)['"]?\s*[=:]\s*['"]?([A-Za-z][\w.-]+)"""
)
VERSION = re.compile(
    r'(?:MARKETING_VERSION|CFBundleShortVersionString|versionName)\s*[=:]\s*["\']?(\d+\.\d+(?:\.\d+)?)',
)

def _walk(folder):
    root = Path(folder)
    if not root.is_dir():
        raise ValueError('Choose an existing project folder.')
    for directory, dirs, files in os.walk(root):
        dirs[:] = sorted(name for name in dirs if name not in SKIP and not name.startswith('.'))
        for name in sorted(files):
            path = Path(directory) / name
            if path.is_symlink():
                continue
            yield root, path

def scan_project(folder, apple_ids):
    """Read the project folder on this computer. No GitHub and no Visual Studio."""
    bundles, versions, evidence = set(), set(), {}
    scanned = skipped = 0
    for root, path in _walk(folder):
        if path.suffix.lower() not in SOURCE_TYPES | EXTRA_TYPES:
            continue
        try:
            if path.stat().st_size > 512_000:
                skipped += 1
                continue
            source = path.read_text(encoding='utf-8', errors='replace')
        except OSError:
            skipped += 1
            continue
        scanned += 1
        where = str(path.relative_to(root))
        bundles.update(item for item in BUNDLE.findall(source) if '$(' not in item and not item.endswith('.test'))
        versions.update(VERSION.findall(source))
        for line_number, line in enumerate(source.splitlines(), 1):
            candidates = set(PRODUCT.findall(line))
            candidates.update(item for item in apple_ids if f'"{item}"' in line or f"'{item}'" in line)
            for item in candidates:
                evidence.setdefault(item, f'{where}:{line_number}')
    return {'bundles': bundles, 'versions': versions, 'products': evidence, 'scanned': scanned, 'skipped': skipped}

CANDIDATES = (
    Path(r'D:\VERIFYLY\Verifyly'),
    Path(r'D:\Verifyly'),
    Path(r'D:\VERIFYLY\Verifyly-clean'),
)

def known_match(bundle_id, candidates=None):
    """Check the folders already on this PC before searching the drive."""
    if not bundle_id:
        return None
    for folder in candidates or CANDIDATES:
        folder = Path(folder)
        if not folder.is_dir():
            continue
        for path in (folder / 'app.json', folder / 'mobile' / 'app.json', folder / 'project.pbxproj'):
            try:
                text = path.read_text(encoding='utf-8', errors='replace')
            except OSError:
                continue
            if bundle_id in text and ('bundleIdentifier' in text or 'PRODUCT_BUNDLE_IDENTIFIER' in text or '"package"' in text):
                return folder
    return None

def find_project(bundle_id, roots=None):
    """Find the local project folder for this App Store bundle id."""
    if not bundle_id:
        return None
    found = known_match(bundle_id)
    if found and roots is None:
        return found
    if roots is None:
        home = Path.home()
        roots = [home / 'Documents', home / 'Desktop', home / 'source', home / 'repos', Path('D:/')]
    needles = ('bundleIdentifier', 'PRODUCT_BUNDLE_IDENTIFIER', 'applicationId', '"package"', 'package ')
    names = {'app.json', 'project.pbxproj', 'build.gradle', 'build.gradle.kts'}
    for root in roots:
        root = Path(root)
        if not root.is_dir():
            continue
        for directory, dirs, files in os.walk(root):
            current = Path(directory)
            if len(current.relative_to(root).parts) > 3:
                dirs.clear()
                continue
            dirs[:] = sorted(name for name in dirs if name not in SKIP and not name.startswith('.'))
            for name in files:
                if name not in names and not name.endswith('.pbxproj'):
                    continue
                path = current / name
                try:
                    if path.stat().st_size > 1_000_000:
                        continue
                    text = path.read_text(encoding='utf-8', errors='replace')
                except OSError:
                    continue
                if bundle_id in text and any(marker in text for marker in needles):
                    return current
    return None

def compare_subscriptions(folder, apple_ids):
    found = scan_project(folder, apple_ids)
    evidence = found['products']
    report = [f"Local code comparison · {found['scanned']} files read, {found['skipped']} skipped"]
    for item in sorted(set(apple_ids) | evidence.keys()):
        if item in apple_ids and item in evidence:
            report.append(f'MATCH · {item} appears in Apple and {evidence[item]}')
        elif item in apple_ids:
            report.append(f'REVIEW CODE · {item} exists in Apple. No matching literal found. Check the paywall or remote product configuration.')
        else:
            report.append(f'REVIEW STORE OR CODE · {item} in {evidence[item]} was not returned by Apple. Check the selected app record and exact product ID.')
    report.append('Literal matches do not verify runtime purchases. Remote configuration and dynamically constructed IDs may require a device test.')
    return '\n'.join(report)
