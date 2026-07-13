"""
app.py — TBG Proposal Generation Server
Receives webhook from Zapier, generates PDF + Excel, uploads to Dropbox,
updates Asana task to Delivered with file links.

Deploy to Render.com — free tier works perfectly.
Set these environment variables in Render:
  DROPBOX_TOKEN   — Dropbox access token
  ASANA_TOKEN     — Asana personal access token
  ANTHROPIC_KEY   — Anthropic API key (optional, for future use)
"""

import os, json, re, threading
from datetime import datetime
from flask import Flask, request, jsonify

app = Flask(__name__)

# ── HELPERS ───────────────────────────────────────────────────────────────────

def parse_plan_names(notes_text, section):
    """Extract INCLUDE plan names from the notes field for a given section."""
    lines = notes_text.split('\n')
    in_section = False
    plans = []
    for line in lines:
        line = line.strip()
        if line.upper().startswith(section.upper()):
            in_section = True
            continue
        if in_section:
            # Stop at next section
            if any(line.upper().startswith(s) for s in ['MEDICAL', 'DENTAL', 'VISION', 'CLIENT']):
                if not line.upper().startswith(section.upper()):
                    break
            if 'INCLUDE' in line.upper() and 'EXCLUDE' not in line.upper()[:8]:
                # Extract plan name — everything after "INCLUDE - " and before " - $"
                match = re.search(r'INCLUDE\s*[-–]\s*(.+?)\s*[-–]\s*\$', line, re.IGNORECASE)
                if match:
                    plans.append(match.group(1).strip())
    return plans

def generate_files(client_name, effective_date, quote_id, task_id, notes):
    """Run the proposal generation pipeline."""
    import sys
    sys.path.insert(0, '/opt/render/project/src')

    from proposal_data import (
        CLIENT, CONTRIBUTIONS, MEDICAL_PLANS, DENTAL_PLANS, VISION_PLANS
    )

    # Update client info dynamically
    CLIENT['name'] = client_name.replace(' — Review for Proposal', '').strip()
    CLIENT['effective_date'] = effective_date
    CLIENT['quote_id'] = quote_id

    # Parse selected plans from notes
    med_selected   = parse_plan_names(notes, 'MEDICAL')
    den_selected   = parse_plan_names(notes, 'DENTAL')
    vis_selected   = parse_plan_names(notes, 'VISION')

    print(f"Medical selected: {med_selected}")
    print(f"Dental selected:  {den_selected}")
    print(f"Vision selected:  {vis_selected}")

    # Set include flags
    for p in MEDICAL_PLANS:
        p['include'] = any(sel.lower() in p['plan_name'].lower() or
                           p['plan_name'].lower() in sel.lower()
                           for sel in med_selected)
    for p in DENTAL_PLANS:
        p['include'] = any(sel.lower() in p['plan_name'].lower() or
                           p['plan_name'].lower() in sel.lower()
                           for sel in den_selected)
    for p in VISION_PLANS:
        p['include'] = any(sel.lower() in p['plan_name'].lower() or
                           p['plan_name'].lower() in sel.lower()
                           for sel in vis_selected)

    # Generate files
    timestamp  = datetime.now().strftime('%Y%m%d_%H%M%S')
    safe_name  = CLIENT['name'].replace(' ', '_').replace('/', '-')
    eff        = effective_date.replace('/', '').replace(' ', '_').replace(',', '')[:10]
    pdf_name   = f"Proposal_{safe_name}_{eff}_v{timestamp}.pdf"
    excel_name = f"Proposal_{safe_name}_{eff}_v{timestamp}.xlsx"
    pdf_path   = f"/tmp/{pdf_name}"
    excel_path = f"/tmp/{excel_name}"

    from generate_pdf   import generate_pdf
    from generate_excel import generate_excel
    generate_pdf(pdf_path)
    generate_excel(excel_path)

    return pdf_path, excel_path, pdf_name, excel_name, CLIENT['name']


def upload_to_dropbox(pdf_path, excel_path, pdf_name, excel_name, client_name):
    """Upload files to Dropbox and return shared links."""
    import dropbox

    dbx = dropbox.Dropbox(os.environ['DROPBOX_TOKEN'])
    folder = f"/Benefits Group/Proposals/2026/{client_name.replace(' ', '_')}"

    links = {}
    for local_path, file_name in [(pdf_path, pdf_name), (excel_path, excel_name)]:
        db_path = f"{folder}/{file_name}"
        with open(local_path, 'rb') as f:
            dbx.files_upload(f.read(), db_path,
                             mode=dropbox.files.WriteMode.overwrite)
        # Create shared link
        try:
            link = dbx.sharing_create_shared_link_with_settings(db_path)
            links[file_name] = link.url.replace('?dl=0', '?dl=1')
        except dropbox.exceptions.ApiError:
            existing = dbx.sharing_list_shared_links(path=db_path)
            links[file_name] = existing.links[0].url.replace('?dl=0', '?dl=1')

    return links


def update_asana_task(task_id, client_name, pdf_link, excel_link, pdf_name, excel_name):
    """Move Asana task to Delivered and add comment with links."""
    import requests

    token   = os.environ['ASANA_TOKEN']
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type':  'application/json'
    }

    # Section GID for Proposal Delivered
    delivered_section = '1216532264374832'

    # Move to Delivered section
    requests.post(
        f'https://app.asana.com/api/1.0/sections/{delivered_section}/addTask',
        headers=headers,
        json={'data': {'task': task_id}}
    )

    # Add comment with links
    comment = (
        f"✅ Proposal generated successfully!\n\n"
        f"📄 PDF: {pdf_link}\n"
        f"📊 Excel: {excel_link}\n\n"
        f"Files: {pdf_name} | {excel_name}\n"
        f"Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}"
    )
    requests.post(
        f'https://app.asana.com/api/1.0/tasks/{task_id}/stories',
        headers=headers,
        json={'data': {'text': comment}}
    )
    print(f"Asana task {task_id} moved to Delivered")


def run_pipeline(client_name, effective_date, quote_id, task_id, notes):
    """Full pipeline — runs in background thread."""
    try:
        print(f"Starting pipeline for {client_name}")

        # Generate files
        pdf_path, excel_path, pdf_name, excel_name, clean_name = generate_files(
            client_name, effective_date, quote_id, task_id, notes
        )
        print(f"Files generated: {pdf_name}, {excel_name}")

        # Upload to Dropbox
        links = upload_to_dropbox(pdf_path, excel_path, pdf_name, excel_name, clean_name)
        print(f"Uploaded to Dropbox: {links}")

        # Update Asana
        pdf_link   = links.get(pdf_name,   'Upload failed')
        excel_link = links.get(excel_name, 'Upload failed')
        update_asana_task(task_id, clean_name, pdf_link, excel_link, pdf_name, excel_name)

        print(f"Pipeline complete for {client_name}")

    except Exception as e:
        print(f"Pipeline error: {e}")
        import traceback
        traceback.print_exc()


# ── ROUTES ────────────────────────────────────────────────────────────────────

@app.route('/', methods=['GET'])
def health():
    return jsonify({'status': 'TBG Proposal Generator running', 'version': '1.0'})


@app.route('/generate', methods=['POST'])
def generate():
    """Webhook endpoint — called by Zapier."""
    data = request.get_json(force=True, silent=True) or request.form.to_dict()

    client_name    = data.get('client_name', '')
    effective_date = data.get('effective_date', '')
    quote_id       = data.get('quote_id', '')
    task_id        = data.get('task_id', '')
    notes          = data.get('notes', '')

    print(f"Received request for: {client_name}")

    if not client_name or not task_id:
        return jsonify({'error': 'Missing client_name or task_id'}), 400

    # Run pipeline in background so webhook returns immediately
    thread = threading.Thread(
        target=run_pipeline,
        args=(client_name, effective_date, quote_id, task_id, notes)
    )
    thread.start()

    return jsonify({
        'status':  'accepted',
        'message': f'Generating proposal for {client_name}',
        'task_id': task_id
    }), 202


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
