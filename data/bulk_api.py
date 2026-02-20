"""
Bulk API 2.0 - Operations for large data volumes.
Adapted from existing sf_bulk.py framework.
"""
import time
import csv
import requests
import pandas as pd
from io import StringIO
from typing import Optional

from config import SF_API_VERSION, BULK_POLL_INTERVAL


class BulkAPI:
    """
    Salesforce Bulk API 2.0 client for large data operations.
    """
    
    def __init__(self, instance_url: str, session_id: str):
        """
        Initialize Bulk API client.
        
        Args:
            instance_url: Salesforce instance URL (e.g., na1.salesforce.com)
            session_id: Valid session ID
        """
        self.instance_url = instance_url
        self.session_id = session_id
        self.api_version = SF_API_VERSION
    
    def _headers(self, content_type: str = None) -> dict:
        """Get request headers."""
        h = {"Authorization": f"Bearer {self.session_id}"}
        if content_type:
            h["Content-Type"] = content_type
        return h
    
    def _check_response(self, resp: requests.Response, action: str = ""):
        """Check response status and raise on error."""
        if resp.status_code not in (200, 201):
            raise Exception(f"❌ {action} | HTTP {resp.status_code}: {resp.text}")
    
    # ==================== QUERY OPERATIONS ====================
    
    def create_query_job(
        self,
        query: str,
        operation: str = "query",
        line_ending: str = "LF",
        column_delimiter: str = "COMMA"
    ) -> str:
        """Create a Bulk Query job."""
        url = f"https://{self.instance_url}/services/data/v{self.api_version}/jobs/query"
        payload = {
            "operation": operation,
            "query": query,
            "contentType": "CSV",
            "lineEnding": line_ending,
            "columnDelimiter": column_delimiter
        }
        resp = requests.post(url, headers=self._headers("application/json"), json=payload)
        self._check_response(resp, "Error creating query job")
        return resp.json().get("id")
    
    def wait_for_completion(
        self,
        job_id: str,
        mode: str,
        poll_interval: int = None,
        timeout: int = None,
        progress_callback=None
    ) -> dict:
        """
        Wait for a job to complete.
        
        Args:
            job_id: Job ID to monitor
            mode: 'query' or 'ingest'
            poll_interval: Seconds between checks
            timeout: Maximum wait time in seconds
            progress_callback: Optional callback(state, records_processed)
            
        Returns:
            Final job status dictionary
        """
        poll_interval = poll_interval or BULK_POLL_INTERVAL
        url = f"https://{self.instance_url}/services/data/v{self.api_version}/jobs/{mode}/{job_id}"
        start = time.time()
        
        while True:
            resp = requests.get(url, headers=self._headers())
            self._check_response(resp, f"Error checking job {job_id}")
            data = resp.json()
            state = data.get("state")
            
            if progress_callback:
                records = data.get("numberRecordsProcessed", 0)
                progress_callback(state, records)
            
            if state in ("JobComplete", "Failed", "Aborted"):
                return data
            
            if timeout and (time.time() - start > timeout):
                raise TimeoutError(f"Job {job_id} timed out after {timeout}s")
            
            time.sleep(poll_interval)
    
    def download_query_results(
        self,
        job_id: str,
        max_records: int = 250000
    ) -> list[dict]:
        """Download results from a completed query job."""
        url = f"https://{self.instance_url}/services/data/v{self.api_version}/jobs/query/{job_id}/results"
        locator = None
        results = []
        
        while True:
            params = {"maxRecords": max_records}
            if locator:
                params["locator"] = locator
            
            resp = requests.get(url, headers=self._headers("application/json"), params=params)
            if resp.status_code != 200:
                raise Exception(f"❌ Error downloading results: {resp.text}")
            
            csv_file = StringIO(resp.text)
            reader = csv.DictReader(csv_file)
            results.extend(reader)
            
            locator = resp.headers.get("Sforce-Locator")
            if not locator or locator.lower() == "null":
                break
        
        return results
    
    def run_query(
        self,
        query: str,
        poll_interval: int = None,
        progress_callback=None
    ) -> list[dict]:
        """
        Full query flow: create job, wait, download results.
        
        Args:
            query: SOQL query string
            poll_interval: Seconds between status checks
            progress_callback: Optional callback for progress updates
            
        Returns:
            List of record dictionaries
        """
        job_id = self.create_query_job(query)
        self.wait_for_completion(
            job_id,
            "query",
            poll_interval=poll_interval,
            progress_callback=progress_callback
        )
        return self.download_query_results(job_id)
    
    # ==================== INGEST OPERATIONS ====================
    
    def create_ingest_job(
        self,
        object_name: str,
        operation: str = "update",
        line_ending: str = "LF",
        external_id_field: str = None
    ) -> str:
        """
        Create a Bulk Ingest job.
        
        Args:
            object_name: Salesforce object API name
            operation: 'insert', 'update', 'upsert', or 'delete'
            line_ending: Line ending format
            external_id_field: Required for upsert operations
            
        Returns:
            Job ID
        """
        url = f"https://{self.instance_url}/services/data/v{self.api_version}/jobs/ingest"
        payload = {
            "object": object_name,
            "operation": operation,
            "contentType": "CSV",
            "lineEnding": line_ending
        }
        
        if external_id_field and operation == "upsert":
            payload["externalIdFieldName"] = external_id_field
        
        resp = requests.post(url, headers=self._headers("application/json"), json=payload)
        self._check_response(resp, f"Error creating {operation} job")
        return resp.json().get("id")
    
    def upload_data(self, job_id: str, csv_data: str):
        """Upload CSV data to an ingest job."""
        url = f"https://{self.instance_url}/services/data/v{self.api_version}/jobs/ingest/{job_id}/batches"
        resp = requests.put(
            url,
            headers=self._headers("text/csv; charset=UTF-8"),
            data=csv_data.encode("utf-8")
        )
        self._check_response(resp, "Error uploading data")
    
    def close_ingest_job(self, job_id: str):
        """Close an ingest job to start processing."""
        url = f"https://{self.instance_url}/services/data/v{self.api_version}/jobs/ingest/{job_id}"
        resp = requests.patch(
            url,
            headers=self._headers("application/json"),
            json={"state": "UploadComplete"}
        )
        self._check_response(resp, "Error closing job")
    
    def get_ingest_results(self, job_id: str) -> tuple[list, list]:
        """
        Get results from a completed ingest job.
        
        Returns:
            Tuple of (success_records, failed_records)
        """
        base_url = f"https://{self.instance_url}/services/data/v{self.api_version}/jobs/ingest/{job_id}"
        
        # Successful records
        resp_success = requests.get(
            f"{base_url}/successfulResults",
            headers=self._headers()
        )
        
        # Failed records
        resp_failed = requests.get(
            f"{base_url}/failedResults",
            headers=self._headers()
        )
        
        success_results = []
        failed_results = []
        
        if resp_success.status_code == 200 and resp_success.text.strip():
            csv_file = StringIO(resp_success.text)
            success_results = list(csv.DictReader(csv_file))
        
        if resp_failed.status_code == 200 and resp_failed.text.strip():
            csv_file = StringIO(resp_failed.text)
            failed_results = list(csv.DictReader(csv_file))
        
        return success_results, failed_results
    
    def _records_to_csv(self, records: list[dict]) -> str:
        """Convert list of dictionaries to CSV string."""
        if not records:
            return ""
        
        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=records[0].keys(), lineterminator='\n')
        writer.writeheader()
        writer.writerows(records)
        return output.getvalue()
    
    def _df_to_csv(self, df: pd.DataFrame) -> str:
        """Convert DataFrame to CSV string."""
        return df.to_csv(index=False, lineterminator='\n')
    
    def run_update(
        self,
        object_name: str,
        records: list[dict],
        poll_interval: int = None,
        progress_callback=None
    ) -> tuple[list, list]:
        """
        Full update flow: create job, upload, wait, get results.
        
        Args:
            object_name: Salesforce object API name
            records: List of record dictionaries (must include Id)
            poll_interval: Seconds between status checks
            progress_callback: Optional progress callback
            
        Returns:
            Tuple of (success_records, failed_records)
        """
        # Validate records have Id
        if records and 'Id' not in records[0]:
            raise ValueError("Records must include 'Id' field for updates")
        
        csv_data = self._records_to_csv(records)
        
        job_id = self.create_ingest_job(object_name, operation="update")
        self.upload_data(job_id, csv_data)
        self.close_ingest_job(job_id)
        
        self.wait_for_completion(
            job_id,
            "ingest",
            poll_interval=poll_interval,
            progress_callback=progress_callback
        )
        
        return self.get_ingest_results(job_id)
    
    def run_insert(
        self,
        object_name: str,
        records: list[dict],
        poll_interval: int = None,
        progress_callback=None
    ) -> tuple[list, list]:
        """
        Full insert flow: create job, upload, wait, get results.
        
        Args:
            object_name: Salesforce object API name
            records: List of record dictionaries
            poll_interval: Seconds between status checks
            progress_callback: Optional progress callback
            
        Returns:
            Tuple of (success_records, failed_records)
        """
        csv_data = self._records_to_csv(records)
        
        job_id = self.create_ingest_job(object_name, operation="insert")
        self.upload_data(job_id, csv_data)
        self.close_ingest_job(job_id)
        
        self.wait_for_completion(
            job_id,
            "ingest",
            poll_interval=poll_interval,
            progress_callback=progress_callback
        )
        
        return self.get_ingest_results(job_id)
    
    def run_delete(
        self,
        object_name: str,
        record_ids: list[str],
        poll_interval: int = None,
        progress_callback=None
    ) -> tuple[list, list]:
        """
        Full delete flow.
        
        Args:
            object_name: Salesforce object API name
            record_ids: List of record IDs to delete
            poll_interval: Seconds between status checks
            progress_callback: Optional progress callback
            
        Returns:
            Tuple of (success_records, failed_records)
        """
        records = [{"Id": rid} for rid in record_ids]
        csv_data = self._records_to_csv(records)
        
        job_id = self.create_ingest_job(object_name, operation="delete")
        self.upload_data(job_id, csv_data)
        self.close_ingest_job(job_id)
        
        self.wait_for_completion(
            job_id,
            "ingest",
            poll_interval=poll_interval,
            progress_callback=progress_callback
        )
        
        return self.get_ingest_results(job_id)
    
    def run_update_df(
        self,
        object_name: str,
        df: pd.DataFrame,
        poll_interval: int = None,
        progress_callback=None
    ) -> tuple[list, list]:
        """
        Update using a DataFrame.
        
        Args:
            object_name: Salesforce object API name
            df: DataFrame with Id column and fields to update
            poll_interval: Seconds between status checks
            progress_callback: Optional progress callback
            
        Returns:
            Tuple of (success_records, failed_records)
        """
        if 'Id' not in df.columns:
            raise ValueError("DataFrame must include 'Id' column")
        
        csv_data = self._df_to_csv(df)
        
        job_id = self.create_ingest_job(object_name, operation="update")
        self.upload_data(job_id, csv_data)
        self.close_ingest_job(job_id)
        
        self.wait_for_completion(
            job_id,
            "ingest",
            poll_interval=poll_interval,
            progress_callback=progress_callback
        )
        
        return self.get_ingest_results(job_id)
