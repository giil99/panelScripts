"""
Script: Assets sin Contrato

Detecta assets que no tienen ningún contrato asociado.
Esto puede indicar un problema de integridad de datos donde los assets
quedaron huérfanos durante algún proceso.
"""
import pandas as pd
from core.base_script import BaseScript, ScriptResult, ScriptMetrics, ColumnConfig, ColumnType
from core.script_registry import register_script
from config import ASSET_STATUS_MAP


@register_script
class AssetsSinContrato(BaseScript):
    """
    Detecta assets sin contrato asociado.
    """
    
    name = "Assets sin Contrato"
    description = "Detecta assets huérfanos sin contrato asociado"
    category = "Detección de inconsistencias"
    version = "1.0"
    author = "AG"
    
    supports_preview = True
    supports_update = False
    requires_confirmation = False
    
    def get_queries(self, preview: bool = False) -> list[str]:
        """Return query for assets without contracts."""
        limit_clause = "LIMIT 1000" if preview else ""
        
        query = f"""
            SELECT Id, Name, Product2.ProductCode, Status, NewCo_OriginContractType__c, 
                   CreatedDate, vlocity_cmt__OrderProductId__r.NewCo_contractoffLK__c,
                   vlocity_cmt__OrderProductId__r.NewCo_contractoffLK__r.Status
            FROM Asset
            WHERE vlocity_cmt__ParentItemId__c = NULL 
            AND acn_fld_Contract__c = NULL
            {limit_clause}
        """
        
        return [query]
    
    def process(self, query_results: dict[str, pd.DataFrame]) -> ScriptResult:
        """Process assets without contracts."""
        df = query_results.get('query_0', pd.DataFrame())
        
        if df.empty:
            return ScriptResult(
                success=True,
                data=pd.DataFrame(),
                metrics=ScriptMetrics(total_records=0)
            )
        
        # Enrich with status labels
        df['StatusLabel'] = df['Status'].map(ASSET_STATUS_MAP)
        
        # Calculate metrics
        metrics = ScriptMetrics(total_records=len(df))
        
        # Count by status
        status_counts = df['Status'].value_counts()
        for status, count in status_counts.items():
            label = ASSET_STATUS_MAP.get(status, status)
            metrics.add_metric(
                f'status_{status}',
                count,
                f'En {label}',
                '📊'
            )
        
        # Active assets without contract (critical)
        active_count = len(df[df['Status'] == '03'])
        metrics.add_metric(
            'active_without_contract',
            active_count,
            'Activos sin Contrato',
            '🔴' if active_count > 0 else '✅'
        )
        
        return ScriptResult(
            success=True,
            data=df,
            metrics=metrics
        )
    
    def get_column_config(self) -> list[ColumnConfig]:
        """Define column configuration."""
        return [
            ColumnConfig('Name', 'Nombre Asset', ColumnType.TEXT),
            ColumnConfig('Product2.ProductCode', 'Código Producto', ColumnType.TEXT),
            ColumnConfig('StatusLabel', 'Estado', ColumnType.STATUS),
            ColumnConfig('NewCo_OriginContractType__c', 'Tipo Contrato Origen', ColumnType.TEXT),
            ColumnConfig('CreatedDate', 'Creado', ColumnType.DATETIME),
        ]
    
    def get_groupby_options(self) -> list[str]:
        """Return columns for grouping."""
        return ['StatusLabel', 'Status', 'Product2.ProductCode']
    
    def detect_anomalies(self, data: pd.DataFrame) -> pd.DataFrame:
        """Active assets without contract are anomalies."""
        if data.empty:
            return pd.DataFrame()
        
        anomalies = data[data['Status'] == '03'].copy()
        
        if anomalies.empty:
            return pd.DataFrame()
        
        anomalies['anomaly_type'] = 'Asset Activo sin Contrato'
        anomalies['anomaly_severity'] = 'Alta'
        
        return anomalies
    
    def get_chart_recommendations(self) -> list[dict]:
        """Recommend charts."""
        return [
            {
                'type': 'pie',
                'names': 'StatusLabel',
                'title': 'Distribución por Estado'
            },
            {
                'type': 'bar',
                'x': 'Product2.ProductCode',
                'title': 'Assets por Código de Producto'
            }
        ]
