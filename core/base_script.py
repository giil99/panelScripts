"""
Base class for all scripts.
Provides the contract that all scripts must implement.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional, Callable, Dict, List
from enum import Enum
import pandas as pd
from datetime import datetime


class ColumnType(Enum):
    """Types of columns for visualization."""
    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    DATETIME = "datetime"
    STATUS = "status"
    LINK = "link"
    BOOLEAN = "boolean"
    CURRENCY = "currency"


@dataclass
class ColumnConfig:
    """Configuration for a result column."""
    name: str
    display_name: str
    type: ColumnType = ColumnType.TEXT
    filterable: bool = True
    groupable: bool = True
    sortable: bool = True
    visible: bool = True
    format_func: Optional[Callable] = None
    status_map: Optional[dict] = None
    link_template: Optional[str] = None  # e.g., "https://instance.salesforce.com/{Id}/view"


@dataclass
class ScriptMetrics:
    """Metrics calculated from script execution."""
    total_records: int = 0
    processed_records: int = 0
    success_count: int = 0
    error_count: int = 0
    custom_metrics: dict = field(default_factory=dict)
    
    def add_metric(self, key: str, value: Any, label: str = None, icon: str = None):
        """Add a custom metric."""
        self.custom_metrics[key] = {
            "value": value,
            "label": label or key,
            "icon": icon or "📊"
        }


@dataclass
class ScriptResult:
    """Result of a script execution."""
    success: bool = True
    data: Optional[pd.DataFrame] = None
    metrics: Optional[ScriptMetrics] = None
    intermediate_data: dict = field(default_factory=dict)  # Data from each query step
    anomalies: Optional[pd.DataFrame] = None  # Records flagged as anomalies
    error_message: Optional[str] = None
    warnings: list = field(default_factory=list)
    execution_time: float = 0.0
    executed_at: datetime = field(default_factory=datetime.now)
    script_instance: Optional[Any] = None  # Reference to the script for UI access
    causisticas: dict = field(default_factory=dict)  # Dict[str, CausisticaResult] for multi-scenario scripts
    has_causisticas: bool = False  # Flag to indicate if script uses causística framework
    
    def to_dict(self) -> dict:
        """Convert result to dictionary for serialization."""
        result = {
            "success": self.success,
            "record_count": len(self.data) if self.data is not None else 0,
            "metrics": self.metrics.custom_metrics if self.metrics else {},
            "error_message": self.error_message,
            "warnings": self.warnings,
            "execution_time": self.execution_time,
            "executed_at": self.executed_at.isoformat(),
            "has_causisticas": self.has_causisticas
        }
        
        if self.has_causisticas:
            result["causisticas"] = {
                code: caus.to_dict() for code, caus in self.causisticas.items()
            }
        
        return result


class BaseScript(ABC):
    """
    Abstract base class for all data processing scripts.
    
    To create a new script:
    1. Inherit from BaseScript
    2. Define class attributes (name, description, category)
    3. Implement get_queries() and process()
    4. Optionally override get_column_config() and detect_anomalies()
    """
    
    # Class attributes - override in subclasses
    name: str = "Unnamed Script"
    description: str = "No description provided"
    category: str = "General"
    version: str = "1.0"
    author: str = "Unknown"
    
    # Execution options
    supports_preview: bool = True  # Can run in preview mode (limit results)
    supports_update: bool = False  # Can perform updates (write operations)
    requires_confirmation: bool = True  # Requires user confirmation before updates
    uses_causisticas: bool = False  # Set to True if script uses causística framework
    
    def __init__(self, sf_client=None):
        """
        Initialize the script with an optional Salesforce client.
        
        Args:
            sf_client: SalesforceClient instance for API calls
        """
        self.sf_client = sf_client
        self._intermediate_data = {}
        self._warnings = []
        self._causistica_manager = None
        
        # Initialize causística manager if script uses it
        if self.uses_causisticas:
            from core.causistica import CausisticaManager
            self._causistica_manager = CausisticaManager()
    
    @abstractmethod
    def get_queries(self, preview: bool = False) -> list[str]:
        """
        Return the SOQL queries needed for this script.
        
        Args:
            preview: If True, limit results for preview mode
            
        Returns:
            List of SOQL query strings
        """
        pass
    
    @abstractmethod
    def process(self, query_results: dict[str, pd.DataFrame]) -> ScriptResult:
        """
        Process the query results and return the final result.
        
        Args:
            query_results: Dictionary mapping query index to DataFrame
            
        Returns:
            ScriptResult with processed data and metrics
        """
        pass
    
    def get_column_config(self) -> list[ColumnConfig]:
        """
        Return column configuration for the result table.
        Override to customize column display.
        
        Returns:
            List of ColumnConfig objects
        """
        return []  # Default: auto-detect from DataFrame
    
    def detect_anomalies(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Detect anomalies in the processed data.
        Override to implement custom anomaly detection.
        
        Args:
            data: Processed DataFrame
            
        Returns:
            DataFrame containing only anomalous records
        """
        return pd.DataFrame()  # Default: no anomalies
    
    def get_groupby_options(self) -> list[str]:
        """
        Return default columns available for grouping.
        Override to customize.
        
        Returns:
            List of column names
        """
        return []
    
    def get_filter_options(self) -> dict[str, list]:
        """
        Return filter options for specific columns.
        Override to provide predefined filter values.
        
        Returns:
            Dictionary mapping column names to list of values
        """
        return {}
    
    def get_update_operations(self) -> list[dict]:
        """
        Return available update operations (if supports_update=True).
        Override to define what updates the script can perform.
        
        Returns:
            List of operation definitions with 'name', 'description', 'fields'
        """
        return []
    
    def execute_update(self, operation: str, data: pd.DataFrame) -> tuple[list, list]:
        """
        Execute an update operation.
        Override to implement update logic.
        
        Args:
            operation: Name of the operation to execute
            data: DataFrame with records to update
            
        Returns:
            Tuple of (success_records, failed_records)
        """
        raise NotImplementedError("Update operations not implemented")
    
    def add_warning(self, message: str):
        """Add a warning message to the execution result."""
        self._warnings.append(message)
    
    def store_intermediate(self, key: str, data: pd.DataFrame):
        """Store intermediate data for debugging/analysis."""
        self._intermediate_data[key] = data
    
    def get_chart_recommendations(self) -> list[dict]:
        """
        Return recommended chart configurations.
        Override to suggest visualizations.
        
        Returns:
            List of chart configuration dictionaries
        """
        return [
            {"type": "bar", "x": None, "y": "count", "title": "Distribución"},
            {"type": "pie", "values": "count", "names": None, "title": "Proporción"}
        ]
    
    def validate_prerequisites(self) -> tuple[bool, str]:
        """
        Validate that prerequisites are met before execution.
        Override for custom validation.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if self.sf_client is None:
            return False, "Salesforce client not configured"
        return True, ""
    
    # Causística framework support methods
    
    def setup_causisticas(self):
        """
        Setup causísticas for this script.
        Override this to register causística definitions.
        
        Example:
            from core.causistica import CausisticaDefinition
            
            self._causistica_manager.register(CausisticaDefinition(
                code="A1",
                name="SC En Corso con Asset Incorrecto",
                description="...",
                validator=self._validate_a1,
                processor=self._process_a1
            ))
        """
        pass
    
    def get_causistica_manager(self):
        """Get the causística manager instance."""
        return self._causistica_manager
    
    def has_causisticas(self) -> bool:
        """Check if this script uses the causística framework."""
        return self.uses_causisticas and self._causistica_manager is not None
    
    def get_causistica_results(self) -> dict:
        """Get all causística results from the manager."""
        if self._causistica_manager:
            return self._causistica_manager.get_all_results()
        return {}
    
    def __repr__(self):
        return f"<{self.__class__.__name__}: {self.name}>"
