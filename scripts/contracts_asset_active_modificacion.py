"""
Script: Contratos con Asset Activo y Modificación en Curso

Detecta y regulariza contratos que tienen un asset en estado '03' (Activo) 
y otro en estado '04' (Modificación en curso).

Regularización:
- Asset en estado '04' (Modificación en curso) → Status='05' (Modificado)
- Provisioning Status → 'Retired'
- Action → 'Disconnect'

Aparece en Omega como doble contrato activo, lo cual es incorrecto.
"""
import pandas as pd
from collections import defaultdict
from core.base_script import BaseScript, ScriptResult, ScriptMetrics, ColumnConfig, ColumnType
from core.script_registry import register_script
from config import ASSET_STATUS_MAP


@register_script
class ContractsAssetActiveAndModificacion(BaseScript):
    """
    Detecta y regulariza contratos con asset activo y modificación en curso.
    """
    
    name = "Contratos - Activo y Modificación En Curso"
    description = "Regulariza contratos con asset activo (03) y modificación (04)"
    category = "Regularización"
    version = "2.0"
    author = "AG"
    
    supports_preview = True
    supports_update = True
    requires_confirmation = True
    
    # Status codes
    ASSET_STATUS_ACTIVE = '03'
    ASSET_STATUS_MOD_EN_CURSO = '04'  # Modificación en curso
    
    def get_queries(self, preview: bool = False) -> list[str]:
        """Return query for assets."""
        limit_clause = "LIMIT 5000" if preview else ""
        
        query = f"""
            SELECT Id, Name, Status, acn_fld_Contract__c, vlocity_cmt__ContractId__c,
                   CreatedDate, acn_fld_EndDateVersion__c, acn_fld_StartDateVersion__c
            FROM Asset 
            WHERE Status IN ('{self.ASSET_STATUS_ACTIVE}', '{self.ASSET_STATUS_MOD_EN_CURSO}')
            AND vlocity_cmt__ParentItemId__c = NULL 
            AND (acn_fld_Contract__c != null OR vlocity_cmt__ContractId__c != null)
            {limit_clause}
        """
        
        return [query]
    
    def process(self, query_results: dict[str, pd.DataFrame]) -> ScriptResult:
        """Process assets to find contracts with both states."""
        df = query_results.get('query_0', pd.DataFrame())
        
        if df.empty:
            return ScriptResult(
                success=True,
                data=pd.DataFrame(),
                metrics=ScriptMetrics(total_records=0)
            )
        
        self.store_intermediate('assets_raw', df)
        
        # Group by both contract fields
        contract_assets_acn = defaultdict(list)
        contract_assets_vlocity = defaultdict(list)
        
        for _, row in df.iterrows():
            asset_dict = row.to_dict()
            
            acn_contract = row.get('acn_fld_Contract__c')
            vlocity_contract = row.get('vlocity_cmt__ContractId__c')
            
            if pd.notna(acn_contract) and acn_contract:
                contract_assets_acn[acn_contract].append(asset_dict)
            
            if pd.notna(vlocity_contract) and vlocity_contract:
                contract_assets_vlocity[vlocity_contract].append(asset_dict)
        
        # Find contracts with both statuses
        results = []
        processed_contracts = set()
        
        for contract_id, assets in contract_assets_acn.items():
            if contract_id not in processed_contracts:
                processed_contracts.add(contract_id)
                result = self._check_contract(contract_id, assets, 'acn_fld_Contract__c')
                if result:
                    results.append(result)
        
        for contract_id, assets in contract_assets_vlocity.items():
            if contract_id not in processed_contracts:
                processed_contracts.add(contract_id)
                result = self._check_contract(contract_id, assets, 'vlocity_cmt__ContractId__c')
                if result:
                    results.append(result)
        
        df_result = pd.DataFrame(results)
        
        # Calculate metrics
        metrics = ScriptMetrics(total_records=len(df_result))
        
        metrics.add_metric(
            'contracts_affected',
            len(df_result),
            'Contratos Afectados',
            '⚠️' if len(df_result) > 0 else '✅'
        )
        
        if not df_result.empty:
            total_mod_assets = df_result['ModEnCursoCount'].sum()
            metrics.add_metric(
                'mod_assets_to_update',
                total_mod_assets,
                'Assets Mod. a Actualizar',
                '📝'
            )
        
        return ScriptResult(
            success=True,
            data=df_result,
            metrics=metrics
        )
    
    def _check_contract(self, contract_id: str, assets: list, link_field: str) -> dict:
        """Check if contract has both active and modificacion en curso assets."""
        statuses = set(a.get('Status') for a in assets)
        
        if self.ASSET_STATUS_ACTIVE not in statuses or self.ASSET_STATUS_MOD_EN_CURSO not in statuses:
            return None
        
        # Separate by status
        active_assets = [a for a in assets if a['Status'] == self.ASSET_STATUS_ACTIVE]
        mod_assets = [a for a in assets if a['Status'] == self.ASSET_STATUS_MOD_EN_CURSO]
        
        # Get the main active asset (oldest by CreatedDate)
        active_asset = sorted(active_assets, key=lambda x: x.get('CreatedDate', '') or '')[0] if active_assets else {}
        
        # Get themod en curso asset (newest by CreatedDate)
        mod_asset = sorted(mod_assets, key=lambda x: x.get('CreatedDate', '') or '', reverse=True)[0] if mod_assets else {}
        
        return {
            'ContractId': contract_id,
            'LinkField': link_field,
            'ActiveAssetCount': len(active_assets),
            'ModEnCursoCount': len(mod_assets),
            'TotalAssets': len(assets),
            'ActiveAssetId': active_asset.get('Id', ''),
            'ActiveAssetName': active_asset.get('Name', ''),
            'ActiveAssetCreatedDate': active_asset.get('CreatedDate', ''),
            'ModAssetId': mod_asset.get('Id', ''),
            'ModAssetName': mod_asset.get('Name', ''),
            'ModAssetCreatedDate': mod_asset.get('CreatedDate', ''),
            'ModAssetIds': '; '.join([a['Id'] for a in mod_assets])
        }
    
    def get_column_config(self) -> list[ColumnConfig]:
        """Define column configuration."""
        return [
            ColumnConfig('ContractId', 'Contrato', ColumnType.LINK),
            ColumnConfig('LinkField', 'Campo Relación', ColumnType.TEXT),
            ColumnConfig('ActiveAssetName', 'Asset Activo', ColumnType.TEXT),
            ColumnConfig('ModAssetName', 'Asset Mod. En Curso', ColumnType.TEXT),
            ColumnConfig('ModEnCursoCount', 'Nº Mod. En Curso', ColumnType.NUMBER),
            ColumnConfig('TotalAssets', 'Total Assets', ColumnType.NUMBER),
            ColumnConfig('ActiveAssetCreatedDate', 'Creado (Activo)', ColumnType.DATETIME),
            ColumnConfig('ModAssetCreatedDate', 'Creado (Mod)', ColumnType.DATETIME),
        ]
    
    def get_groupby_options(self) -> list[str]:
        """Return columns for grouping."""
        return ['LinkField', 'ActiveAssetCount', 'ModEnCursoCount']
    
    def prepare_update_data(self, data: pd.DataFrame, selected_ids: list[str]) -> list[dict]:
        """Prepare update records for modificacion en curso assets."""
        updates = []
        
        for _, row in data.iterrows():
            if row.get('ContractId') not in selected_ids:
                continue
            
            # Get all mod asset IDs (could be multiple)
            mod_asset_ids_str = row.get('ModAssetIds', '')
            if mod_asset_ids_str:
                mod_asset_ids = mod_asset_ids_str.split('; ')
                
                for mod_asset_id in mod_asset_ids:
                    if mod_asset_id:
                        updates.append({
                            'Id': mod_asset_id,
                            'Status': '05',  # Modificado
                            'vlocity_cmt__ProvisioningStatus__c': 'Retired',
                            'vlocity_cmt__Action__c': 'Disconnect'
                        })
        
        return updates
    
    def detect_anomalies(self, data: pd.DataFrame) -> pd.DataFrame:
        """All contracts with both states are anomalies."""
        if data.empty:
            return pd.DataFrame()
        
        anomalies = data.copy()
        anomalies['anomaly_type'] = 'Activo y Modificación En Curso'
        anomalies['anomaly_severity'] = 'Media'
        
        return anomalies
    
    def get_chart_recommendations(self) -> list[dict]:
        """Recommend charts."""
        return [
            {
                'type': 'bar',
                'x': 'ModEnCursoCount',
                'title': 'Por Nº Modificación En Curso'
            },
            {
                'type': 'pie',
                'names': 'LinkField',
                'title': 'Por Campo de Relación'
            }
        ]
