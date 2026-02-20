"""
Script: Fixes Generales

Script multipropósito para detección y corrección de
diversos problemas de datos comunes en la org.
"""
import pandas as pd
from core.base_script import BaseScript, ScriptResult, ScriptMetrics, ColumnConfig, ColumnType
from core.script_registry import register_script
from config import ASSET_STATUS_MAP, CONTRACT_STATUS_MAP


@register_script
class FixesGenerales(BaseScript):
    """
    Detección y corrección de problemas de datos generales.
    """
    
    name = "Fixes Generales - Datos Inconsistentes"
    description = "Detecta diversos problemas de datos comunes para corrección"
    category = "Regularización"
    version = "1.0"
    author = "AG"
    
    supports_preview = True
    supports_update = True
    requires_confirmation = True
    
    def get_queries(self, preview: bool = False) -> list[str]:
        """Return queries for common data issues."""
        limit_clause = "LIMIT 2000" if preview else ""
        
        # Query 1: Assets with null mandatory fields
        query_assets_null = f"""
            SELECT Id, Name, Status, acn_fld_Contract__c,
                   vlocity_cmt__ProvisioningStatus__c,
                   vlocity_cmt__Action__c,
                   acn_fld_StartDateVersion__c,
                   LastModifiedDate
            FROM Asset
            WHERE vlocity_cmt__ParentItemId__c = null
            AND Status = '03'
            AND (vlocity_cmt__ProvisioningStatus__c = null 
                 OR acn_fld_StartDateVersion__c = null)
            {limit_clause}
        """
        
        # Query 2: Contracts with missing required relationships
        query_contracts_null = f"""
            SELECT Id, ContractNumber, Status,
                   NewCo_ServiceAccount__c,
                   AccountId,
                   vlocity_cmt__QuoteId__c,
                   StartDate, EndDate
            FROM Contract
            WHERE Status = '02'
            AND (NewCo_ServiceAccount__c = null OR AccountId = null)
            {limit_clause}
        """
        
        return [query_assets_null, query_contracts_null]
    
    def process(self, query_results: dict[str, pd.DataFrame]) -> ScriptResult:
        """Process results combining all data quality issues."""
        df_assets = query_results.get('query_0', pd.DataFrame())
        df_contracts = query_results.get('query_1', pd.DataFrame())
        
        results = []
        
        # Process asset issues
        if not df_assets.empty:
            for _, row in df_assets.iterrows():
                issue = 'Sin ProvisioningStatus' if pd.isna(row.get('vlocity_cmt__ProvisioningStatus__c')) else 'Sin StartDate'
                results.append({
                    'RecordId': row['Id'],
                    'RecordType': 'Asset',
                    'RecordName': row.get('Name', ''),
                    'Issue': issue,
                    'Status': ASSET_STATUS_MAP.get(row.get('Status', ''), row.get('Status', '')),
                    'LastModified': row.get('LastModifiedDate', '')
                })
        
        # Process contract issues
        if not df_contracts.empty:
            for _, row in df_contracts.iterrows():
                issues = []
                if pd.isna(row.get('NewCo_ServiceAccount__c')):
                    issues.append('Sin ServiceAccount')
                if pd.isna(row.get('AccountId')):
                    issues.append('Sin Account')
                
                results.append({
                    'RecordId': row['Id'],
                    'RecordType': 'Contract',
                    'RecordName': row.get('ContractNumber', ''),
                    'Issue': ', '.join(issues),
                    'Status': CONTRACT_STATUS_MAP.get(row.get('Status', ''), row.get('Status', '')),
                    'LastModified': ''
                })
        
        df_result = pd.DataFrame(results)
        
        # Calculate metrics
        total = len(df_result)
        metrics = ScriptMetrics(total_records=total)
        
        metrics.add_metric(
            'total_issues',
            total,
            'Problemas Totales',
            '⚠️' if total > 0 else '✅'
        )
        
        asset_issues = len(df_assets) if not df_assets.empty else 0
        contract_issues = len(df_contracts) if not df_contracts.empty else 0
        
        metrics.add_metric(
            'asset_issues',
            asset_issues,
            'Assets',
            '📦'
        )
        
        metrics.add_metric(
            'contract_issues',
            contract_issues,
            'Contratos',
            '📋'
        )
        
        return ScriptResult(
            success=True,
            data=df_result,
            metrics=metrics
        )
    
    def get_column_config(self) -> list[ColumnConfig]:
        """Define column configuration."""
        return [
            ColumnConfig('RecordId', 'ID', ColumnType.LINK),
            ColumnConfig('RecordType', 'Tipo', ColumnType.TEXT),
            ColumnConfig('RecordName', 'Nombre', ColumnType.TEXT),
            ColumnConfig('Issue', 'Problema', ColumnType.TEXT),
            ColumnConfig('Status', 'Estado', ColumnType.STATUS),
        ]
    
    def get_groupby_options(self) -> list[str]:
        """Return columns for grouping."""
        return ['RecordType', 'Issue', 'Status']
    
    def detect_anomalies(self, data: pd.DataFrame) -> pd.DataFrame:
        """All records are anomalies."""
        if data.empty:
            return pd.DataFrame()
        
        anomalies = data.copy()
        anomalies['anomaly_type'] = data['Issue']
        anomalies['anomaly_severity'] = 'Media'
        
        return anomalies
    
    def get_chart_recommendations(self) -> list[dict]:
        """Recommend charts."""
        return [
            {
                'type': 'pie',
                'names': 'RecordType',
                'title': 'Por Tipo de Registro'
            },
            {
                'type': 'bar',
                'x': 'Issue',
                'title': 'Por Tipo de Problema'
            }
        ]
    
    def get_update_operations(self) -> list[dict]:
        """Define update operations."""
        return [
            {
                'name': 'fix_provisioning_status',
                'description': 'Establecer ProvisioningStatus a Active para assets activos',
                'fields': {
                    'vlocity_cmt__ProvisioningStatus__c': 'Active'
                }
            }
        ]
