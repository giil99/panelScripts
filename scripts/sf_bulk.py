import time
import requests
import csv
from io import StringIO
from simple_salesforce import Salesforce
import json
import os

# Configuration
API_VERSION = "62.0"

# Global variables to hold session info
instance_url = None
session_id = None

def login(env='pre'):
    """
    Authenticates with Salesforce using credentials from salesforce_credentials.json.
    env: 'pre' or 'pro'
    """
    global instance_url, session_id
    
    # Locate credentials file
    # Assuming the script is run from the directory where salesforce_credentials.json is, 
    # or we look in the current directory.
    creds_path = 'salesforce_credentials.json'
    if not os.path.exists(creds_path):
        # Try to find it in the same directory as this script if imported
        script_dir = os.path.dirname(os.path.abspath(__file__))
        creds_path = os.path.join(script_dir, 'salesforce_credentials.json')
        
    if not os.path.exists(creds_path):
        raise FileNotFoundError(f"Could not find salesforce_credentials.json at {creds_path}")

    with open(creds_path, 'r', encoding='utf-8') as f:
        creds = json.load(f)[env]

    USERNAME = creds['USERNAME']
    PASSWORD = creds['PASSWORD']
    SECURITY_TOKEN = creds['SECURITY_TOKEN']
    DOMAIN = creds['DOMAIN']

    try:
        sf = Salesforce(username=USERNAME, password=PASSWORD, security_token=SECURITY_TOKEN, domain=DOMAIN)
        instance_url = sf.sf_instance
        session_id = sf.session_id
        print(f"Authentication successful. Instance: {instance_url}")
    except Exception as e:
        print("Authentication error:", e)
        raise e

def setHeaders(content_type=None):
    h = {"Authorization": f"Bearer {session_id}"}
    if content_type:
        h["Content-Type"] = content_type
    return h

def checkResponse(resp, action_message=""):
    if resp.status_code not in (200, 201):
        raise Exception(f"❌ {action_message} | HTTP {resp.status_code}: {resp.text}")

# --- Bulk Ingest ---

def create_bulk_ingest_job(object_name, operation, line_ending="LF", extra_payload=None):
    """
    Create a Bulk Ingest job.
    extra_payload: dict of additional fields (e.g., externalIdFieldName for upsert)
    """
    url = f"https://{instance_url}/services/data/v{API_VERSION}/jobs/ingest"
    payload = {
        "object": object_name,
        "operation": operation,
        "contentType": "CSV",
        "lineEnding": line_ending
    }

    if extra_payload:
        payload.update(extra_payload)

    resp = requests.post(url, headers=setHeaders("application/json"), json=payload)
    checkResponse(resp, "Error creating ingest job")
    return resp.json()["id"]

def upload_bulk_data(job_id, csv_data):
    url = f"https://{instance_url}/services/data/v{API_VERSION}/jobs/ingest/{job_id}/batches"
    resp = requests.put(url, headers=setHeaders("text/csv; charset=UTF-8"), data=csv_data.encode("utf-8"))
    checkResponse(resp, "Error uploading data in ingest")

def close_bulk_ingest_job(job_id):
    url = f"https://{instance_url}/services/data/v{API_VERSION}/jobs/ingest/{job_id}"
    resp = requests.patch(url, headers=setHeaders("application/json"), json={"state": "UploadComplete"})
    checkResponse(resp, "Error closing ingest job")

# --- Bulk Query ---

def create_bulk_query_job(query: str, operation="query", line_ending="LF", column_delimiter="COMMA") -> str:
    """Create a Bulk Query job (CSV only)."""
    url = f"https://{instance_url}/services/data/v{API_VERSION}/jobs/query"
    payload = {
        "operation": operation,
        "query": query,
        "contentType": "CSV",
        "lineEnding": line_ending,
        "columnDelimiter": column_delimiter,
    }

    resp = requests.post(url, headers=setHeaders("application/json"), json=payload)
    checkResponse(resp, "Error creating query job")
    return resp.json().get("id")

# --- Job Polling ---

def wait_for_completion(job_id: str, mode: str, poll_interval=20, timeout=None) -> dict:
    """Poll the job until completion or timeout."""
    url = f"https://{instance_url}/services/data/v{API_VERSION}/jobs/{mode}/{job_id}"
    start = time.time()

    while True:
        resp = requests.get(url, headers=setHeaders())
        checkResponse(resp, f"Error checking job status {job_id}")
        data = resp.json()
        state = data.get("state")
        print(f"⏳ Job {job_id} state: {state}")

        if state in ("JobComplete", "Failed", "Aborted"):
            print(f"✅ Job finished: {state}")
            return data

        if timeout and (time.time() - start > timeout):
            raise TimeoutError(f"Job {job_id} timed out after {timeout}s")

        time.sleep(poll_interval)

# --- Download Results ---

def download_bulk_query_job(job_id: str, max_records=250000):
    url_results = f'https://{instance_url}/services/data/v{API_VERSION}/jobs/query/{job_id}/results'
    locator = None
    chunk = 0
    results = []

    while True:
        params = {'maxRecords': max_records}
        if locator:
            params['locator'] = locator

        resp = requests.get(
            url_results,
            headers=setHeaders('application/json'),
            params=params
        )
        if resp.status_code != 200:
            raise Exception(f'❌ Error downloading chunk {chunk + 1}: {resp.text}')

        csv_file = StringIO(resp.content.decode('utf-8'))
        reader = csv.DictReader(csv_file)
        results.extend(reader)

        locator = resp.headers.get('Sforce-Locator')
        if not locator or locator.lower() == 'null':
            break

        chunk += 1
        print(f'📦 Fetched chunk {chunk}, next locator: {locator}')

    return results

# ---------------------------
# Get Job Results (Ingest Jobs)
# ---------------------------

def get_job_results(job_id):
    """Obtiene los resultados del job para verificar éxitos y errores"""
    print(f"\nObteniendo resultados del job {job_id}...")
    
    try:
        # Obtener resultados exitosos
        success_url = f"https://{instance_url}/services/data/v{API_VERSION}/jobs/ingest/{job_id}/successfulResults"
        success_resp = requests.get(success_url, headers=setHeaders())
        
        # Obtener resultados con errores
        failed_url = f"https://{instance_url}/services/data/v{API_VERSION}/jobs/ingest/{job_id}/failedResults"
        failed_resp = requests.get(failed_url, headers=setHeaders())
        
        # Parsear resultados
        success_count = 0
        error_count = 0
        errors_log = []
        
        if success_resp.status_code == 200 and success_resp.text.strip():
            success_csv = StringIO(success_resp.text)
            success_reader = csv.DictReader(success_csv)
            success_count = sum(1 for _ in success_reader)
        
        if failed_resp.status_code == 200 and failed_resp.text.strip():
            failed_csv = StringIO(failed_resp.text)
            failed_reader = csv.DictReader(failed_csv)
            for row in failed_reader:
                error_count += 1
                error_msg = f"Order ID: {row.get('Id', 'N/A')} - Error: {row.get('sf__Error', 'Unknown error')}"
                errors_log.append(error_msg)
        
        print(f"\n{'='*60}")
        print(f"RESUMEN DE REGISTROS PROCESADOS")
        print(f"{'='*60}")
        print(f"✓ Registros procesados correctamente: {success_count}")
        print(f"✗ Errores: {error_count}")
        
        if errors_log:
            print(f"\nErrores detallados:")
            for error in errors_log[:10]:
                print(f"  - {error}")
            if len(errors_log) > 10:
                print(f"  ... y {len(errors_log) - 10} errores más")
        
        return success_count, error_count, errors_log
        
    except Exception as e:
        print(f"✗ Error obteniendo resultados del job: {str(e)}")
        return 0, 0, []
   


# --- Public Convenience Methods ---

def run_bulk_query(query: str, max_records=250000, poll_interval=5):
    """Full flow: create job, wait for completion, and get results."""
    job_id = create_bulk_query_job(query)
    wait_for_completion(job_id, "query", poll_interval=poll_interval)
    return download_bulk_query_job(job_id, max_records=max_records)

def run_bulk_insert(object_name, csv_data):
    job_id = create_bulk_ingest_job(object_name, operation="insert")
    upload_bulk_data(job_id, csv_data)
    close_bulk_ingest_job(job_id)
    wait_for_completion(job_id, "ingest")
    get_job_results(job_id)
    return job_id

def run_bulk_update(object_name, csv_data):
    job_id = create_bulk_ingest_job(object_name, operation="update")
    upload_bulk_data(job_id, csv_data)
    close_bulk_ingest_job(job_id)
    wait_for_completion(job_id, "ingest")
    get_job_results(job_id)
    return job_id

def run_bulk_delete(object_name, csv_data):
    job_id = create_bulk_ingest_job(object_name, operation="delete")
    upload_bulk_data(job_id, csv_data)
    close_bulk_ingest_job(job_id)
    wait_for_completion(job_id, "ingest")
    get_job_results(job_id)
    return job_id

def run_bulk_upsert(object_name, csv_data, external_id_field, poll_interval=5):
    job_id = create_bulk_ingest_job(
        object_name,
        operation="upsert",
        extra_payload={"externalIdFieldName": external_id_field},
    )
    upload_bulk_data(job_id, csv_data)
    close_bulk_ingest_job(job_id)
    wait_for_completion(job_id, "ingest", poll_interval=poll_interval)
    get_job_results(job_id)
    return job_id
