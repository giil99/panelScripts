"""
Script: Desajuste Tarifa Service Point

Detecta desajustes entre la tarifa del contrato/asset y la del Service Point.
Esto puede causar errores en la facturación y en los procesos de switching.
"""
import pandas as pd
from core.base_script import BaseScript, ScriptResult, ScriptMetrics, ColumnConfig, ColumnType
from core.script_registry import register_script
from config import ASSET_STATUS_MAP


@register_script
class DesajusteTarifaServicePoint(BaseScript):
    """
    Detecta desajustes entre tarifa del asset y service point.
    """
    
    name = "Desajuste Tarifa Service Point"
    description = "Detecta inconsistencias entre tarifa del asset y service point"
    category = "Detección de inconsistencias"
    version = "1.0"
    author = "AG"
    
    supports_preview = True
    supports_update = True
    requires_confirmation = True
    
    def get_queries(self, preview: bool = False) -> list[str]:
        """Return queries for assets and service points."""
        limit_clause = "LIMIT 2000" if preview else ""
        
        # Query for assets with their service point tariff
        query = f"""
            SELECT Id, Name, Status, acn_fld_Contract__c, 
                   acn_fld_Contract__r.ContractNumber,
                   acn_fld_Contract__r.acn_fld_CUPS__c,
                   acn_fld_Contract__r.acn_fld_CUPS__r.Name,
                   acn_fld_Contract__r.acn_fld_CUPS__r.acn_fld_Tarifa__c,
                   NewCo_Tarifa__c, CreatedDate
            FROM Asset
            WHERE vlocity_cmt__ParentItemId__c = null
            AND acn_fld_Contract__r.Status = '02'
            AND Status = '03'
            {limit_clause}
        """
        
        return [query]
    
    def process(self, query_results: dict[str, pd.DataFrame]) -> ScriptResult:
        """Process assets to find tariff mismatches."""
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
            asset_tariff = row.get('NewCo_Tarifa__c', '')
            sp_tariff = row.get('acn_fld_Contract__r.acn_fld_CUPS__r.acn_fld_Tarifa__c', '')
            
            # Skip if either is empty
            if not asset_tariff or not sp_tariff:
                continue
            
            # Check for mismatch
            if str(asset_tariff).strip() != str(sp_tariff).strip():
                mismatches.append({
                    'AssetId': row['Id'],
                    'AssetName': row['Name'],
                    'ContractId': row['acn_fld_Contract__c'],
                    'ContractNumber': row.get('acn_fld_Contract__r.ContractNumber', ''),
                    'CUPS': row.get('acn_fld_Contract__r.acn_fld_CUPS__r.Name', ''),
                    'AssetTariff': asset_tariff,
                    'ServicePointTariff': sp_tariff,
                    'Status': row['Status'],
                    'CreatedDate': row['CreatedDate']
                })
        
        df_result = pd.DataFrame(mismatches)
        
        # Calculate metrics
        metrics = ScriptMetrics(total_records=len(df_result))
        
        metrics.add_metric(
            'tariff_mismatches',
            len(df_result),
            'Desajustes de Tarifa',
            '🔴' if len(df_result) > 0 else '✅'
        )
        
        metrics.add_metric(
            'total_assets_checked',
            len(df),
            'Assets Verificados',
            '📊'
        )
        
        if len(df) > 0:
            mismatch_rate = (len(df_result) / len(df)) * 100
            metrics.add_metric(
                'mismatch_rate',
                round(mismatch_rate, 2),
                '% Desajustes',
                '📈'
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
            ColumnConfig('CUPS', 'CUPS', ColumnType.TEXT),
            ColumnConfig('AssetName', 'Asset', ColumnType.TEXT),
            ColumnConfig('AssetTariff', 'Tarifa Asset', ColumnType.TEXT),
            ColumnConfig('ServicePointTariff', 'Tarifa SP', ColumnType.TEXT),
            ColumnConfig('CreatedDate', 'Creado', ColumnType.DATETIME),
        ]
    
    def get_groupby_options(self) -> list[str]:
        """Return columns for grouping."""
        return ['AssetTariff', 'ServicePointTariff']
    
    def detect_anomalies(self, data: pd.DataFrame) -> pd.DataFrame:
        """All mismatches are anomalies."""
        if data.empty:
            return pd.DataFrame()
        
        anomalies = data.copy()
        anomalies['anomaly_type'] = 'Desajuste Tarifa Asset/SP'
        anomalies['anomaly_severity'] = 'Media'
        
        return anomalies
    
    def get_chart_recommendations(self) -> list[dict]:
        """Recommend charts."""
        return [
            {
                'type': 'bar',
                'x': 'AssetTariff',
                'title': 'Desajustes por Tarifa Asset'
            },
            {
                'type': 'bar',
                'x': 'ServicePointTariff',
                'title': 'Desajustes por Tarifa SP'
            }
        ]
    
    def get_update_operations(self) -> list[dict]:
        """Define update operations."""
        return [
            {
                'name': 'sync_tariff_to_sp',
                'description': 'Sincronizar tarifa del Asset al Service Point',
                'fields': {
                    'acn_fld_Tarifa__c': '(tarifa del asset)'
                }
            }
        ]
