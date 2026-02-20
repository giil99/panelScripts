"""
Script: Contratos con Fechas Inconsistentes

Detecta contratos que tienen fechas de inicio/fin inconsistentes,
como fecha fin anterior a fecha inicio, o fechas faltantes.
"""
import pandas as pd
from core.base_script import BaseScript, ScriptResult, ScriptMetrics, ColumnConfig, ColumnType
from core.script_registry import register_script
from config import CONTRACT_STATUS_MAP


@register_script
class ContratosConFechasInconsistentes(BaseScript):
    """
    Detecta contratos con fechas inconsistentes.
    """
    
    name = "Contratos - Fechas Inconsistentes"
    description = "Detecta contratos con fechas de inicio/fin inconsistentes"
    category = "Detección de inconsistencias"
    version = "1.0"
    author = "AG"
    
    supports_preview = True
    supports_update = False
    requires_confirmation = False
    
    def get_queries(self, preview: bool = False) -> list[str]:
        """Return query for contracts."""
        limit_clause = "LIMIT 2000" if preview else ""
        
        query = f"""
            SELECT Id, ContractNumber, Status, StartDate, EndDate,
                   NewCo_ServiceAccount__c, NewCo_ServiceAccount__r.Name,
                   CreatedDate, LastModifiedDate
            FROM Contract
            WHERE Status IN ('01', '02', '03')
            {limit_clause}
        """
        
        return [query]
    
    def process(self, query_results: dict[str, pd.DataFrame]) -> ScriptResult:
        """Process contracts to find date inconsistencies."""
        df = query_results.get('query_0', pd.DataFrame())
        
        if df.empty:
            return ScriptResult(
                success=True,
                data=pd.DataFrame(),
                metrics=ScriptMetrics(total_records=0)
            )
        
        self.store_intermediate('contracts_raw', df)
        
        # Convert dates
        df['StartDate'] = pd.to_datetime(df['StartDate'], errors='coerce')
        df['EndDate'] = pd.to_datetime(df['EndDate'], errors='coerce')
        
        # Detect inconsistencies
        inconsistencies = []
        
        for _, row in df.iterrows():
            issues = []
            
            # Check for missing start date
            if pd.isna(row['StartDate']):
                issues.append('Sin fecha inicio')
            
            # Check for end date before start date
            if pd.notna(row['StartDate']) and pd.notna(row['EndDate']):
                if row['EndDate'] < row['StartDate']:
                    issues.append('Fecha fin < Fecha inicio')
            
            # Check for active contract with end date in past
            if row['Status'] == '02' and pd.notna(row['EndDate']):
                if row['EndDate'] < pd.Timestamp.now():
                    issues.append('Contrato activo con fecha fin pasada')
            
            if issues:
                inconsistencies.append({
                    'ContractId': row['Id'],
                    'ContractNumber': row['ContractNumber'],
                    'Status': row['Status'],
                    'StartDate': row['StartDate'],
                    'EndDate': row['EndDate'],
                    'ServiceAccount': row.get('NewCo_ServiceAccount__r.Name', ''),
                    'Issues': '; '.join(issues),
                    'IssueCount': len(issues)
                })
        
        df_result = pd.DataFrame(inconsistencies)
        
        if not df_result.empty:
            df_result['StatusLabel'] = df_result['Status'].map(CONTRACT_STATUS_MAP)
        
        # Calculate metrics
        metrics = ScriptMetrics(total_records=len(df_result))
        
        metrics.add_metric(
            'contracts_with_issues',
            len(df_result),
            'Contratos con Problemas',
            '🔴' if len(df_result) > 0 else '✅'
        )
        
        # Count by issue type
        if not df_result.empty:
            all_issues = '; '.join(df_result['Issues'].tolist()).split('; ')
            issue_counts = pd.Series(all_issues).value_counts()
            for issue, count in issue_counts.items():
                if issue:
                    metrics.add_metric(
                        f'issue_{issue[:20]}',
                        count,
                        issue[:30],
                        '⚠️'
                    )
        
        return ScriptResult(
            success=True,
            data=df_result,
            metrics=metrics
        )
    
    def get_column_config(self) -> list[ColumnConfig]:
        """Define column configuration."""
        return [
            ColumnConfig('ContractNumber', 'Nº Contrato', ColumnType.TEXT),
            ColumnConfig('StatusLabel', 'Estado', ColumnType.STATUS),
            ColumnConfig('StartDate', 'Fecha Inicio', ColumnType.DATE),
            ColumnConfig('EndDate', 'Fecha Fin', ColumnType.DATE),
            ColumnConfig('Issues', 'Problemas', ColumnType.TEXT),
            ColumnConfig('IssueCount', 'Nº Problemas', ColumnType.NUMBER),
        ]
    
    def get_groupby_options(self) -> list[str]:
        """Return columns for grouping."""
        return ['StatusLabel', 'Issues', 'IssueCount']
    
    def detect_anomalies(self, data: pd.DataFrame) -> pd.DataFrame:
        """All contracts with date issues are anomalies."""
        if data.empty:
            return pd.DataFrame()
        
        anomalies = data.copy()
        anomalies['anomaly_type'] = 'Fechas Inconsistentes'
        anomalies['anomaly_severity'] = 'Media'
        
        return anomalies
    
    def get_chart_recommendations(self) -> list[dict]:
        """Recommend charts."""
        return [
            {
                'type': 'pie',
                'names': 'StatusLabel',
                'title': 'Distribución por Estado'
            },
            {
                'type': 'bar',
                'x': 'IssueCount',
                'title': 'Contratos por Nº de Problemas'
            }
        ]
