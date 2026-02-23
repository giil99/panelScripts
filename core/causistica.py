"""
Causística Framework - Support for multiple business scenarios within a single script.

This module provides the infrastructure for scripts that need to detect and report
multiple different business scenarios (causísticas), each with its own dataset,
metrics, and validation logic.
"""
from dataclasses import dataclass, field
from typing import Optional, Callable, Any, Dict, List
import pandas as pd
from datetime import datetime


@dataclass
class CausisticaResult:
    """Result of a single causística (business scenario)."""
    code: str  # e.g., "A1", "C2", "D11"
    name: str  # Human-readable name
    data: pd.DataFrame  # Records found for this causística
    description: str = ""  # Detailed explanation
    severity: str = "warning"  # "info", "warning", "error", "critical"
    count: int = 0  # Number of records
    custom_metrics: dict = field(default_factory=dict)
    
    def __post_init__(self):
        """Calculate count after initialization."""
        if self.data is not None and not self.data.empty:
            self.count = len(self.data)
    
    def add_metric(self, key: str, value: Any, label: str = None, icon: str = None):
        """Add a custom metric to this causística."""
        self.custom_metrics[key] = {
            "value": value,
            "label": label or key,
            "icon": icon or "📊"
        }
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "code": self.code,
            "name": self.name,
            "description": self.description,
            "severity": self.severity,
            "count": self.count,
            "custom_metrics": self.custom_metrics
        }


@dataclass
class CausisticaDefinition:
    """
    Definition of a causística with its validation and processing logic.
    
    This allows scripts to define reusable validation functions that can be
    applied to different datasets.
    """
    code: str  # e.g., "A1", "C2"
    name: str  # Human-readable name
    description: str  # What this causística detects
    severity: str = "warning"  # Default severity
    validator: Optional[Callable] = None  # Function that validates records
    processor: Optional[Callable] = None  # Function that enriches/transforms data
    
    def validate(self, record: dict, context: dict = None) -> Optional[dict]:
        """
        Validate a single record against this causística.
        
        Args:
            record: Dictionary with record data
            context: Optional context (e.g., related records, lookup data)
            
        Returns:
            Dictionary with validation result if error detected, None otherwise.
            Result dict should include: 'error_detected', 'alerta', additional fields
        """
        if self.validator:
            return self.validator(record, context or {})
        return None
    
    def process_records(self, records: List[dict], context: dict = None) -> pd.DataFrame:
        """
        Process multiple records for this causística.
        
        Args:
            records: List of record dictionaries
            context: Optional context data
            
        Returns:
            DataFrame with processed records
        """
        if self.processor:
            return self.processor(records, context or {})
        return pd.DataFrame(records)


class CausisticaManager:
    """
    Manager for handling multiple causísticas within a script.
    
    This class provides a clean way to organize complex business logic
    across multiple related scenarios.
    """
    
    def __init__(self):
        """Initialize the causística manager."""
        self.definitions: Dict[str, CausisticaDefinition] = {}
        self.results: Dict[str, CausisticaResult] = {}
        self.shared_context: dict = {}
    
    def register(self, definition: CausisticaDefinition):
        """Register a causística definition."""
        self.definitions[definition.code] = definition
    
    def set_context(self, key: str, value: Any):
        """Set shared context data available to all causísticas."""
        self.shared_context[key] = value
    
    def get_context(self, key: str, default=None) -> Any:
        """Get shared context data."""
        return self.shared_context.get(key, default)
    
    def process_records(
        self,
        records: List[dict],
        causistica_codes: Optional[List[str]] = None,
        context: dict = None
    ) -> Dict[str, CausisticaResult]:
        """
        Process records through specified causísticas.
        
        Args:
            records: List of records to process
            causistica_codes: List of causística codes to check (None = all)
            context: Additional context for this processing batch
            
        Returns:
            Dictionary mapping causística code to result
        """
        merge_context = {**self.shared_context, **(context or {})}
        codes_to_check = causistica_codes or list(self.definitions.keys())
        
        # Group records by causística
        causistica_records: Dict[str, List[dict]] = {code: [] for code in codes_to_check}
        
        for record in records:
            for code in codes_to_check:
                definition = self.definitions.get(code)
                if definition:
                    validation_result = definition.validate(record, merge_context)
                    if validation_result and validation_result.get('error_detected'):
                        # Add causística info to record
                        enriched_record = {**record, **validation_result}
                        causistica_records[code].append(enriched_record)
        
        # Create results for each causística
        results = {}
        for code, records_list in causistica_records.items():
            if records_list:  # Only create result if there are records
                definition = self.definitions[code]
                df = definition.process_records(records_list, merge_context)
                
                result = CausisticaResult(
                    code=code,
                    name=definition.name,
                    description=definition.description,
                    severity=definition.severity,
                    data=df
                )
                results[code] = result
                self.results[code] = result
        
        return results
    
    def get_all_results(self) -> Dict[str, CausisticaResult]:
        """Get all causística results."""
        return self.results
    
    def get_result(self, code: str) -> Optional[CausisticaResult]:
        """Get result for a specific causística."""
        return self.results.get(code)
    
    def get_total_records(self) -> int:
        """Get total number of records across all causísticas."""
        return sum(result.count for result in self.results.values())
    
    def get_summary(self) -> pd.DataFrame:
        """Get summary DataFrame of all causísticas."""
        summary_data = []
        for code, result in self.results.items():
            summary_data.append({
                'Código': code,
                'Nombre': result.name,
                'Registros': result.count,
                'Severidad': result.severity,
                'Descripción': result.description
            })
        return pd.DataFrame(summary_data)
    
    def clear(self):
        """Clear all results (keep definitions)."""
        self.results.clear()
        self.shared_context.clear()


# Validation helper functions that can be used in causística validators

def validate_asset_status(
    expected_status: str,
    actual_status: str,
    context_message: str = ""
) -> Optional[dict]:
    """
    Helper to validate asset status.
    
    Args:
        expected_status: Expected status code
        actual_status: Actual status code from record
        context_message: Additional context for error message
        
    Returns:
        Validation result dict if error detected, None otherwise
    """
    if actual_status != expected_status:
        return {
            'error_detectado': True,
            'status_esperado': expected_status,
            'status_actual': actual_status,
            'alerta': f'{context_message} - Esperado: {expected_status}, Actual: {actual_status}'
        }
    return None


def validate_asset_exists(assets: List[dict], contract_id: str) -> Optional[dict]:
    """
    Helper to validate that a contract has assets.
    
    Args:
        assets: List of asset records
        contract_id: Contract ID being validated
        
    Returns:
        Validation result dict if no assets found
    """
    if not assets or len(assets) == 0:
        return {
            'error_detectado': True,
            'alerta': f'Contrato {contract_id} sin assets'
        }
    return None


def get_most_recent_asset(assets: List[dict], date_field: str = 'CreatedDate') -> Optional[dict]:
    """
    Get the most recent asset from a list.
    
    Args:
        assets: List of asset dictionaries
        date_field: Field name containing the date
        
    Returns:
        Most recent asset or None
    """
    if not assets:
        return None
    
    sorted_assets = sorted(
        assets,
        key=lambda x: x.get(date_field, '1900-01-01T00:00:00.000+0000'),
        reverse=True
    )
    return sorted_assets[0]


def get_most_recent_solicitud(solicitudes: List[dict], date_field: str = 'CreatedDate') -> Optional[dict]:
    """
    Get the most recent solicitud from a list.
    
    Args:
        solicitudes: List of solicitud dictionaries
        date_field: Field name containing the date
        
    Returns:
        Most recent solicitud or None
    """
    if not solicitudes:
        return None
    
    sorted_solicitudes = sorted(
        solicitudes,
        key=lambda x: x.get(date_field, '1900-01-01'),
        reverse=True
    )
    return sorted_solicitudes[0]
