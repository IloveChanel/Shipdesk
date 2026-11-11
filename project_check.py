"""Find literal Apple subscription identifiers in local source."""
import os
import re
from pathlib import Path

SOURCE_TYPES = {'.swift', '.m', '.mm', '.kt', '.java', '.dart', '.ts', '.tsx', '.js', '.jsx', '.cs', '.storekit'}
SKIP = {'.git', 'node_modules', 'build', 'dist', 'Pods', 'vendor', 'DerivedData'}
PRODUCT = re.compile(r"""["']([A-Za-z0-9][A-Za-z0-9_.-]*(?:monthly|annual|yearly|weekly)[A-Za-z0-9_.-]*)["']""", re.I)

def compare_subscriptions(folder, apple_ids):
    root = Path(folder)
    if not root.is_dir():
        raise ValueError('Choose an existing project folder.')
    evidence = {}
    scanned = 0
    skipped = 0
    for directory, dirs, files in os.walk(root):
        dirs[:] = sorted(name for name in dirs if name not in SKIP and not name.startswith('.'))
        for name in sorted(files):
            path = Path(directory) / name
            if path.suffix.lower() not in SOURCE_TYPES or path.is_symlink():
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
            for line_number, line in enumerate(source.splitlines(), 1):
                candidates = set(PRODUCT.findall(line))
                candidates.update(item for item in apple_ids if f'"{item}"' in line or f"'{item}'" in line)
                for item in candidates:
                    evidence.setdefault(item, f'{path.relative_to(root)}:{line_number}')
    report = [f'Local code comparison · {scanned} files read, {skipped} skipped']
    for item in sorted(set(apple_ids) | evidence.keys()):
        if item in apple_ids and item in evidence:
            report.append(f'MATCH · {item} appears in Apple and {evidence[item]}')
        elif item in apple_ids:
            report.append(f'REVIEW CODE · {item} exists in Apple. No matching literal found. Check the paywall or remote product configuration.')
        else:
            report.append(f'REVIEW STORE OR CODE · {item} in {evidence[item]} was not returned by Apple. Check the selected app record and exact product ID.')
    report.append('Literal matches do not verify runtime purchases. Remote configuration and dynamically constructed IDs may require a device test.')
    return '\n'.join(report)
