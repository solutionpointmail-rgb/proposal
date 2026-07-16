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

def find_client_dropbox_folder(client_name, dbx):
    search_name = client_name.replace(' — Review for Proposal', '').strip()
    candidates = [
        f"/Solutionpoint Groups/1. Solutionpoint Groups/Proposals/2026/{search_name}",
        f"/Solutionpoint Groups/1. Solutionpoint Groups/2.  HOT LEADS/{search_name}/Quoting/3. Proposal",
        f"/Solutionpoint Groups/1. Solutionpoint Groups/3. WARM LEADS/{search_name}/Quoting/3. Proposal",
        f"/Solutionpoint Groups/1. Solutionpoint Groups/4. RENEWALS/{search_name}/Quoting/3. Proposal",
    ]
    for path in candidates:
        try:
            dbx.files_get_metadata(path)
            print(f"Found existing folder: {path}", flush=True)
            return path
        except Exception:
            continue
    return None


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
    clean_name = client_name.replace(' — Review for Proposal', '').strip()

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
            # No selections sent — include all
            for p in all_plans:
                p['include'] = True
            return all_plans

        for p in all_plans:
            p['include'] = any(
                sel.lower().strip() in p['plan_name'].lower() or
                p['plan_name'].lower() in sel.lower().strip()
                for sel in selected_names
            )
        return all_plans

    MEDICAL_PLANS = filter_plans(all_medical_json, med_sel, True)
    DENTAL_PLANS  = filter_plans(all_dental_json,  den_sel, True)
    VISION_PLANS  = filter_plans(all_vision_json,  vis_sel, True)

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

        # Build dynamic selector URL
        if not selector_url:
            safe_client = clean_name.lower().replace(' ', '').replace('_','').replace('-','').replace('.','').replace(',','')
            selector_url = f"https://solutionpointmail-rgb.github.io/proposal/{safe_client}-aug2026.html"

        comment = (
            f"✅ Proposal generated!\n\n"
            f"📄 PDF: {pdf_link}\n"
            f"📊 Excel: {excel_link}\n\n"
            f"📁 Saved to: {folder}\n\n"
            f"Plans included:\n"
            f"Medical ({len(inc_med)}): {', '.join(inc_med) if inc_med else 'None selected'}\n"
            f"Dental ({len(inc_den)}): {', '.join(inc_den) if inc_den else 'None selected'}\n"
            f"Vision ({len(inc_vis)}): {', '.join(inc_vis) if inc_vis else 'None selected'}\n\n"
            f"🔄 Revise selections: {selector_url}\n\n"
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
    data = request.get_json(force=True, silent=True) or request.form.to_dict()

    client_name         = data.get('client_name', '')
    effective_date      = data.get('effective_date', '')
    quote_id            = data.get('quote_id', '')
    task_id             = data.get('task_id', '')
    notes               = data.get('notes', '')
    medical_plans       = data.get('medical_plans', '')
    dental_plans        = data.get('dental_plans', '')
    vision_plans        = data.get('vision_plans', '')
    enrolling_employees = data.get('enrolling_employees', '')
    selector_url        = data.get('selector_url', '')
    all_medical_json    = data.get('all_medical_json', '')
    all_dental_json     = data.get('all_dental_json', '')
    all_vision_json     = data.get('all_vision_json', '')

    # Zapier flattens JSON arrays into individual fields like:
    # raw_payload.all_medical_json.1.carrier, raw_payload.all_medical_json.1.plan_name, etc.
    # We reconstruct the plan arrays from the raw_payload dict.
    import json as _j

    raw_payload = data.get('raw_payload', '')
    print(f"DEBUG raw_payload: {len(str(raw_payload))} chars", flush=True)

    def reconstruct_plans_from_flat(raw_dict, prefix):
        """Rebuild plan array from Zapier-flattened fields like prefix.1.carrier, prefix.2.carrier..."""
        plans = []
        i = 1
        while True:
            carrier = raw_dict.get(f'{prefix}.{i}.carrier') or raw_dict.get(f'{prefix}_{i}_carrier')
            plan_name = raw_dict.get(f'{prefix}.{i}.plan_name') or raw_dict.get(f'{prefix}_{i}_plan_name')
            if not carrier and not plan_name:
                break
            plan = {
                'carrier':        carrier or '',
                'plan_name':      plan_name or '',
                'monthly_premium': float(raw_dict.get(f'{prefix}.{i}.monthly_premium') or raw_dict.get(f'{prefix}_{i}_monthly_premium') or 0),
                'plan_type':      raw_dict.get(f'{prefix}.{i}.plan_type') or raw_dict.get(f'{prefix}_{i}_plan_type') or '',
                'funding':        raw_dict.get(f'{prefix}.{i}.funding') or raw_dict.get(f'{prefix}_{i}_funding') or '',
                'deductible_in_ind': raw_dict.get(f'{prefix}.{i}.deductible_in_ind') or raw_dict.get(f'{prefix}_{i}_deductible_in_ind') or '',
                'oop_in_ind':     raw_dict.get(f'{prefix}.{i}.oop_in_ind') or raw_dict.get(f'{prefix}_{i}_oop_in_ind') or '',
                'coinsurance_in': raw_dict.get(f'{prefix}.{i}.coinsurance_in') or raw_dict.get(f'{prefix}_{i}_coinsurance_in') or '',
                'doctor_visit':   raw_dict.get(f'{prefix}.{i}.doctor_visit') or raw_dict.get(f'{prefix}_{i}_doctor_visit') or '',
                'rate_ee':        float(raw_dict.get(f'{prefix}.{i}.rate_ee') or raw_dict.get(f'{prefix}_{i}_rate_ee') or 0),
                'include':        True,
            }
            plans.append(plan)
            i += 1
        return plans

    if raw_payload:
        try:
            raw = _j.loads(raw_payload) if isinstance(raw_payload, str) else raw_payload
            if isinstance(raw, dict):
                print(f"DEBUG raw keys sample: {list(raw.keys())[:15]}", flush=True)
                # Print ALL keys that contain 'medical' to find exact format
                med_keys = [k for k in raw.keys() if 'medical' in k.lower() or 'all_med' in k.lower()]
                print(f"DEBUG medical-related keys: {med_keys[:10]}", flush=True)
                
                # Try to reconstruct plans from flattened Zapier fields
                med_plans = reconstruct_plans_from_flat(raw, 'all_medical_json')
                den_plans = reconstruct_plans_from_flat(raw, 'all_dental_json')
                vis_plans = reconstruct_plans_from_flat(raw, 'all_vision_json')
                
                if med_plans:
                    all_medical_json = _j.dumps(med_plans)
                    print(f"✅ Reconstructed {len(med_plans)} medical plans from flat fields", flush=True)
                if den_plans:
                    all_dental_json = _j.dumps(den_plans)
                    print(f"✅ Reconstructed {len(den_plans)} dental plans from flat fields", flush=True)
                if vis_plans:
                    all_vision_json = _j.dumps(vis_plans)
                    print(f"✅ Reconstructed {len(vis_plans)} vision plans from flat fields", flush=True)

                if not enrolling_employees:
                    enrolling_employees = str(raw.get('enrolling_employees', ''))
                if not selector_url:
                    selector_url = raw.get('selector_url', '')
        except Exception as e:
            print(f"⚠️ raw_payload parse error: {e}", flush=True)
            import traceback; traceback.print_exc()

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


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
