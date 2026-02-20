"""
Script: Contratos Baja con Assets Status No Válido

Detecta contratos en baja que tienen assets con estados que 
deberían haber sido actualizados (no en baja correspondiente).
"""
import pandas as pd
from core.base_script import BaseScript, ScriptResult, ScriptMetrics, ColumnConfig, ColumnType
from core.script_registry import register_script
from config import ASSET_STATUS_MAP, CONTRACT_STATUS_MAP


@register_script
class ContratosBajaAssetsStatusInvalido(BaseScript):
    """
    Detecta contratos baja con assets en status incorrecto.
    """
    
    name = "Contratos Baja - Assets Status Inválido"
    description = "Detecta contratos en baja con assets que no reflejan la baja"
    category = "Regularización"
    version = "1.0"
    author = "AG"
    
    supports_preview = True
    supports_update = True
    requires_confirmation = True
    
    # Contract baja statuses
    CONTRACT_BAJA_STATUSES = ['03', '04', '05', '06']  # Inactivo, Baja, Cancelado, Finalizado
    
    # Valid asset statuses for baja contracts
    VALID_ASSET_BAJA_STATUSES = ['06', '13', '14', '15', '21', '28']  # Baja en curso, Cancelado, Baja, Rechazado, Sin Vigencia, Inactivo
    
    def get_queries(self, preview: bool = False) -> list[str]:
        """Return query for assets of baja contracts."""
        limit_clause = "LIMIT 5000" if preview else ""
        contract_statuses = "','".join(self.CONTRACT_BAJA_STATUSES)
        
        query = f"""
            SELECT Id, Name, Status, acn_fld_Contract__c,
                   acn_fld_Contract__r.ContractNumber,
                   acn_fld_Contract__r.Status,
                   vlocity_cmt__ProvisioningStatus__c, vlocity_cmt__Action__c,
                   CreatedDate
            FROM Asset
            WHERE vlocity_cmt__ParentItemId__c = null
            AND acn_fld_Contract__r.Status IN ('{contract_statuses}')
            {limit_clause}
        """
        
        return [query]
    
    def process(self, query_results: dict[str, pd.DataFrame]) -> ScriptResult:
        """Process assets to find invalid statuses."""
        df = query_results.get('query_0', pd.DataFrame())
        
        if df.empty:
            return ScriptResult(
                success=True,
                data=pd.DataFrame(),
                metrics=ScriptMetrics(total_records=0)
            )
        
        self.store_intermediate('assets_raw', df)
        
        # Filter assets with invalid status
        invalid_mask = ~df['Status'].isin(self.VALID_ASSET_BAJA_STATUSES)
        df_invalid = df[invalid_mask].copy()
        
        if not df_invalid.empty:
            df_invalid['AssetStatusLabel'] = df_invalid['Status'].map(ASSET_STATUS_MAP)
            df_invalid['ContractStatusLabel'] = df_invalid['acn_fld_Contract__r.Status'].map(CONTRACT_STATUS_MAP)
        
        # Calculate metrics
        metrics = ScriptMetrics(total_records=len(df_invalid))
        
        metrics.add_metric(
            'assets_invalid_status',
            len(df_invalid),
            'Assets con Status Inválido',
            '🔴' if len(df_invalid) > 0 else '✅'
        )
        
        metrics.add_metric(
            'total_assets_checked',
            len(df),
            'Assets Verificados',
            '📊'
        )
        
        # Count by asset status
        if not df_invalid.empty:
            status_counts = df_invalid['AssetStatusLabel'].value_counts()
            for status, count in status_counts.items():
                if status:
                    metrics.add_metric(
                        f'status_{status[:10]}',
                        count,
                        f'{status[:15]}',
                        '📊'
                    )
        
        return ScriptResult(
            success=True,
            data=df_invalid,
            metrics=metrics
        )
    
    def get_column_config(self) -> list[ColumnConfig]:
        """Define column configuration."""
        return [
            ColumnConfig('Name', 'Asset', ColumnType.TEXT),
            ColumnConfig('acn_fld_Contract__r.ContractNumber', 'Contrato', ColumnType.TEXT),
            ColumnConfig('ContractStatusLabel', 'Estado Contrato', ColumnType.STATUS),
            ColumnConfig('AssetStatusLabel', 'Estado Asset', ColumnType.STATUS),
            ColumnConfig('vlocity_cmt__ProvisioningStatus__c', 'Provisioning', ColumnType.TEXT),
            ColumnConfig('vlocity_cmt__Action__c', 'Action', ColumnType.TEXT),
            ColumnConfig('CreatedDate', 'Creado', ColumnType.DATETIME),
        ]
    
    def get_groupby_options(self) -> list[str]:
        """Return columns for grouping."""
        return ['AssetStatusLabel', 'ContractStatusLabel']
    
    def detect_anomalies(self, data: pd.DataFrame) -> pd.DataFrame:
        """All invalid assets are anomalies."""
        if data.empty:
            return pd.DataFrame()
        
        anomalies = data.copy()
        anomalies['anomaly_type'] = 'Asset Status Inválido en Contrato Baja'
        anomalies['anomaly_severity'] = 'Alta'
        
        return anomalies
    
    def get_chart_recommendations(self) -> list[dict]:
        """Recommend charts."""
        return [
            {
                'type': 'pie',
                'names': 'AssetStatusLabel',
                'title': 'Por Estado de Asset'
            },
            {
                'type': 'bar',
                'x': 'ContractStatusLabel',
                'title': 'Por Estado de Contrato'
            }
        ]
    
    def get_update_operations(self) -> list[dict]:
        """Define update operations."""
        return [
            {
                'name': 'set_baja_status',
                'description': 'Actualizar asset a estado baja correspondiente',
                'fields': {
                    'Status': '(14 Baja / 13 Cancelado / 28 Inactivo)',
                    'vlocity_cmt__ProvisioningStatus__c': 'Retired',
                    'vlocity_cmt__Action__c': 'Disconnect'
                }
            }
        ]
