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


def _mmddyyyy(value):
    """'December 1, 2026', '12/1/2026' or '2026-12-01' -> '12/01/2026'. Blank if unparseable."""
    if not value:
        return ''
    for fmt in ('%B %d, %Y', '%b %d, %Y', '%m/%d/%Y', '%Y-%m-%d', '%m-%d-%Y'):
        try:
            return datetime.strptime(value.strip(), fmt).strftime('%m/%d/%Y')
        except ValueError:
            continue
    return ''


def build_client_and_plans(client_name, effective_date, quote_id, enrolling_employees,
                            contributions, medical_plans_str, dental_plans_str, vision_plans_str,
                            all_medical_json, all_dental_json, all_vision_json):
    """
    Build CLIENT dict and plan lists from webhook data.
    Uses full plan JSON if available, otherwise falls back to plan names only.
    """
    clean_name = scrub_name(client_name.replace(' — Review for Proposal', ''))

    # Address, county and SIC are not in the selector payload. They used to be hard-coded
    # (a Nashville address, Davidson County, SIC 9512) and printed on every client's proposal.
    # Leave them blank; the PDF and Excel skip blank lines.
    CLIENT = {
        'name': clean_name,
        'effective_date': effective_date or 'TBD',
        'effective_date_mmddyyyy': _mmddyyyy(effective_date),
        'quote_id': quote_id or 'TBD',
        'state': '',
        'zip': '',
        'county': '',
        'sic': '',
        'sic_code': '',
        'address': '',
        'city_state_zip': '',
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
        'agency': 'The Benefits Group',
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
            'sub_agency': '',
            'phone':     '(615) 560-3667',
            'email':     'happy@benefits.place',
        }
        if not hasattr(pd_module, 'DISCLAIMER_TEXT') or not pd_module.DISCLAIMER_TEXT:
            pd_module.DISCLAIMER_TEXT = (
                'This proposal is for informational purposes only and is subject to carrier approval. '
                'Rates and benefits are not guaranteed until formally issued by the carrier. '
                'Prepared by The Benefits Group.'
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
        # No match never creates a per-client folder (that is how the stray
        # /Benefits Group/Proposals/2026/GunnCo folder appeared). Unmatched
        # proposals all land in ONE holding folder and the Asana comment says so.
        UNFILED_FOLDER = "/Benefits Group/Proposals/_NEEDS FILING"
        folder = existing_folder or UNFILED_FOLDER
        if not existing_folder:
            print(f"⚠️ No client folder for '{clean_name}' — filing in {folder}", flush=True)

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

        unfiled_warning = "" if existing_folder else (
            f"⚠️ NEEDS FILING: no Dropbox folder matched \"{clean_name}\" under HOT LEADS, "
            f"WARM LEADS, RENEWALS or CURRENT CLIENTS, so the files went to {folder}. "
            f"Move them into the client's Quoting/3. Proposal folder, and check the folder "
            f"name matches the Asana name.\n\n"
        )
        comment = (
            unfiled_warning +
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
_SKIP_WORDS = ('test', 'acme', 'testco', 'not sure', 'bofa deez', 'sample', 'demo', 'keep here', 'retrieval', 'group status')


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
    """
    'Acme Co Quoting 12/01/2026' -> ('Acme Co', 'quoting'). None if it isn't one of ours.

    A real project name ends with the keyword or with an effective date. Utility
    boards put words after it instead — "Carrier Renewal Retrieval", "LEAD &
    RENEWAL GROUP STATUS", "AAA - KEEP HERE - Renewal Acceptance from website" —
    so anything with a non-date tail is dropped.
    """
    import re as _re
    low = project_name.lower()
    kind = 'renewal' if 'renewal' in low else ('quoting' if 'quoting' in low else None)
    if not kind:
        return None, None

    parts = _re.split(r'\b(quoting|renewal)\b', project_name, maxsplit=1, flags=_re.I)
    head = parts[0]
    tail = parts[2] if len(parts) > 2 else ''

    # Tail must be empty or just an effective date.
    if not _re.match(r'^[\s,\-–—:()]*(\d{1,2}[/\-.]\d{1,2}([/\-.]\d{2,4})?)?[\s,\-–—:()]*$', tail):
        return None, None

    name = _re.sub(r'[\s,\-–—:]+$', '', head).strip()

    # An unmatched "(" means the date sat inside the parens:
    # "Nashville InnerCity Ministries Client (01/01 Renewal)" — a duplicate board.
    if name.count('(') != name.count(')'):
        return None, None
    if len(name) < 3:
        return None, None

    return name, kind


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


# ============================================================
# TOOL DOWNLOADS — added 2026-10-13
# The Client Quote Summary routine downloads the document generator from here
# when its own repo checkout is missing. Only the files named below are served.
# ============================================================
_TOOL_FILES = {'renewal_analysis.py', 'renewal_analysis_example.json',
               'pipeline_report.py', 'pipeline_report_example.json'}
_TOOL_BINARIES = {'tbg-logo.png': 'image/png'}
_FONT_FILES = {'SourceSerif4_600SemiBold.ttf', 'PublicSans_400Regular.ttf', 'PublicSans_400Regular_Italic.ttf',
               'PublicSans_600SemiBold.ttf', 'PublicSans_700Bold.ttf', 'IBMPlexMono-Regular.ttf',
               'IBMPlexMono-Medium.ttf'}


@app.route('/tools/<name>', methods=['GET'])
def tool_file(name):
    from flask import send_from_directory
    here = os.path.dirname(os.path.abspath(__file__))
    if name in _TOOL_FILES:
        return send_from_directory(here, name, mimetype='text/plain')
    if name in _TOOL_BINARIES:
        return send_from_directory(here, name, mimetype=_TOOL_BINARIES[name])
    return jsonify({'error': 'not found'}), 404


@app.route('/tools/fonts/<name>', methods=['GET'])
def tool_font(name):
    from flask import send_from_directory
    if name not in _FONT_FILES:
        return jsonify({'error': 'not found'}), 404
    return send_from_directory(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts'), name,
                               mimetype='font/ttf')


# ============================================================
# CORRECTLY-TYPED ATTACHMENT LINKS FOR CARRIER EMAILS
# Asana's download links serve spreadsheets as text/plain, and Zapier passes that type on, so
# carriers' encrypted-mail viewers could not open the census. The Send Carrier Emails routine asks
# for a short-lived link here instead; the link serves the same Asana file with the right type and
# file name.
#   POST /attachment-link   {"attachment_gid": "123"}   (X-TBG-Secret; the routine environment adds it)
#     -> {"status":"success","url":"https://.../attachment-file/<gid>/<exp>/<sig>/<file name>", ...}
#   GET  /attachment-file/<gid>/<exp>/<sig>/<name>      (no auth; signed, valid 20 minutes)
# ============================================================
_MIME_BY_EXT = {
    '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    '.xls': 'application/vnd.ms-excel',
    '.csv': 'text/csv',
    '.pdf': 'application/pdf',
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    '.doc': 'application/msword',
    '.zip': 'application/zip',
}
_LINK_TTL = 20 * 60


def _link_sig(gid, exp):
    import hmac, hashlib
    key = (TBG_SECRET or 'unset').encode()
    return hmac.new(key, f'{gid}|{exp}'.encode(), hashlib.sha256).hexdigest()[:32]


def _asana_attachment(gid):
    import requests as _rq
    r = _rq.get(f'https://app.asana.com/api/1.0/attachments/{gid}',
                headers={'Authorization': f"Bearer {os.environ['ASANA_TOKEN']}"},
                params={'opt_fields': 'name,size,download_url,host'}, timeout=25)
    r.raise_for_status()
    return r.json().get('data', {})


@app.route('/attachment-link', methods=['POST'])
def attachment_link():
    import time as _t
    from urllib.parse import quote
    if not _tbg_authorized():
        return jsonify({'error': 'unauthorized'}), 401
    data = request.get_json(silent=True) or {}
    gid = str(data.get('attachment_gid') or '').strip()
    if not gid.isdigit():
        return jsonify({'error': 'attachment_gid (numeric) is required'}), 400
    try:
        att = _asana_attachment(gid)
    except Exception as e:
        return jsonify({'error': f'Asana lookup failed: {e}'}), 502
    name = att.get('name') or f'attachment-{gid}'
    ext = os.path.splitext(name)[1].lower()
    exp = int(_t.time()) + _LINK_TTL
    url = (f"{request.host_url.rstrip('/').replace('http://', 'https://')}/attachment-file/"
           f"{gid}/{exp}/{_link_sig(gid, exp)}/{quote(name)}")
    return jsonify({'status': 'success', 'url': url, 'name': name, 'size': att.get('size'),
                    'content_type': _MIME_BY_EXT.get(ext, 'application/octet-stream'),
                    'expires_in_seconds': _LINK_TTL}), 200


@app.route('/attachment-file/<gid>/<int:exp>/<sig>/<path:name>', methods=['GET', 'HEAD'])
def attachment_file(gid, exp, sig, name):
    import hmac, time as _t
    import requests as _rq
    from flask import Response
    if not gid.isdigit() or exp < _t.time() or not hmac.compare_digest(sig, _link_sig(gid, exp)):
        return jsonify({'error': 'link expired or invalid'}), 403
    try:
        att = _asana_attachment(gid)
        r = _rq.get(att['download_url'], timeout=60)
        r.raise_for_status()
        content = r.content
    except Exception as e:
        print(f"❌ attachment-file error: {e}", flush=True)
        return jsonify({'error': 'could not fetch the file'}), 502
    real = att.get('name') or name
    ext = os.path.splitext(real)[1].lower()
    out = Response(content if request.method == 'GET' else b'',
                   mimetype=_MIME_BY_EXT.get(ext, 'application/octet-stream'))
    safe = real.replace('"', '')
    out.headers['Content-Disposition'] = f'attachment; filename="{safe}"'
    out.headers['Content-Length'] = str(len(content))
    out.headers['Cache-Control'] = 'no-store'
    return out


# ============================================================
# ODOO PIPELINE (read-only)
# The Zapier Odoo feed only returns the 100 most recently created records, so older
# opportunities fall off it. This reads every active opportunity straight from Odoo's
# external API. Read-only: it only calls search_read.
#
#   GET /odoo-pipeline            (X-TBG-Secret required; the routine environment adds it)
#
# Render environment variables:
#   ODOO_URL      https://the-benefits-group.odoo.com
#   ODOO_LOGIN    will@benefits.place          (the Odoo user the API key belongs to)
#   ODOO_API_KEY  <a key made in Odoo: My Profile > Account Security > Add API Key>
#   ODOO_DB       optional; defaults to the subdomain of ODOO_URL
# ============================================================
_ODOO_FIELDS = ['id', 'name', 'partner_name', 'contact_name', 'email_from', 'email_domain_criterion',
                'stage_id', 'date_last_stage_update', 'date_deadline', 'create_date', 'write_date',
                'expected_revenue', 'user_id', 'description', 'type', 'active']


@app.route('/odoo-pipeline', methods=['GET'])
def odoo_pipeline():
    import re as _re
    import xmlrpc.client as _x
    if not _tbg_authorized():
        return jsonify({'error': 'unauthorized'}), 401
    url = os.environ.get('ODOO_URL', '').rstrip('/')
    login = os.environ.get('ODOO_LOGIN', '')
    key = os.environ.get('ODOO_API_KEY', '')
    if not (url and login and key):
        return jsonify({'error': 'Odoo is not configured on Render (ODOO_URL, ODOO_LOGIN, ODOO_API_KEY)'}), 503
    db = os.environ.get('ODOO_DB') or _re.sub(r'^https?://', '', url).split('.')[0]
    try:
        common = _x.ServerProxy(f'{url}/xmlrpc/2/common', allow_none=True)
        uid = common.authenticate(db, login, key, {})
        if not uid:
            return jsonify({'error': 'Odoo rejected the login or API key', 'db': db}), 502
        models = _x.ServerProxy(f'{url}/xmlrpc/2/object', allow_none=True)
        include_leads = request.args.get('leads', '') == '1'
        domain = [['active', '=', True]]
        if not include_leads:
            domain.append(['type', '=', 'opportunity'])
        rows = models.execute_kw(db, uid, key, 'crm.lead', 'search_read', [domain],
                                 {'fields': _ODOO_FIELDS, 'limit': 2000, 'order': 'write_date desc'})
        stages = models.execute_kw(db, uid, key, 'crm.stage', 'search_read', [[]],
                                   {'fields': ['id', 'name', 'sequence', 'is_won'], 'order': 'sequence'})
    except Exception as e:
        print(f"❌ odoo-pipeline error: {e}", flush=True)
        return jsonify({'error': f'Odoo call failed: {e}', 'db': db}), 502
    for r in rows:
        desc = r.get('description') or ''
        r['description'] = _re.sub(r'<[^>]+>', ' ', desc).strip()[:2000] if desc else ''
        st = r.get('stage_id')
        r['stage'] = st[1] if isinstance(st, list) and len(st) > 1 else ''
    return jsonify({'status': 'success', 'count': len(rows), 'stages': stages, 'records': rows}), 200


# ============================================================
# LATEST NEW BUSINESS PIPELINE CHECK
# The Pipeline Check routine files each run's PDF and HTML into PIPELINE_REPORT_FOLDER
# with /save-file. This serves the newest one to the Action Center's "Open latest report"
# link. Read-only, behind the same read token as /clients.
#   GET /pipeline-report?t=<TBG_READ_TOKEN>              -> newest PDF
#   GET /pipeline-report?t=<TBG_READ_TOKEN>&format=html  -> newest interactive page
# ============================================================
PIPELINE_REPORT_FOLDER = '/Solutionpoint Groups/Pipeline Reports'


@app.route('/pipeline-report', methods=['GET'])
def pipeline_report():
    from flask import Response
    supplied = request.args.get('t', '') or request.headers.get('X-TBG-Read', '')
    if not TBG_READ_TOKEN or supplied != TBG_READ_TOKEN:
        return jsonify({'error': 'unauthorized'}), 401
    want_html = request.args.get('format', '').lower() == 'html'
    ext = '.html' if want_html else '.pdf'
    try:
        dbx_module, dbx = _dropbox_client()
        res = dbx.files_list_folder(PIPELINE_REPORT_FOLDER)
        entries = list(res.entries)
        while res.has_more:
            res = dbx.files_list_folder_continue(res.cursor)
            entries.extend(res.entries)
        files = [e for e in entries
                 if isinstance(e, dbx_module.files.FileMetadata)
                 and e.name.lower().endswith(ext)
                 and not e.name.lower().endswith('-email.html')
                 and e.name.lower().startswith('new business pipeline check')]
        if not files:
            return Response('<p style="font-family:Arial">No Pipeline Check report has been filed yet. '
                            'Run it from the Action Center, or wait for the 7:45 AM weekday run.</p>',
                            status=404, mimetype='text/html')
        newest = max(files, key=lambda e: (e.name, e.server_modified))
        _, resp = dbx.files_download(newest.path_lower)
        out = Response(resp.content, mimetype='text/html' if want_html else 'application/pdf')
        out.headers['Content-Disposition'] = f'inline; filename="{newest.name}"'
        out.headers['Cache-Control'] = 'no-store'
        return out
    except Exception as e:
        print(f"❌ pipeline-report error: {e}", flush=True)
        return jsonify({'error': f'could not read the report folder: {e}'}), 502


# ============================================================
# ATTACH A GROUP'S CENSUS FROM DROPBOX TO ITS ASANA TASK
# Used by the Send for Quotes routine. The file goes Dropbox -> this server -> Asana,
# so the census never passes through a temporary public link, Zapier, or a chat tool.
#
#   curl -sS -X POST https://proposal-fgqm.onrender.com/attach-census \
#     -H "X-TBG-Secret: $TBG_API_SECRET" -H "Content-Type: application/json" \
#     -d '{"dropbox_path": "/Solutionpoint Groups/.../Quoting/1. Census/Acme Census.xlsx",
#          "asana_task": "1219370086624997"}'
# ============================================================
_CENSUS_EXTS = ('.xlsx', '.xls', '.csv', '.pdf')


@app.route('/attach-census', methods=['POST'])
def attach_census():
    import requests as _rq
    if not _tbg_authorized():
        return jsonify({'error': 'unauthorized'}), 401

    data = request.get_json(silent=True) or {}
    path = (data.get('dropbox_path') or '').strip()
    task = str(data.get('asana_task') or '').strip()

    # The Dropbox connector shows paths under "/William Brown/..."; this app's token is
    # rooted one level lower. Accept either form.
    if path.startswith('/William Brown/'):
        path = path[len('/William Brown'):]
    name = path.rsplit('/', 1)[-1]

    if not path.startswith('/') or not task.isdigit():
        return jsonify({'error': 'dropbox_path (starting with /) and numeric asana_task are required'}), 400
    if '/quoting/' not in path.lower() or not name.lower().endswith(_CENSUS_EXTS):
        return jsonify({'error': 'only spreadsheet/CSV/PDF files inside a client Quoting folder can be attached'}), 400

    try:
        _, dbx = _dropbox_client()
        meta, resp = dbx.files_download(path)
        content = resp.content
    except Exception as e:
        print(f"❌ attach-census Dropbox error: {e}", flush=True)
        return jsonify({'error': f'Dropbox download failed: {e}'}), 502

    headers = {'Authorization': f"Bearer {os.environ['ASANA_TOKEN']}"}
    try:
        # Skip if a file with the same name is already on the task.
        existing = _rq.get(f'https://app.asana.com/api/1.0/attachments',
                           headers=headers, params={'parent': task, 'opt_fields': 'name'},
                           timeout=25)
        existing.raise_for_status()
        for att in existing.json().get('data', []):
            if att.get('name') == meta.name:
                return jsonify({'status': 'success', 'already_attached': True,
                                'name': meta.name, 'attachment_gid': att.get('gid')}), 200

        r = _rq.post('https://app.asana.com/api/1.0/attachments', headers=headers,
                     data={'parent': task},
                     files={'file': (meta.name, content)}, timeout=60)
        r.raise_for_status()
        att = r.json().get('data', {})
    except Exception as e:
        print(f"❌ attach-census Asana error: {e}", flush=True)
        return jsonify({'error': f'Asana upload failed: {e}'}), 502

    print(f"✅ attach-census: {meta.name} ({len(content)} bytes) → task {task}", flush=True)
    return jsonify({'status': 'success', 'name': meta.name, 'bytes': len(content),
                    'attachment_gid': att.get('gid'), 'task': task}), 200


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
