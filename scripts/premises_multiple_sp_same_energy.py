"""
Script: Premises con Múltiples Service Points de Misma Energía

Detecta Premises que tienen más de un Service Point del mismo tipo de energía,
lo cual puede indicar un error de datos o duplicados.

Implementa lógica completa del notebook PremisesConServicePointMismaEnergia.ipynb
"""
import pandas as pd
from core.base_script import BaseScript, ScriptResult, ScriptMetrics, ColumnConfig, ColumnType
from core.script_registry import register_script
from core.causistica import CausisticaManager, CausisticaDefinition, CausisticaResult


@register_script
class PremisesConServicePointMismaEnergia(BaseScript):
    """
    Detecta premises con múltiples service points del mismo tipo de energía.
    Analiza duplicados por tipo de energía (Electricidad/Gas).
    """
    
    name = "Premises - Múltiples SP Misma Energía"
    description = "Detecta premises con varios Service Points del mismo tipo"
    category = "Detección de inconsistencias"
    version = "2.0"
    author = "AG"
    
    supports_preview = True
    supports_update = False
    requires_confirmation = False
    uses_causisticas = True  # Usa framework de causísticas
    
    def get_queries(self, preview: bool = False) -> list[str]:
        """Return query for service points (LÓGICA EXACTA DEL NOTEBOOK)."""
        limit_clause = "LIMIT 5000" if preview else ""
        
        # QUERY DEL NOTEBOOK - usar vlocity_cmt__ServiceType__c (NO ServicePointType)
        query = f"""
            SELECT Id, Name, 
                   acn_fld_Account__c,
                   vlocity_cmt__PremisesId__c, 
                   vlocity_cmt__PremisesId__r.Name,
                   acn_fld_toll__c,
                   vlocity_cmt__ServiceType__c,
                   acn_fld_Status__c, 
                   CreatedDate
            FROM vlocity_cmt__ServicePoint__c
            WHERE vlocity_cmt__PremisesId__c != null
            {limit_clause}
        """
        
        return [query]
    
    def setup_causisticas(self):
        """Define las causísticas de este script."""
        
        # Causística por tipo de energía
        self._causistica_manager.register(CausisticaDefinition(
            code="ELEC",
            name="Premises con Múltiples SP Electricidad",
            description="Premises que tienen más de un Service Point de tipo Electricidad",
            severity="warning"
        ))
        
        self._causistica_manager.register(CausisticaDefinition(
            code="GAS",
            name="Premises con Múltiples SP Gas",
            description="Premises que tienen más de un Service Point de tipo Gas",
            severity="warning"
        ))
        
        self._causistica_manager.register(CausisticaDefinition(
            code="OTROS",
            name="Premises con Múltiples SP Otros Tipos",
            description="Premises con múltiples Service Points de otros tipos de energía",
            severity="info"
        ))
    
    def process(self, query_results: dict[str, pd.DataFrame]) -> ScriptResult:
        """Process service points to find duplicates per premises."""
        df = query_results.get('query_0', pd.DataFrame())
        
        if df.empty:
            return ScriptResult(
                success=True,
                data=pd.DataFrame(),
                metrics=ScriptMetrics(total_records=0),
                has_causisticas=False
            )
        
        self.store_intermediate('service_points_raw', df)
        
        # Group by premises and service point type (USAR vlocity_cmt__ServiceType__c DEL NOTEBOOK)
        grouped = df.groupby(
            ['vlocity_cmt__PremisesId__c', 'vlocity_cmt__ServiceType__c']
        ).agg({
            'Id': ['count', lambda x: '; '.join(x.astype(str))],
            'Name': lambda x: '; '.join(x.astype(str)),
            'vlocity_cmt__PremisesId__r.Name': 'first',
            'acn_fld_Account__c': 'first',  # Agregar campo del notebook
            'acn_fld_toll__c': 'first',  # Agregar campo del notebook
            'CreatedDate': 'min',
            'acn_fld_Status__c': lambda x: '; '.join(x.dropna().astype(str)) if not x.isna().all() else ''
        }).reset_index()
        
        grouped.columns = [
            'PremisesId', 'ServicePointType', 'SPCount', 'ServicePointIds',
            'ServicePointNames', 'PremisesName', 'AccountId', 'Toll', 'OldestCreatedDate', 'Status'
        ]
        
        # Filter only those with more than one
        duplicates = grouped[grouped['SPCount'] > 1].copy()
        
        if duplicates.empty:
            return ScriptResult(
                success=True,
                data=pd.DataFrame(),
                metrics=ScriptMetrics(total_records=0),
                has_causisticas=False
            )
        
        # Separate by energy type
        duplicates_electricidad = duplicates[
            duplicates['ServicePointType'].str.contains('Electricidad', case=False, na=False)
        ].copy()
        
        duplicates_gas = duplicates[
            duplicates['ServicePointType'].str.contains('Gas', case=False, na=False)
        ].copy()
        
        duplicates_otros = duplicates[
            ~duplicates['ServicePointType'].str.contains('Electricidad|Gas', case=False, na=False)
        ].copy()
        
        # Create causística results
        if not duplicates_electricidad.empty:
            caus_elec = CausisticaResult(
                code="ELEC",
                name=self._causistica_manager.definitions['ELEC'].name,
                description=self._causistica_manager.definitions['ELEC'].description,
                severity="warning",
                data=duplicates_electricidad
            )
            caus_elec.add_metric(
                'premises_count',
                len(duplicates_electricidad),
                'Premises con Duplicados Electricidad',
                '⚡'
            )
            self._causistica_manager.results['ELEC'] = caus_elec
        
        if not duplicates_gas.empty:
            caus_gas = CausisticaResult(
                code="GAS",
                name=self._causistica_manager.definitions['GAS'].name,
                description=self._causistica_manager.definitions['GAS'].description,
                severity="warning",
                data=duplicates_gas
            )
            caus_gas.add_metric(
                'premises_count',
                len(duplicates_gas),
                'Premises con Duplicados Gas',
                '🔥'
            )
            self._causistica_manager.results['GAS'] = caus_gas
        
        if not duplicates_otros.empty:
            caus_otros = CausisticaResult(
                code="OTROS",
                name=self._causistica_manager.definitions['OTROS'].name,
                description=self._causistica_manager.definitions['OTROS'].description,
                severity="info",
                data=duplicates_otros
            )
            caus_otros.add_metric(
                'premises_count',
                len(duplicates_otros),
                'Premises con Duplicados Otros',
                '📊'
            )
            self._causistica_manager.results['OTROS'] = caus_otros
        
        # Calculate global metrics
        total_premises = len(duplicates)
        total_sps = duplicates['SPCount'].sum()
        
        metrics = ScriptMetrics(total_records=total_premises)
        metrics.add_metric(
            'total_premises',
            total_premises,
            'Premises con Duplicados',
            '🏢'
        )
        metrics.add_metric(
            'total_service_points',
            total_sps,
            'Total Service Points Duplicados',
            '🔌'
        )
        metrics.add_metric(
            'electricidad',
            len(duplicates_electricidad),
            'Duplicados Electricidad',
            '⚡'
        )
        metrics.add_metric(
            'gas',
            len(duplicates_gas),
            'Duplicados Gas',
            '🔥'
        )
        
        # Summary data for simple view
        summary_data = []
        for code, caus in self.get_causistica_results().items():
            summary_data.append({
                'Tipo': code,
                'Nombre': caus.name,
                'Premises': caus.count,
                'Severidad': caus.severity
            })
        
        summary_df = pd.DataFrame(summary_data) if summary_data else duplicates
        
        return ScriptResult(
            success=True,
            data=summary_df,
            metrics=metrics,
            causisticas=self.get_causistica_results(),
            has_causisticas=True
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
