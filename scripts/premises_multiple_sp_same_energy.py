"""
Script: Premises con Múltiples Service Points de Misma Energía

Detecta Premises que tienen más de un Service Point del mismo tipo de energía,
lo cual puede indicar un error de datos o duplicados.
"""
import pandas as pd
from core.base_script import BaseScript, ScriptResult, ScriptMetrics, ColumnConfig, ColumnType
from core.script_registry import register_script


@register_script
class PremisesConServicePointMismaEnergia(BaseScript):
    """
    Detecta premises con múltiples service points del mismo tipo de energía.
    """
    
    name = "Premises - Múltiples SP Misma Energía"
    description = "Detecta premises con varios Service Points del mismo tipo"
    category = "Detección de inconsistencias"
    version = "1.0"
    author = "AG"
    
    supports_preview = True
    supports_update = False
    requires_confirmation = False
    
    def get_queries(self, preview: bool = False) -> list[str]:
        """Return query for service points."""
        limit_clause = "LIMIT 5000" if preview else ""
        
        query = f"""
            SELECT Id, Name, vlocity_cmt__PremisesId__c, 
                   vlocity_cmt__PremisesId__r.Name,
                   vlocity_cmt__ServicePointType__c, 
                   acn_fld_Status__c, CreatedDate
            FROM vlocity_cmt__ServicePoint__c
            WHERE vlocity_cmt__PremisesId__c != null
            {limit_clause}
        """
        
        return [query]
    
    def process(self, query_results: dict[str, pd.DataFrame]) -> ScriptResult:
        """Process service points to find duplicates per premises."""
        df = query_results.get('query_0', pd.DataFrame())
        
        if df.empty:
            return ScriptResult(
                success=True,
                data=pd.DataFrame(),
                metrics=ScriptMetrics(total_records=0)
            )
        
        self.store_intermediate('service_points_raw', df)
        
        # Group by premises and service point type
        grouped = df.groupby(
            ['vlocity_cmt__PremisesId__c', 'vlocity_cmt__ServicePointType__c']
        ).agg({
            'Id': 'count',
            'Name': lambda x: '; '.join(x.astype(str)),
            'vlocity_cmt__PremisesId__r.Name': 'first',
            'CreatedDate': 'min'
        }).reset_index()
        
        grouped.columns = [
            'PremisesId', 'ServicePointType', 'SPCount', 
            'ServicePointNames', 'PremisesName', 'OldestCreatedDate'
        ]
        
        # Filter only those with more than one
        duplicates = grouped[grouped['SPCount'] > 1].copy()
        
        # Calculate metrics
        metrics = ScriptMetrics(total_records=len(duplicates))
        
        metrics.add_metric(
            'premises_with_duplicates',
            len(duplicates),
            'Premises con Duplicados',
            '🔴' if len(duplicates) > 0 else '✅'
        )
        
        # Count by type
        if not duplicates.empty:
            type_counts = duplicates['ServicePointType'].value_counts()
            for sp_type, count in type_counts.items():
                if sp_type:
                    metrics.add_metric(
                        f'type_{sp_type}',
                        count,
                        f'Tipo: {sp_type}',
                        '📊'
                    )
        
        return ScriptResult(
            success=True,
            data=duplicates,
            metrics=metrics
        )
    
    def get_column_config(self) -> list[ColumnConfig]:
        """Define column configuration."""
        return [
            ColumnConfig('PremisesName', 'Premises', ColumnType.TEXT),
            ColumnConfig('ServicePointType', 'Tipo SP', ColumnType.TEXT),
            ColumnConfig('SPCount', 'Nº Service Points', ColumnType.NUMBER),
            ColumnConfig('ServicePointNames', 'Nombres SP', ColumnType.TEXT),
            ColumnConfig('OldestCreatedDate', 'Más Antiguo', ColumnType.DATETIME),
        ]
    
    def get_groupby_options(self) -> list[str]:
        """Return columns for grouping."""
        return ['ServicePointType', 'SPCount']
    
    def detect_anomalies(self, data: pd.DataFrame) -> pd.DataFrame:
        """All duplicates are anomalies."""
        if data.empty:
            return pd.DataFrame()
        
        anomalies = data.copy()
        anomalies['anomaly_type'] = 'Múltiples SP Misma Energía'
        anomalies['anomaly_severity'] = 'Media'
        
        return anomalies
    
    def get_chart_recommendations(self) -> list[dict]:
        """Recommend charts."""
        return [
            {
                'type': 'pie',
                'names': 'ServicePointType',
                'title': 'Distribución por Tipo de SP'
            },
            {
                'type': 'bar',
                'x': 'SPCount',
                'title': 'Distribución por Nº de SPs'
            }
        ]
