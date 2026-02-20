"""
Script: Contratos Inactivos con Assets en Status Inválido

Detecta contratos inactivos/finalizados que tienen assets con estados no válidos,
mostrándose incorrectamente como activos en sistemas externos (OMEGA).

Reglas de corrección:
- Status 13 (Cancelado): Si el contrato tiene solo 1 asset y la CR más antigua está 'Cancelada'
- Status 15 (Rechazado): Si el contrato tiene solo 1 asset y la CR contiene "Rechazado"
- Status 28 (Inactivo): En cualquier otro caso

También actualiza provisioning y action a Retired/Disconnect.
"""
import pandas as pd
from core.base_script import BaseScript, ScriptResult, ScriptMetrics, ColumnConfig, ColumnType
from core.script_registry import register_script
from config import ASSET_STATUS_MAP, CONTRACT_STATUS_MAP, CONTRACT_REQUEST_STATUS_MAP


@register_script
class ContratosInactivosStatusInvalido(BaseScript):
    """
    Detecta y corrige assets con status inválido en contratos inactivos.
    """
    
    name = "Contratos Inactivos - Assets Status Inválido"
    description = "Detecta contratos inactivos con assets que muestran estado activo"
    category = "Regularización"
    version = "1.0"
    author = "AG"
    
    supports_preview = True
    supports_update = True
    requires_confirmation = True
    
    # Status constants
    CONTRACT_INACTIVE_STATUSES = ['03', '04', '05', '06']  # Inactivo, Baja, Cancelado, Finalizado
    ASSET_INVALID_STATUSES = ['01', '02', '03', '04', '05', '06']  # Estados que no deberían estar
    
    ASSET_STATUS_CANCELADO = '13'
    ASSET_STATUS_RECHAZADO = '15'
    ASSET_STATUS_INACTIVO = '28'
    
    def get_queries(self, preview: bool = False) -> list[str]:
        """Return queries for assets and contract requests."""
        limit_clause = "LIMIT 1000" if preview else ""
        
        inactive_statuses = "','".join(self.CONTRACT_INACTIVE_STATUSES)
        invalid_asset_statuses = "','".join(self.ASSET_INVALID_STATUSES)
        
        # Query 1: Assets de contratos inactivos con status "activo"
        query_assets = f"""
            SELECT Id, Name, acn_fld_Contract__c, acn_fld_Contract__r.ContractNumber,
                   acn_fld_Contract__r.Status, Status, 
                   vlocity_cmt__ProvisioningStatus__c, vlocity_cmt__Action__c,
                   CreatedDate, LastModifiedDate
            FROM Asset
            WHERE acn_fld_Contract__r.Status IN ('{inactive_statuses}')
            AND Status IN ('{invalid_asset_statuses}')
            AND vlocity_cmt__ParentItemId__c = null
            {limit_clause}
        """
        
        # Query 2: Contract Requests para determinar el status correcto
        query_crs = f"""
            SELECT Id, Name, acn_fld_Contract__c, acn_fld_Status__c, 
                   acn_fld_Sctype__c, CreatedDate
            FROM acn_obj_ContractRequest__c
            WHERE acn_fld_Contract__c != null
        """
        
        return [query_assets, query_crs]
    
    def process(self, query_results: dict[str, pd.DataFrame]) -> ScriptResult:
        """Process and determine correct status for each asset."""
        df_assets = query_results.get('query_0', pd.DataFrame())
        df_crs = query_results.get('query_1', pd.DataFrame())
        
        if df_assets.empty:
            return ScriptResult(
                success=True,
                data=pd.DataFrame(),
                metrics=ScriptMetrics(total_records=0)
            )
        
        self.store_intermediate('assets_raw', df_assets)
        self.store_intermediate('crs_raw', df_crs)
        
        # Get unique contracts
        contract_ids = df_assets['acn_fld_Contract__c'].unique()
        
        # Count assets per contract
        assets_per_contract = df_assets.groupby('acn_fld_Contract__c').size()
        
        # Filter CRs for our contracts
        df_crs_filtered = df_crs[df_crs['acn_fld_Contract__c'].isin(contract_ids)]
        
        if not df_crs_filtered.empty:
            df_crs_filtered['CreatedDate'] = pd.to_datetime(df_crs_filtered['CreatedDate'])
            df_crs_filtered = df_crs_filtered.sort_values('CreatedDate')
        
        # Process each asset
        results = []
        
        for _, asset in df_assets.iterrows():
            contract_id = asset['acn_fld_Contract__c']
            num_assets = assets_per_contract.get(contract_id, 1)
            
            # Get CRs for this contract
            contract_crs = df_crs_filtered[
                df_crs_filtered['acn_fld_Contract__c'] == contract_id
            ]
            
            # Determine target status
            target_status = self.ASSET_STATUS_INACTIVO  # Default
            status_reason = "Sin CR específica"
            
            if num_assets == 1 and not contract_crs.empty:
                oldest_cr = contract_crs.iloc[0]
                cr_status = str(oldest_cr['acn_fld_Status__c']).lower()
                
                if 'cancelado' in cr_status or oldest_cr['acn_fld_Status__c'] == '05':
                    target_status = self.ASSET_STATUS_CANCELADO
                    status_reason = "CR más antigua cancelada"
                elif 'rechazado' in cr_status or oldest_cr['acn_fld_Status__c'] == '04':
                    target_status = self.ASSET_STATUS_RECHAZADO
                    status_reason = "CR más antigua rechazada"
                else:
                    target_status = self.ASSET_STATUS_INACTIVO
                    status_reason = f"CR en estado: {oldest_cr['acn_fld_Status__c']}"
            elif num_assets > 1:
                status_reason = f"Contrato con {num_assets} assets"
            
            results.append({
                'ContractId': contract_id,
                'ContractNumber': asset.get('acn_fld_Contract__r.ContractNumber', ''),
                'ContractStatus': asset.get('acn_fld_Contract__r.Status', ''),
                'ContractStatusLabel': CONTRACT_STATUS_MAP.get(
                    asset.get('acn_fld_Contract__r.Status', ''), ''
                ),
                'AssetId': asset['Id'],
                'AssetName': asset['Name'],
                'CurrentStatus': asset['Status'],
                'CurrentStatusLabel': ASSET_STATUS_MAP.get(asset['Status'], ''),
                'CurrentProvisioning': asset.get('vlocity_cmt__ProvisioningStatus__c', ''),
                'CurrentAction': asset.get('vlocity_cmt__Action__c', ''),
                'TargetStatus': target_status,
                'TargetStatusLabel': ASSET_STATUS_MAP.get(target_status, ''),
                'StatusReason': status_reason,
                'NumAssets': num_assets,
                'NumCRs': len(contract_crs),
                'LastModifiedDate': asset['LastModifiedDate']
            })
        
        df_resultado = pd.DataFrame(results)
        
        # Metrics
        metrics = ScriptMetrics(
            total_records=len(df_resultado),
            processed_records=len(df_assets)
        )
        
        # Count by target status
        if not df_resultado.empty:
            status_counts = df_resultado['TargetStatus'].value_counts()
            for status, count in status_counts.items():
                label = ASSET_STATUS_MAP.get(status, status)
                metrics.add_metric(
                    f'target_{status}',
                    count,
                    f'A estado {label}',
                    '🏷️'
                )
        
        metrics.add_metric(
            'contratos_unicos',
            df_resultado['ContractId'].nunique() if not df_resultado.empty else 0,
            'Contratos Únicos',
            '📄'
        )
        
        return ScriptResult(
            success=True,
            data=df_resultado,
            metrics=metrics
        )
    
    def get_column_config(self) -> list[ColumnConfig]:
        """Define column configuration for display."""
        return [
            ColumnConfig('ContractNumber', 'Nº Contrato', ColumnType.TEXT),
            ColumnConfig('ContractStatusLabel', 'Estado Contrato', ColumnType.STATUS),
            ColumnConfig('AssetName', 'Asset', ColumnType.TEXT),
            ColumnConfig('CurrentStatusLabel', 'Estado Actual', ColumnType.STATUS),
            ColumnConfig('TargetStatusLabel', 'Estado Objetivo', ColumnType.STATUS),
            ColumnConfig('StatusReason', 'Razón', ColumnType.TEXT),
            ColumnConfig('NumAssets', 'Nº Assets', ColumnType.NUMBER),
        ]
    
    def get_groupby_options(self) -> list[str]:
        """Return columns for grouping."""
        return [
            'ContractStatusLabel',
            'CurrentStatusLabel',
            'TargetStatusLabel',
            'StatusReason',
            'NumAssets'
        ]
    
    def get_update_operations(self) -> list[dict]:
        """Define update operations."""
        return [
            {
                'name': 'update_status_and_provisioning',
                'description': 'Actualizar status, provisioning=Retired, action=Disconnect',
                'fields': {
                    'Status': 'dynamic',  # From TargetStatus
                    'vlocity_cmt__ProvisioningStatus__c': 'Retired',
                    'vlocity_cmt__Action__c': 'Disconnect'
                }
            }
        ]
    
    def execute_update(self, operation: str, data: pd.DataFrame) -> tuple[list, list]:
        """Execute the update operation."""
        if operation != 'update_status_and_provisioning':
            raise ValueError(f"Unknown operation: {operation}")
        
        if data.empty:
            return [], []
        
        # Prepare records with individual target status
        records = [
            {
                'Id': row['AssetId'],
                'Status': row['TargetStatus'],
                'vlocity_cmt__ProvisioningStatus__c': 'Retired',
                'vlocity_cmt__Action__c': 'Disconnect'
            }
            for _, row in data.iterrows()
        ]
        
        return self.sf_client.bulk_update('Asset', records)
    
    def detect_anomalies(self, data: pd.DataFrame) -> pd.DataFrame:
        """All records are anomalies - invalid status."""
        if data.empty:
            return pd.DataFrame()
        
        result = data.copy()
        result['anomaly_type'] = 'Asset con Status Inválido'
        
        # Classify severity
        def get_severity(row):
            if row['NumAssets'] > 3:
                return 'Alta'
            elif row['NumAssets'] > 1:
                return 'Media'
            return 'Baja'
        
        result['anomaly_severity'] = result.apply(get_severity, axis=1)
        return result
