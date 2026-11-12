import tempfile
import unittest
import json
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

import check_project
import guide
import project_check
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

    def test_folder_scan_reads_bundle_and_product(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'App.pbxproj').write_text(
                'PRODUCT_BUNDLE_IDENTIFIER = com.example.app;\nMARKETING_VERSION = 1.2.0;\n', encoding='utf-8')
            (root / 'Pay.swift').write_text('let id = "com.example.monthly"\n', encoding='utf-8')
            found = project_check.scan_project(root, ['com.example.monthly'])
            self.assertIn('com.example.app', found['bundles'])
            self.assertIn('1.2.0', found['versions'])
            self.assertIn('com.example.monthly', found['products'])

    def test_find_project_by_bundle_id(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = root / 'Verifyly'
            app.mkdir()
            (app / 'app.json').write_text('{"ios":{"bundleIdentifier":"com.verifyly.app"}}', encoding='utf-8')
            self.assertEqual(project_check.find_project('com.verifyly.app', [root]), app)
            self.assertIsNone(project_check.find_project('com.other.app', [root]))

    def test_known_verifyly_folder_wins(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'Verifyly'
            (root / 'mobile').mkdir(parents=True)
            (root / 'mobile' / 'app.json').write_text(
                '{"ios":{"bundleIdentifier":"com.verifyly.app"}}', encoding='utf-8')
            self.assertEqual(project_check.known_match('com.verifyly.app', [root]), root)



    def test_guide_says_code_when_bundle_differs(self):
        text = guide.explain({
            'app': {'name': 'Demo', 'bundleId': 'com.store.app'},
            'code': {'scanned': 2, 'bundles': {'com.code.app'}, 'versions': set(), 'products': {}},
            'release': {'id': 'v', 'versionString': '1.0', 'platform': 'IOS', 'appVersionState': 'PREPARE_FOR_SUBMISSION', 'buildId': 'b'},
            'build': {'processingState': 'VALID'},
            'locales': [{'locale': 'en-US', 'description': 'Hello', 'keywords': 'demo', 'supportUrl': 'https://example.com', 'sets': [{'screenshots': ['a.png']}]}],
            'review': {'contactFirstName': 'A', 'contactLastName': 'B', 'contactPhone': '1', 'contactEmail': 'a@b.c'},
            'subscriptions': [],
            'product_ids': [],
        })
        self.assertIn('YOUR CODE', text)
        self.assertIn('com.store.app', text)
        self.assertNotIn('GitHub', text.split('YOUR CODE', 1)[1][:80])

    def test_guide_says_store_when_screenshots_missing(self):
        text = guide.explain({
            'app': {'name': 'Demo', 'bundleId': 'com.store.app'},
            'code': {'scanned': 1, 'bundles': {'com.store.app'}, 'versions': {'1.0'}, 'products': {}},
            'release': {'id': 'v', 'versionString': '1.0', 'platform': 'IOS', 'appVersionState': 'PREPARE_FOR_SUBMISSION', 'buildId': 'b'},
            'build': {'processingState': 'VALID'},
            'locales': [{'locale': 'en-US', 'description': 'Hello', 'keywords': 'demo', 'supportUrl': 'https://example.com', 'sets': []}],
            'review': {'contactFirstName': 'A', 'contactLastName': 'B', 'contactPhone': '1', 'contactEmail': 'a@b.c'},
            'subscriptions': [],
            'product_ids': [],
        })
        self.assertIn('APP STORE · en-US has no screenshots.', text)
        self.assertIn('PASS · Your code uses the same bundle id', text)

    def test_confused_question_uses_the_guide(self):
        self.assertTrue(guide.wants_guide("I'm not sure how to submit this"))
        self.assertFalse(guide.wants_guide('Check subscription pricing and offer codes'))

    def test_one_problem_at_a_time(self):
        text = '\n'.join([
            'PASS · Bundle matches',
            'APP STORE · English has no screenshots.',
            'Upload them in App Store Connect.',
            'How to fix:',
            '1. Open this version.',
            '2. Upload the iPhone screenshot.',
            'YOUR CODE · The bundle id does not match.',
            'The folder says com.other.',
            'How to fix:',
            '1. Set the bundle id.',
        ])
        items = guide.problems(text)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]['where'], 'APP STORE')
        shown, _ = guide.one_step(text, 0, False)
        self.assertIn('Step 1 of 2', shown)
        self.assertIn('Open this version.', shown)
        self.assertNotIn('Set the bundle id.', shown)
        helped, _ = guide.one_step(text, 0, True)
        self.assertIn('2. Upload the iPhone screenshot.', helped)


    def test_powershell_check_links_the_folder(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = root / 'Verifyly'
            (app / 'mobile').mkdir(parents=True)
            (app / 'mobile' / 'app.json').write_text(
                '{"ios":{"bundleIdentifier":"com.verifyly.app"}}', encoding='utf-8')
            (app / 'Pay.swift').write_text('let id = "verifyly.plus.monthly"\n', encoding='utf-8')
            lines = check_project.local_report(app, 'com.verifyly.app')
            self.assertTrue(lines[0].startswith('PASS'))
            self.assertTrue(any('com.verifyly.app is in this folder' in line for line in lines))
            settings = root / 'settings'
            with patch('check_project.store.apple_apps', return_value=[
                {'id': 'app123', 'attributes': {'name': 'Verifyly', 'bundleId': 'com.verifyly.app'}}
            ]), patch('check_project.store.token', return_value='token'), patch(
                'check_project.load_saved', return_value=('KEY', '', 'key.p8')):
                linked = check_project.link_store(settings, app, 'com.verifyly.app')
            self.assertIn('app123', json.loads((settings / 'projects.json').read_text()))
            self.assertTrue(linked[0].startswith('PASS'))


