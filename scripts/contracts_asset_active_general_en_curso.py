"""
Script: Contratos con Asset Activo y Estados Incompatibles (COMPLETO)

PRESERVA 100% DE LA LÓGICA DEL NOTEBOOK ContractsAssetActiveAndGeneralEnCurso.ipynb

Detecta contratos con asset activo ('03') y assets en estados incompatibles.
Estados incompatibles: 01,06,07,09,10,12,11,17,18,22,23,24,25,26,27,29
Aparece en Omega como doble contrato activo.
"""
import pandas as pd
from core.base_script import BaseScript, ScriptResult, ScriptMetrics, ColumnConfig, ColumnType
from core.script_registry import register_script
from config import ASSET_STATUS_MAP


@register_script
class ContractsAssetActiveAndGeneralEnCurso(BaseScript):
    """
    Detecta contratos con asset activo y estados incompatibles.
    Preserva 100% de la lógica del notebook: 17 estados (03 + 16 incompatibles).
    """
    
    name = "Contratos - Activo y Estados Incompatibles"
    description = "Detecta contratos con asset activo y estados incompatibles (16 estados)"
    category = "Detección de inconsistencias"
    version = "2.0"
    author = "AG"
    
    supports_preview = True
    supports_update = False
    requires_confirmation = False
    
    # ESTADOS DEL NOTEBOOK - COMPLETOS
    ASSET_STATUS_ACTIVE = '03'
    # TODOS los estados incompatibles del notebook
    INCOMPATIBLE_STATUSES = ['01', '06', '07', '09', '10', '12', '11', '17', '18', '22', '23', '24', '25', '26', '27', '29']
    
    def get_queries(self, preview: bool = False) -> list[str]:
        """Return query for assets (QUERY COMPLETA DEL NOTEBOOK - 17 estados)."""
        limit_clause = "LIMIT 5000" if preview else ""
        
        # QUERY EXACTA DEL NOTEBOOK: Status 03 + TODOS los incompatibles
        all_statuses = [self.ASSET_STATUS_ACTIVE] + self.INCOMPATIBLE_STATUSES
        status_list = ','.join([f"'{s}'" for s in all_statuses])
        
        query = f"""
            SELECT Id, Name, Status, 
                   acn_fld_Contract__c, 
                   vlocity_cmt__ContractId__c,
                   acn_fld_Contract__r.ContractNumber,
                   CreatedDate, 
                   acn_fld_EndDateVersion__c, 
                   acn_fld_StartDateVersion__c
            FROM Asset 
            WHERE Status IN ({status_list})
            AND vlocity_cmt__ParentItemId__c = NULL 
            AND (acn_fld_Contract__c != null OR vlocity_cmt__ContractId__c != null)
            {limit_clause}
        """
        
        return [query]
    
    def process(self, query_results: dict[str, pd.DataFrame]) -> ScriptResult:
        """Process assets to find contracts with both states (LÓGICA DEL NOTEBOOK)."""
        df = query_results.get('query_0', pd.DataFrame())
        
        if df.empty:
            return ScriptResult(
                success=True,
                data=pd.DataFrame(),
                metrics=ScriptMetrics(total_records=0)
            )
        
        self.store_intermediate('assets_raw', df)
        
        # LÓGICA DEL NOTEBOOK: Group by AMBOS campos (acn_fld_Contract__c Y vlocity_cmt__ContractId__c)
        contract_assets_acn = {}
        contract_assets_vlocity = {}
        
        for _, asset in df.iterrows():
            asset_dict = asset.to_dict()
            
            acn_contract = asset_dict.get('acn_fld_Contract__c')
            if acn_contract and acn_contract != '':
                if acn_contract not in contract_assets_acn:
                    contract_assets_acn[acn_contract] = []
                contract_assets_acn[acn_contract].append(asset_dict)
            
            vlocity_contract = asset_dict.get('vlocity_cmt__ContractId__c')
            if vlocity_contract and vlocity_contract != '':
                if vlocity_contract not in contract_assets_vlocity:
                    contract_assets_vlocity[vlocity_contract] = []
                contract_assets_vlocity[vlocity_contract].append(asset_dict)
        
        # LÓGICA DEL NOTEBOOK: Filtrar contratos con asset activo Y estado incompatible
        def has_active_and_incompatible(assets):
            """Check if contract has asset '03' AND any incompatible status"""
            statuses = set(a['Status'] for a in assets)
            has_active = self.ASSET_STATUS_ACTIVE in statuses
            has_incompatible = any(status in self.INCOMPATIBLE_STATUSES for status in statuses)
            return has_active and has_incompatible
        
        contracts_with_both_acn = {k: v for k, v in contract_assets_acn.items() if has_active_and_incompatible(v)}
        contracts_with_both_vlocity = {k: v for k, v in contract_assets_vlocity.items() if has_active_and_incompatible(v)}
        
        # Procesar y evitar duplicados
        results = []
        processed_contracts = set()
        
        def process_contract_group(contract_id, assets, link_field):
            if contract_id in processed_contracts:
                return None
            processed_contracts.add(contract_id)
            
            # Separar por status
            active_assets = [a for a in assets if a['Status'] == self.ASSET_STATUS_ACTIVE]
            incompatible_assets = [a for a in assets if a['Status'] in self.INCOMPATIBLE_STATUSES]
            
            if not active_assets or not incompatible_assets:
                return None
            
            # Obtener el asset activo más viejo
            active_asset = sorted(active_assets, key=lambda x: x['CreatedDate'] if x['CreatedDate'] else '')[0]
            
            # Contar assets por status
            status_counts = {}
            for asset in assets:
                status = asset['Status']
                status_counts[status] = status_counts.get(status, 0) + 1
            
            return {
                'ContractId': contract_id,
                'LinkField': link_field,
                'ContractNumber': assets[0].get('acn_fld_Contract__r.ContractNumber', ''),
                'ActiveAssetId': active_asset['Id'],
                'ActiveAssetName': active_asset['Name'],
                'IncompatibleAssetCount': len(incompatible_assets),
                'IncompatibleStatuses': ', '.join(sorted(set(a['Status'] for a in incompatible_assets))),
                'TotalAssets': len(assets)
            }
        
        # Procesar ambos grupos
        for contract_id, assets in contracts_with_both_acn.items():
            result = process_contract_group(contract_id, assets, 'acn_fld_Contract__c')
            if result:
                results.append(result)
        
        for contract_id, assets in contracts_with_both_vlocity.items():
            result = process_contract_group(contract_id, assets, 'vlocity_cmt__ContractId__c')
            if result:
                results.append(result)
        
        df_result = pd.DataFrame(results)
        
        # Calculate metrics
        metrics = ScriptMetrics(
            total_records=len(df_result),
            message=f"{len(df_result)} contratos con asset activo y estados incompatibles"
        )
        
        metrics.add_metric(
            'contracts_affected',
            len(df_result),
            'Contratos Afectados',
            '⚠️' if len(df_result) > 0 else '✅'
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
            ColumnConfig('LinkField', 'Campo Link', ColumnType.TEXT),
            ColumnConfig('ActiveAssetId', 'Asset Activo ID', ColumnType.LINK),
            ColumnConfig('IncompatibleAssetCount', '# Assets Incompatibles', ColumnType.NUMBER),
            ColumnConfig('IncompatibleStatuses', 'Estados Incompatibles', ColumnType.TEXT),
            ColumnConfig('TotalAssets', 'Total Assets', ColumnType.NUMBER),
        ]
    
    def get_groupby_options(self) -> list[str]:
        """Return columns for grouping."""
        return ['ActiveAssetCount', 'GeneralEnCursoCount']
    
    def detect_anomalies(self, data: pd.DataFrame) -> pd.DataFrame:
        """All contracts with both states are anomalies."""
        if data.empty:
            return pd.DataFrame()
        
        anomalies = data.copy()
        anomalies['anomaly_type'] = 'Activo y General En Curso'
        anomalies['anomaly_severity'] = 'Media'
        
        return anomalies
    
    def get_chart_recommendations(self) -> list[dict]:
        """Recommend charts."""
        return [
            {
                'type': 'bar',
                'x': 'TotalAssets',
                'title': 'Por Total de Assets'
            }
        ]
