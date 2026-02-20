"""
Script: Tarifa Incorrecta en Contrato

Detecta contratos cuya tarifa no coincide con la esperada según su configuración.
"""
import pandas as pd
from core.base_script import BaseScript, ScriptResult, ScriptMetrics, ColumnConfig, ColumnType
from core.script_registry import register_script
from config import CONTRACT_STATUS_MAP


@register_script
class TarifaIncorrectaContrato(BaseScript):
    """
    Detecta contratos con tarifa incorrecta.
    """
    
    name = "Tarifa Incorrecta en Contrato"
    description = "Detecta contratos cuya tarifa no coincide con la configuración"
    category = "Detección de inconsistencias"
    version = "1.0"
    author = "AG"
    
    supports_preview = True
    supports_update = True
    requires_confirmation = True
    
    def get_queries(self, preview: bool = False) -> list[str]:
        """Return query for contracts with tariff info."""
        limit_clause = "LIMIT 2000" if preview else ""
        
        query = f"""
            SELECT Id, ContractNumber, Status, 
                   acn_fld_CUPS__c, acn_fld_CUPS__r.Name,
                   acn_fld_CUPS__r.acn_fld_Tarifa__c,
                   NewCo_Tarifa__c, acn_fld_BusinessDivision__c,
                   CreatedDate, StartDate
            FROM Contract
            WHERE Status = '02'
            AND acn_fld_CUPS__c != null
            {limit_clause}
        """
        
        return [query]
    
    def process(self, query_results: dict[str, pd.DataFrame]) -> ScriptResult:
        """Process contracts to find tariff mismatches."""
        df = query_results.get('query_0', pd.DataFrame())
        
        if df.empty:
            return ScriptResult(
                success=True,
                data=pd.DataFrame(),
                metrics=ScriptMetrics(total_records=0)
            )
        
        self.store_intermediate('contracts_raw', df)
        
        # Find mismatches
        mismatches = []
        
        for _, row in df.iterrows():
            contract_tariff = str(row.get('NewCo_Tarifa__c', '') or '').strip()
            cups_tariff = str(row.get('acn_fld_CUPS__r.acn_fld_Tarifa__c', '') or '').strip()
            
            # Skip if either is empty
            if not contract_tariff or not cups_tariff:
                continue
            
            # Check for mismatch
            if contract_tariff != cups_tariff:
                mismatches.append({
                    'ContractId': row['Id'],
                    'ContractNumber': row['ContractNumber'],
                    'CUPS': row.get('acn_fld_CUPS__r.Name', ''),
                    'ContractTariff': contract_tariff,
                    'CUPSTariff': cups_tariff,
                    'BusinessDivision': row.get('acn_fld_BusinessDivision__c', ''),
                    'StartDate': row.get('StartDate'),
                    'CreatedDate': row.get('CreatedDate')
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
            'contracts_checked',
            len(df),
            'Contratos Verificados',
            '📊'
        )
        
        # Count by business division
        if not df_result.empty and 'BusinessDivision' in df_result.columns:
            div_counts = df_result['BusinessDivision'].value_counts()
            for div, count in div_counts.items():
                if div:
                    metrics.add_metric(
                        f'div_{div}',
                        count,
                        f'División: {div}',
                        '📊'
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
            ColumnConfig('ContractTariff', 'Tarifa Contrato', ColumnType.TEXT),
            ColumnConfig('CUPSTariff', 'Tarifa CUPS', ColumnType.TEXT),
            ColumnConfig('BusinessDivision', 'División', ColumnType.TEXT),
            ColumnConfig('StartDate', 'Fecha Inicio', ColumnType.DATE),
        ]
    
    def get_groupby_options(self) -> list[str]:
        """Return columns for grouping."""
        return ['ContractTariff', 'CUPSTariff', 'BusinessDivision']
    
    def detect_anomalies(self, data: pd.DataFrame) -> pd.DataFrame:
        """All mismatches are anomalies."""
        if data.empty:
            return pd.DataFrame()
        
        anomalies = data.copy()
        anomalies['anomaly_type'] = 'Tarifa Incorrecta'
        anomalies['anomaly_severity'] = 'Media'
        
        return anomalies
    
    def get_chart_recommendations(self) -> list[dict]:
        """Recommend charts."""
        return [
            {
                'type': 'pie',
                'names': 'BusinessDivision',
                'title': 'Desajustes por División'
            },
            {
                'type': 'bar',
                'x': 'ContractTariff',
                'title': 'Por Tarifa Contrato'
            }
        ]
    
    def get_update_operations(self) -> list[dict]:
        """Define update operations."""
        return [
            {
                'name': 'sync_tariff_from_cups',
                'description': 'Actualizar tarifa del contrato desde el CUPS',
                'fields': {
                    'NewCo_Tarifa__c': '(tarifa del CUPS)'
                }
            }
        ]
