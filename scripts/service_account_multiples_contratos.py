"""
Script: Service Account con Múltiples Contratos

Detecta Service Accounts que tienen múltiples contratos activos,
lo cual puede indicar duplicados o errores de gestión.
"""
import pandas as pd
from core.base_script import BaseScript, ScriptResult, ScriptMetrics, ColumnConfig, ColumnType
from core.script_registry import register_script
from config import CONTRACT_STATUS_MAP


@register_script
class ServiceAccountMultiplesContratos(BaseScript):
    """
    Detecta Service Accounts con múltiples contratos activos.
    """
    
    name = "Service Account - Múltiples Contratos"
    description = "Detecta cuentas de servicio con varios contratos activos"
    category = "Detección de inconsistencias"
    version = "2.0"
    author = "AG"
    
    supports_preview = True
    supports_update = False
    requires_confirmation = False
    
    def get_queries(self, preview: bool = False) -> list[str]:
        """Return query for active contracts."""
        limit_clause = "LIMIT 5000" if preview else ""
        
        query = f"""
            SELECT Id, ContractNumber, Status, NewCo_ServiceAccount__c,
                   NewCo_ServiceAccount__r.Name, StartDate, EndDate, CreatedDate
            FROM Contract
            WHERE Status = '02'
            AND NewCo_ServiceAccount__c != null
            {limit_clause}
        """
        
        return [query]
    
    def process(self, query_results: dict[str, pd.DataFrame]) -> ScriptResult:
        """Process contracts to find service accounts with multiple."""
        df = query_results.get('query_0', pd.DataFrame())
        
        if df.empty:
            return ScriptResult(
                success=True,
                data=pd.DataFrame(),
                metrics=ScriptMetrics(total_records=0)
            )
        
        self.store_intermediate('contracts_raw', df)
        
        # Group by service account
        grouped = df.groupby('NewCo_ServiceAccount__c').agg({
            'Id': 'count',
            'ContractNumber': lambda x: '; '.join(x.astype(str)),
            'NewCo_ServiceAccount__r.Name': 'first',
            'StartDate': 'min',
            'CreatedDate': 'min'
        }).reset_index()
        
        grouped.columns = [
            'ServiceAccountId', 'ContractCount', 'ContractNumbers',
            'ServiceAccountName', 'OldestStartDate', 'OldestCreatedDate'
        ]
        
        # Filter only those with more than one
        multiple = grouped[grouped['ContractCount'] > 1].copy()
        
        # Sort by contract count descending
        multiple = multiple.sort_values('ContractCount', ascending=False)
        
        # Calculate metrics
        metrics = ScriptMetrics(total_records=len(multiple))
        
        metrics.add_metric(
            'accounts_with_multiple',
            len(multiple),
            'Cuentas con Múltiples',
            '⚠️' if len(multiple) > 0 else '✅'
        )
        
        # Count by number of contracts
        if not multiple.empty:
            count_distribution = multiple['ContractCount'].value_counts().sort_index()
            for count, num_accounts in count_distribution.items():
                if count <= 5:
                    metrics.add_metric(
                        f'with_{count}_contracts',
                        num_accounts,
                        f'Con {count} contratos',
                        '📊'
                    )
            
            # More than 5
            more_than_5 = len(multiple[multiple['ContractCount'] > 5])
            if more_than_5 > 0:
                metrics.add_metric(
                    'with_more_than_5',
                    more_than_5,
                    'Con más de 5 contratos',
                    '🔴'
                )
        
        return ScriptResult(
            success=True,
            data=multiple,
            metrics=metrics
        )
    
    def get_column_config(self) -> list[ColumnConfig]:
        """Define column configuration."""
        return [
            ColumnConfig('ServiceAccountName', 'Service Account', ColumnType.TEXT),
            ColumnConfig('ContractCount', 'Nº Contratos', ColumnType.NUMBER),
            ColumnConfig('ContractNumbers', 'Números de Contrato', ColumnType.TEXT),
            ColumnConfig('OldestStartDate', 'Inicio Más Antiguo', ColumnType.DATE),
            ColumnConfig('OldestCreatedDate', 'Creado Más Antiguo', ColumnType.DATETIME),
        ]
    
    def get_groupby_options(self) -> list[str]:
        """Return columns for grouping."""
        return ['ContractCount']
    
    def detect_anomalies(self, data: pd.DataFrame) -> pd.DataFrame:
        """Accounts with many contracts are anomalies."""
        if data.empty:
            return pd.DataFrame()
        
        # Only flag those with more than 3 contracts as anomalies
        anomalies = data[data['ContractCount'] > 3].copy()
        
        if anomalies.empty:
            return pd.DataFrame()
        
        anomalies['anomaly_type'] = 'Muchos Contratos en Service Account'
        anomalies['anomaly_severity'] = 'Media'
        
        return anomalies
    
    def get_chart_recommendations(self) -> list[dict]:
        """Recommend charts."""
        return [
            {
                'type': 'bar',
                'x': 'ContractCount',
                'title': 'Distribución por Nº de Contratos'
            }
        ]
