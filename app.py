"""
app.py — TBG Proposal Generation Server v3
- Fixed plan parsing (INCLUDE vs EXCLUDE)
- Dynamic Dropbox folder routing to existing client structure
"""

import os, re, sys
from datetime import datetime
from flask import Flask, request, jsonify

app = Flask(__name__)

def parse_selected_plans(plans_text):
    """Parse comma-separated plan names from webhook field."""
    if not plans_text:
        return []
    # Handle both comma-separated and newline-separated
    plans = []
    for p in re.split(r'[,\n]', plans_text):
        p = p.strip()
        if p and len(p) > 2:
            plans.append(p)
    return plans


def find_client_dropbox_folder(client_name, dbx):
    """
    Try to find existing client proposal folder using direct path checks.
    Checks known TBG folder structures before falling back to new folder.
    """
    search_name = client_name.replace(' — Review for Proposal', '').strip()

    # Known path patterns to check in order
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


def run_pipeline(client_name, effective_date, quote_id, task_id, notes, medical_plans='', dental_plans='', vision_plans=''):
    print(f"=== PIPELINE START: {client_name} ===", flush=True)

    try:
        sys.path.insert(0, '/opt/render/project/src')
        from proposal_data import CLIENT, CONTRIBUTIONS, MEDICAL_PLANS, DENTAL_PLANS, VISION_PLANS
        print("✅ proposal_data imported", flush=True)

        # Clean client name
        clean_name = client_name.replace(' — Review for Proposal', '').strip()
        CLIENT['name']         = clean_name
        CLIENT['effective_date'] = effective_date or CLIENT['effective_date']
        CLIENT['quote_id']     = quote_id or CLIENT['quote_id']

        # Parse selected plans from dedicated webhook fields
        med_sel = parse_selected_plans(medical_plans)
        den_sel = parse_selected_plans(dental_plans)
        vis_sel = parse_selected_plans(vision_plans)
        print(f"Medical selected:  {med_sel}", flush=True)
        print(f"Dental selected:   {den_sel}", flush=True)
        print(f"Vision selected:   {vis_sel}", flush=True)

        # Set include flags
        for p in MEDICAL_PLANS:
            p['include'] = bool(med_sel) and any(
                s.lower() in p['plan_name'].lower() or p['plan_name'].lower() in s.lower()
                for s in med_sel)
        for p in DENTAL_PLANS:
            p['include'] = bool(den_sel) and any(
                s.lower() in p['plan_name'].lower() or p['plan_name'].lower() in s.lower()
                for s in den_sel)
        for p in VISION_PLANS:
            p['include'] = bool(vis_sel) and any(
                s.lower() in p['plan_name'].lower() or p['plan_name'].lower() in s.lower()
                for s in vis_sel)

        # Only use fallback if NO lines of coverage were selected at all
        # If broker selected 0 medical plans intentionally, respect that
        nothing_selected = not med_sel and not den_sel and not vis_sel
        if nothing_selected:
            print("⚠️ No plans selected at all — including all as fallback", flush=True)
            for p in MEDICAL_PLANS: p['include'] = True
            for p in DENTAL_PLANS:  p['include'] = True
            for p in VISION_PLANS:  p['include'] = True

        inc_med = [p['plan_name'] for p in MEDICAL_PLANS if p['include']]
        inc_den = [p['plan_name'] for p in DENTAL_PLANS  if p['include']]
        inc_vis = [p['plan_name'] for p in VISION_PLANS  if p['include']]
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

        # Try to find existing client folder, fall back to Benefits Group structure
        existing_folder = find_client_dropbox_folder(clean_name, dbx)
        if existing_folder:
            folder = existing_folder
        else:
            folder = f"/Benefits Group/Proposals/2026/{safe_name}"
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

        # Move to Delivered section
        requests.post(
            'https://app.asana.com/api/1.0/sections/1216532264374832/addTask',
            headers=headers,
            json={'data': {'task': task_id}}
        )

        pdf_link   = links.get(pdf_name,   'Not available')
        excel_link = links.get(excel_name, 'Not available')

        comment = (
            f"✅ Proposal generated!\n\n"
            f"📄 PDF: {pdf_link}\n"
            f"📊 Excel: {excel_link}\n\n"
            f"📁 Saved to: {folder}\n\n"
            f"Plans included:\n"
            f"Medical ({len(inc_med)}): {', '.join(inc_med)}\n"
            f"Dental ({len(inc_den)}):  {', '.join(inc_den)}\n"
            f"Vision ({len(inc_vis)}):  {', '.join(inc_vis)}\n\n"
            f"🔄 Revise selections: https://solutionpointmail-rgb.github.io/proposal/tenngreen-aug2026.html\n\n"
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
    return jsonify({'status': 'TBG Proposal Generator v3', 'version': '3.0'})


@app.route('/generate', methods=['POST'])
def generate():
    data = request.get_json(force=True, silent=True) or request.form.to_dict()

    client_name    = data.get('client_name', '')
    effective_date = data.get('effective_date', '')
    quote_id       = data.get('quote_id', '')
    task_id        = data.get('task_id', '')
    notes          = data.get('notes', '')
    medical_plans  = data.get('medical_plans', '')
    dental_plans   = data.get('dental_plans', '')
    vision_plans   = data.get('vision_plans', '')

    print(f"Received: {client_name} | task: {task_id}", flush=True)
    print(f"Medical: {medical_plans}", flush=True)
    print(f"Dental:  {dental_plans}", flush=True)
    print(f"Vision:  {vision_plans}", flush=True)

    if not client_name or not task_id:
        return jsonify({'error': 'Missing client_name or task_id'}), 400

    success, folder, pdf_link, excel_link = run_pipeline(
        client_name, effective_date, quote_id, task_id, notes,
        medical_plans, dental_plans, vision_plans
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
    headers = {'Authorization': f'token {gh_token}', 'Accept': 'application/vnd.github.v3+json', 'Content-Type': 'application/json'}
    sha = None
    try:
        req = ur.Request(api_url, headers=headers)
        with ur.urlopen(req) as r:
            sha = json.loads(r.read()).get('sha')
    except Exception:
        pass
    payload = {'message': f'Auto-generate selector: {filename}', 'content': b64.b64encode(html_content.encode()).decode()}
    if sha:
        payload['sha'] = sha
    try:
        req = ur.Request(api_url, data=json.dumps(payload).encode(), method='PUT', headers=headers)
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
