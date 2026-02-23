"""
Script: Assets - Fecha Incorrecta (Gas)

Detecta assets de GAS donde un asset antiguo tiene fecha de inicio MAYOR que el más reciente
con la misma Directriz, lo que causa descuadres en Omega.

Lógica:
1. Query assets sin parent de contratos activos
2. Filtrar assets de GAS (name contiene 'gas')
3. Agrupar por contrato
4. Ordenar por CreatedDate descendente
5. Comparar: si un asset tiene StartDateVersion > más reciente Y misma Directriz → problema
"""
import pandas as pd
from datetime import datetime
from collections import defaultdict
from core.base_script import BaseScript, ScriptResult, ScriptMetrics, ColumnConfig, ColumnType
from core.script_registry import register_script
from config import ASSET_STATUS_MAP


@register_script
class AssetsFechaIncorrecta(BaseScript):
    """
    Detecta assets de Gas con fecha de inicio mayor que el más reciente (misma Directriz).
    """
    
    name = "Assets - Fecha Incorrecta (Gas)"
    description = "Assets Gas con StartDate > más reciente (misma Directriz)"
    category = "Detección de inconsistencias"
    version = "2.0"
    author = "AG"
    
    supports_preview = True
    supports_update = False
    requires_confirmation = False
    
    def get_queries(self, preview: bool = False) -> list[str]:
        """Return query for gas assets with date info."""
        limit_clause = "LIMIT 5000" if preview else ""
        
        query = f"""
            SELECT Id, acn_fld_StartDateVersion__c, acn_fld_EndDateVersion__c, 
                   acn_fld_Contract__c, acn_fld_Contract__r.acn_fld_ContractCode2__c,
                   acn_fld_CUPS__c, CreatedDate, Name, Status, NewCo_Directriz__c
            FROM Asset
            WHERE vlocity_cmt__ParentItemId__c = null
            AND acn_fld_Contract__r.Status = '02'
            {limit_clause}
        """
        
        return [query]
    
    def process(self, query_results: dict[str, pd.DataFrame]) -> ScriptResult:
        """Process gas assets to find date inconsistencies."""
        df = query_results.get('query_0', pd.DataFrame())
        
        if df.empty:
            return ScriptResult(
                success=True,
                data=pd.DataFrame(),
                metrics=ScriptMetrics(total_records=0)
            )
        
        self.store_intermediate('assets_raw', df)
        
        # Filter gas assets only
        df['Name'] = df['Name'].fillna('')
        gas_assets = df[df['Name'].str.lower().str.contains('gas', na=False)]
        
        self.store_intermediate('gas_assets', gas_assets)
        
        # Group by contract
        assets_by_contract = defaultdict(list)
        for _, row in gas_assets.iterrows():
            contract_id = row.get('acn_fld_Contract__c', '')
            if contract_id:
                assets_by_contract[contract_id].append(row.to_dict())
        
        # Find problematic contracts
        problematic_contracts = []
        
        for contract_id, contract_assets in assets_by_contract.items():
            # Need at least 2 assets
            if len(contract_assets) < 2:
                continue
            
            # Sort by CreatedDate descending (most recent first)
            sorted_assets = sorted(
                contract_assets,
                key=lambda a: self._safe_date(a.get('CreatedDate', '')) or datetime.min,
                reverse=True
            )
            
            most_recent = sorted_assets[0]
            most_recent_start_str = most_recent.get('acn_fld_StartDateVersion__c', '')
            most_recent_directriz = most_recent.get('NewCo_Directriz__c', '')
            
            if not most_recent_start_str:
                continue
            
            most_recent_start = self._safe_date(most_recent_start_str)
            if not most_recent_start:
                continue
            
            # Check all other assets
            for asset in sorted_assets[1:]:
                asset_start_str = asset.get('acn_fld_StartDateVersion__c', '')
                asset_directriz = asset.get('NewCo_Directriz__c', '')
                
                if not asset_start_str:
                    continue
                
                asset_start = self._safe_date(asset_start_str)
                if not asset_start:
                    continue
                
                # If this asset's start date is HIGHER than most recent's AND has same Directriz, it's problematic
                if asset_start > most_recent_start and asset_directriz == most_recent_directriz:
                    problematic_contracts.append({
                        'Contract_Id': contract_id,
                        'Contract_Code': most_recent.get('acn_fld_Contract__r.acn_fld_ContractCode2__c', ''),
                        'MostRecent_Name': most_recent.get('Name', ''),
                        'MostRecent_CreatedDate': most_recent.get('CreatedDate', ''),
                        'MostRecent_StartDateVersion': most_recent_start_str,
                        'MostRecent_EndDateVersion': most_recent.get('acn_fld_EndDateVersion__c', ''),
                        'MostRecent_Status': most_recent.get('Status', ''),
                        'MostRecent_StatusLabel': ASSET_STATUS_MAP.get(most_recent.get('Status', ''), most_recent.get('Status', '')),
                        'MostRecent_Directriz': most_recent_directriz,
                        'Problematic_Name': asset.get('Name', ''),
                        'Problematic_CreatedDate': asset.get('CreatedDate', ''),
                        'Problematic_StartDateVersion': asset_start_str,
                        'Problematic_EndDateVersion': asset.get('acn_fld_EndDateVersion__c', ''),
                        'Problematic_Status': asset.get('Status', ''),
                        'Problematic_StatusLabel': ASSET_STATUS_MAP.get(asset.get('Status', ''), asset.get('Status', '')),
                        'Problematic_Directriz': asset_directriz,
                        'Asset_Count': len(contract_assets)
                    })
                    break  # Only report first problematic asset per contract
        
        df_result = pd.DataFrame(problematic_contracts)
        
        # Calculate metrics
        metrics = ScriptMetrics(total_records=len(df_result))
        
        metrics.add_metric(
            'total_assets',
            len(df),
            'Total Assets',
            '📊'
        )
        
        metrics.add_metric(
            'gas_assets',
            len(gas_assets),
            'Assets Gas',
            '⚡'
        )
        
        metrics.add_metric(
            'contracts_analyzed',
            len(assets_by_contract),
            'Contratos Analizados',
            '📋'
        )
        
        metrics.add_metric(
            'problematic_contracts',
            len(df_result),
            'Contratos con Problema',
            '❌' if len(df_result) > 0 else '✅'
        )
        
        return ScriptResult(
            success=True,
            data=df_result,
            metrics=metrics
        )
    
    def _safe_date(self, date_str):
        """Parse date safely."""
        try:
            if not date_str or pd.isna(date_str):
                return None
            date_str = str(date_str).split('T')[0] if 'T' in str(date_str) else str(date_str)
            return datetime.strptime(date_str, '%Y-%m-%d')
        except Exception:
            return None
    
    def get_column_config(self) -> list[ColumnConfig]:
        """Define column configuration."""
        return [
            ColumnConfig('Contract_Code', 'Contrato', ColumnType.LINK),
            ColumnConfig('MostRecent_Name', 'Asset Reciente', ColumnType.TEXT),
            ColumnConfig('MostRecent_StartDateVersion', 'Fecha Inicio (Reciente)', ColumnType.DATE),
            ColumnConfig('MostRecent_StatusLabel', 'Estado (Reciente)', ColumnType.STATUS),
            ColumnConfig('MostRecent_Directriz', 'Directriz (Reciente)', ColumnType.TEXT),
            ColumnConfig('Problematic_Name', 'Asset Problemático', ColumnType.TEXT),
            ColumnConfig('Problematic_StartDateVersion', 'Fecha Inicio (Problem)', ColumnType.DATE),
            ColumnConfig('Problematic_StatusLabel', 'Estado (Problem)', ColumnType.STATUS),
            ColumnConfig('Problematic_Directriz', 'Directriz (Problem)', ColumnType.TEXT),
            ColumnConfig('Asset_Count', 'Total Assets', ColumnType.NUMBER),
        ]
    
    def get_groupby_options(self) -> list[str]:
        """Return columns for grouping."""
        return ['MostRecent_StatusLabel', 'Problematic_StatusLabel', 'MostRecent_Directriz']
    
    def detect_anomalies(self, data: pd.DataFrame) -> pd.DataFrame:
        """All contracts with date issues are anomalies."""
        if data.empty:
            return pd.DataFrame()
        
        anomalies = data.copy()
        anomalies['anomaly_type'] = 'Fecha Descuadre Gas'
        anomalies['anomaly_severity'] = 'Alta'
        
        return anomalies
    
    def get_chart_recommendations(self) -> list[dict]:
        """Recommend charts."""
        return [
            {
                'type': 'bar',
                'x': 'MostRecent_Directriz',
                'title': 'Por Directriz'
            },
            {
                'type': 'pie',
                'names': 'MostRecent_StatusLabel',
                'title': 'Estado Asset Reciente'
            }
        ]
