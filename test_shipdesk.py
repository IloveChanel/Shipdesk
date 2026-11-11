import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

import screenshots
import store

class ShipDeskTests(unittest.TestCase):
    def test_compare_and_export(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            png = b'\x89PNG\r\n\x1a\n\x00\x00\x00\x0dIHDR\x00\x00\x00\x02\x00\x00\x00\x03'
            (path / 'home.png').write_bytes(png)
            before = screenshots.inventory(path)
            (path / 'home.png').write_bytes(png + b'new')
            self.assertEqual(screenshots.compare(before, screenshots.inventory(path)),
                             [('home.png', 'Changed', (2, 3))])
            target = path / 'export.zip'
            self.assertEqual(screenshots.export(path, target), 1)
            with ZipFile(target) as archive:
                self.assertEqual(archive.read('home.png'), png + b'new')

    @patch('store.request')
    def test_play_drops_edit_after_read_failure(self, request):
        request.side_effect = [{'id': 'edit1'}, RuntimeError('read failed'), {}]
        with self.assertRaisesRegex(RuntimeError, 'read failed'):
            store.play_listing('com.example.app', 'token')
        self.assertEqual(request.call_args.args[2], 'DELETE')

    @patch('store.request')
    def test_apple_rejects_pagination_on_unexpected_host(self, request):
        request.return_value = {'data': [], 'links': {'next': 'https://example.org'}}
        with self.assertRaisesRegex(ValueError, 'pagination host'):
            store.apple_apps('token')
        self.assertEqual(request.call_count, 1)
