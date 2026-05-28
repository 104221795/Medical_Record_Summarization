import argparse
import base64
import json
import re
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


API_DIR = Path(__file__).resolve().parent
SRC_DIR = API_DIR.parent / 'src'
STATIC_DIR = API_DIR / 'ui'
EXAMPLE_DIR = API_DIR / 'examples'
sys.path.insert(0, str(SRC_DIR))

import constants


MODEL = 'gemini-2.5-flash-lite'
TIMEOUT_SECONDS = 30
MAX_INPUT_CHARS = 48000
MAX_SOURCES = 60
CITATION_RE = re.compile(r'\[(E\d+)\]')
WORKFLOWS = {
    'record': {
        'label': 'Active record',
        'description': 'Longitudinal chart to active care view',
        'instruction': (
            'Summarize the active medical record for clinician chart review. '
            'Prioritize active problems, notable findings, treatments, and '
            'follow-up explicitly documented in the source.'
        ),
        'example': (
            '2026-05-18 Outpatient visit: Patient reports weak urinary stream '
            'and nocturia three times nightly for six months.\n'
            'Exam: Enlarged prostate without palpable mass.\n'
            'Assessment: Lower urinary tract symptoms, likely BPH; CAD stable; '
            'type 2 diabetes under monitoring.\n'
            'Plan: Check PSA, urinalysis and HbA1c. Start tamsulosin 0.4 mg '
            'nightly. Refer to urology. Continue atorvastatin and metformin.'
        ),
    },
    'radiology': {
        'label': 'Diagnostic report',
        'description': 'Imaging findings to supported impression',
        'instruction': (
            'Summarize the radiology findings into a concise impression for '
            'clinical review. Do not add diagnoses not evidenced in the report.'
        ),
        'example': (
            'Chest X-ray findings: Heart size within normal limits. No focal '
            'alveolar consolidation or pleural effusion. No pulmonary edema. '
            'Dense right upper lung nodule is compatible with prior '
            'granulomatous disease.'
        ),
    },
    'handoff': {
        'label': 'Encounter handoff',
        'description': 'Visit narrative to assessment and next steps',
        'instruction': (
            'Create a clinician handoff summary from the encounter note, '
            'including documented assessment, treatment, and pending actions.'
        ),
        'example': (
            'Emergency visit: Patient presented with fever and productive '
            'cough for three days. Oxygen saturation 96% on room air. Chest '
            'radiograph shows no acute infiltrate. Viral panel is pending. '
            'Plan is oral hydration, antipyretic as needed, and return '
            'precautions for worsening breathlessness.'
        ),
    },
}
SUMMARY_FIELDS = (
    ('clinical_overview', 'Clinical overview'),
    ('active_problems', 'Active problems'),
    ('key_findings', 'Key findings'),
    ('treatments_and_plan', 'Treatments and plan'),
    ('follow_up', 'Follow-up / pending actions'),
    ('uncertainties', 'Uncertainties and missing information'),
)


class GeminiError(RuntimeError):
    pass


class InputError(ValueError):
    pass


def load_json_file(file_name):
    return json.loads((EXAMPLE_DIR / file_name).read_text(encoding='utf-8'))


def clean_text(value):
    return re.sub(r'\s+', ' ', str(value or '')).strip()


def split_text_sources(text):
    blocks = [clean_text(item) for item in text.splitlines() if clean_text(item)]
    if len(blocks) <= 1:
        blocks = [
            clean_text(item)
            for item in re.split(r'(?<=[.!?])\s+', text.strip())
            if clean_text(item)
        ]
    sources = []
    for index, block in enumerate(blocks[:MAX_SOURCES], start=1):
        sources.append({
            'id': f'E{index}',
            'type': 'Narrative',
            'label': f'Record segment {index}',
            'text': block,
        })
    return sources


def coding_text(value):
    if not isinstance(value, dict):
        return clean_text(value)
    if value.get('text'):
        return clean_text(value['text'])
    codings = value.get('coding', [])
    if codings:
        coding = codings[0]
        return clean_text(coding.get('display') or coding.get('code'))
    return ''


def reference_label(resource):
    return f"{resource.get('resourceType', 'Resource')}/{resource.get('id', 'unidentified')}"


def fhir_source_text(resource):
    kind = resource.get('resourceType')
    if kind == 'Condition':
        status = coding_text(resource.get('clinicalStatus'))
        statement = coding_text(resource.get('code'))
        return f'Condition: {statement}. Clinical status: {status}.'
    if kind == 'Observation':
        name = coding_text(resource.get('code'))
        quantity = resource.get('valueQuantity', {})
        value = quantity.get('value', resource.get('valueString', ''))
        unit = quantity.get('unit', '')
        return f'Observation: {name}: {value} {unit}.'.strip()
    if kind == 'DiagnosticReport':
        return f"Diagnostic report conclusion: {clean_text(resource.get('conclusion'))}"
    if kind == 'MedicationRequest':
        medication = coding_text(resource.get('medicationCodeableConcept'))
        status = resource.get('status', '')
        dosage = resource.get('dosageInstruction', [{}])[0].get('text', '')
        return f'Medication request: {medication}; status: {status}; directions: {dosage}.'
    if kind == 'AllergyIntolerance':
        substance = coding_text(resource.get('code'))
        criticality = resource.get('criticality', '')
        return f'Allergy/intolerance: {substance}; criticality: {criticality}.'
    if kind == 'Procedure':
        return f"Procedure: {coding_text(resource.get('code'))}; status: {resource.get('status', '')}."
    if kind == 'ServiceRequest':
        return f"Service request: {coding_text(resource.get('code'))}; status: {resource.get('status', '')}."
    if kind == 'Encounter':
        reason = coding_text((resource.get('reasonCode') or [{}])[0])
        return f"Encounter: status {resource.get('status', '')}; reason: {reason}."
    if kind == 'DocumentReference':
        return f"Clinical document: {clean_text(resource.get('description'))}"
    return ''


def sources_from_fhir(bundle):
    if not isinstance(bundle, dict) or bundle.get('resourceType') != 'Bundle':
        raise InputError('FHIR input must be a FHIR R4 Bundle resource.')
    sources = []
    for entry in bundle.get('entry', []):
        resource = entry.get('resource', {})
        text = clean_text(fhir_source_text(resource))
        if text:
            sources.append({
                'id': f'E{len(sources) + 1}',
                'type': resource.get('resourceType', 'Resource'),
                'label': reference_label(resource),
                'text': text,
            })
        if len(sources) >= MAX_SOURCES:
            break
    if not sources:
        raise InputError(
            'No supported clinical resources found. Try Condition, Observation, '
            'DiagnosticReport, MedicationRequest, Encounter, or ServiceRequest.'
        )
    return sources


def build_grounded_request(sources, workflow):
    evidence = '\n'.join(
        f"[{item['id']}] {item['label']}: {item['text']}" for item in sources
    )
    system_prompt = (
        'You are an evidence-grounded clinical documentation assistant in a '
        'Vinmec-oriented concept prototype. Your output supports clinician '
        'review and is never a final clinical decision. Use only facts stated '
        'in the supplied evidence. Do not infer diagnoses, treatments, dates, '
        'or negative findings. If a fact is absent, write "Not documented in '
        'available record." Every factual bullet must include one or more '
        'evidence citations exactly like [E1]. Return valid JSON only.'
    )
    schema = {
        'clinical_overview': ['concise supported statement [E1]'],
        'active_problems': ['supported problem statement [E1]'],
        'key_findings': ['supported finding [E1]'],
        'treatments_and_plan': ['documented intervention only [E1]'],
        'follow_up': ['documented follow-up only [E1]'],
        'uncertainties': ['Not documented in available record.'],
    }
    prompt = (
        f"Workflow: {WORKFLOWS[workflow]['label']}\n"
        f"Instruction: {WORKFLOWS[workflow]['instruction']}\n\n"
        f"Evidence:\n{evidence}\n\n"
        f"Return this JSON shape:\n{json.dumps(schema)}"
    )
    return {
        'system_instruction': {'parts': [{'text': system_prompt}]},
        'contents': [{'role': 'user', 'parts': [{'text': prompt}]}],
        'generationConfig': {
            'temperature': 0.1,
            'responseMimeType': 'application/json',
        },
    }


def call_gemini(request_body):
    if not constants.GEMINI_API_KEY:
        raise GeminiError('GEMINI_API_KEY is missing from .env.')
    request = urllib.request.Request(
        constants.GEMINI_URL_MODEL[MODEL],
        data=json.dumps(request_body).encode('utf-8'),
        headers={
            'Content-Type': 'application/json',
            'x-goog-api-key': constants.GEMINI_API_KEY,
        },
        method='POST',
    )
    for attempt in range(2):
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                result = json.loads(response.read().decode('utf-8'))
            parts = result['candidates'][0]['content']['parts']
            return ''.join(item.get('text', '') for item in parts).strip()
        except urllib.error.HTTPError as exc:
            raw_response = exc.read().decode('utf-8')
            try:
                body = json.loads(raw_response)
                message = body.get('error', {}).get('message', raw_response)
            except json.JSONDecodeError:
                message = raw_response
            if exc.code in (429, 503) and attempt == 0:
                time.sleep(1.2)
                continue
            raise GeminiError(f'Gemini request failed: {message}') from exc
        except (KeyError, IndexError, TypeError) as exc:
            raise GeminiError('Gemini returned no usable summary.') from exc
        except urllib.error.URLError as exc:
            raise GeminiError(f'Unable to reach Gemini: {exc.reason}') from exc
        except TimeoutError as exc:
            raise GeminiError('Gemini did not respond within 30 seconds.') from exc


def parse_summary(raw_output):
    cleaned = raw_output.strip()
    if cleaned.startswith('```'):
        cleaned = re.sub(r'^```(?:json)?\s*|\s*```$', '', cleaned).strip()
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise GeminiError('Gemini returned an invalid structured summary.') from exc
    summary = {}
    for field, _ in SUMMARY_FIELDS:
        items = value.get(field, [])
        if isinstance(items, str):
            items = [items]
        summary[field] = [clean_text(item) for item in items if clean_text(item)]
    return summary


def validate_citations(summary, sources):
    valid_ids = {item['id'] for item in sources}
    referenced_ids = set()
    uncited = []
    invalid = []
    total_claims = 0
    supported_claims = 0
    for field, _ in SUMMARY_FIELDS:
        for claim in summary[field]:
            if claim.lower().startswith('not documented'):
                continue
            total_claims += 1
            claim_ids = set(CITATION_RE.findall(claim))
            referenced_ids.update(claim_ids)
            invalid_ids = sorted(claim_ids - valid_ids)
            if invalid_ids:
                invalid.append({'claim': claim, 'ids': invalid_ids})
            elif claim_ids:
                supported_claims += 1
            else:
                uncited.append(claim)
    score = round((supported_claims / total_claims) * 100) if total_claims else 100
    alerts = []
    if uncited:
        alerts.append(f'{len(uncited)} generated claim(s) have no evidence citation.')
    if invalid:
        alerts.append(f'{len(invalid)} generated claim(s) cite unavailable evidence.')
    if not alerts:
        alerts.append('All generated factual claims include available source citations.')
    return {
        'citation_coverage': score,
        'referenced_sources': sorted(referenced_ids & valid_ids),
        'uncited_claims': uncited,
        'invalid_citations': invalid,
        'alerts': alerts,
        'status': 'Clinician review required',
    }


def summary_plain_text(summary):
    text = []
    for field, label in SUMMARY_FIELDS:
        text.append(label.upper())
        text.extend(f'- {item}' for item in summary[field])
        text.append('')
    return '\n'.join(text).strip()


def draft_fhir_export(summary, sources, request_id, generated_at):
    content = summary_plain_text(summary)
    document_id = f'ai-summary-{request_id}'
    composition_id = f'composition-{request_id}'
    encoded = base64.b64encode(content.encode('utf-8')).decode('ascii')
    sections = []
    for field, label in SUMMARY_FIELDS:
        bullets = ''.join(f'<li>{escape(item)}</li>' for item in summary[field])
        sections.append({
            'title': label,
            'text': {
                'status': 'generated',
                'div': (
                    '<div xmlns="http://www.w3.org/1999/xhtml">'
                    f'<ul>{bullets}</ul></div>'
                ),
            },
        })
    return {
        'resourceType': 'Bundle',
        'type': 'collection',
        'id': f'draft-summary-export-{request_id}',
        'timestamp': generated_at,
        'meta': {'tag': [{'display': 'AI-generated draft - clinician review required'}]},
        'entry': [
            {
                'resource': {
                    'resourceType': 'Composition',
                    'id': composition_id,
                    'status': 'preliminary',
                    'type': {'text': 'AI-assisted clinical summary draft'},
                    'date': generated_at,
                    'title': 'Clinical Summary Draft - Review Required',
                    'author': [{'display': f'ClinSumm prototype using {MODEL}'}],
                    'section': sections,
                }
            },
            {
                'resource': {
                    'resourceType': 'DocumentReference',
                    'id': document_id,
                    'status': 'current',
                    'docStatus': 'preliminary',
                    'description': 'AI-assisted summary draft requiring clinician attestation',
                    'content': [{
                        'attachment': {
                            'contentType': 'text/plain',
                            'data': encoded,
                            'title': 'Clinical Summary Draft',
                        }
                    }],
                }
            },
            {
                'resource': {
                    'resourceType': 'Provenance',
                    'id': f'provenance-{request_id}',
                    'recorded': generated_at,
                    'target': [
                        {'reference': f'Composition/{composition_id}'},
                        {'reference': f'DocumentReference/{document_id}'},
                    ],
                    'agent': [{
                        'type': {'text': 'assembler'},
                        'who': {'display': f'ClinSumm prototype / {MODEL}'},
                    }],
                    'entity': [
                        {'role': 'source', 'what': {'display': item['label']}}
                        for item in sources
                    ],
                }
            },
        ],
    }


def create_summary(payload):
    workflow = payload.get('workflow', 'record')
    input_type = payload.get('input_type', 'text')
    if workflow not in WORKFLOWS:
        raise InputError('Unknown clinical workflow.')
    if input_type == 'text':
        text = payload.get('text', '')
        if not isinstance(text, str) or not text.strip():
            raise InputError('Enter a clinical record to summarize.')
        if len(text) > MAX_INPUT_CHARS:
            raise InputError(f'Input is limited to {MAX_INPUT_CHARS:,} characters.')
        sources = split_text_sources(text)
    elif input_type == 'fhir':
        bundle = payload.get('fhir_bundle')
        if isinstance(bundle, str):
            try:
                bundle = json.loads(bundle)
            except json.JSONDecodeError as exc:
                raise InputError('FHIR Bundle JSON is invalid.') from exc
        sources = sources_from_fhir(bundle)
    else:
        raise InputError('Input type must be narrative text or FHIR Bundle.')

    raw_summary = call_gemini(build_grounded_request(sources, workflow))
    summary = parse_summary(raw_summary)
    safety = validate_citations(summary, sources)
    request_id = str(uuid.uuid4())[:8]
    generated_at = datetime.now(timezone.utc).isoformat()
    return {
        'request_id': request_id,
        'generated_at': generated_at,
        'model': MODEL,
        'workflow': workflow,
        'input_type': input_type,
        'summary': summary,
        'sources': sources,
        'safety': safety,
        'review_status': 'AI draft - clinician attestation required before EMR writeback',
        'fhir_export': draft_fhir_export(summary, sources, request_id, generated_at),
    }


class DemoHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path
        if path == '/':
            return self.send_static('index.html', 'text/html; charset=utf-8')
        if path == '/api/config':
            return self.send_json({
                'model': MODEL,
                'workflows': WORKFLOWS,
                'max_input_chars': MAX_INPUT_CHARS,
                'configured': bool(constants.GEMINI_API_KEY),
                'capabilities': [
                    'Active Summarizer',
                    'Citation-based Summary',
                    'Hallucination Safety Gate',
                    'FHIR R4 Integration Preview',
                ],
            })
        if path == '/api/examples/fhir':
            return self.send_json(load_json_file('fhir_encounter_bundle.json'))
        if path.startswith('/assets/'):
            asset_name = path.removeprefix('/assets/')
            content_types = {
                'styles.css': 'text/css; charset=utf-8',
                'app.js': 'application/javascript; charset=utf-8',
            }
            if asset_name in content_types:
                return self.send_static(asset_name, content_types[asset_name])
        self.send_error(404, 'Not found')

    def do_POST(self):
        if urlparse(self.path).path != '/api/summarize':
            return self.send_error(404, 'Not found')
        try:
            content_length = int(self.headers.get('Content-Length', '0'))
            payload = json.loads(self.rfile.read(content_length).decode('utf-8'))
        except (ValueError, json.JSONDecodeError):
            return self.send_json({'error': 'Invalid JSON request.'}, status=400)
        try:
            result = create_summary(payload)
        except InputError as exc:
            return self.send_json({'error': str(exc)}, status=400)
        except GeminiError as exc:
            return self.send_json({'error': str(exc)}, status=502)
        self.send_json(result)

    def send_static(self, file_name, content_type):
        file_path = STATIC_DIR / file_name
        try:
            body = file_path.read_bytes()
        except FileNotFoundError:
            return self.send_error(404, 'Asset not found')
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, value, status=200):
        body = json.dumps(value).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format_string, *args):
        print(f'[enterprise-demo] {self.address_string()} - {format_string % args}')


def main():
    parser = argparse.ArgumentParser(description='Run the clinical summary enterprise prototype.')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), DemoHandler)
    print(f'Clinical Summary enterprise prototype ready at http://{args.host}:{args.port}')
    print(f'Model: {MODEL} | API key configured: {bool(constants.GEMINI_API_KEY)}')
    print('Concept prototype only: no production HIS/EMR connection or clinical attestation.')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nStopping clinical summary prototype.')
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
