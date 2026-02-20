"""
Script: Assets - Fecha Incorrecta

Detecta assets con fechas de vigencia inconsistentes o incorrectas.
Por ejemplo:
- Fecha inicio vacía
- Fecha fin anterior a fecha inicio
- Fecha inicio en el futuro para assets activos
"""
import pandas as pd
from datetime import datetime
from core.base_script import BaseScript, ScriptResult, ScriptMetrics, ColumnConfig, ColumnType
from core.script_registry import register_script
from config import ASSET_STATUS_MAP


@register_script
class AssetsFechaIncorrecta(BaseScript):
    """
    Detecta assets con fechas de vigencia incorrectas.
    """
    
    name = "Assets - Fechas Incorrectas"
    description = "Detecta assets con fechas de vigencia inconsistentes"
    category = "Detección de inconsistencias"
    version = "1.0"
    author = "AG"
    
    supports_preview = True
    supports_update = True
    requires_confirmation = True
    
    def get_queries(self, preview: bool = False) -> list[str]:
        """Return query for assets with date info."""
        limit_clause = "LIMIT 5000" if preview else ""
        
        query = f"""
            SELECT Id, Name, Status, acn_fld_Contract__c,
                   acn_fld_Contract__r.ContractNumber,
                   acn_fld_StartDateVersion__c, acn_fld_EndDateVersion__c,
                   NewCo_Fecha_inicio_vigencia__c,
                   CreatedDate, LastModifiedDate
            FROM Asset
            WHERE vlocity_cmt__ParentItemId__c = null
            AND acn_fld_Contract__c != null
            {limit_clause}
        """
        
        return [query]
    
    def process(self, query_results: dict[str, pd.DataFrame]) -> ScriptResult:
        """Process assets to find date issues."""
        df = query_results.get('query_0', pd.DataFrame())
        
        if df.empty:
            return ScriptResult(
                success=True,
                data=pd.DataFrame(),
                metrics=ScriptMetrics(total_records=0)
            )
        
        self.store_intermediate('assets_raw', df)
        
        # Convert dates
        df['acn_fld_StartDateVersion__c'] = pd.to_datetime(
            df['acn_fld_StartDateVersion__c'], errors='coerce'
        )
        df['acn_fld_EndDateVersion__c'] = pd.to_datetime(
            df['acn_fld_EndDateVersion__c'], errors='coerce'
        )
        
        today = pd.Timestamp.now().normalize()
        
        # Find issues
        issues_list = []
        
        for _, row in df.iterrows():
            status = str(row.get('Status', '')).strip()
            start_date = row.get('acn_fld_StartDateVersion__c')
            end_date = row.get('acn_fld_EndDateVersion__c')
            
            issues = []
            
            # Check for missing start date on active assets
            if status == '03' and pd.isna(start_date):
                issues.append('Activo sin fecha inicio')
            
            # Check for end date before start date
            if pd.notna(start_date) and pd.notna(end_date):
                if end_date < start_date:
                    issues.append('Fecha fin < fecha inicio')
            
            # Check for start date in future on active assets
            if status == '03' and pd.notna(start_date):
                if start_date > today:
                    issues.append('Activo con fecha inicio futura')
            
            # Check for active without end date that should have it
            if status in ['05', '14', '28'] and pd.isna(end_date):
                issues.append('Baja/Modificado sin fecha fin')
            
            if issues:
                issues_list.append({
                    'AssetId': row['Id'],
                    'AssetName': row['Name'],
                    'ContractId': row['acn_fld_Contract__c'],
                    'ContractNumber': row.get('acn_fld_Contract__r.ContractNumber', ''),
                    'Status': status,
                    'StatusLabel': ASSET_STATUS_MAP.get(status, status),
                    'StartDate': start_date,
                    'EndDate': end_date,
                    'Issues': '; '.join(issues),
                    'IssueCount': len(issues)
                })
        
        df_result = pd.DataFrame(issues_list)
        
        # Calculate metrics
        metrics = ScriptMetrics(total_records=len(df_result))
        
        metrics.add_metric(
            'assets_with_issues',
            len(df_result),
            'Assets con Problemas',
            '🔴' if len(df_result) > 0 else '✅'
        )
        
        metrics.add_metric(
            'assets_checked',
            len(df),
            'Assets Verificados',
            '📊'
        )
        
        # Count by issue type
        if not df_result.empty:
            all_issues = '; '.join(df_result['Issues'].tolist()).split('; ')
            issue_counts = pd.Series(all_issues).value_counts()
            for issue, count in issue_counts.items():
                if issue:
                    metrics.add_metric(
                        f'issue_{issue[:15]}',
                        count,
                        issue[:20],
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
            ColumnConfig('AssetName', 'Asset', ColumnType.TEXT),
            ColumnConfig('ContractNumber', 'Contrato', ColumnType.TEXT),
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
        """All assets with date issues are anomalies."""
        if data.empty:
            return pd.DataFrame()
        
        anomalies = data.copy()
        anomalies['anomaly_type'] = 'Fechas Incorrectas'
        anomalies['anomaly_severity'] = 'Media'
        
        return anomalies
    
    def get_chart_recommendations(self) -> list[dict]:
        """Recommend charts."""
        return [
            {
                'type': 'pie',
                'names': 'StatusLabel',
                'title': 'Por Estado'
            },
            {
                'type': 'bar',
                'x': 'IssueCount',
                'title': 'Por Nº de Problemas'
            }
        ]
