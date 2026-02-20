"""
Script: Billing Accounts sin Método de Pago

Detecta Billing Accounts que no tienen un método de pago asociado.
Esto puede causar problemas en la facturación y cobranza.
"""
import pandas as pd
from core.base_script import BaseScript, ScriptResult, ScriptMetrics, ColumnConfig, ColumnType
from core.script_registry import register_script


@register_script
class BillingAccountsWithoutPaymentMethod(BaseScript):
    """
    Detecta Billing Accounts sin método de pago.
    """
    
    name = "Billing Accounts sin Método Pago"
    description = "Detecta cuentas de facturación sin método de pago asociado"
    category = "Detección de inconsistencias"
    version = "1.0"
    author = "AG"
    
    supports_preview = True
    supports_update = False
    requires_confirmation = False
    
    def get_queries(self, preview: bool = False) -> list[str]:
        """Return query for billing accounts without payment method."""
        limit_clause = "LIMIT 1000" if preview else ""
        
        query = f"""
            SELECT Id, Name, vlocity_cmt__PaymentMethodId__c, 
                   vlocity_cmt__Status__c, CreatedDate, LastModifiedDate,
                   vlocity_cmt__AccountId__c, vlocity_cmt__AccountId__r.Name
            FROM vlocity_cmt__BillingAccount__c
            WHERE vlocity_cmt__PaymentMethodId__c = null
            AND vlocity_cmt__Status__c = 'Active'
            {limit_clause}
        """
        
        return [query]
    
    def process(self, query_results: dict[str, pd.DataFrame]) -> ScriptResult:
        """Process billing accounts without payment method."""
        df = query_results.get('query_0', pd.DataFrame())
        
        if df.empty:
            return ScriptResult(
                success=True,
                data=pd.DataFrame(),
                metrics=ScriptMetrics(total_records=0)
            )
        
        # Calculate metrics
        metrics = ScriptMetrics(total_records=len(df))
        
        metrics.add_metric(
            'accounts_without_payment',
            len(df),
            'Sin Método de Pago',
            '🔴' if len(df) > 0 else '✅'
        )
        
        # Count by status
        if 'vlocity_cmt__Status__c' in df.columns:
            status_counts = df['vlocity_cmt__Status__c'].value_counts()
            for status, count in status_counts.items():
                metrics.add_metric(
                    f'status_{status}',
                    count,
                    f'Estado: {status}',
                    '📊'
                )
        
        return ScriptResult(
            success=True,
            data=df,
            metrics=metrics
        )
    
    def get_column_config(self) -> list[ColumnConfig]:
        """Define column configuration."""
        return [
            ColumnConfig('Name', 'Nombre', ColumnType.TEXT),
            ColumnConfig('vlocity_cmt__AccountId__r.Name', 'Cuenta', ColumnType.TEXT),
            ColumnConfig('vlocity_cmt__Status__c', 'Estado', ColumnType.STATUS),
            ColumnConfig('CreatedDate', 'Creado', ColumnType.DATETIME),
            ColumnConfig('LastModifiedDate', 'Modificado', ColumnType.DATETIME),
        ]
    
    def get_groupby_options(self) -> list[str]:
        """Return columns for grouping."""
        return ['vlocity_cmt__Status__c']
    
    def detect_anomalies(self, data: pd.DataFrame) -> pd.DataFrame:
        """All active billing accounts without payment are anomalies."""
        if data.empty:
            return pd.DataFrame()
        
        anomalies = data.copy()
        anomalies['anomaly_type'] = 'Billing Account sin Método de Pago'
        anomalies['anomaly_severity'] = 'Alta'
        
        return anomalies
    
    def get_chart_recommendations(self) -> list[dict]:
        """Recommend charts."""
        return [
            {
                'type': 'bar',
                'x': 'vlocity_cmt__Status__c',
                'title': 'Distribución por Estado'
            }
        ]
