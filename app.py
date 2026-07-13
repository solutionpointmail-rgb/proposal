"""
app.py — TBG Proposal Generation Server v3
- Fixed plan parsing (INCLUDE vs EXCLUDE)
- Dynamic Dropbox folder routing to existing client structure
"""

import os, re, sys
from datetime import datetime
from flask import Flask, request, jsonify

app = Flask(__name__)

def parse_selected_plans(notes_text, section):
    """
    Parse INCLUDE plans from notes field.
    Handles both formats:
    - MEDICAL: Plan A, Plan B (comma-separated on one line)
    - MEDICAL - MARK INCLUDE OR EXCLUDE
      - INCLUDE - Plan A - $X/mo
      - EXCLUDE - Plan B - $X/mo
    """
    if not notes_text:
        return []

    lines = notes_text.split('\n')
    plans = []
    in_section = False

    for line in lines:
        stripped = line.strip()
        upper = stripped.upper()

        # Detect section header
        if upper.startswith(section.upper() + ':') or upper.startswith(section.upper() + ' - MARK') or upper.startswith(section.upper() + ' -MARK'):
            in_section = True
            # Plans may be on same line after colon
            after_colon = stripped[len(section):].lstrip(':- ').strip()
            if after_colon and 'MARK' not in after_colon.upper():
                for plan in after_colon.split(','):
                    plan = plan.strip()
                    if plan and 'EXCLUDE' not in plan.upper():
                        plan = re.sub(r'\s*-\s*\$[\d,\.]+.*', '', plan).strip()
                        plan = re.sub(r'^INCLUDE\s*[-–]\s*', '', plan, flags=re.IGNORECASE).strip()
                        if plan:
                            plans.append(plan)
            continue

        if in_section:
            # Stop at next section
            if any(upper.startswith(s) for s in ['MEDICAL', 'DENTAL', 'VISION', 'CLIENT', 'SUBMITTED', '---']):
                if not upper.startswith(section.upper()):
                    break

            if not stripped:
                continue

            # Handle "- INCLUDE - Plan Name - $X/mo" format
            if 'INCLUDE' in upper and 'EXCLUDE' not in upper[:upper.find('INCLUDE') + 10]:
                # Extract plan name — between INCLUDE and the price
                plan = re.sub(r'^[-–•]\s*', '', stripped)
                plan = re.sub(r'^INCLUDE\s*[-–]\s*', '', plan, flags=re.IGNORECASE).strip()
                plan = re.sub(r'\s*[-–]\s*\$[\d,\.]+.*', '', plan).strip()
                plan = re.sub(r'\s*-\s*Level Fund.*', '', plan, flags=re.IGNORECASE).strip()
                plan = re.sub(r'\s*-\s*HSA eligible.*', '', plan, flags=re.IGNORECASE).strip()
                if plan and len(plan) > 3:
                    plans.append(plan)
            # Skip explicit EXCLUDE lines
            elif 'EXCLUDE' in upper:
                continue
            # Handle comma-separated plan names (no INCLUDE/EXCLUDE prefix)
            elif ',' in stripped and '$' not in stripped:
                for plan in stripped.split(','):
                    plan = plan.strip()
                    if plan:
                        plans.append(plan)

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


def run_pipeline(client_name, effective_date, quote_id, task_id, notes):
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

        # Parse selected plans
        med_sel = parse_selected_plans(notes, 'MEDICAL')
        den_sel = parse_selected_plans(notes, 'DENTAL')
        vis_sel = parse_selected_plans(notes, 'VISION')
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

        # Fallback: include all if parsing found nothing
        if not any(p['include'] for p in MEDICAL_PLANS):
            print("⚠️ No medical plans matched — including all", flush=True)
            for p in MEDICAL_PLANS: p['include'] = True
        if not any(p['include'] for p in DENTAL_PLANS):
            print("⚠️ No dental plans matched — including all", flush=True)
            for p in DENTAL_PLANS: p['include'] = True
        if not any(p['include'] for p in VISION_PLANS):
            print("⚠️ No vision plans matched — including all", flush=True)
            for p in VISION_PLANS: p['include'] = True

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
        dbx = dbx_module.Dropbox(os.environ['DROPBOX_TOKEN'])

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

    print(f"Received: {client_name} | task: {task_id}", flush=True)

    if not client_name or not task_id:
        return jsonify({'error': 'Missing client_name or task_id'}), 400

    success, folder, pdf_link, excel_link = run_pipeline(
        client_name, effective_date, quote_id, task_id, notes
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


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
