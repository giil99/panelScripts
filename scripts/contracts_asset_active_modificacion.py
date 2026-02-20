"""
Script: Contratos con Asset Activo y Modificación en Curso

Detecta contratos que tienen un asset en estado '03' (Activo) 
y otro en estado '04' (Modificación en curso).
"""
import pandas as pd
from core.base_script import BaseScript, ScriptResult, ScriptMetrics, ColumnConfig, ColumnType
from core.script_registry import register_script
from config import ASSET_STATUS_MAP


@register_script
class ContractsAssetActiveAndModificacion(BaseScript):
    """
    Detecta contratos con asset activo y modificación en curso.
    """
    
    name = "Contratos - Activo y Modificación En Curso"
    description = "Detecta contratos con asset activo y modificación en curso"
    category = "Detección de inconsistencias"
    version = "1.0"
    author = "AG"
    
    supports_preview = True
    supports_update = False
    requires_confirmation = False
    
    # Status codes
    ASSET_STATUS_ACTIVE = '03'
    ASSET_STATUS_MOD_EN_CURSO = '04'  # Modificación en curso
    
    def get_queries(self, preview: bool = False) -> list[str]:
        """Return query for assets."""
        limit_clause = "LIMIT 5000" if preview else ""
        
        query = f"""
            SELECT Id, Name, Status, acn_fld_Contract__c, 
                   acn_fld_Contract__r.ContractNumber,
                   CreatedDate, acn_fld_EndDateVersion__c, acn_fld_StartDateVersion__c
            FROM Asset 
            WHERE Status IN ('{self.ASSET_STATUS_ACTIVE}', '{self.ASSET_STATUS_MOD_EN_CURSO}')
            AND vlocity_cmt__ParentItemId__c = NULL 
            AND acn_fld_Contract__c != null
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
        
        # Group by contract
        contract_assets = df.groupby('acn_fld_Contract__c').apply(
            lambda x: x.to_dict('records')
        ).to_dict()
        
        # Find contracts with both statuses
        results = []
        
        for contract_id, assets in contract_assets.items():
            if not contract_id:
                continue
            
            statuses = set(a.get('Status') for a in assets)
            if self.ASSET_STATUS_ACTIVE in statuses and self.ASSET_STATUS_MOD_EN_CURSO in statuses:
                active_assets = [a for a in assets if a['Status'] == self.ASSET_STATUS_ACTIVE]
                mod_assets = [a for a in assets if a['Status'] == self.ASSET_STATUS_MOD_EN_CURSO]
                
                results.append({
                    'ContractId': contract_id,
                    'ContractNumber': assets[0].get('acn_fld_Contract__r.ContractNumber', ''),
                    'ActiveAssetCount': len(active_assets),
                    'ModEnCursoCount': len(mod_assets),
                    'ActiveAssetIds': '; '.join([a['Id'] for a in active_assets]),
                    'ModAssetIds': '; '.join([a['Id'] for a in mod_assets]),
                    'TotalAssets': len(assets)
                })
        
        df_result = pd.DataFrame(results)
        
        # Calculate metrics
        metrics = ScriptMetrics(total_records=len(df_result))
        
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
            ColumnConfig('ActiveAssetCount', 'Assets Activos', ColumnType.NUMBER),
            ColumnConfig('ModEnCursoCount', 'Mod. En Curso', ColumnType.NUMBER),
            ColumnConfig('TotalAssets', 'Total Assets', ColumnType.NUMBER),
        ]
    
    def get_groupby_options(self) -> list[str]:
        """Return columns for grouping."""
        return ['ActiveAssetCount', 'ModEnCursoCount']
    
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
                'x': 'TotalAssets',
                'title': 'Por Total de Assets'
            }
        ]
