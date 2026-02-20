"""
Script: Assets - Desajuste Provisioning y Action

Detecta assets cuyo estado de provisioning o action no coincide 
con el estado esperado según su Status.

Por ejemplo:
- Assets en status Activo (03) deberían tener ProvisioningStatus='Active'
- Assets en status Baja deberían tener ProvisioningStatus='Retired', Action='Disconnect'
"""
import pandas as pd
from core.base_script import BaseScript, ScriptResult, ScriptMetrics, ColumnConfig, ColumnType
from core.script_registry import register_script
from config import ASSET_STATUS_MAP


@register_script
class AssetsDesajusteProvisioningAction(BaseScript):
    """
    Detecta assets con desajuste entre Status y Provisioning/Action.
    """
    
    name = "Assets - Desajuste Provisioning"
    description = "Detecta inconsistencias entre Estado, Provisioning y Action"
    category = "Regularización"
    version = "1.0"
    author = "AG"
    
    supports_preview = True
    supports_update = True
    requires_confirmation = True
    
    # Expected provisioning by status
    STATUS_PROVISIONING_MAP = {
        '01': ('Pending', None),         # Borrador
        '02': ('Pending', 'Add'),         # Alta en curso
        '03': ('Active', 'Add'),          # Activado
        '04': ('Pending', 'Change'),      # Modificación en curso
        '05': ('Retired', 'Disconnect'),  # Modificado
        '06': ('Pending', 'Disconnect'),  # Baja en curso
        '08': ('Suspended', None),        # Cortado
        '13': ('Cancelled', 'Disconnect'),# Cancelado
        '14': ('Retired', 'Disconnect'),  # Baja
        '15': ('Rejected', 'Disconnect'), # Rechazado
        '28': ('Retired', 'Disconnect'),  # Inactivo
    }
    
    def get_queries(self, preview: bool = False) -> list[str]:
        """Return query for assets with provisioning info."""
        limit_clause = "LIMIT 5000" if preview else ""
        
        query = f"""
            SELECT Id, Name, Status, acn_fld_Contract__c,
                   acn_fld_Contract__r.ContractNumber,
                   vlocity_cmt__ProvisioningStatus__c, vlocity_cmt__Action__c,
                   CreatedDate, LastModifiedDate
            FROM Asset
            WHERE vlocity_cmt__ParentItemId__c = null
            AND acn_fld_Contract__c != null
            {limit_clause}
        """
        
        return [query]
    
    def process(self, query_results: dict[str, pd.DataFrame]) -> ScriptResult:
        """Process assets to find provisioning mismatches."""
        df = query_results.get('query_0', pd.DataFrame())
        
        if df.empty:
            return ScriptResult(
                success=True,
                data=pd.DataFrame(),
                metrics=ScriptMetrics(total_records=0)
            )
        
        self.store_intermediate('assets_raw', df)
        
        # Find mismatches
        mismatches = []
        
        for _, row in df.iterrows():
            status = str(row.get('Status', '')).strip()
            current_prov = str(row.get('vlocity_cmt__ProvisioningStatus__c', '') or '').strip()
            current_action = str(row.get('vlocity_cmt__Action__c', '') or '').strip()
            
            expected = self.STATUS_PROVISIONING_MAP.get(status)
            if not expected:
                continue
            
            expected_prov, expected_action = expected
            
            # Check for mismatch
            prov_mismatch = expected_prov and current_prov != expected_prov
            action_mismatch = expected_action and current_action != expected_action
            
            if prov_mismatch or action_mismatch:
                issues = []
                if prov_mismatch:
                    issues.append(f'Prov: {current_prov} → {expected_prov}')
                if action_mismatch:
                    issues.append(f'Action: {current_action} → {expected_action}')
                
                mismatches.append({
                    'AssetId': row['Id'],
                    'AssetName': row['Name'],
                    'ContractId': row['acn_fld_Contract__c'],
                    'ContractNumber': row.get('acn_fld_Contract__r.ContractNumber', ''),
                    'Status': status,
                    'StatusLabel': ASSET_STATUS_MAP.get(status, status),
                    'CurrentProvisioning': current_prov,
                    'CurrentAction': current_action,
                    'ExpectedProvisioning': expected_prov,
                    'ExpectedAction': expected_action or '',
                    'Issues': '; '.join(issues),
                    'LastModifiedDate': row.get('LastModifiedDate')
                })
        
        df_result = pd.DataFrame(mismatches)
        
        # Calculate metrics
        metrics = ScriptMetrics(total_records=len(df_result))
        
        metrics.add_metric(
            'total_mismatches',
            len(df_result),
            'Desajustes',
            '🔴' if len(df_result) > 0 else '✅'
        )
        
        metrics.add_metric(
            'assets_checked',
            len(df),
            'Assets Verificados',
            '📊'
        )
        
        # Count by status
        if not df_result.empty:
            status_counts = df_result['StatusLabel'].value_counts()
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
            data=df_result,
            metrics=metrics
        )
    
    def get_column_config(self) -> list[ColumnConfig]:
        """Define column configuration."""
        return [
            ColumnConfig('AssetName', 'Asset', ColumnType.TEXT),
            ColumnConfig('ContractNumber', 'Contrato', ColumnType.TEXT),
            ColumnConfig('StatusLabel', 'Estado', ColumnType.STATUS),
            ColumnConfig('CurrentProvisioning', 'Prov. Actual', ColumnType.TEXT),
            ColumnConfig('ExpectedProvisioning', 'Prov. Esperado', ColumnType.TEXT),
            ColumnConfig('CurrentAction', 'Action Actual', ColumnType.TEXT),
            ColumnConfig('ExpectedAction', 'Action Esperado', ColumnType.TEXT),
            ColumnConfig('Issues', 'Problemas', ColumnType.TEXT),
        ]
    
    def get_groupby_options(self) -> list[str]:
        """Return columns for grouping."""
        return ['StatusLabel', 'CurrentProvisioning', 'CurrentAction']
    
    def detect_anomalies(self, data: pd.DataFrame) -> pd.DataFrame:
        """All mismatches are anomalies."""
        if data.empty:
            return pd.DataFrame()
        
        anomalies = data.copy()
        anomalies['anomaly_type'] = 'Desajuste Provisioning/Action'
        anomalies['anomaly_severity'] = 'Media'
        
        return anomalies
    
    def get_chart_recommendations(self) -> list[dict]:
        """Recommend charts."""
        return [
            {
                'type': 'pie',
                'names': 'StatusLabel',
                'title': 'Desajustes por Estado'
            },
            {
                'type': 'bar',
                'x': 'CurrentProvisioning',
                'title': 'Por Provisioning Actual'
            }
        ]
    
    def get_update_operations(self) -> list[dict]:
        """Define update operations."""
        return [
            {
                'name': 'fix_provisioning',
                'description': 'Corregir Provisioning y Action según Status',
                'fields': {
                    'vlocity_cmt__ProvisioningStatus__c': '(valor esperado)',
                    'vlocity_cmt__Action__c': '(valor esperado)'
                }
            }
        ]
