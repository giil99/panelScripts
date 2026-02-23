"""
Script: Assets Hijos sin Padre (Regularización)

Detecta y repara assets hijos que quedaron huérfanos sin asociar al padre.
Estos aparecen incorrectamente en la página del contrato.

Lógica:
1. Buscar assets hijos huérfanos (sin parent, sin ProductServiceCRMId, etc.)
2. Obtener TODOS los assets de los contratos afectados
3. Identificar padres válidos: ProductServiceCRMId != null, ProductFamily = Gas/Electricidad
4. Identificar padres sin hijos (que NO tienen assets con ParentId = padre.Id)
5. Asignar huérfanos al primer padre sin hijos del contrato:
   - ParentId = padre.Id
   - vlocity_cmt__ParentItemId__c = padre.vlocity_cmt__RootItemId__c (o AssetReferenceId)
   - vlocity_cmt__RootItemId__c = padre.vlocity_cmt__RootItemId__c (o AssetReferenceId)

Condiciones de búsqueda de huérfanos:
- NewCo_ProductServiceCRMId__c = null
- acn_fld_Contract__c != null
- ParentId = null
- Product2.ProductCode != 'S0012'
- ProductFamily != 'Gas' y != 'Electricidad'
"""
import pandas as pd
from collections import defaultdict
from typing import List, Dict, Any
from core.base_script import BaseScript, ScriptResult, ScriptMetrics, ColumnConfig, ColumnType
from core.script_registry import register_script
from config import ASSET_STATUS_MAP


@register_script
class AssetsHijosSinPadre(BaseScript):
    """
    Detecta y repara assets hijos sin padre asociado.
    """
    
    name = "Assets Hijos sin Padre"
    description = "Repara assets hijos huérfanos asociándolos al padre correcto"
    category = "Regularización"
    version = "2.0"
    author = "AG"
    
    supports_preview = True
    supports_update = True
    requires_confirmation = True
    
    def get_queries(self, preview: bool = False) -> list[str]:
        """Return queries for orphan child assets and parent assets."""
        limit_clause = "LIMIT 1000" if preview else ""
        
        # Query 1: Assets hijos huérfanos
        query_orphans = f"""
            SELECT Id, Status, acn_fld_Contract__c, acn_fld_Contract__r.Status, 
                   Product2.Name, Product2.ProductCode, ParentId,
                   Parent.vlocity_cmt__RootItemId__c, vlocity_cmt__ParentItemId__c,  
                   vlocity_cmt__AssetReferenceId__c, vlocity_cmt__ProvisioningStatus__c, 
                   vlocity_cmt__Action__c, CreatedDate,
                   vlocity_cmt__OrderProductId__r.Order.vlocity_cmt__OriginatingChannel__c,
                   ProductFamily
            FROM Asset 
            WHERE NewCo_ProductServiceCRMId__c = null 
            AND acn_fld_Contract__c != null
            AND ParentId = null 
            AND Product2.ProductCode != 'S0012' 
            AND ProductFamily != 'Gas' 
            AND ProductFamily != 'Electricidad'
            {limit_clause}
        """
        
        return [query_orphans]
    
    def process(self, query_results: dict[str, pd.DataFrame]) -> ScriptResult:
        """Process orphan child assets and find parent assets to associate them."""
        df_orphans = query_results.get('query_0', pd.DataFrame())
        
        if df_orphans.empty:
            return ScriptResult(
                success=True,
                data=pd.DataFrame(),
                metrics=ScriptMetrics(total_records=0)
            )
        
        self.store_intermediate('orphans_raw', df_orphans)
        
        # Group orphans by contract
        orphans_by_contract = defaultdict(list)
        for _, row in df_orphans.iterrows():
            contract_id = row.get('acn_fld_Contract__c')
            if contract_id:
                orphans_by_contract[contract_id].append(row.to_dict())
        
        # Get unique contract IDs
        contract_ids = list(orphans_by_contract.keys())
        
        if not contract_ids:
            return ScriptResult(
                success=True,
                data=pd.DataFrame(),
                metrics=ScriptMetrics(total_records=0)
            )
        
        # Query 2: Get ALL assets from affected contracts to find parent candidates
        # We need to use vlocity_cmt__ContractId__c for this secondary query
        contract_ids_str = "','".join(contract_ids)
        
        query_all_assets = f"""
            SELECT Id, vlocity_cmt__ContractId__c,
                   vlocity_cmt__ContractId__r.acn_fld_ContractCode2__c,
                   Status, ParentId, vlocity_cmt__ParentItemId__c,
                   vlocity_cmt__RootItemId__c, vlocity_cmt__AssetReferenceId__c,
                   NewCo_ProductServiceCRMId__c, Product2.Name, Product2.ProductCode,
                   ProductFamily, acn_fld_StartDateVersion__c, CreatedDate
            FROM Asset
            WHERE vlocity_cmt__ContractId__c IN ('{contract_ids_str}')
        """
        
        # Execute second query using internal query method
        df_all_assets = self._execute_additional_query(query_all_assets)
        
        self.store_intermediate('all_assets_raw', df_all_assets)
        
        # Process: Find parents and associate orphans
        results = self._find_and_associate_parents(orphans_by_contract, df_all_assets)
        
        df_result = pd.DataFrame(results)
        
        # Calculate metrics
        metrics = ScriptMetrics(total_records=len(df_result))
        
        metrics.add_metric(
            'orphan_assets',
            len(df_orphans),
            'Assets Huérfanos',
            '🔴'
        )
        
        metrics.add_metric(
            'affected_contracts',
            len(orphans_by_contract),
            'Contratos Afectados',
            '📋'
        )
        
        if not df_result.empty:
            can_assign = len(df_result[df_result['CanAssign'] == True])
            cannot_assign = len(df_result[df_result['CanAssign'] == False])
            
            metrics.add_metric(
                'can_assign',
                can_assign,
                'Assets Asignables',
                '✅' if can_assign > 0 else '⚠️'
            )
            
            metrics.add_metric(
                'cannot_assign',
                cannot_assign,
                'Sin Padre Disponible',
                '⚠️' if cannot_assign > 0 else '✅'
            )
        
        return ScriptResult(
            success=True,
            data=df_result,
            metrics=metrics
        )
    
    def _execute_additional_query(self, query: str) -> pd.DataFrame:
        """Execute an additional SOQL query using the Salesforce client."""
        try:
            from data.salesforce_client import get_salesforce_client
            sf = get_salesforce_client()
            
            # Use Bulk API for large results
            from data.bulk_api import run_bulk_query
            results = run_bulk_query(sf, query)
            
            return pd.DataFrame(results)
        except Exception as e:
            print(f"Warning: Could not execute additional query: {e}")
            return pd.DataFrame()
    
    def _find_and_associate_parents(
        self, 
        orphans_by_contract: Dict[str, List[Dict[str, Any]]],
        df_all_assets: pd.DataFrame
    ) -> List[Dict[str, Any]]:
        """Find parent assets without children and prepare associations."""
        
        results = []
        
        # Group all assets by contract
        all_assets_by_contract = defaultdict(list)
        for _, row in df_all_assets.iterrows():
            contract_id = row.get('vlocity_cmt__ContractId__c')
            if contract_id:
                all_assets_by_contract[contract_id].append(row.to_dict())
        
        # Process each contract with orphans
        for contract_id, orphans in orphans_by_contract.items():
            all_assets = all_assets_by_contract.get(contract_id, [])
            
            if not all_assets:
                # No assets found for this contract in secondary query
                for orphan in orphans:
                    results.append({
                        'OrphanAssetId': orphan.get('Id'),
                        'OrphanAssetName': orphan.get('Product2.Name', ''),
                        'OrphanProductCode': orphan.get('Product2.ProductCode', ''),
                        'ContractId': contract_id,
                        'ParentAssetId': None,
                        'ParentAssetName': None,
                        'ParentRootItemId': None,
                        'CanAssign': False,
                        'Reason': 'No assets found in secondary query'
                    })
                continue
            
            # Identify valid parents
            valid_parents = []
            for asset in all_assets:
                parent_item_id = asset.get('vlocity_cmt__ParentItemId__c')
                product_service_crm_id = asset.get('NewCo_ProductServiceCRMId__c')
                product_family = asset.get('ProductFamily', '')
                product_code = asset.get('Product2.ProductCode', '')
                
                # Valid parent criteria
                if (not parent_item_id or parent_item_id == '') and \
                   product_service_crm_id and \
                   (product_family == 'Gas' or product_family == 'Electricidad') and \
                   product_code != 'S0012':
                    valid_parents.append(asset)
            
            # Find parents without children
            parents_without_children = []
            for parent in valid_parents:
                parent_id = parent.get('Id')
                has_children = False
                
                # Check if any asset has this parent_id as ParentId
                for asset in all_assets:
                    if asset.get('ParentId') == parent_id:
                        has_children = True
                        break
                
                if not has_children:
                    parents_without_children.append(parent)
            
            # Assign orphans to first available parent
            if parents_without_children:
                parent = parents_without_children[0]
                parent_id = parent.get('Id')
                parent_root_item_id = parent.get('vlocity_cmt__RootItemId__c')
                parent_asset_reference_id = parent.get('vlocity_cmt__AssetReferenceId__c')
                
                # Use RootItemId if available, otherwise AssetReferenceId
                value_to_assign = parent_root_item_id if parent_root_item_id else parent_asset_reference_id
                
                for orphan in orphans:
                    results.append({
                        'OrphanAssetId': orphan.get('Id'),
                        'OrphanAssetName': orphan.get('Product2.Name', ''),
                        'OrphanProductCode': orphan.get('Product2.ProductCode', ''),
                        'ContractId': contract_id,
                        'ParentAssetId': parent_id,
                        'ParentAssetName': parent.get('Product2.Name', ''),
                        'ParentProductCode': parent.get('Product2.ProductCode', ''),
                        'ParentRootItemId': value_to_assign,
                        'CanAssign': bool(value_to_assign),
                        'Reason': 'Parent found and ready to assign' if value_to_assign else 'Parent has no RootItemId/AssetReferenceId'
                    })
            else:
                # No parent available
                for orphan in orphans:
                    results.append({
                        'OrphanAssetId': orphan.get('Id'),
                        'OrphanAssetName': orphan.get('Product2.Name', ''),
                        'OrphanProductCode': orphan.get('Product2.ProductCode', ''),
                        'ContractId': contract_id,
                        'ParentAssetId': None,
                        'ParentAssetName': None,
                        'ParentRootItemId': None,
                        'CanAssign': False,
                        'Reason': f'No parent without children available (total valid parents: {len(valid_parents)})'
                    })
        
        return results
    
    def get_column_config(self) -> list[ColumnConfig]:
        """Define column configuration."""
        return [
            ColumnConfig('OrphanAssetName', 'Asset Huérfano', ColumnType.TEXT),
            ColumnConfig('OrphanProductCode', 'Código Producto', ColumnType.TEXT),
            ColumnConfig('ContractId', 'Contrato', ColumnType.LINK),
            ColumnConfig('ParentAssetName', 'Padre Asignado', ColumnType.TEXT),
            ColumnConfig('ParentProductCode', 'Código Padre', ColumnType.TEXT),
            ColumnConfig('CanAssign', 'Puede Asignar', ColumnType.BOOLEAN),
            ColumnConfig('Reason', 'Estado/Razón', ColumnType.TEXT),
        ]
    
    def get_groupby_options(self) -> list[str]:
        """Return columns for grouping."""
        return ['ContractId', 'CanAssign', 'Reason']
    
    def prepare_update_data(self, data: pd.DataFrame, selected_ids: list[str]) -> list[dict]:
        """Prepare update records to associate orphans to parents."""
        updates = []
        
        for _, row in data.iterrows():
            orphan_id = row.get('OrphanAssetId')
            
            if orphan_id not in selected_ids:
                continue
            
            if not row.get('CanAssign', False):
                continue
            
            parent_id = row.get('ParentAssetId')
            parent_root_item_id = row.get('ParentRootItemId')
            
            if parent_id and parent_root_item_id:
                updates.append({
                    'Id': orphan_id,
                    'ParentId': parent_id,
                    'vlocity_cmt__ParentItemId__c': parent_root_item_id,
                    'vlocity_cmt__RootItemId__c': parent_root_item_id
                })
        
        return updates
    
    def detect_anomalies(self, data: pd.DataFrame) -> pd.DataFrame:
        """Orphans that cannot be assigned are anomalies."""
        if data.empty:
            return pd.DataFrame()
        
        anomalies = data[data['CanAssign'] == False].copy()
        
        if anomalies.empty:
            return pd.DataFrame()
        
        anomalies['anomaly_type'] = 'Asset Hijo sin Padre Disponible'
        anomalies['anomaly_severity'] = 'Media'
        
        return anomalies
    
    def get_chart_recommendations(self) -> list[dict]:
        """Recommend charts."""
        return [
            {
                'type': 'pie',
                'names': 'CanAssign',
                'title': 'Asignabilidad'
            },
            {
                'type': 'bar',
                'x': 'Reason',
                'title': 'Por Razón'
            }
        ]
