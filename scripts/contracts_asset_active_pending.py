"""
Script: Contratos con Asset Activo y Pendiente

Detecta contratos que tienen un asset en estado '03' (Activo) y otro en '02' (Alta en curso).

Se regulariza actualizando el ASSET PENDING (02):
- StartDate: fecha inicial del asset activo
- EndDate: misma fecha inicial del asset activo  
- Status: '21' (Sin Vigencia)
- ProvisioningStatus: 'Retired'
- Action: 'Disconnect'
"""
import pandas as pd
from core.base_script import BaseScript, ScriptResult, ScriptMetrics, ColumnConfig, ColumnType
from core.script_registry import register_script
from config import ASSET_STATUS_MAP


@register_script
class ContractsAssetActivePending(BaseScript):
    """
    Detecta contratos con assets en estado activo y pendiente simultáneamente.
    """
    
    name = "Contratos - Asset Activo y Pendiente"
    description = "Detecta contratos con asset activo (03) y pendiente (02)"
    category = "Regularización"
    version = "1.0"
    author = "AG"
    
    supports_preview = True
    supports_update = True
    requires_confirmation = True
    
    # Status constants
    ASSET_STATUS_ACTIVE = '03'
    ASSET_STATUS_PENDING = '02'
    ASSET_STATUS_SIN_VIGENCIA = '21'
    
    # Categories that indicate desistimiento
    CR_CATEGORIES_SKIP = ['28', '46', '66']
    
    def get_queries(self, preview: bool = False) -> list[str]:
        """Return queries for assets and contract requests."""
        limit_clause = "LIMIT 5000" if preview else ""
        
        # Query 1: Assets in status 02 and 03
        query_assets = f"""
            SELECT Id, Name, Status, acn_fld_Contract__c, vlocity_cmt__ContractId__c, 
                   CreatedDate, acn_fld_EndDateVersion__c, acn_fld_StartDateVersion__c
            FROM Asset 
            WHERE Status IN ('{self.ASSET_STATUS_ACTIVE}', '{self.ASSET_STATUS_PENDING}')
            AND vlocity_cmt__ParentItemId__c = NULL 
            AND (acn_fld_Contract__c != null OR vlocity_cmt__ContractId__c != null)
            {limit_clause}
        """
        
        # Query 2: Contract Requests with desistimiento categories
        query_crs = f"""
            SELECT Id, acn_fld_Contract__c, acn_fld_Category__c
            FROM acn_obj_ContractRequest__c 
            WHERE acn_fld_Category__c IN ('28', '46', '66')
        """
        
        return [query_assets, query_crs]
    
    def process(self, query_results: dict[str, pd.DataFrame]) -> ScriptResult:
        """Process assets to find contracts with both active and pending."""
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
        
        # Get contracts with desistimiento
        contracts_with_desistimiento = set()
        if not df_crs.empty:
            contracts_with_desistimiento = set(df_crs['acn_fld_Contract__c'].dropna())
        
        # Group by contract
        contract_assets = df_assets.groupby('acn_fld_Contract__c').apply(
            lambda x: x.to_dict('records')
        ).to_dict()
        
        # Find contracts with both active and pending
        results = []
        skipped_desistimiento = []
        invalid_assets = []
        
        for contract_id, assets in contract_assets.items():
            if not contract_id:
                continue
                
            # Check if has both statuses
            statuses = set(a.get('Status') for a in assets)
            if not (self.ASSET_STATUS_ACTIVE in statuses and self.ASSET_STATUS_PENDING in statuses):
                continue
            
            # Check for desistimiento
            if contract_id in contracts_with_desistimiento:
                skipped_desistimiento.append({
                    'ContractId': contract_id,
                    'AssetCount': len(assets),
                    'Reason': 'Tiene Desistimiento (cat 28/46/66)'
                })
                continue
            
            # Separate by status
            active_assets = [a for a in assets if a['Status'] == self.ASSET_STATUS_ACTIVE]
            pending_assets = [a for a in assets if a['Status'] == self.ASSET_STATUS_PENDING]
            
            # Get active asset (oldest)
            active_asset = sorted(
                active_assets, 
                key=lambda x: x.get('CreatedDate', '') or ''
            )[0]
            
            # Get pending asset (newest)
            pending_asset = sorted(
                pending_assets, 
                key=lambda x: x.get('CreatedDate', '') or '', 
                reverse=True
            )[0]
            
            # Validate active asset has start date
            active_start = active_asset.get('acn_fld_StartDateVersion__c')
            if not active_start:
                invalid_assets.append({
                    'ContractId': contract_id,
                    'ActiveAssetId': active_asset.get('Id'),
                    'PendingAssetId': pending_asset.get('Id'),
                    'Reason': 'Asset activo sin fecha inicio'
                })
                continue
            
            results.append({
                'ContractId': contract_id,
                'ActiveAssetId': active_asset.get('Id'),
                'ActiveAssetName': active_asset.get('Name'),
                'ActiveAssetStartDate': active_start,
                'PendingAssetId': pending_asset.get('Id'),
                'PendingAssetName': pending_asset.get('Name'),
                'NewStartDate': active_start,
                'NewEndDate': active_start,
                'TargetStatus': self.ASSET_STATUS_SIN_VIGENCIA,
                'TotalActiveAssets': len(active_assets),
                'TotalPendingAssets': len(pending_assets)
            })
        
        df_result = pd.DataFrame(results)
        df_skipped = pd.DataFrame(skipped_desistimiento)
        df_invalid = pd.DataFrame(invalid_assets)
        
        self.store_intermediate('skipped_desistimiento', df_skipped)
        self.store_intermediate('invalid_assets', df_invalid)
        
        # Calculate metrics
        metrics = ScriptMetrics(total_records=len(df_result))
        
        metrics.add_metric(
            'contracts_to_fix',
            len(df_result),
            'Contratos a Regularizar',
            '🔴' if len(df_result) > 0 else '✅'
        )
        
        metrics.add_metric(
            'skipped_desistimiento',
            len(df_skipped),
            'Saltados (Desistimiento)',
            '⏭️'
        )
        
        metrics.add_metric(
            'invalid_assets',
            len(df_invalid),
            'Con Errores de Datos',
            '⚠️' if len(df_invalid) > 0 else '✅'
        )
        
        return ScriptResult(
            success=True,
            data=df_result,
            metrics=metrics
        )
    
    def get_column_config(self) -> list[ColumnConfig]:
        """Define column configuration."""
        return [
            ColumnConfig('ContractId', 'ID Contrato', ColumnType.LINK),
            ColumnConfig('ActiveAssetId', 'Asset Activo', ColumnType.LINK),
            ColumnConfig('ActiveAssetStartDate', 'Inicio Activo', ColumnType.DATE),
            ColumnConfig('PendingAssetId', 'Asset Pendiente', ColumnType.LINK),
            ColumnConfig('NewStartDate', 'Nueva Fecha Inicio', ColumnType.DATE),
            ColumnConfig('NewEndDate', 'Nueva Fecha Fin', ColumnType.DATE),
            ColumnConfig('TargetStatus', 'Status Objetivo', ColumnType.STATUS),
        ]
    
    def get_groupby_options(self) -> list[str]:
        """Return columns for grouping."""
        return ['TotalActiveAssets', 'TotalPendingAssets']
    
    def detect_anomalies(self, data: pd.DataFrame) -> pd.DataFrame:
        """All contracts with both states are anomalies."""
        if data.empty:
            return pd.DataFrame()
        
        anomalies = data.copy()
        anomalies['anomaly_type'] = 'Asset Activo y Pendiente'
        anomalies['anomaly_severity'] = 'Alta'
        
        return anomalies
    
    def get_chart_recommendations(self) -> list[dict]:
        """Recommend charts."""
        return [
            {
                'type': 'bar',
                'x': 'TotalPendingAssets',
                'title': 'Distribución por Nº Assets Pendientes'
            }
        ]
    
    def get_update_operations(self) -> list[dict]:
        """Define update operations."""
        return [
            {
                'name': 'update_pending_asset',
                'description': 'Actualizar asset pendiente a Sin Vigencia',
                'fields': {
                    'Status': '21',
                    'acn_fld_StartDateVersion__c': '(fecha inicio del activo)',
                    'acn_fld_EndDateVersion__c': '(fecha inicio del activo)',
                    'vlocity_cmt__ProvisioningStatus__c': 'Retired',
                    'vlocity_cmt__Action__c': 'Disconnect'
                }
            }
        ]
