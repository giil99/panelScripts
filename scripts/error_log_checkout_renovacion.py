"""
Script: Error Log Checkout Renovación

Detecta y analiza error logs del proceso de checkout de renovación,
identificando assets huérfanos que necesitan ser reparados.
"""
import pandas as pd
from datetime import datetime, timedelta
from core.base_script import BaseScript, ScriptResult, ScriptMetrics, ColumnConfig, ColumnType
from core.script_registry import register_script
from config import ASSET_STATUS_MAP


@register_script
class ErrorLogCheckoutRenovacion(BaseScript):
    """
    Analiza error logs del checkout de renovación.
    """
    
    name = "Error Log Checkout Renovación"
    description = "Analiza errores del proceso de renovación y detecta assets a reparar"
    category = "Regularización"
    version = "1.0"
    author = "AG"
    
    supports_preview = True
    supports_update = True
    requires_confirmation = True
    
    # Error process name
    ERROR_PROCESS = 'NewCo_CheckoutRenovacionQueable.execute'
    
    def get_queries(self, preview: bool = False) -> list[str]:
        """Return queries for error logs and related data."""
        limit_clause = "LIMIT 500" if preview else ""
        
        # Query 1: Error logs de la última semana
        query_errors = f"""
            SELECT Id, CreatedDate, Process__c, DescriptionErrorLog__c, 
                   AdditionalInformation__c, RecordId__c 
            FROM ErrorLogRecording__c 
            WHERE CreatedDate >= LAST_WEEK
            AND Process__c = '{self.ERROR_PROCESS}'
            {limit_clause}
        """
        
        return [query_errors]
    
    def process(self, query_results: dict[str, pd.DataFrame]) -> ScriptResult:
        """Process error logs to identify affected orders and assets."""
        df_errors = query_results.get('query_0', pd.DataFrame())
        
        if df_errors.empty:
            return ScriptResult(
                success=True,
                data=pd.DataFrame(),
                metrics=ScriptMetrics(total_records=0)
            )
        
        self.store_intermediate('error_logs_raw', df_errors)
        
        # Extract unique Order IDs from error logs
        order_ids = df_errors['RecordId__c'].dropna().unique().tolist()
        
        # Group errors by Order
        errors_by_order = df_errors.groupby('RecordId__c').agg({
            'Id': 'count',
            'CreatedDate': 'max',
            'DescriptionErrorLog__c': 'first'
        }).reset_index()
        
        errors_by_order.columns = [
            'OrderId', 'ErrorCount', 'LastErrorDate', 'ErrorDescription'
        ]
        
        # Calculate metrics
        metrics = ScriptMetrics(total_records=len(errors_by_order))
        
        metrics.add_metric(
            'total_errors',
            len(df_errors),
            'Total Errores',
            '🔴' if len(df_errors) > 0 else '✅'
        )
        
        metrics.add_metric(
            'orders_affected',
            len(order_ids),
            'Orders Afectadas',
            '📦'
        )
        
        # Count by error description
        if not df_errors.empty and 'DescriptionErrorLog__c' in df_errors.columns:
            desc_counts = df_errors['DescriptionErrorLog__c'].value_counts()
            for desc, count in desc_counts.head(3).items():
                if desc:
                    short_desc = str(desc)[:30] + '...' if len(str(desc)) > 30 else str(desc)
                    metrics.add_metric(
                        f'error_{hash(desc) % 1000}',
                        count,
                        short_desc,
                        '⚠️'
                    )
        
        # Add warning about needing additional queries
        self.add_warning(
            "Para reparación completa, se necesitan consultas adicionales de OrderItems y Assets. "
            "Ejecutar el notebook original para proceso completo de reparación."
        )
        
        return ScriptResult(
            success=True,
            data=errors_by_order,
            metrics=metrics
        )
    
    def get_column_config(self) -> list[ColumnConfig]:
        """Define column configuration."""
        return [
            ColumnConfig('OrderId', 'ID Order', ColumnType.LINK),
            ColumnConfig('ErrorCount', 'Nº Errores', ColumnType.NUMBER),
            ColumnConfig('LastErrorDate', 'Último Error', ColumnType.DATETIME),
            ColumnConfig('ErrorDescription', 'Descripción', ColumnType.TEXT),
        ]
    
    def get_groupby_options(self) -> list[str]:
        """Return columns for grouping."""
        return ['ErrorCount', 'ErrorDescription']
    
    def detect_anomalies(self, data: pd.DataFrame) -> pd.DataFrame:
        """Orders with errors are anomalies."""
        if data.empty:
            return pd.DataFrame()
        
        anomalies = data.copy()
        anomalies['anomaly_type'] = 'Error Checkout Renovación'
        anomalies['anomaly_severity'] = 'Alta'
        
        return anomalies
    
    def get_chart_recommendations(self) -> list[dict]:
        """Recommend charts."""
        return [
            {
                'type': 'bar',
                'x': 'ErrorCount', 
                'title': 'Por Nº de Errores'
            }
        ]
    
    def get_update_operations(self) -> list[dict]:
        """Define update operations."""
        return [
            {
                'name': 'repair_orphan_assets',
                'description': 'Reparar assets huérfanos asociándolos al contrato',
                'fields': {
                    'acn_fld_Contract__c': '(ID contrato)',
                    'Status': '03',
                    'acn_fld_StartDateVersion__c': '(fecha de la order)'
                }
            }
        ]
