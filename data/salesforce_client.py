"""
Salesforce Client - Manages authentication and API operations.
"""
import json
import os
from pathlib import Path
from typing import Optional
from simple_salesforce import Salesforce

from config import SF_API_VERSION, SF_CREDENTIALS_PATH


class SalesforceClient:
    """
    Client for Salesforce API operations.
    Handles authentication and provides methods for queries and updates.
    """
    
    def __init__(self, env: str = 'pre'):
        """
        Initialize the Salesforce client.
        
        Args:
            env: Environment to connect to ('pre' or 'pro')
        """
        self.env = env
        self.sf: Optional[Salesforce] = None
        self.instance_url: Optional[str] = None
        self.session_id: Optional[str] = None
        self._bulk_api = None
        self._is_authenticated = False
    
    @property
    def is_authenticated(self) -> bool:
        """Check if client is authenticated."""
        return self._is_authenticated
    
    def authenticate(self, credentials_path: str = None) -> bool:
        """
        Authenticate with Salesforce using sf_bulk.py for unified session handling.
        Args:
            credentials_path: Path to credentials JSON file
        Returns:
            True if authentication successful
        """
        import sys
        from pathlib import Path
        scripts_dir = str(Path(__file__).parent.parent / "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        import sf_bulk

        # Use sf_bulk login (will print logs and set global session)
        sf_bulk.login(self.env)
        self.instance_url = sf_bulk.instance_url
        self.session_id = sf_bulk.session_id
        self._is_authenticated = True
        self.sf = None  # Not used, but kept for compatibility
        self._bulk_api = None
        return True
    
    def disconnect(self):
        """Disconnect from Salesforce."""
        self.sf = None
        self.instance_url = None
        self.session_id = None
        self._bulk_api = None
        self._is_authenticated = False
    
    def query(self, soql: str, poll_interval: int = 15) -> list[dict]:
        """
        Execute a SOQL query using sf_bulk.py for unified logging and efficiency.
        Args:
            soql: SOQL query string
            poll_interval: Seconds between status checks
        Returns:
            List of record dictionaries
        """
        if not self._is_authenticated:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        import sys
        from pathlib import Path
        scripts_dir = str(Path(__file__).parent.parent / "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        import sf_bulk

        # Ensure login/session is set
        if not sf_bulk.session_id or not sf_bulk.instance_url:
            sf_bulk.login(self.env)

        print(f"[SalesforceClient] Ejecutando query via sf_bulk.py: {soql}")
        results = sf_bulk.run_bulk_query(soql, poll_interval=poll_interval)
        return results
    
    def bulk_query(self, soql: str, poll_interval: int = 15) -> list[dict]:
        """
        Execute a SOQL query using Bulk API 2.0 via sf_bulk.py for better logging and efficiency.
        Args:
            soql: SOQL query string
            poll_interval: Seconds between status checks
        Returns:
            List of record dictionaries
        """
        if not self._is_authenticated:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        # Use sf_bulk.py for bulk query
        import sys
        from pathlib import Path
        scripts_dir = str(Path(__file__).parent.parent / "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        import sf_bulk

        # Ensure login/session is set
        if not sf_bulk.session_id or not sf_bulk.instance_url:
            sf_bulk.login(self.env)

        print(f"[SalesforceClient] Ejecutando bulk_query via sf_bulk.py: {soql}")
        results = sf_bulk.run_bulk_query(soql, poll_interval=poll_interval)
        return results
    
    def bulk_update(
        self,
        object_name: str,
        records: list[dict],
        poll_interval: int = 15
    ) -> tuple[list, list]:
        """
        Update records using Bulk API 2.0.
        
        Args:
            object_name: Salesforce object API name
            records: List of dictionaries with Id and fields to update
            poll_interval: Seconds between status checks
            
        Returns:
            Tuple of (success_records, failed_records)
        """
        if not self._is_authenticated:
            raise RuntimeError("Not authenticated. Call authenticate() first.")
        
        return self._bulk_api.run_update(
            object_name,
            records,
            poll_interval=poll_interval
        )
    
    def bulk_insert(
        self,
        object_name: str,
        records: list[dict],
        poll_interval: int = 15
    ) -> tuple[list, list]:
        """
        Insert records using Bulk API 2.0.
        
        Args:
            object_name: Salesforce object API name
            records: List of dictionaries with field values
            poll_interval: Seconds between status checks
            
        Returns:
            Tuple of (success_records, failed_records)
        """
        if not self._is_authenticated:
            raise RuntimeError("Not authenticated. Call authenticate() first.")
        
        return self._bulk_api.run_insert(
            object_name,
            records,
            poll_interval=poll_interval
        )
    
    def describe_object(self, object_name: str) -> dict:
        """
        Get metadata description of a Salesforce object.
        
        Args:
            object_name: API name of the object
            
        Returns:
            Object metadata dictionary
        """
        if not self._is_authenticated:
            raise RuntimeError("Not authenticated. Call authenticate() first.")
        
        return getattr(self.sf, object_name).describe()
    
    def get_picklist_values(self, object_name: str, field_name: str) -> list[dict]:
        """
        Get picklist values for a field.
        
        Args:
            object_name: API name of the object
            field_name: API name of the field
            
        Returns:
            List of picklist value dictionaries
        """
        desc = self.describe_object(object_name)
        for field in desc['fields']:
            if field['name'] == field_name:
                return field.get('picklistValues', [])
        return []
    
    def get_instance_url_full(self) -> str:
        """Get full Salesforce instance URL."""
        return f"https://{self.instance_url}"
    
    def get_record_url(self, record_id: str) -> str:
        """Get URL to view a specific record."""
        return f"https://{self.instance_url}/lightning/r/{record_id}/view"
