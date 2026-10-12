"""
app.py — TBG Proposal Generation Server v4
- Dynamic plan data from webhook (no proposal_data.py dependency)
- Client info built from webhook payload
- Dynamic selector URL per client
"""

import os, re, sys, json
from datetime import datetime
from flask import Flask, request, jsonify

app = Flask(__name__)

def scrub_name(value):
    """Strip invisible characters that ride along from the selector page / Zapier.

    A trailing BOM (\ufeff) on the client name is why GunnCo's proposal missed its folder
    on 2026-10-12: the lookup path ended in a character Dropbox has no match for.
    """
    if not value:
        return ''
    for ch in ('\ufeff', '\u200b', '\u200c', '\u200d', '\u2060'):
        value = value.replace(ch, '')
    value = value.replace('\u00a0', ' ')
    return ' '.join(value.split()).strip()


def find_client_dropbox_folder(client_name, dbx):
    search_name = scrub_name(client_name.replace(' — Review for Proposal', ''))
    if not search_name:
        return None

    roots = [
        "/Solutionpoint Groups/1. Solutionpoint Groups/Proposals/2026/{n}",
        "/Solutionpoint Groups/1. Solutionpoint Groups/2.  HOT LEADS/{n}/Quoting/3. Proposal",
        "/Solutionpoint Groups/1. Solutionpoint Groups/3. WARM LEADS/{n}/Quoting/3. Proposal",
        "/Solutionpoint Groups/1. Solutionpoint Groups/4. RENEWALS/{n}/Quoting/3. Proposal",
        "/Solutionpoint Groups/1. Solutionpoint Groups/1. CURRENT CLIENTS/{n}/Quoting/3. Proposal",
    ]

    import re as _re
    names = [search_name]
    trimmed = _re.sub(r'[,\s]+(inc|llc|l\.l\.c\.|co|corp|corporation|ltd)\.?$', '', search_name, flags=_re.I).strip()
    if trimmed and trimmed != search_name:
        names.append(trimmed)

    for name in names:
        for template in roots:
            path = template.format(n=name)
            try:
                dbx.files_get_metadata(path)
                print(f"Found existing folder: {path}", flush=True)
                return path
            except Exception:
                continue

    # No path matched. Search Dropbox for the client's folder before falling back.
    try:
        import dropbox as _dbx
        opts = _dbx.files.SearchOptions(
            path="/Solutionpoint Groups/1. Solutionpoint Groups",
            file_status=_dbx.files.FileStatus.active,
            filename_only=True,
        )
        res = dbx.files_search_v2(query=names[-1], options=opts)
        for match in res.matches:
            meta = match.metadata.get_metadata()
            if not isinstance(meta, _dbx.files.FolderMetadata):
                continue
            candidate = f"{meta.path_lower}/quoting/3. proposal"
            try:
                found = dbx.files_get_metadata(candidate)
                print(f"Found folder by search: {found.path_display}", flush=True)
                return found.path_display
            except Exception:
                continue
    except Exception as e:
        print(f"Dropbox folder search failed: {e}", flush=True)

    print(f"NO FOLDER MATCH for '{search_name}' — using the fallback path", flush=True)
    return None


def canonical_selector_url(url, clean_name=''):
    """Always hand Asana the live GitHub Pages link.

    The selector page sends selector_url = window.location.href. Opened from the Dropbox
    backup copy that is a file:///C:/Users/... path, which only resolves on one machine —
    Lindsey or Alex clicking it gets nothing (Will, 2026-10-12). Keep https URLs as they
    are; rebuild anything else from the page's filename.
    """
    import os as _os, urllib.parse as _up
    PAGES = 'https://solutionpointmail-rgb.github.io/proposal/'
    if url and url.lower().startswith('https://'):
        return url
    name = ''
    if url:
        cleaned = url.split('?')[0].split('#')[0].replace('\\', '/')
        name = _os.path.basename(_up.unquote(cleaned))
    if not name.lower().endswith('.html'):
        safe_client = (clean_name or '').lower()
        for ch in (' ', '_', '-', '.', ',', '&'):
            safe_client = safe_client.replace(ch, '')
        name = f"{safe_client}-aug2026.html" if safe_client else ''
    return PAGES + name if name else ''


def parse_plan_names(plans_text):
    """Parse comma-separated plan names."""
    if not plans_text:
        return []
    plans = []
    for p in re.split(r'[,\n]', plans_text):
        p = p.strip()
        if p and len(p) > 2:
            plans.append(p)
    return plans


def build_client_and_plans(client_name, effective_date, quote_id, enrolling_employees,
                            contributions, medical_plans_str, dental_plans_str, vision_plans_str,
                            all_medical_json, all_dental_json, all_vision_json):
    """
    Build CLIENT dict and plan lists from webhook data.
    Uses full plan JSON if available, otherwise falls back to plan names only.
    """
    clean_name = scrub_name(client_name.replace(' — Review for Proposal', ''))

    CLIENT = {
        'name': clean_name,
        'effective_date': effective_date or 'August 1, 2026',
        'effective_date_mmddyyyy': '08/01/2026',
        'quote_id': quote_id or 'TBD',
        'state': 'TN',
        'zip': '37212',
        'county': 'Davidson',
        'sic': '9512',
        'sic_code': '9512',
        'address': '1213 16th Ave South',
        'city_state_zip': 'Nashville, TN 37212',
        'tier_ee': 'Employee Only',
        'tier_es': 'Employee + Spouse',
        'tier_ec': 'Employee + Children',
        'tier_ef': 'Employee + Family',
        'total_employees': int(enrolling_employees) if enrolling_employees else 15,
        'eligible_employees': int(enrolling_employees) if enrolling_employees else 15,
        'enrolling_employees': int(enrolling_employees) if enrolling_employees else 15,
        'waiving_employees': 0,
        'presenter_name': 'The Benefits Group',
        'presenter_phone': '(615) 560-3667',
        'presenter_email': 'happy@benefits.place',
        'agency': 'Solutionpoint Consulting',
    }

    CONTRIBUTIONS = {
        'medical_ee': contributions.get('medical_ee', '50%'),
        'medical_dep': contributions.get('medical_dep', '0%'),
        'dental_ee': contributions.get('dental_ee', '0%'),
        'dental_dep': contributions.get('dental_dep', '0%'),
        'vision_ee': contributions.get('vision_ee', '0%'),
        'vision_dep': contributions.get('vision_dep', '0%'),
        'life': '100% employee only',
    }

    # Selected plan names
    med_sel = parse_plan_names(medical_plans_str)
    den_sel = parse_plan_names(dental_plans_str)
    vis_sel = parse_plan_names(vision_plans_str)

    # Try to use full plan JSON objects from webhook
    def filter_plans(all_json, selected_names, default_include_all):
        try:
            all_plans = json.loads(all_json) if all_json else []
        except Exception:
            all_plans = []

        if not all_plans:
            return []

        if not selected_names:
            # Nothing selected for this coverage line. An empty selection means the broker
            # deliberately left this line out — include none. Before 2026-10-12 this
            # included every plan, which is how a proposal ended up with 47 dental plans.
            # The include-everything fallback only applies when the request carried no
            # selection fields at all (default_include_all), i.e. an older caller.
            for p in all_plans:
                p['include'] = bool(default_include_all)
            return all_plans

        for p in all_plans:
            p['include'] = any(
                sel.lower().strip() in p['plan_name'].lower() or
                p['plan_name'].lower() in sel.lower().strip()
                for sel in selected_names
            )
        return all_plans

    # True only when the caller sent no selection fields whatsoever (legacy payload).
    legacy_payload = all(v is None for v in (medical_plans_str, dental_plans_str, vision_plans_str))

    MEDICAL_PLANS = filter_plans(all_medical_json, med_sel, legacy_payload)
    DENTAL_PLANS  = filter_plans(all_dental_json,  den_sel, legacy_payload)
    VISION_PLANS  = filter_plans(all_vision_json,  vis_sel, legacy_payload)

    print(f"Medical plans loaded: {len(MEDICAL_PLANS)} total, {sum(1 for p in MEDICAL_PLANS if p.get('include'))} selected", flush=True)
    print(f"Dental plans loaded:  {len(DENTAL_PLANS)} total, {sum(1 for p in DENTAL_PLANS if p.get('include'))} selected", flush=True)
    print(f"Vision plans loaded:  {len(VISION_PLANS)} total, {sum(1 for p in VISION_PLANS if p.get('include'))} selected", flush=True)

    return CLIENT, CONTRIBUTIONS, MEDICAL_PLANS, DENTAL_PLANS, VISION_PLANS


def run_pipeline(client_name, effective_date, quote_id, task_id, notes,
                 medical_plans='', dental_plans='', vision_plans='',
                 enrolling_employees='', contributions=None,
                 all_medical_json='', all_dental_json='', all_vision_json='',
                 selector_url=''):

    print(f"=== PIPELINE START: {client_name} ===", flush=True)

    try:
        sys.path.insert(0, '/opt/render/project/src')

        if contributions is None:
            contributions = {}

        CLIENT, CONTRIBUTIONS, MEDICAL_PLANS, DENTAL_PLANS, VISION_PLANS = build_client_and_plans(
            client_name, effective_date, quote_id, enrolling_employees, contributions,
            medical_plans, dental_plans, vision_plans,
            all_medical_json, all_dental_json, all_vision_json
        )

        clean_name = CLIENT['name']

        # Inject into proposal_data module so generate_pdf/excel pick them up
        import proposal_data as pd_module
        pd_module.CLIENT       = CLIENT
        pd_module.CONTRIBUTIONS = CONTRIBUTIONS
        pd_module.MEDICAL_PLANS = MEDICAL_PLANS
        pd_module.DENTAL_PLANS  = DENTAL_PLANS
        pd_module.VISION_PLANS  = VISION_PLANS
        pd_module.PRODUCER = {
            'name':      'William Brown',
            'agency':    'The Benefits Group',
            'sub_agency': 'Solutionpoint Consulting',
            'phone':     '(615) 560-3667',
            'email':     'happy@benefits.place',
        }
        if not hasattr(pd_module, 'DISCLAIMER_TEXT') or not pd_module.DISCLAIMER_TEXT:
            pd_module.DISCLAIMER_TEXT = (
                'This proposal is for informational purposes only and is subject to carrier approval. '
                'Rates and benefits are not guaranteed until formally issued by the carrier. '
                'Prepared by The Benefits Group / Solutionpoint Consulting.'
            )

        inc_med = [p['plan_name'] for p in MEDICAL_PLANS if p.get('include')]
        inc_den = [p['plan_name'] for p in DENTAL_PLANS  if p.get('include')]
        inc_vis = [p['plan_name'] for p in VISION_PLANS  if p.get('include')]
        print(f"Including medical: {inc_med}", flush=True)
        print(f"Including dental:  {inc_den}", flush=True)
        print(f"Including vision:  {inc_vis}", flush=True)

        # Generate files
        timestamp  = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_name  = clean_name.replace(' ', '_').replace('/', '-')
        pdf_name   = f"Proposal_{safe_name}_{timestamp}.pdf"
        excel_name = f"Proposal_{safe_name}_{timestamp}.xlsx"
        pdf_path   = f"/tmp/{pdf_name}"
        excel_path = f"/tmp/{excel_name}"

        print("Generating PDF...", flush=True)
        from generate_pdf import generate_pdf
        generate_pdf(pdf_path)
        print(f"✅ PDF: {pdf_name}", flush=True)

        print("Generating Excel...", flush=True)
        from generate_excel import generate_excel
        generate_excel(excel_path)
        print(f"✅ Excel: {excel_name}", flush=True)

        # Upload to Dropbox
        print("Uploading to Dropbox...", flush=True)
        import dropbox as dbx_module
        dbx = dbx_module.Dropbox(
            oauth2_refresh_token=os.environ['DROPBOX_REFRESH_TOKEN'],
            app_key=os.environ['DROPBOX_APP_KEY'],
            app_secret=os.environ['DROPBOX_APP_SECRET']
        )

        existing_folder = find_client_dropbox_folder(clean_name, dbx)
        folder = existing_folder or f"/Benefits Group/Proposals/2026/{safe_name}"
        if not existing_folder:
            print(f"Using new folder: {folder}", flush=True)

        links = {}
        for local_path, file_name in [(pdf_path, pdf_name), (excel_path, excel_name)]:
            db_path = f"{folder}/{file_name}"
            with open(local_path, 'rb') as f:
                dbx.files_upload(f.read(), db_path,
                                 mode=dbx_module.files.WriteMode.overwrite)
            try:
                link = dbx.sharing_create_shared_link_with_settings(db_path)
                links[file_name] = link.url.replace('?dl=0', '?dl=1')
            except dbx_module.exceptions.ApiError:
                existing = dbx.sharing_list_shared_links(path=db_path)
                links[file_name] = existing.links[0].url.replace('?dl=0', '?dl=1')
            print(f"✅ Uploaded: {file_name} → {folder}", flush=True)

        # Update Asana
        print("Updating Asana...", flush=True)
        import requests
        headers = {
            'Authorization': f"Bearer {os.environ['ASANA_TOKEN']}",
            'Content-Type': 'application/json'
        }

        requests.post(
            'https://app.asana.com/api/1.0/sections/1216532264374832/addTask',
            headers=headers,
            json={'data': {'task': task_id}}
        )

        pdf_link   = links.get(pdf_name,   'Not available')
        excel_link = links.get(excel_name, 'Not available')

        # Always link Asana to the live page, never to a local Dropbox copy
        selector_url = canonical_selector_url(selector_url, clean_name)

        comment = (
            f"✅ Proposal generated!\n\n"
            f"📄 PDF: {pdf_link}\n"
            f"📊 Excel: {excel_link}\n\n"
            f"📁 Saved to: {folder}\n\n"
            f"Plans included:\n"
            f"Medical ({len(inc_med)}): {', '.join(inc_med) if inc_med else 'None selected'}\n"
            f"Dental ({len(inc_den)}): {', '.join(inc_den) if inc_den else 'None selected'}\n"
            f"Vision ({len(inc_vis)}): {', '.join(inc_vis) if inc_vis else 'None selected'}\n\n"
            f"🔄 Revise selections: {selector_url}\n(A backup copy of this page is also in the client's Quoting/3. Proposal folder.)\n\n"
            f"Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}"
        )
        requests.post(
            f'https://app.asana.com/api/1.0/tasks/{task_id}/stories',
            headers=headers,
            json={'data': {'text': comment}}
        )
        print(f"✅ Asana task {task_id} → Delivered", flush=True)
        print(f"=== PIPELINE COMPLETE: {clean_name} ===", flush=True)
        return True, folder, pdf_link, excel_link

    except Exception as e:
        print(f"❌ PIPELINE ERROR: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return False, None, None, None


@app.route('/', methods=['GET'])
def health():
    return jsonify({'status': 'TBG Proposal Generator v4', 'version': '4.0'})


@app.route('/generate', methods=['POST'])
def generate():
    if not _tbg_authorized():
        return jsonify({'error': 'unauthorized'}), 401
    data = request.get_json(force=True, silent=True) or request.form.to_dict()

    client_name         = data.get('client_name', '')
    effective_date      = data.get('effective_date', '')
    quote_id            = data.get('quote_id', '')
    task_id             = data.get('task_id', '')
    notes               = data.get('notes', '')
    medical_plans       = data.get('medical_plans')
    dental_plans        = data.get('dental_plans')
    vision_plans        = data.get('vision_plans')
    enrolling_employees = data.get('enrolling_employees', '')
    selector_url        = data.get('selector_url', '')
    all_medical_json    = data.get('all_medical_json', '')
    all_dental_json     = data.get('all_dental_json', '')
    all_vision_json     = data.get('all_vision_json', '')

    import json as _j, base64 as _b64

    def decode_plan_field(val):
        """Decode base64-encoded plan JSON from selector page, or fall back to raw string."""
        if not val:
            return ''
        if isinstance(val, list):
            return _j.dumps(val)
        s = str(val).strip()
        # Try base64 decode first
        try:
            decoded = _b64.b64decode(s).decode('utf-8')
            if decoded.startswith('[') or decoded.startswith('{'):
                print(f"  ✅ base64 decoded: {len(decoded)} chars", flush=True)
                return decoded
        except Exception:
            pass
        # Already a JSON string?
        if s.startswith('['):
            return s
        return s

    all_medical_json = decode_plan_field(all_medical_json)
    all_dental_json  = decode_plan_field(all_dental_json)
    all_vision_json  = decode_plan_field(all_vision_json)

    # Also check raw_payload for enrolling_employees and selector_url
    raw_payload = data.get('raw_payload', '')
    if raw_payload:
        try:
            raw = _j.loads(raw_payload) if isinstance(raw_payload, str) else raw_payload
            if isinstance(raw, dict):
                if not enrolling_employees:
                    enrolling_employees = str(raw.get('enrolling_employees', ''))
                if not selector_url:
                    selector_url = raw.get('selector_url', '')
        except Exception:
            pass

    print(f"✅ Final plan data — med:{len(str(all_medical_json))} den:{len(str(all_dental_json))} vis:{len(str(all_vision_json))} chars", flush=True)

    # Contributions
    contributions = {
        'medical_ee':  data.get('contributions_medical_ee', '50%'),
        'medical_dep': data.get('contributions_medical_dep', '0%'),
        'dental_ee':   data.get('contributions_dental_ee', '0%'),
        'dental_dep':  data.get('contributions_dental_dep', '0%'),
        'vision_ee':   data.get('contributions_vision_ee', '0%'),
        'vision_dep':  data.get('contributions_vision_dep', '0%'),
    }

    print(f"Received: {client_name} | task: {task_id}", flush=True)
    print(f"Medical selected: {medical_plans}", flush=True)
    print(f"Dental selected:  {dental_plans}", flush=True)
    print(f"Vision selected:  {vision_plans}", flush=True)

    if not client_name or not task_id:
        return jsonify({'error': 'Missing client_name or task_id'}), 400

    success, folder, pdf_link, excel_link = run_pipeline(
        client_name, effective_date, quote_id, task_id, notes,
        medical_plans, dental_plans, vision_plans,
        enrolling_employees, contributions,
        all_medical_json, all_dental_json, all_vision_json,
        selector_url
    )

    if success:
        return jsonify({
            'status':     'complete',
            'message':    f'Proposal generated for {client_name}',
            'folder':     folder,
            'pdf_link':   pdf_link,
            'excel_link': excel_link
        }), 200
    else:
        return jsonify({'status': 'error', 'message': 'Pipeline failed — check Render logs'}), 500


@app.route('/push-to-github', methods=['POST'])
def push_to_github():
    if not _tbg_authorized():
        return jsonify({'error': 'unauthorized'}), 401
    data = request.get_json(force=True, silent=True) or {}
    filename     = data.get('filename', '')
    html_content = data.get('content', '')
    gh_token     = data.get('github_token', '') or os.environ.get('GITHUB_TOKEN', '')
    if not filename or not html_content:
        return jsonify({'error': 'Missing filename or content'}), 400
    if not gh_token:
        return jsonify({'error': 'Missing github_token'}), 400
    import base64 as b64, urllib.request as ur
    api_url = f'https://api.github.com/repos/solutionpointmail-rgb/proposal/contents/{filename}'
    hdrs = {'Authorization': f'token {gh_token}', 'Accept': 'application/vnd.github.v3+json', 'Content-Type': 'application/json'}
    sha = None
    try:
        req = ur.Request(api_url, headers=hdrs)
        with ur.urlopen(req) as r:
            sha = json.loads(r.read()).get('sha')
    except Exception:
        pass
    payload = {'message': f'Auto-generate selector: {filename}', 'content': b64.b64encode(html_content.encode()).decode()}
    if sha:
        payload['sha'] = sha
    try:
        req = ur.Request(api_url, data=json.dumps(payload).encode(), method='PUT', headers=hdrs)
        with ur.urlopen(req) as r:
            json.loads(r.read())
        url = f'https://solutionpointmail-rgb.github.io/proposal/{filename}'
        print(f'✅ Pushed {filename}', flush=True)
        return jsonify({'status': 'success', 'filename': filename, 'url': url}), 200
    except Exception as e:
        print(f'❌ GitHub push error: {e}', flush=True)
        return jsonify({'error': str(e)}), 500


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
def tbg_health():
    """Quick check that the app is awake and configured. No secret required."""
    return jsonify({
        'status': 'ok',
        'secret_configured': bool(TBG_SECRET),
        'github_token_configured': bool(os.environ.get('GITHUB_TOKEN')),
        'dropbox_configured': all(os.environ.get(k) for k in
                                  ('DROPBOX_REFRESH_TOKEN', 'DROPBOX_APP_KEY', 'DROPBOX_APP_SECRET')),
    }), 200



# ============================================================
# LIVE GROUP LIST — added 2026-10-12
# GET /clients?t=<TBG_READ_TOKEN>
# Returns the groups currently in the pipeline, read from Asana, so the
# Action Center's picker stops being a hand-typed list.
# ============================================================

TBG_READ_TOKEN = os.environ.get('TBG_READ_TOKEN', '')

_CLIENTS_CACHE = {'at': 0, 'payload': None}
_CLIENTS_TTL = 300          # seconds; Asana is polled at most once every 5 minutes
_PAGES_BASE = 'https://solutionpointmail-rgb.github.io/proposal/'

# Sandbox and placeholder projects that must never reach the picker.
_SKIP_WORDS = ('test', 'acme', 'testco', 'not sure', 'bofa deez', 'sample', 'demo')


def _asana_get(path, params=None):
    import requests as _rq
    r = _rq.get(
        f'https://app.asana.com/api/1.0/{path}',
        headers={'Authorization': f"Bearer {os.environ['ASANA_TOKEN']}"},
        params=params or {}, timeout=25,
    )
    r.raise_for_status()
    return r.json()


def _slug(name):
    out = []
    for ch in (name or '').lower():
        if ch.isalnum():
            out.append(ch)
    return ''.join(out)


def _selector_index():
    """Map slug -> live selector page URL, from the files in the proposal repo."""
    import urllib.request as ur
    index = {}
    token = os.environ.get('GITHUB_TOKEN', '')
    if not token:
        return index
    req = ur.Request(
        'https://api.github.com/repos/solutionpointmail-rgb/proposal/contents/',
        headers={'Authorization': f'token {token}', 'Accept': 'application/vnd.github.v3+json'},
    )
    try:
        with ur.urlopen(req, timeout=20) as r:
            for entry in json.loads(r.read()):
                name = entry.get('name', '')
                if entry.get('type') == 'file' and name.endswith('.html') and 'template' not in name:
                    index[_slug(name.rsplit('-', 1)[0])] = _PAGES_BASE + name
    except Exception as e:
        print(f'selector index failed: {e}', flush=True)
    return index


def _group_name_from_project(project_name):
    """'Acme Co Quoting 12/01/2026' -> ('Acme Co', 'quoting'). None if it isn't one of ours."""
    import re as _re
    low = project_name.lower()
    kind = 'renewal' if 'renewal' in low else ('quoting' if 'quoting' in low else None)
    if not kind:
        return None, None
    cut = _re.split(r'\b(quoting|renewal)\b', project_name, maxsplit=1, flags=_re.I)[0]
    cut = _re.sub(r'[\s,\-–—:]+$', '', cut).strip()
    return (cut or None), kind


def _match_selector(name, index):
    """Find this group's selector page. File names drop suffixes like Inc/LLC, so match loosely."""
    import re as _re
    want = _slug(name)
    if want in index:
        return index[want]
    core = _slug(_re.sub(r'[,\s]+(inc|llc|l\.l\.c\.|co|corp|corporation|ltd)\.?$', '', name, flags=_re.I))
    if core and core in index:
        return index[core]
    for key, url in index.items():
        if len(key) >= 6 and (want.startswith(key) or key.startswith(core or want)):
            return url
    return None


@app.route('/clients', methods=['GET'])
def clients():
    """Live group list for the Action Center picker. Read-only, its own token."""
    import time as _t
    supplied = request.args.get('t', '') or request.headers.get('X-TBG-Read', '')
    if not TBG_READ_TOKEN or supplied != TBG_READ_TOKEN:
        return jsonify({'error': 'unauthorized'}), 401

    if _CLIENTS_CACHE['payload'] and (_t.time() - _CLIENTS_CACHE['at']) < _CLIENTS_TTL:
        body = dict(_CLIENTS_CACHE['payload'], cached=True)
        resp = jsonify(body)
        resp.headers['Access-Control-Allow-Origin'] = '*'
        return resp, 200

    try:
        workspaces = _asana_get('workspaces').get('data', [])
        if not workspaces:
            raise RuntimeError('no Asana workspace visible to this token')
        ws = workspaces[0]['gid']

        projects, offset = [], None
        while True:
            params = {'workspace': ws, 'archived': 'false', 'limit': 100, 'opt_fields': 'name'}
            if offset:
                params['offset'] = offset
            page = _asana_get('projects', params)
            projects.extend(page.get('data', []))
            offset = (page.get('next_page') or {}).get('offset')
            if not offset or len(projects) > 600:
                break

        selectors = _selector_index()
        seen, groups = set(), []
        for p in projects:
            raw = (p.get('name') or '').strip()
            low = raw.lower()
            if any(w in low for w in _SKIP_WORDS):
                continue
            name, kind = _group_name_from_project(raw)
            if not name or name.lower() in seen:
                continue
            seen.add(name.lower())
            entry = {'name': name, 'kind': kind, 'project': raw}
            url = _match_selector(name, selectors)
            if url:
                entry['selector'] = url
            groups.append(entry)

        groups.sort(key=lambda g: g['name'].lower())
        payload = {'generated': _t.strftime('%Y-%m-%dT%H:%M:%SZ', _t.gmtime()),
                   'count': len(groups), 'groups': groups}
        _CLIENTS_CACHE['at'] = _t.time()
        _CLIENTS_CACHE['payload'] = payload
        print(f'/clients: {len(groups)} groups from {len(projects)} projects', flush=True)
        resp = jsonify(dict(payload, cached=False))
        resp.headers['Access-Control-Allow-Origin'] = '*'
        return resp, 200

    except Exception as e:
        print(f'/clients error: {e}', flush=True)
        resp = jsonify({'error': str(e)})
        resp.headers['Access-Control-Allow-Origin'] = '*'
        return resp, 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
