"""Read-only Apple and Google publishing connectors."""
import base64
import os
import shutil
import json
import re
import subprocess
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

APPLE = 'https://api.appstoreconnect.apple.com'
PLAY = 'https://androidpublisher.googleapis.com/androidpublisher/v3'

def encoded(value):
    return base64.urlsafe_b64encode(value).rstrip(b'=').decode()

def apple_key_id(key_path):
    filename = re.split(r'[/\\]', key_path.strip())[-1]
    match = re.fullmatch(r'AuthKey_([A-Za-z0-9]{10})(?: \(\d+\))?\.p8', filename, re.IGNORECASE)
    return match[1].upper() if match else None

def openssl_path():
    executable = shutil.which('openssl')
    if executable:
        return executable
    for location in ('ProgramFiles', 'ProgramFiles(x86)', 'LOCALAPPDATA'):
        base = os.environ.get(location)
        if not base:
            continue
        git = Path(base) / ('Programs/Git' if location == 'LOCALAPPDATA' else 'Git')
        executable = git / 'usr/bin/openssl.exe'
        if executable.is_file():
            return str(executable)
    raise RuntimeError('OpenSSL was not found. Install Git for Windows or add OpenSSL to PATH.')

def token(key_id, issuer, key_path):
    if not Path(key_path).is_file():
        raise ValueError('The Apple key file is missing. Choose it again using Browse.')
    now = int(time.time())
    claims = {'iat': now, 'exp': now + 600, 'aud': 'appstoreconnect-v1'}
    claims.update({'iss': issuer} if issuer else {'sub': 'user'})
    parts = [encoded(json.dumps(value).encode()) for value in
             ({'alg': 'ES256', 'kid': key_id, 'typ': 'JWT'}, claims)]
    message = '.'.join(parts)
    signature = subprocess.run(
        [openssl_path(), 'dgst', '-sha256', '-sign', str(Path(key_path).resolve())],
        input=message.encode(), capture_output=True, check=True,
    ).stdout
    if len(signature) < 8 or signature[0] != 48 or signature[2] != 2:
        raise ValueError('Expected an Apple P-256 signing key')
    r_end = 4 + signature[3]
    if signature[r_end] != 2:
        raise ValueError('Invalid ECDSA signature')
    integers = (signature[4:r_end], signature[r_end + 2:])
    raw = b''.join(int.from_bytes(part, 'big').to_bytes(32, 'big') for part in integers)
    return message + '.' + encoded(raw)

def request(url, bearer, method='GET', payload=None):
    headers = {'Authorization': 'Bearer ' + bearer}
    if payload is not None:
        headers['Content-Type'] = 'application/json'
    try:
        with urlopen(Request(url, headers=headers, method=method,
                             data=json.dumps(payload).encode() if payload is not None else None),
                     timeout=25) as response:
            data = response.read()
            return json.loads(data) if data else {}
    except HTTPError as error:
        try:
            body = json.loads(error.read())
        except ValueError:
            body = {}
        details = body.get('errors', [])
        message = '; '.join(item.get('detail', item.get('title', '')) for item in details)
        if isinstance(body.get('error'), dict):
            message = body['error'].get('message', message)
        raise RuntimeError(f'Store API returned {error.code}. {message}') from None

def apple_list(path, bearer):
    url = APPLE + path
    while url:
        parsed = urlsplit(url)
        if parsed.scheme != 'https' or parsed.netloc != urlsplit(APPLE).netloc:
            raise ValueError('Unexpected Apple pagination host')
        response = request(url, bearer)
        yield from response.get('data', [])
        url = response.get('links', {}).get('next')

def apple_apps(bearer):
    return list(apple_list('/v1/apps?limit=100', bearer))

def apple_releases(app_id, bearer):
    versions = apple_list(f'/v1/apps/{app_id}/appStoreVersions?' +
                          urlencode({'include': 'build', 'limit': 20}), bearer)
    return [{'id': item['id'], **item['attributes'],
             'buildId': (item.get('relationships', {}).get('build', {}).get('data') or {}).get('id')}
            for item in versions]

def apple_listing(version_id, bearer):
    localizations = apple_list(f'/v1/appStoreVersions/{version_id}/appStoreVersionLocalizations', bearer)
    return [{'locale': loc['attributes']['locale'],
             'sets': [{'device': group['attributes']['screenshotDisplayType'],
                       'screenshots': [shot['attributes']['fileName'] for shot in
                                       apple_list(f"/v1/appScreenshotSets/{group['id']}/appScreenshots", bearer)]}
                      for group in apple_list(f"/v1/appStoreVersionLocalizations/{loc['id']}/appScreenshotSets", bearer)]}
            for loc in localizations]

def apple_offers(app_id, bearer):
    result = []
    for group in apple_list(f'/v1/apps/{app_id}/subscriptionGroups', bearer):
        for sub in apple_list(f"/v1/subscriptionGroups/{group['id']}/subscriptions", bearer):
            offers = apple_list(f"/v1/subscriptions/{sub['id']}/offerCodes", bearer)
            result.append({'product': sub['attributes'].get('productId'),
                           'state': sub['attributes'].get('state'),
                           'offers': [offer['attributes'] for offer in offers]})
    return result

def play_listing(package, bearer):
    if not re.fullmatch(r'[A-Za-z][\w]*(?:\.[A-Za-z][\w]*)+', package, re.ASCII):
        raise ValueError('Enter a valid Android package name')
    url = f'{PLAY}/applications/{package}/edits'
    edit = request(url, bearer, 'POST', {})['id']
    try:
        return request(f'{url}/{edit}/listings', bearer).get('listings', [])
    finally:
        request(f'{url}/{edit}', bearer, 'DELETE')


def apple_app(app_id, bearer):
    return request(APPLE + f'/v1/apps/{app_id}', bearer)['data']['attributes']

def apple_version_localizations(version_id, bearer):
    rows = apple_list(f'/v1/appStoreVersions/{version_id}/appStoreVersionLocalizations', bearer)
    return [{
        'locale': row['attributes'].get('locale'),
        'description': (row['attributes'].get('description') or '').strip(),
        'keywords': (row['attributes'].get('keywords') or '').strip(),
        'supportUrl': (row['attributes'].get('supportUrl') or '').strip(),
        'whatsNew': (row['attributes'].get('whatsNew') or '').strip(),
    } for row in rows]

def apple_review_detail(version_id, bearer):
    try:
        data = request(APPLE + f'/v1/appStoreVersions/{version_id}/appStoreReviewDetail', bearer)
    except RuntimeError as error:
        if '404' in str(error):
            return None
        raise
    return (data.get('data') or {}).get('attributes')

def apple_build(build_id, bearer):
    if not build_id:
        return None
    data = request(APPLE + f'/v1/builds/{build_id}', bearer)
    return (data.get('data') or {}).get('attributes') or {}

def apple_subscription_setup(app_id, bearer):
    """Read each subscription so the check can compare it with the project."""
    for group in apple_list(f'/v1/apps/{app_id}/subscriptionGroups', bearer):
        for subscription in apple_list(f"/v1/subscriptionGroups/{group['id']}/subscriptions", bearer):
            endpoint = f"/v1/subscriptions/{subscription['id']}"
            yield subscription, endpoint


def apple_us_prices(endpoint, bearer):
    query = urlencode({'filter[territory]': 'USA', 'include': 'subscriptionPricePoint'})
    url = APPLE + endpoint + '/prices?' + query
    while url:
        parsed = urlsplit(url)
        if parsed.scheme != 'https' or parsed.netloc != urlsplit(APPLE).netloc:
            raise ValueError('Unexpected Apple pagination host')
        page = request(url, bearer)
        points = {row['id']: row['attributes'].get('customerPrice')
                  for row in page.get('included', []) if row['type'] == 'subscriptionPricePoints'}
        for row in page.get('data', []):
            point = (row.get('relationships', {}).get('subscriptionPricePoint', {}).get('data') or {}).get('id')
            yield row['attributes'].get('startDate'), points.get(point), row['attributes'].get('preserved')
        url = page.get('links', {}).get('next')
