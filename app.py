# ============================================================
# DIRECT-WRITE ENDPOINTS — added 2026-10-12
# Lets the Claude routines write straight to Dropbox and GitHub
# instead of handing files to a person to file by hand.
# Paste this block into app.py just above:  if __name__ == '__main__':
# ============================================================

TBG_SECRET = os.environ.get('TBG_API_SECRET', '')


def _tbg_authorized():
    """Every endpoint below requires the shared secret. No secret set = refuse everything."""
    return bool(TBG_SECRET) and request.headers.get('X-TBG-Secret', '') == TBG_SECRET


def _dropbox_client():
    import dropbox as dbx_module
    client = dbx_module.Dropbox(
        oauth2_refresh_token=os.environ['DROPBOX_REFRESH_TOKEN'],
        app_key=os.environ['DROPBOX_APP_KEY'],
        app_secret=os.environ['DROPBOX_APP_SECRET'],
    )
    return dbx_module, client


def _github_put(filename, content_bytes, gh_token, message):
    """Create or update a file in the proposal repo. Returns the Pages URL."""
    import base64 as b64, urllib.request as ur
    api_url = f'https://api.github.com/repos/solutionpointmail-rgb/proposal/contents/{filename}'
    hdrs = {
        'Authorization': f'token {gh_token}',
        'Accept': 'application/vnd.github.v3+json',
        'Content-Type': 'application/json',
    }
    sha = None
    try:
        req = ur.Request(api_url, headers=hdrs)
        with ur.urlopen(req) as r:
            sha = json.loads(r.read()).get('sha')
    except Exception:
        pass  # file doesn't exist yet
    payload = {'message': message, 'content': b64.b64encode(content_bytes).decode()}
    if sha:
        payload['sha'] = sha
    req = ur.Request(api_url, data=json.dumps(payload).encode(), method='PUT', headers=hdrs)
    with ur.urlopen(req) as r:
        json.loads(r.read())
    return f'https://solutionpointmail-rgb.github.io/proposal/{filename}'


@app.route('/save-file', methods=['POST'])
def save_file():
    """
    Write any file to Dropbox. The body is the raw file bytes, so .docx, .pdf and
    .xlsx all work — nothing is base64-encoded or retyped along the way.

      curl -X POST https://proposal-fgqm.onrender.com/save-file \
        -H "X-TBG-Secret: $TBG_API_SECRET" \
        -H "X-Dropbox-Path: /Solutionpoint Groups/1. Solutionpoint Groups/1. CURRENT CLIENTS/Acme Co/Quoting/3. Proposal/Acme Co Renewal Carrier Comparison DRAFT.docx" \
        --data-binary @"Acme Co Renewal Carrier Comparison DRAFT.docx"
    """
    if not _tbg_authorized():
        return jsonify({'error': 'unauthorized'}), 401

    dropbox_path = request.headers.get('X-Dropbox-Path', '').strip()
    if not dropbox_path.startswith('/'):
        return jsonify({'error': 'X-Dropbox-Path header missing, or does not start with /'}), 400

    body = request.get_data()
    if not body:
        return jsonify({'error': 'Empty body — send the file with --data-binary'}), 400

    overwrite = request.headers.get('X-Overwrite', 'true').lower() != 'false'

    try:
        dbx_module, dbx = _dropbox_client()
        mode = (dbx_module.files.WriteMode.overwrite if overwrite
                else dbx_module.files.WriteMode.add)
        meta = dbx.files_upload(body, dropbox_path, mode=mode, autorename=not overwrite)

        link = ''
        try:
            link = dbx.sharing_create_shared_link_with_settings(meta.path_display).url
        except dbx_module.exceptions.ApiError:
            existing = dbx.sharing_list_shared_links(path=meta.path_display).links
            if existing:
                link = existing[0].url

        print(f"✅ save-file: {len(body)} bytes → {meta.path_display}", flush=True)
        return jsonify({
            'status': 'success',
            'path': meta.path_display,
            'bytes': len(body),
            'link': link,
        }), 200
    except Exception as e:
        print(f"❌ save-file error: {e}", flush=True)
        return jsonify({'error': str(e)}), 500


@app.route('/push-selector', methods=['POST'])
def push_selector():
    """
    Publish a plan selector page to GitHub Pages. The body is the raw HTML.

      curl -X POST https://proposal-fgqm.onrender.com/push-selector \
        -H "X-TBG-Secret: $TBG_API_SECRET" \
        -H "X-Filename: acmeco-dec2026.html" \
        --data-binary @acmeco-dec2026.html
    """
    if not _tbg_authorized():
        return jsonify({'error': 'unauthorized'}), 401

    filename = request.headers.get('X-Filename', '').strip()
    if not filename.endswith('.html') or '/' in filename:
        return jsonify({'error': 'X-Filename must be a bare .html filename'}), 400

    body = request.get_data()
    if not body:
        return jsonify({'error': 'Empty body — send the HTML with --data-binary'}), 400

    gh_token = os.environ.get('GITHUB_TOKEN', '')
    if not gh_token:
        return jsonify({'error': 'GITHUB_TOKEN is not set on the server'}), 500

    try:
        url = _github_put(filename, body, gh_token, f'Auto: selector page for {filename}')
        print(f"✅ push-selector: {filename}", flush=True)
        return jsonify({'status': 'success', 'filename': filename, 'url': url}), 200
    except Exception as e:
        print(f"❌ push-selector error: {e}", flush=True)
        return jsonify({'error': str(e)}), 500


@app.route('/health', methods=['GET'])
def health():
    """Quick check that the app is awake and configured. No secret required."""
    return jsonify({
        'status': 'ok',
        'secret_configured': bool(TBG_SECRET),
        'github_token_configured': bool(os.environ.get('GITHUB_TOKEN')),
        'dropbox_configured': all(os.environ.get(k) for k in
                                  ('DROPBOX_REFRESH_TOKEN', 'DROPBOX_APP_KEY', 'DROPBOX_APP_SECRET')),
    }), 200


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
