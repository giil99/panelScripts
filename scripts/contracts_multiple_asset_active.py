"""
Script: Contratos con Múltiples Assets Activos

Detecta contratos que tienen más de un asset en estado activo (03).
Se regulariza de manera que:

1. Casuística 1: El asset activo más viejo con fecha fin informada se pone en 
   modificado (05) con provisioning Retired y action Disconnect.
   
2. Casuística 2: Si el asset más viejo no tiene fecha fin:
   a. Si fecha_inicio == fecha_fin_calculada → Status 20 (Sin Vigencia)
   b. Si fecha_inicio < fecha_fin_calculada → Status 05 (Modificado)
   c. Si fecha_inicio > fecha_fin_calculada → Marcar para revisión manual
"""
import pandas as pd
from datetime import datetime, timedelta
from core.base_script import BaseScript, ScriptResult, ScriptMetrics, ColumnConfig, ColumnType
from core.script_registry import register_script
from config import ASSET_STATUS_MAP


@register_script
class ContractsMultipleAssetActive(BaseScript):
    """
    Detecta y regulariza contratos con múltiples assets activos.
    """
    
    name = "Contratos - Múltiples Assets Activos"
    description = "Detecta contratos con más de un asset en estado activo"
    category = "Regularización"
    version = "1.0"
    author = "AG"
    
    supports_preview = True
    supports_update = True
    requires_confirmation = True
    
    # Status constants
    ASSET_STATUS_ACTIVE = '03'
    ASSET_STATUS_MODIFICADO = '05'
    ASSET_STATUS_SIN_VIGENCIA = '20'
    
    def get_queries(self, preview: bool = False) -> list[str]:
        """Return query for active assets."""
        limit_clause = "LIMIT 5000" if preview else ""
        
        query = f"""
            SELECT Id, Name, Status, acn_fld_Contract__c, vlocity_cmt__ContractId__c, 
                   CreatedDate, acn_fld_EndDateVersion__c, acn_fld_StartDateVersion__c
            FROM Asset 
            WHERE Status = '{self.ASSET_STATUS_ACTIVE}' 
            AND vlocity_cmt__ParentItemId__c = NULL 
            AND (acn_fld_Contract__c != null OR vlocity_cmt__ContractId__c != null)
            {limit_clause}
        """
        
        return [query]
    
    def process(self, query_results: dict[str, pd.DataFrame]) -> ScriptResult:
        """Process assets to find contracts with multiple active assets."""
        df = query_results.get('query_0', pd.DataFrame())
        
        if df.empty:
            return ScriptResult(
                success=True,
                data=pd.DataFrame(),
                metrics=ScriptMetrics(total_records=0)
            )
        
        self.store_intermediate('assets_raw', df)
        
        # LÓGICA DEL NOTEBOOK: Group by AMBOS campos de contrato
        # (acn_fld_Contract__c Y vlocity_cmt__ContractId__c)
        contract_assets_acn = {}
        contract_assets_vlocity = {}
        
        for _, asset in df.iterrows():
            asset_dict = asset.to_dict()
            
            # Agrupar por acn_fld_Contract__c
            acn_contract = asset_dict.get('acn_fld_Contract__c')
            if acn_contract and acn_contract != '':
                if acn_contract not in contract_assets_acn:
                    contract_assets_acn[acn_contract] = []
                contract_assets_acn[acn_contract].append(asset_dict)
            
            # Agrupar por vlocity_cmt__ContractId__c
            vlocity_contract = asset_dict.get('vlocity_cmt__ContractId__c')
            if vlocity_contract and vlocity_contract != '':
                if vlocity_contract not in contract_assets_vlocity:
                    contract_assets_vlocity[vlocity_contract] = []
                contract_assets_vlocity[vlocity_contract].append(asset_dict)
        
        # Filter contracts with more than one active asset
        multi_asset_acn = {
            k: v for k, v in contract_assets_acn.items() if len(v) > 1
        }
        multi_asset_vlocity = {
            k: v for k, v in contract_assets_vlocity.items() if len(v) > 1
        }
        
        # Combinar ambos (evitar duplicados usando un set)
        processed_contracts = set()
        results = []
        casuistica1_count = 0
        casuistica2_count = 0
        revisar_manual_count = 0
        
        def process_contract_group(contract_id, assets, link_field):
            """Procesar un grupo de assets de un contrato."""
            nonlocal casuistica1_count, casuistica2_count, revisar_manual_count
            
            if contract_id in processed_contracts:
                return None
            processed_contracts.add(contract_id)
            # Sort by CreatedDate (oldest first)
            sorted_assets = sorted(
                assets, 
                key=lambda x: x.get('CreatedDate', '') or ''
            )
            
            oldest_asset = sorted_assets[0]
            newest_asset = sorted_assets[-1]
            
            # Determine casuistica
            has_end_date = bool(oldest_asset.get('acn_fld_EndDateVersion__c'))
            
            if has_end_date:
                casuistica = 'CASUISTICA_1'
                target_status = self.ASSET_STATUS_MODIFICADO
                casuistica1_count += 1
            else:
                casuistica = 'CASUISTICA_2'
                # Need to calculate end date from newest asset start date
                newest_start = newest_asset.get('acn_fld_StartDateVersion__c')
                oldest_start = oldest_asset.get('acn_fld_StartDateVersion__c')
                
                if newest_start and oldest_start:
                    # Calculate: end_date = newest_start - 1 day
                    try:
                        newest_dt = pd.to_datetime(newest_start).date()
                        oldest_dt = pd.to_datetime(oldest_start).date()
                        calculated_end = newest_dt - timedelta(days=1)
                        
                        if oldest_dt == calculated_end:
                            target_status = self.ASSET_STATUS_SIN_VIGENCIA
                        elif oldest_dt < calculated_end:
                            target_status = self.ASSET_STATUS_MODIFICADO
                        else:
                            target_status = 'REVISAR_MANUAL'
                            revisar_manual_count += 1
                    except:
                        target_status = 'REVISAR_MANUAL'
                        revisar_manual_count += 1
                else:
                    target_status = 'REVISAR_MANUAL'
                    revisar_manual_count += 1
                
                casuistica2_count += 1
            
            return {
                'ContractId': contract_id,
                'LinkField': link_field,
                'AssetCount': len(assets),
                'OldestAssetId': oldest_asset.get('Id'),
                'OldestAssetName': oldest_asset.get('Name'),
                'OldestAssetEndDate': oldest_asset.get('acn_fld_EndDateVersion__c'),
                'OldestAssetStartDate': oldest_asset.get('acn_fld_StartDateVersion__c'),
                'NewestAssetId': newest_asset.get('Id'),
                'NewestAssetStartDate': newest_asset.get('acn_fld_StartDateVersion__c'),
                'Casuistica': casuistica,
                'TargetStatus': target_status,
                'AllAssetIds': '; '.join([a.get('Id', '') for a in assets])
            }
        
        # Procesar AMBOS grupos (ACN y Vlocity) como en el notebook
        for contract_id, assets in multi_asset_acn.items():
            result = process_contract_group(contract_id, assets, 'acn_fld_Contract__c')
            if result:
                results.append(result)
        
        for contract_id, assets in multi_asset_vlocity.items():
            result = process_contract_group(contract_id, assets, 'vlocity_cmt__ContractId__c')
            if result:
                results.append(result)
        
        df_result = pd.DataFrame(results)
        
        # Calculate metrics
        metrics = ScriptMetrics(total_records=len(df_result))
        
        metrics.add_metric(
            'total_contracts',
            len(df_result),
            'Contratos con Múltiples Assets',
            '🔴' if len(df_result) > 0 else '✅'
        )
        
        metrics.add_metric(
            'casuistica1',
            casuistica1_count,
            'Casuística 1 (con EndDate)',
            '📊'
        )
        
        metrics.add_metric(
            'casuistica2',
            casuistica2_count,
            'Casuística 2 (sin EndDate)',
            '📊'
        )
        
        metrics.add_metric(
            'revisar_manual',
            revisar_manual_count,
            'Requieren Revisión Manual',
            '⚠️' if revisar_manual_count > 0 else '✅'
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
            ColumnConfig('LinkField', 'Campo Link', ColumnType.TEXT),
            ColumnConfig('AssetCount', 'Nº Assets', ColumnType.NUMBER),
            ColumnConfig('OldestAssetId', 'Asset Más Viejo', ColumnType.LINK),
            ColumnConfig('OldestAssetStartDate', 'Inicio Viejo', ColumnType.DATE),
            ColumnConfig('OldestAssetEndDate', 'Fin Viejo', ColumnType.DATE),
            ColumnConfig('Casuistica', 'Casuística', ColumnType.TEXT),
            ColumnConfig('TargetStatus', 'Status Objetivo', ColumnType.STATUS),
        ]
    
    def get_groupby_options(self) -> list[str]:
        """Return columns for grouping."""
        return ['Casuistica', 'TargetStatus', 'AssetCount']
    
    def detect_anomalies(self, data: pd.DataFrame) -> pd.DataFrame:
        """All contracts with multiple active assets are anomalies."""
        if data.empty:
            return pd.DataFrame()
        
        anomalies = data.copy()
        anomalies['anomaly_type'] = 'Múltiples Assets Activos'
        anomalies['anomaly_severity'] = 'Alta'
        
        return anomalies
    
    def get_chart_recommendations(self) -> list[dict]:
        """Recommend charts."""
        return [
            {
                'type': 'pie',
                'names': 'Casuistica',
                'title': 'Distribución por Casuística'
            },
            {
                'type': 'bar',
                'x': 'TargetStatus',
                'title': 'Assets por Status Objetivo'
            }
        ]
    
    def get_update_operations(self) -> list[dict]:
        """Define update operations."""
        return [
            {
                'name': 'update_oldest_asset',
                'description': 'Actualizar asset más viejo a Modificado/Sin Vigencia',
                'fields': {
                    'Status': '(05 o 20)',
                    'vlocity_cmt__ProvisioningStatus__c': 'Retired',
                    'vlocity_cmt__Action__c': 'Disconnect'
                }
            }
        ]
