"""Compare exact PNG contents and export approved screenshots."""
import hashlib
import struct
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

def inventory(directory):
    result = {}
    for file in sorted(Path(directory).glob('*.png')):
        data = file.read_bytes()
        if data[:8] != b'\x89PNG\r\n\x1a\n' or data[12:16] != b'IHDR' or len(data) < 24:
            raise ValueError(f'Invalid PNG header: {file.name}')
        width, height = struct.unpack('>II', data[16:24])
        if not width or not height:
            raise ValueError(f'Invalid PNG dimensions: {file.name}')
        result[file.name] = (width, height, hashlib.sha256(data).hexdigest())
    return result

def compare(before, after):
    return [(name, 'Added' if name not in before else 'Removed' if name not in after
             else 'Identical' if before[name] == after[name] else 'Changed',
             (after.get(name) or before[name])[:2])
            for name in sorted(before.keys() | after.keys())]

def export(directory, target):
    files = inventory(directory)
    if not files:
        raise ValueError('Choose a folder containing PNG screenshots')
    with ZipFile(target, 'w', ZIP_DEFLATED) as archive:
        for name in files:
            archive.write(Path(directory) / name, arcname=name)
    return len(files)

APPLE_SLOTS = {
    'iPhone 6.9″ · 1320 × 2868': (1320, 2868),
    'iPhone 6.9″ · 1290 × 2796': (1290, 2796),
    'iPad 13″ · 2064 × 2752': (2064, 2752),
}

def check_size(directory, target):
    files = inventory(directory)
    if not files:
        raise ValueError('Choose a folder containing PNG screenshots.')
    return '\n'.join(f"{'PASS' if size[:2] == target else 'RESIZE'} · {name}: {size[0]} × {size[1]}"
                     for name, size in files.items())

def resize_set(directory, target_zip, target):
    try:
        from PIL import Image, ImageOps
    except ImportError:
        raise RuntimeError('Install Pillow with your ShipDesk Python: -m pip install Pillow') from None
    from io import BytesIO
    from tempfile import NamedTemporaryFile

    files = inventory(directory)
    if not files:
        raise ValueError('Choose a folder containing PNG screenshots.')
    destination = Path(target_zip)
    with NamedTemporaryFile(dir=destination.parent, delete=False) as temporary:
        temporary_path = Path(temporary.name)
    try:
        with ZipFile(temporary_path, 'w', ZIP_DEFLATED) as archive:
            for name in files:
                with Image.open(Path(directory) / name) as source:
                    image = ImageOps.exif_transpose(source).convert('RGBA')
                    fitted = ImageOps.contain(image, target, Image.Resampling.LANCZOS)
                    canvas = Image.new('RGB', target, '#10131c')
                    offset = tuple((outer - inner) // 2 for outer, inner in zip(target, fitted.size))
                    canvas.paste(fitted, offset, fitted)
                    data = BytesIO()
                    canvas.save(data, format='PNG')
                    archive.writestr(name, data.getvalue())
        temporary_path.replace(destination)
    finally:
        temporary_path.unlink(missing_ok=True)
    return f'Exported {len(files)} PNG files at {target[0]} × {target[1]}. Review the padding before upload.'
