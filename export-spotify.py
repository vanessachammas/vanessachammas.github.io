#!/usr/bin/env python3
"""
Export your Spotify stats to spotify-data.json.

Usage:
  1. First run:  python3 export-spotify.py
     It will open your browser to authorize, then save your data.
  2. Later runs: python3 export-spotify.py
     It will reuse the saved refresh token.
"""

import json
import hashlib
import base64
import secrets
import http.server
import threading
import webbrowser
import urllib.parse
import urllib.request
import os
import sys

CLIENT_ID = '1bfc6a0cc6fb46189fa163bf12407c11'
CLIENT_SECRET = os.environ.get('SPOTIFY_CLIENT_SECRET', '')
REDIRECT_PORT = 8888
REDIRECT_URI = f'http://127.0.0.1:{REDIRECT_PORT}/callback'
SCOPES = 'user-top-read user-read-recently-played user-read-currently-playing'
TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.spotify-token.json')
OUTPUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'spotify-data.json')

# CI mode: use SPOTIFY_REFRESH_TOKEN env var instead of local token file
CI_MODE = os.environ.get('CI', '') == 'true'


def save_token(data):
    with open(TOKEN_FILE, 'w') as f:
        json.dump(data, f)


def load_token():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE) as f:
            return json.load(f)
    return None


def pkce_verifier():
    return secrets.token_urlsafe(96)


def pkce_challenge(verifier):
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b'=').decode()


def authorize():
    verifier = pkce_verifier()
    challenge = pkce_challenge(verifier)

    params = urllib.parse.urlencode({
        'client_id': CLIENT_ID,
        'response_type': 'code',
        'redirect_uri': REDIRECT_URI,
        'scope': SCOPES,
        'code_challenge_method': 'S256',
        'code_challenge': challenge,
    })

    auth_code = None
    server_ready = threading.Event()

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            nonlocal auth_code
            qs = urllib.parse.urlparse(self.path).query
            code = urllib.parse.parse_qs(qs).get('code', [None])[0]
            if code:
                auth_code = code
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.end_headers()
                self.wfile.write(b'<h2>Done! You can close this tab.</h2>')
            else:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b'No code received.')

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(('127.0.0.1', REDIRECT_PORT), Handler)
    thread = threading.Thread(target=server.handle_request)
    thread.start()

    url = f'https://accounts.spotify.com/authorize?{params}'
    print(f'Opening browser for authorization...')
    webbrowser.open(url)

    thread.join(timeout=120)
    server.server_close()

    if not auth_code:
        print('Authorization failed or timed out.')
        sys.exit(1)

    # Exchange code for token
    data_dict = {
        'grant_type': 'authorization_code',
        'code': auth_code,
        'redirect_uri': REDIRECT_URI,
        'code_verifier': verifier,
    }
    
    if CLIENT_SECRET:
        data_dict['client_id'] = CLIENT_ID
    else:
        data_dict['client_id'] = CLIENT_ID
    
    data = urllib.parse.urlencode(data_dict).encode()

    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    
    # Use Basic Authentication if client_secret is available
    if CLIENT_SECRET:
        credentials = base64.b64encode(f'{CLIENT_ID}:{CLIENT_SECRET}'.encode()).decode()
        headers['Authorization'] = f'Basic {credentials}'

    req = urllib.request.Request(
        'https://accounts.spotify.com/api/token',
        data=data,
        headers=headers,
    )
    
    try:
        with urllib.request.urlopen(req) as resp:
            token_data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        print(f'Error exchanging code for token (HTTP {e.code}): {error_body}', file=sys.stderr)
        raise

    save_token(token_data)
    return token_data['access_token']


def refresh(token_data):
    data_dict = {
        'grant_type': 'refresh_token',
        'refresh_token': token_data['refresh_token'],
    }
    
    # If we have client_secret, use Basic Authentication
    if CLIENT_SECRET:
        data_dict['client_id'] = CLIENT_ID
    
    data = urllib.parse.urlencode(data_dict).encode()

    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    
    # Use Basic Authentication if client_secret is available
    if CLIENT_SECRET:
        credentials = base64.b64encode(f'{CLIENT_ID}:{CLIENT_SECRET}'.encode()).decode()
        headers['Authorization'] = f'Basic {credentials}'
    else:
        # Fallback: include client_id in body for public clients
        data = urllib.parse.urlencode({
            'client_id': CLIENT_ID,
            'grant_type': 'refresh_token',
            'refresh_token': token_data['refresh_token'],
        }).encode()

    req = urllib.request.Request(
        'https://accounts.spotify.com/api/token',
        data=data,
        headers=headers,
    )
    
    try:
        with urllib.request.urlopen(req) as resp:
            new_data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        print(f'Error refreshing token (HTTP {e.code}): {error_body}', file=sys.stderr)
        raise

    if 'refresh_token' not in new_data:
        new_data['refresh_token'] = token_data['refresh_token']
    save_token(new_data)
    return new_data['access_token']


def get_access_token():
    # In CI, use the refresh token from environment
    if CI_MODE:
        rt = os.environ.get('SPOTIFY_REFRESH_TOKEN', '')
        if not rt:
            print('Error: SPOTIFY_REFRESH_TOKEN env var not set.')
            sys.exit(1)
        token_data = {'refresh_token': rt}
        try:
            return refresh(token_data)
        except Exception as e:
            print(f'Error: Failed to refresh token in CI mode. Check SPOTIFY_REFRESH_TOKEN and SPOTIFY_CLIENT_SECRET env vars.', file=sys.stderr)
            sys.exit(1)

    token_data = load_token()
    if token_data and 'refresh_token' in token_data:
        try:
            return refresh(token_data)
        except Exception:
            pass
    return authorize()


def api_get(token, path):
    req = urllib.request.Request(
        f'https://api.spotify.com/v1{path}',
        headers={'Authorization': f'Bearer {token}'},
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        if e.code == 204:
            return None
        raise


def simplify_artist(a):
    img = a['images'][-1]['url'] if a.get('images') else None
    return {'name': a['name'], 'image': img}


def simplify_track(t):
    img = t['album']['images'][-1]['url'] if t.get('album', {}).get('images') else None
    return {
        'name': t['name'],
        'artists': ', '.join(a['name'] for a in t['artists']),
        'image': img,
    }


def main():
    token = get_access_token()
    print('Fetching your Spotify data...')

    ranges = ['short_term', 'medium_term', 'long_term']
    artists = {}
    tracks = {}
    for r in ranges:
        data = api_get(token, f'/me/top/artists?limit=10&time_range={r}')
        artists[r] = [simplify_artist(a) for a in (data.get('items') or [])]

        data = api_get(token, f'/me/top/tracks?limit=10&time_range={r}')
        tracks[r] = [simplify_track(t) for t in (data.get('items') or [])]

    recent_data = api_get(token, '/me/player/recently-played?limit=10')
    recent = []
    if recent_data and recent_data.get('items'):
        for item in recent_data['items']:
            t = item['track']
            recent.append({
                **simplify_track(t),
                'played_at': item['played_at'],
            })

    from datetime import datetime, timezone
    output = {
        'updated': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'top_artists': artists,
        'top_tracks': tracks,
        'recent': recent,
    }

    with open(OUTPUT_FILE, 'w') as f:
        json.dump(output, f, indent=2)

    print(f'Saved to {OUTPUT_FILE}')
    print(f'  Top artists: {len(artists["short_term"])} (short), {len(artists["medium_term"])} (medium), {len(artists["long_term"])} (long)')
    print(f'  Top tracks:  {len(tracks["short_term"])} (short), {len(tracks["medium_term"])} (medium), {len(tracks["long_term"])} (long)')
    print(f'  Recent:      {len(recent)} tracks')


if __name__ == '__main__':
    main()
