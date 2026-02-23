"""
Script: Contratos - Múltiples Assets en Baja (Regularización)

Detecta y regulariza contratos con múltiples assets en estado baja (Status='12').

CAUSÍSTICA 1 - Asset más viejo CON EndDateVersion informado:
  → Actualiza: Status='05' (Modificado), Provisioning='Retired', Action='Disconnect'

CAUSÍSTICA 2 - Asset más viejo SIN EndDateVersion informado:
  → Calcula EndDate = StartDate del asset más nuevo - 1 día
  → Validaciones:
     - Si StartDate viejo = StartDate nuevo → EndDate=StartDate, Status='21' (Sin Vigencia)
     - Si StartDate viejo = EndDate calculado → Status='21' (Sin Vigencia)
     - Si StartDate viejo < EndDate calculado → Status='05' (Modificado)
     - Si StartDate viejo > EndDate calculado → ERROR - Requiere revisión manual
  → Actualiza: EndDateVersion, Status, Provisioning='Retired', Action='Disconnect'
"""
import pandas as pd
from datetime import datetime, timedelta
from collections import defaultdict
from typing import List, Dict, Any
from core.base_script import BaseScript, ScriptResult, ScriptMetrics, ColumnConfig, ColumnType
from core.script_registry import register_script
from core.causistica import CausisticaDefinition, CausisticaResult, CausisticaManager


@register_script
class ContractsMultipleAssetBaja(BaseScript):
    """
    Detecta y regulariza contratos con múltiples assets en estado baja.
    """
    
    name = "Contratos - Múltiples Assets Baja"
    description = "Regulariza contratos con múltiples assets en baja (Status='12')"
    category = "Regularización"
    version = "2.0"
    author = "AG"
    
    supports_preview = True
    supports_update = True
    requires_confirmation = True
    uses_causistica = True
    
    # Status 12 - Baja (según notebook)
    BAJA_STATUS = '12'
    
    def get_causisticas(self) -> List[CausisticaDefinition]:
        """Define causísticas para múltiples assets en baja."""
        return [
            CausisticaDefinition(
                id='CON_END_DATE',
                name='Asset viejo CON EndDateVersion',
                description='Asset más viejo tiene EndDateVersion informado → Status=05, Provisioning=Retired, Action=Disconnect',
                update_fields=['Status', 'vlocity_cmt__ProvisioningStatus__c', 'vlocity_cmt__Action__c']
            ),
            CausisticaDefinition(
                id='SIN_END_DATE',
                name='Asset viejo SIN EndDateVersion',
                description='Asset más viejo sin EndDateVersion → Calcula EndDate, actualiza Status (05 o 21)',
                update_fields=['acn_fld_EndDateVersion__c', 'Status', 'vlocity_cmt__ProvisioningStatus__c', 'vlocity_cmt__Action__c']
            ),
            CausisticaDefinition(
                id='ERROR_FECHAS',
                name='ERROR - Fechas inconsistentes',
                description='StartDate viejo > EndDate calculado → Requiere revisión manual',
                requires_manual_review=True
            )
        ]
    
    def get_queries(self, preview: bool = False) -> list[str]:
        """Return query for assets in baja status (12)."""
        limit_clause = "LIMIT 5000" if preview else ""
        
        query = f"""
            SELECT Id, Name, Status, acn_fld_Contract__c, vlocity_cmt__ContractId__c,
                   CreatedDate, acn_fld_EndDateVersion__c, acn_fld_StartDateVersion__c
            FROM Asset 
            WHERE Status = '{self.BAJA_STATUS}'
            AND vlocity_cmt__ParentItemId__c = NULL
            AND (acn_fld_Contract__c != null OR vlocity_cmt__ContractId__c != null)
            {limit_clause}
        """
        
        return [query]
    
    def process(self, query_results: dict[str, pd.DataFrame]) -> ScriptResult:
        """Process assets to find contracts with multiple baja assets and apply causísticas."""
        df = query_results.get('query_0', pd.DataFrame())
        
        if df.empty:
            return ScriptResult(
                success=True,
                data=pd.DataFrame(),
                metrics=ScriptMetrics(total_records=0)
            )
        
        self.store_intermediate('assets_raw', df)
        
        # Group by both contract fields
        assets_by_contract_acn = defaultdict(list)
        assets_by_contract_vlocity = defaultdict(list)
        
        for _, row in df.iterrows():
            asset_dict = row.to_dict()
            
            acn_contract = row.get('acn_fld_Contract__c')
            vlocity_contract = row.get('vlocity_cmt__ContractId__c')
            
            if pd.notna(acn_contract) and acn_contract:
                assets_by_contract_acn[acn_contract].append(asset_dict)
            
            if pd.notna(vlocity_contract) and vlocity_contract:
                assets_by_contract_vlocity[vlocity_contract].append(asset_dict)
        
        # Find contracts with multiple assets
        multi_asset_contracts_acn = {k: v for k, v in assets_by_contract_acn.items() if len(v) > 1}
        multi_asset_contracts_vlocity = {k: v for k, v in assets_by_contract_vlocity.items() if len(v) > 1}
        
        # Initialize Causística Manager
        causistica_mgr = CausisticaManager(self.get_causisticas())
        
        # Process contracts
        processed_contracts = set()
        
        for contract_id, contract_assets in multi_asset_contracts_acn.items():
            if contract_id not in processed_contracts:
                processed_contracts.add(contract_id)
                self._process_contract(
                    contract_id, contract_assets, causistica_mgr, 'acn_fld_Contract__c'
                )
        
        for contract_id, contract_assets in multi_asset_contracts_vlocity.items():
            if contract_id not in processed_contracts:
                processed_contracts.add(contract_id)
                self._process_contract(
                    contract_id, contract_assets, causistica_mgr, 'vlocity_cmt__ContractId__c'
                )
        
        # Get results
        df_result = causistica_mgr.to_dataframe()
        
        # Calculate metrics
        metrics = ScriptMetrics(total_records=len(df_result))
        
        metrics.add_metric(
            'total_contracts',
            len(processed_contracts),
            'Contratos con Múltiples Assets',
            '⚠️' if len(processed_contracts) > 0 else '✅'
        )
        
        # Metrics by causística
        for caus_id, count in causistica_mgr.get_counts().items():
            caus_def = causistica_mgr.get_causistica(caus_id)
            metrics.add_metric(
                f'caus_{caus_id.lower()}',
                count,
                caus_def.name[:25],
                '❌' if caus_id == 'ERROR_FECHAS' else '📊'
            )
        
        return ScriptResult(
            success=True,
            data=df_result,
            metrics=metrics
        )
    
    def _process_contract(
        self, 
        contract_id: str, 
        contract_assets: List[Dict[str, Any]], 
        causistica_mgr: CausisticaManager,
        link_field: str
    ):
        """Process a single contract with multiple assets."""
        
        # Sort by CreatedDate (oldest first)
        sorted_assets = sorted(
            contract_assets,
            key=lambda x: x.get('CreatedDate', '') or ''
        )
        
        if len(sorted_assets) < 2:
            return
        
        oldest_asset = sorted_assets[0]
        newest_asset = sorted_assets[-1]
        
        oldest_end_date = oldest_asset.get('acn_fld_EndDateVersion__c')
        oldest_start_date = oldest_asset.get('acn_fld_StartDateVersion__c')
        newest_start_date = newest_asset.get('acn_fld_StartDateVersion__c')
        
        # Common result data
        result_data = {
            'ContractId': contract_id,
            'LinkField': link_field,
            'AssetCount': len(contract_assets),
            'OldestAssetId': oldest_asset.get('Id'),
            'OldestAssetName': oldest_asset.get('Name'),
            'OldestAssetCreatedDate': oldest_asset.get('CreatedDate'),
            'OldestAssetStartDate': oldest_start_date,
            'OldestAssetEndDate': oldest_end_date,
            'NewestAssetStartDate': newest_start_date
        }
        
        # CAUSÍSTICA 1: Asset más viejo CON EndDateVersion
        if pd.notna(oldest_end_date) and oldest_end_date:
            result = CausisticaResult(
                causistica_id='CON_END_DATE',
                entity_id=contract_id,
                entity_type='Contract',
                data=result_data,
                update_data={
                    'Id': oldest_asset.get('Id'),
                    'Status': '05',
                    'vlocity_cmt__ProvisioningStatus__c': 'Retired',
                    'vlocity_cmt__Action__c': 'Disconnect'
                }
            )
            causistica_mgr.add_result(result)
            return
        
        # CAUSÍSTICA 2: Asset más viejo SIN EndDateVersion
        if not oldest_start_date or not newest_start_date:
            result_data['ErrorReason'] = 'Fechas de inicio no informadas'
            result = CausisticaResult(
                causistica_id='ERROR_FECHAS',
                entity_id=contract_id,
                entity_type='Contract',
                data=result_data
            )
            causistica_mgr.add_result(result)
            return
        
        try:
            oldest_start_dt = self._parse_date(oldest_start_date)
            newest_start_dt = self._parse_date(newest_start_date)
            
            if not oldest_start_dt or not newest_start_dt:
                raise ValueError("Error parsing dates")
            
            # VALIDACIÓN PREVIA: Fechas iniciales iguales
            if oldest_start_dt == newest_start_dt:
                new_end_date = oldest_start_dt
                status = '21'  # Sin Vigencia
                result_data['CalculatedEndDate'] = new_end_date.isoformat()
                result_data['CalculationNote'] = 'Fechas iniciales iguales → EndDate=StartDate, Status=21'
                
                result = CausisticaResult(
                    causistica_id='SIN_END_DATE',
                    entity_id=contract_id,
                    entity_type='Contract',
                    data=result_data,
                    update_data={
                        'Id': oldest_asset.get('Id'),
                        'acn_fld_EndDateVersion__c': new_end_date.isoformat(),
                        'Status': status,
                        'vlocity_cmt__ProvisioningStatus__c': 'Retired',
                        'vlocity_cmt__Action__c': 'Disconnect'
                    }
                )
                causistica_mgr.add_result(result)
                return
            
            # Calcular EndDate: StartDate del más nuevo - 1 día
            new_end_date = newest_start_dt - timedelta(days=1)
            
            # Validar: StartDate <= EndDate
            if oldest_start_dt > new_end_date:
                result_data['CalculatedEndDate'] = new_end_date.isoformat()
                result_data['ErrorReason'] = f'StartDate ({oldest_start_dt.isoformat()}) > EndDate calculado ({new_end_date.isoformat()})'
                
                result = CausisticaResult(
                    causistica_id='ERROR_FECHAS',
                    entity_id=contract_id,
                    entity_type='Contract',
                    data=result_data
                )
                causistica_mgr.add_result(result)
                return
            
            # Determinar Status según comparación de fechas
            if oldest_start_dt == new_end_date:
                status = '21'  # Sin Vigencia
                calculation_note = 'StartDate = EndDate calculado → Status=21'
            else:
                status = '05'  # Modificado
                calculation_note = 'StartDate < EndDate calculado → Status=05'
            
            result_data['CalculatedEndDate'] = new_end_date.isoformat()
            result_data['CalculationNote'] = calculation_note
            
            result = CausisticaResult(
                causistica_id='SIN_END_DATE',
                entity_id=contract_id,
                entity_type='Contract',
                data=result_data,
                update_data={
                    'Id': oldest_asset.get('Id'),
                    'acn_fld_EndDateVersion__c': new_end_date.isoformat(),
                    'Status': status,
                    'vlocity_cmt__ProvisioningStatus__c': 'Retired',
                    'vlocity_cmt__Action__c': 'Disconnect'
                }
            )
            causistica_mgr.add_result(result)
            
        except Exception as e:
            result_data['ErrorReason'] = f'Exception: {str(e)}'
            result = CausisticaResult(
                causistica_id='ERROR_FECHAS',
                entity_id=contract_id,
                entity_type='Contract',
                data=result_data
            )
            causistica_mgr.add_result(result)
    
    def _parse_date(self, date_str):
        """Parse date safely."""
        try:
            if not date_str or pd.isna(date_str):
                return None
            date_str = str(date_str).replace('Z', '+00:00')
            return datetime.fromisoformat(date_str).date()
        except Exception:
            return None
    
    def get_column_config(self) -> list[ColumnConfig]:
        """Define column configuration."""
        return [
            ColumnConfig('ContractId', 'Contrato', ColumnType.LINK),
            ColumnConfig('causistica_name', 'Causística', ColumnType.TEXT),
            ColumnConfig('AssetCount', 'Nº Assets Baja', ColumnType.NUMBER),
            ColumnConfig('OldestAssetName', 'Asset Más Viejo', ColumnType.TEXT),
            ColumnConfig('OldestAssetStartDate', 'Fecha Inicio (Viejo)', ColumnType.DATE),
            ColumnConfig('OldestAssetEndDate', 'Fecha Fin (Viejo)', ColumnType.DATE),
            ColumnConfig('CalculatedEndDate', 'Fecha Fin Calculada', ColumnType.DATE),
            ColumnConfig('CalculationNote', 'Nota', ColumnType.TEXT),
            ColumnConfig('ErrorReason', 'Error', ColumnType.TEXT),
        ]
    
    def get_groupby_options(self) -> list[str]:
        """Return columns for grouping."""
        return ['causistica_name', 'AssetCount', 'LinkField']
    
    def prepare_update_data(self, data: pd.DataFrame, selected_ids: list[str]) -> list[dict]:
        """Prepare update records from causística results."""
        updates = []
        
        for _, row in data.iterrows():
            if row.get('ContractId') not in selected_ids:
                continue
            
            # Skip ERROR_FECHAS causística (requires manual review)
            if row.get('causistica_id') == 'ERROR_FECHAS':
                continue
            
            update_record = row.get('update_data')
            if update_record and isinstance(update_record, dict):
                updates.append(update_record)
        
        return updates
    
    def detect_anomalies(self, data: pd.DataFrame) -> pd.DataFrame:
        """Contracts with ERROR_FECHAS are high-severity anomalies."""
        if data.empty:
            return pd.DataFrame()
        
        anomalies = data[data['causistica_id'] == 'ERROR_FECHAS'].copy()
        
        if anomalies.empty:
            return pd.DataFrame()
        
        anomalies['anomaly_type'] = 'Fechas Inconsistentes'
        anomalies['anomaly_severity'] = 'Alta'
        
        return anomalies
    
    def get_chart_recommendations(self) -> list[dict]:
        """Recommend charts."""
        return [
            {
                'type': 'pie',
                'names': 'causistica_name',
                'title': 'Por Causística'
            },
            {
                'type': 'bar',
                'x': 'AssetCount',
                'title': 'Por Nº de Assets'
            }
        ]
