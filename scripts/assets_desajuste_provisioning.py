"""
Script: Assets - Desajuste Provisioning y Action

Detecta assets con desajuste entre ProvisioningStatus y Action:
1. ProvisioningStatus='Retired' + Action='Add' → Debería ser 'Disconnect'
2. Action != 'Add' + ProvisioningStatus='Active' → Inconsistente

Estos desajustes causan errores en Omega.
"""
import pandas as pd
from core.base_script import BaseScript, ScriptResult, ScriptMetrics, ColumnConfig, ColumnType
from core.script_registry import register_script
from config import ASSET_STATUS_MAP


@register_script
class AssetsDesajusteProvisioningAction(BaseScript):
    """
    Detecta assets con desajuste específico entre ProvisioningStatus y Action.
    """
    
    name = "Assets - Desajuste Provisioning"
    description = "Provisioning='Retired'+Action='Add' o Action!='Add'+Prov='Active'"
    category = "Regularización"
    version = "2.0"
    author = "AG"
    
    supports_preview = True
    supports_update = True
    requires_confirmation = True
    
    def get_queries(self, preview: bool = False) -> list[str]:
        """Return query for assets with specific provisioning/action mismatches."""
        limit_clause = "LIMIT 5000" if preview else ""
        
        query = f"""
            SELECT Id, Name, Product2.ProductCode, vlocity_cmt__ParentItemId__c,
                   acn_fld_Contract__r.Status, Status, NewCo_OriginContractType__c,
                   vlocity_cmt__ProvisioningStatus__c, vlocity_cmt__Action__c, CreatedDate
            FROM Asset
            WHERE (vlocity_cmt__ProvisioningStatus__c = 'Retired' AND vlocity_cmt__Action__c = 'Add')
               OR (vlocity_cmt__Action__c != 'Add' AND vlocity_cmt__ProvisioningStatus__c = 'Active')
            {limit_clause}
        """
        
        return [query]
    
    def process(self, query_results: dict[str, pd.DataFrame]) -> ScriptResult:
        """Process assets with provisioning/action mismatches."""
        df = query_results.get('query_0', pd.DataFrame())
        
        if df.empty:
            return ScriptResult(
                success=True,
                data=pd.DataFrame(),
                metrics=ScriptMetrics(total_records=0)
            )
        
        self.store_intermediate('assets_raw', df)
        
        # Add categorization
        def categorize_issue(row):
            prov = str(row.get('vlocity_cmt__ProvisioningStatus__c', '')).strip()
            action = str(row.get('vlocity_cmt__Action__c', '')).strip()
            
            if prov == 'Retired' and action == 'Add':
                return 'Retired+Add (Debería ser Disconnect)'
            elif action != 'Add' and prov == 'Active':
                return f'Active+{action} (Inconsistente)'
            else:
                return 'Otro'
        
        df['IssueType'] = df.apply(categorize_issue, axis=1)
        df['ContractStatus'] = df['acn_fld_Contract__r.Status'].fillna('')
        df['AssetStatusLabel'] = df['Status'].apply(lambda x: ASSET_STATUS_MAP.get(str(x or ''), str(x or '')))
        
        # Calculate metrics
        metrics = ScriptMetrics(total_records=len(df))
        
        metrics.add_metric(
            'total_mismatches',
            len(df),
            'Assets con Desajuste',
            '❌' if len(df) > 0 else '✅'
        )
        
        # Count by issue type
        issue_counts = df['IssueType'].value_counts()
        for issue_type, count in issue_counts.items():
            metrics.add_metric(
                f'issue_{issue_type[:15]}',
                count,
                issue_type[:30],
                '⚠️'
            )
        
        # Count by asset status
        status_counts = df['AssetStatusLabel'].value_counts()
        for status, count in status_counts.head(5).items():
            if status:
                metrics.add_metric(
                    f'status_{status[:10]}',
                    count,
                    f'{status[:15]}',
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
            ColumnConfig('Name', 'Asset', ColumnType.LINK),
            ColumnConfig('IssueType', 'Problema', ColumnType.TEXT),
            ColumnConfig('AssetStatusLabel', 'Estado Asset', ColumnType.STATUS),
            ColumnConfig('vlocity_cmt__ProvisioningStatus__c', 'Provisioning', ColumnType.TEXT),
            ColumnConfig('vlocity_cmt__Action__c', 'Action', ColumnType.TEXT),
            ColumnConfig('ContractStatus', 'Estado Contrato', ColumnType.STATUS),
            ColumnConfig('Product2.ProductCode', 'Producto', ColumnType.TEXT),
            ColumnConfig('NewCo_OriginContractType__c', 'Tipo Origen', ColumnType.TEXT),
            ColumnConfig('CreatedDate', 'Fecha Creación', ColumnType.DATE),
        ]
    
    def get_groupby_options(self) -> list[str]:
        """Return columns for grouping."""
        return ['IssueType', 'AssetStatusLabel', 'vlocity_cmt__ProvisioningStatus__c', 'vlocity_cmt__Action__c']
    
    def prepare_update_data(self, data: pd.DataFrame, selected_ids: list[str]) -> list[dict]:
        """Prepare update records to fix provisioning/action."""
        updates = []
        
        for _, row in data.iterrows():
            if row['Id'] not in selected_ids:
                continue
            
            prov = str(row.get('vlocity_cmt__ProvisioningStatus__c', '')).strip()
            action = str(row.get('vlocity_cmt__Action__c', '')).strip()
            
            update_record = {'Id': row['Id']}
            
            # Fix: Retired + Add → Change Action to Disconnect
            if prov == 'Retired' and action == 'Add':
                update_record['vlocity_cmt__Action__c'] = 'Disconnect'
            
            # Fix: Active + Not Add → Change Provisioning based on Action
            elif prov == 'Active' and action != 'Add':
                if action == 'Disconnect':
                    update_record['vlocity_cmt__ProvisioningStatus__c'] = 'Retired'
                elif action == 'Change':
                    update_record['vlocity_cmt__ProvisioningStatus__c'] = 'Pending'
            
            if len(update_record) > 1:  # Only if we have fields to update
                updates.append(update_record)
        
        return updates
    
    def detect_anomalies(self, data: pd.DataFrame) -> pd.DataFrame:
        """All assets with provisioning mismatches are anomalies."""
        if data.empty:
            return pd.DataFrame()
        
        anomalies = data.copy()
        anomalies['anomaly_type'] = 'Desajuste Provisioning'
        anomalies['anomaly_severity'] = 'Alta'
        
        return anomalies
    
    def get_chart_recommendations(self) -> list[dict]:
        """Recommend charts."""
        return [
            {
                'type': 'pie',
                'names': 'IssueType',
                'title': 'Por Tipo de Problema'
            },
            {
                'type': 'bar',
                'x': 'AssetStatusLabel',
                'title': 'Por Estado Asset'
            }
        ]
