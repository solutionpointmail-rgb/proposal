"""
app.py — TBG Proposal Generation Server v2
Synchronous pipeline execution to avoid Render free tier thread timeout.
"""

import os, json, re, sys
from datetime import datetime
from flask import Flask, request, jsonify

app = Flask(__name__)

def parse_plan_names(notes_text, section):
    lines = notes_text.split('\n')
    in_section = False
    plans = []
    for line in lines:
        line = line.strip()
        if line.upper().startswith(section.upper() + ':') or line.upper().startswith(section.upper() + ' -'):
            in_section = True
            # Check if plans are on same line
            rest = line[len(section):].lstrip(':- ').strip()
            if rest:
                for plan in rest.split(','):
                    plan = plan.strip()
                    if plan and 'EXCLUDE' not in plan.upper():
                        plans.append(plan)
            continue
        if in_section:
            if any(line.upper().startswith(s) for s in ['MEDICAL', 'DENTAL', 'VISION', 'CLIENT', 'SUBMITTED']):
                break
            if line:
                for plan in line.split(','):
                    plan = plan.strip()
                    if plan and 'EXCLUDE' not in plan.upper():
                        # Clean up plan name
                        plan = re.sub(r'\s*-\s*\$[\d,\.]+/mo.*', '', plan).strip()
                        plan = re.sub(r'^INCLUDE\s*-?\s*', '', plan, flags=re.IGNORECASE).strip()
                        if plan:
                            plans.append(plan)
    return plans

def run_pipeline(client_name, effective_date, quote_id, task_id, notes):
    print(f"=== PIPELINE START: {client_name} ===", flush=True)

    try:
        sys.path.insert(0, '/opt/render/project/src')
        from proposal_data import CLIENT, CONTRIBUTIONS, MEDICAL_PLANS, DENTAL_PLANS, VISION_PLANS
        print("✅ proposal_data imported", flush=True)

        # Update client
        CLIENT['name'] = client_name.replace(' — Review for Proposal', '').strip()
        CLIENT['effective_date'] = effective_date or CLIENT['effective_date']
        CLIENT['quote_id'] = quote_id or CLIENT['quote_id']

        # Parse selected plans
        med_sel = parse_plan_names(notes, 'MEDICAL')
        den_sel = parse_plan_names(notes, 'DENTAL')
        vis_sel = parse_plan_names(notes, 'VISION')
        print(f"Medical: {med_sel}", flush=True)
        print(f"Dental:  {den_sel}", flush=True)
        print(f"Vision:  {vis_sel}", flush=True)

        # Set include flags — if parsing finds nothing, include all
        for p in MEDICAL_PLANS:
            p['include'] = not med_sel or any(
                s.lower() in p['plan_name'].lower() or p['plan_name'].lower() in s.lower()
                for s in med_sel)
        for p in DENTAL_PLANS:
            p['include'] = not den_sel or any(
                s.lower() in p['plan_name'].lower() or p['plan_name'].lower() in s.lower()
                for s in den_sel)
        for p in VISION_PLANS:
            p['include'] = not vis_sel or any(
                s.lower() in p['plan_name'].lower() or p['plan_name'].lower() in s.lower()
                for s in vis_sel)

        included_med = [p['plan_name'] for p in MEDICAL_PLANS if p['include']]
        included_den = [p['plan_name'] for p in DENTAL_PLANS  if p['include']]
        included_vis = [p['plan_name'] for p in VISION_PLANS  if p['include']]
        print(f"Including medical: {included_med}", flush=True)
        print(f"Including dental:  {included_den}", flush=True)
        print(f"Including vision:  {included_vis}", flush=True)

        # Generate files
        timestamp  = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_name  = CLIENT['name'].replace(' ', '_').replace('/', '-')
        pdf_name   = f"Proposal_{safe_name}_{timestamp}.pdf"
        excel_name = f"Proposal_{safe_name}_{timestamp}.xlsx"
        pdf_path   = f"/tmp/{pdf_name}"
        excel_path = f"/tmp/{excel_name}"

        print("Generating PDF...", flush=True)
        from generate_pdf import generate_pdf
        generate_pdf(pdf_path)
        print(f"✅ PDF done: {pdf_name}", flush=True)

        print("Generating Excel...", flush=True)
        from generate_excel import generate_excel
        generate_excel(excel_path)
        print(f"✅ Excel done: {excel_name}", flush=True)

        # Upload to Dropbox
        print("Uploading to Dropbox...", flush=True)
        import dropbox
        dbx = dropbox.Dropbox(os.environ['DROPBOX_TOKEN'])
        folder = f"/Benefits Group/Proposals/2026/{CLIENT['name'].replace(' ', '_')}"
        links = {}

        for local_path, file_name in [(pdf_path, pdf_name), (excel_path, excel_name)]:
            db_path = f"{folder}/{file_name}"
            with open(local_path, 'rb') as f:
                dbx.files_upload(f.read(), db_path,
                                 mode=dropbox.files.WriteMode.overwrite)
            try:
                link = dbx.sharing_create_shared_link_with_settings(db_path)
                links[file_name] = link.url.replace('?dl=0', '?dl=1')
            except dropbox.exceptions.ApiError:
                existing = dbx.sharing_list_shared_links(path=db_path)
                links[file_name] = existing.links[0].url.replace('?dl=0', '?dl=1')
            print(f"✅ Uploaded: {file_name}", flush=True)

        # Update Asana
        print("Updating Asana...", flush=True)
        import requests
        token   = os.environ['ASANA_TOKEN']
        headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

        # Move to Delivered
        delivered_section = '1216532264374832'
        requests.post(
            f'https://app.asana.com/api/1.0/sections/{delivered_section}/addTask',
            headers=headers,
            json={'data': {'task': task_id}}
        )

        # Add comment
        pdf_link   = links.get(pdf_name,   'Not available')
        excel_link = links.get(excel_name, 'Not available')
        comment = (
            f"Proposal generated!\n\n"
            f"PDF: {pdf_link}\n"
            f"Excel: {excel_link}\n\n"
            f"Plans included:\n"
            f"Medical: {', '.join(included_med)}\n"
            f"Dental: {', '.join(included_den)}\n"
            f"Vision: {', '.join(included_vis)}\n\n"
            f"Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}"
        )
        requests.post(
            f'https://app.asana.com/api/1.0/tasks/{task_id}/stories',
            headers=headers,
            json={'data': {'text': comment}}
        )
        print(f"✅ Asana updated — task {task_id} moved to Delivered", flush=True)
        print(f"=== PIPELINE COMPLETE: {CLIENT['name']} ===", flush=True)
        return True

    except Exception as e:
        print(f"❌ PIPELINE ERROR: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return False


@app.route('/', methods=['GET'])
def health():
    return jsonify({'status': 'TBG Proposal Generator running', 'version': '2.0'})


@app.route('/generate', methods=['POST'])
def generate():
    data = request.get_json(force=True, silent=True) or request.form.to_dict()

    client_name    = data.get('client_name', '')
    effective_date = data.get('effective_date', '')
    quote_id       = data.get('quote_id', '')
    task_id        = data.get('task_id', '')
    notes          = data.get('notes', '')

    print(f"Received: {client_name} | task: {task_id}", flush=True)

    if not client_name or not task_id:
        return jsonify({'error': 'Missing client_name or task_id'}), 400

    # Run synchronously — Render free tier kills background threads
    success = run_pipeline(client_name, effective_date, quote_id, task_id, notes)

    if success:
        return jsonify({'status': 'complete', 'message': f'Proposal generated for {client_name}'}), 200
    else:
        return jsonify({'status': 'error', 'message': 'Pipeline failed — check Render logs'}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
