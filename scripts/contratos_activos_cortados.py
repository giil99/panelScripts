"""
Script: Contratos Activos con Assets Cortados

Detecta contratos activos cuyo asset más reciente está en estado "Cortado" (08)
pero cuya Solicitud de Contrato de corte está cancelada.

Esto indica que el asset debería volver a su estado anterior (normalmente Activado).
"""
import pandas as pd
from core.base_script import BaseScript, ScriptResult, ScriptMetrics, ColumnConfig, ColumnType
from core.script_registry import register_script
from config import ASSET_STATUS_MAP, CONTRACT_STATUS_MAP, CONTRACT_REQUEST_STATUS_MAP


@register_script
class ContratosActivosCortados(BaseScript):
    """
    Detecta y opcionalmente corrige assets en estado Cortado incorrectamente.
    """
    
    name = "Contratos Activos con Assets Cortados"
    description = "Detecta contratos activos con asset cortado y SC cancelada"
    category = "Regularización"
    version = "1.0"
    author = "AG"
    
    supports_preview = True
    supports_update = True
    requires_confirmation = True
    
    # Status constants
    CONTRACT_STATUS_ACTIVE = "02"
    ASSET_STATUS_CORTADO = "08"
    ASSET_STATUS_ACTIVADO = "03"
    SC_TYPE_CORTE = "21"
    SC_CATEGORY_CORTE = "18"
    SC_STATUS_CANCELADO = "05"
    
    def get_queries(self, preview: bool = False) -> list[str]:
        """
        Return queries to fetch assets and contract requests.
        """
        limit_clause = "LIMIT 1000" if preview else ""
        
        # Query 1: Assets de contratos activos (sin padre - solo root assets)
        query_assets = f"""
            SELECT Id, Name, acn_fld_Contract__c, acn_fld_Contract__r.ContractNumber, 
                   acn_fld_Contract__r.Status, Status, CreatedDate, LastModifiedDate
            FROM Asset
            WHERE acn_fld_Contract__r.Status = '{self.CONTRACT_STATUS_ACTIVE}' 
            AND vlocity_cmt__ParentItemId__c = null
            {limit_clause}
        """
        
        # Query 2: Solicitudes de corte (Tipo 21, Categoría 18)
        query_solicitudes = f"""
            SELECT Id, Name, acn_fld_Contract__c, acn_fld_Sctype__c, 
                   acn_fld_Category__c, acn_fld_Status__c, CreatedDate
            FROM acn_obj_ContractRequest__c
            WHERE acn_fld_Sctype__c = '{self.SC_TYPE_CORTE}'
            AND acn_fld_Category__c = '{self.SC_CATEGORY_CORTE}'
        """
        
        return [query_assets, query_solicitudes]
    
    def process(self, query_results: dict[str, pd.DataFrame]) -> ScriptResult:
        """
        Process assets and contract requests to find mismatches.
        """
        df_assets = query_results.get('query_0', pd.DataFrame())
        df_solicitudes = query_results.get('query_1', pd.DataFrame())
        
        if df_assets.empty:
            return ScriptResult(
                success=True,
                data=pd.DataFrame(),
                metrics=ScriptMetrics(total_records=0)
            )
        
        # Store intermediate data
        self.store_intermediate('assets_raw', df_assets)
        self.store_intermediate('solicitudes_raw', df_solicitudes)
        
        # Process assets - get most recent per contract
        df_assets['LastModifiedDate'] = pd.to_datetime(df_assets['LastModifiedDate'])
        df_assets = df_assets.sort_values(
            ['acn_fld_Contract__c', 'LastModifiedDate'],
            ascending=[True, False]
        )
        
        # Get most recent asset per contract
        df_assets_recientes = df_assets.groupby('acn_fld_Contract__c').first().reset_index()
        
        # Filter only assets in "Cortado" status
        df_assets_cortados = df_assets_recientes[
            df_assets_recientes['Status'] == self.ASSET_STATUS_CORTADO
        ]
        
        if df_assets_cortados.empty:
            return ScriptResult(
                success=True,
                data=pd.DataFrame(),
                metrics=ScriptMetrics(
                    total_records=len(df_assets_recientes),
                    custom_metrics={
                        'assets_cortados': {
                            'value': 0,
                            'label': 'Assets Cortados',
                            'icon': '🔴'
                        }
                    }
                )
            )
        
        self.store_intermediate('assets_cortados', df_assets_cortados)
        
        # Process contract requests for these contracts
        contract_ids_cortados = set(df_assets_cortados['acn_fld_Contract__c'].tolist())
        df_solicitudes_filtered = df_solicitudes[
            df_solicitudes['acn_fld_Contract__c'].isin(contract_ids_cortados)
        ]
        
        if df_solicitudes_filtered.empty:
            self.add_warning("No se encontraron solicitudes de corte para los contratos con assets cortados")
            return ScriptResult(
                success=True,
                data=df_assets_cortados,
                metrics=ScriptMetrics(total_records=len(df_assets_cortados))
            )
        
        # Sort by contract and date (most recent first)
        df_solicitudes_filtered['CreatedDate'] = pd.to_datetime(df_solicitudes_filtered['CreatedDate'])
        df_solicitudes_filtered = df_solicitudes_filtered.sort_values(
            ['acn_fld_Contract__c', 'CreatedDate'],
            ascending=[True, False]
        )
        
        # Find contracts where:
        # 1. Last SC is cancelled
        # 2. No other SC is in non-cancelled status
        contratos_finales = []
        
        for contract_id in df_assets_cortados['acn_fld_Contract__c']:
            solicitudes_contrato = df_solicitudes_filtered[
                df_solicitudes_filtered['acn_fld_Contract__c'] == contract_id
            ]
            
            if len(solicitudes_contrato) > 0:
                # Get last SC
                ultima_solicitud = solicitudes_contrato.iloc[0]
                
                # Check if last SC is cancelled
                if ultima_solicitud['acn_fld_Status__c'] == self.SC_STATUS_CANCELADO:
                    # Check no other SC is active
                    solicitudes_no_canceladas = solicitudes_contrato[
                        solicitudes_contrato['acn_fld_Status__c'] != self.SC_STATUS_CANCELADO
                    ]
                    
                    if len(solicitudes_no_canceladas) == 0:
                        # This contract meets all conditions
                        asset_info = df_assets_cortados[
                            df_assets_cortados['acn_fld_Contract__c'] == contract_id
                        ].iloc[0]
                        
                        contratos_finales.append({
                            'ContractId': contract_id,
                            'ContractNumber': asset_info.get('acn_fld_Contract__r.ContractNumber', ''),
                            'ContractStatus': asset_info.get('acn_fld_Contract__r.Status', ''),
                            'ContractStatusLabel': CONTRACT_STATUS_MAP.get(
                                asset_info.get('acn_fld_Contract__r.Status', ''), ''
                            ),
                            'AssetId': asset_info['Id'],
                            'AssetName': asset_info['Name'],
                            'AssetStatus': asset_info['Status'],
                            'AssetStatusLabel': ASSET_STATUS_MAP.get(asset_info['Status'], ''),
                            'AssetLastModifiedDate': asset_info['LastModifiedDate'],
                            'SC_Id': ultima_solicitud['Id'],
                            'SC_Name': ultima_solicitud['Name'],
                            'SC_Status': ultima_solicitud['acn_fld_Status__c'],
                            'SC_StatusLabel': CONTRACT_REQUEST_STATUS_MAP.get(
                                ultima_solicitud['acn_fld_Status__c'], ''
                            ),
                            'SC_CreatedDate': ultima_solicitud['CreatedDate'],
                            'TotalSolicitudesCorte': len(solicitudes_contrato),
                            'SolicitudesNoCanceladas': 0,
                            'TargetStatus': self.ASSET_STATUS_ACTIVADO,
                            'TargetStatusLabel': ASSET_STATUS_MAP.get(self.ASSET_STATUS_ACTIVADO, '')
                        })
        
        df_resultado = pd.DataFrame(contratos_finales)
        
        # Calculate metrics
        metrics = ScriptMetrics(
            total_records=len(df_resultado),
            processed_records=len(df_assets_recientes)
        )
        metrics.add_metric(
            'total_assets_activos',
            len(df_assets_recientes),
            'Assets de Contratos Activos',
            '📋'
        )
        metrics.add_metric(
            'assets_cortados',
            len(df_assets_cortados),
            'Assets en Estado Cortado',
            '🔴'
        )
        metrics.add_metric(
            'a_regularizar',
            len(df_resultado),
            'Assets a Regularizar',
            '⚠️'
        )
        if len(df_assets_cortados) > 0:
            pct = len(df_resultado) / len(df_assets_cortados) * 100
            metrics.add_metric(
                'porcentaje_regularizacion',
                f"{pct:.1f}%",
                '% con SC Cancelada',
                '📊'
            )
        
        return ScriptResult(
            success=True,
            data=df_resultado,
            metrics=metrics,
            anomalies=df_resultado if not df_resultado.empty else None
        )
    
    def get_column_config(self) -> list[ColumnConfig]:
        """Define column display configuration."""
        return [
            ColumnConfig('ContractNumber', 'Nº Contrato', ColumnType.TEXT),
            ColumnConfig('ContractStatusLabel', 'Estado Contrato', ColumnType.STATUS),
            ColumnConfig('AssetName', 'Asset', ColumnType.TEXT),
            ColumnConfig('AssetStatusLabel', 'Estado Asset', ColumnType.STATUS),
            ColumnConfig('SC_Name', 'Solicitud Corte', ColumnType.TEXT),
            ColumnConfig('SC_StatusLabel', 'Estado SC', ColumnType.STATUS),
            ColumnConfig('TargetStatusLabel', 'Estado Objetivo', ColumnType.STATUS),
            ColumnConfig('TotalSolicitudesCorte', 'Total SC Corte', ColumnType.NUMBER),
        ]
    
    def get_groupby_options(self) -> list[str]:
        """Return columns available for grouping."""
        return [
            'ContractStatusLabel',
            'AssetStatusLabel',
            'SC_StatusLabel',
            'TotalSolicitudesCorte'
        ]
    
    def get_update_operations(self) -> list[dict]:
        """Define available update operations."""
        return [
            {
                'name': 'activate_assets',
                'description': 'Cambiar assets a estado Activado (03)',
                'fields': {'Status': self.ASSET_STATUS_ACTIVADO}
            }
        ]
    
    def execute_update(self, operation: str, data: pd.DataFrame) -> tuple[list, list]:
        """Execute update operation on assets."""
        if operation != 'activate_assets':
            raise ValueError(f"Unknown operation: {operation}")
        
        if data.empty:
            return [], []
        
        # Prepare update records
        records = [
            {'Id': row['AssetId'], 'Status': self.ASSET_STATUS_ACTIVADO}
            for _, row in data.iterrows()
        ]
        
        # Execute bulk update
        return self.sf_client.bulk_update('Asset', records)
    
    def detect_anomalies(self, data: pd.DataFrame) -> pd.DataFrame:
        """All records in this script are anomalies by definition."""
        if data.empty:
            return pd.DataFrame()
        
        # Add anomaly classification
        result = data.copy()
        result['anomaly_type'] = 'Asset Cortado con SC Cancelada'
        result['anomaly_severity'] = 'Media'
        return result
    
    def get_chart_recommendations(self) -> list[dict]:
        """Recommend relevant charts for this script's output."""
        return [
            {
                'type': 'bar',
                'x': 'TotalSolicitudesCorte',
                'y': 'count',
                'title': 'Distribución por Nº de SC de Corte'
            },
            {
                'type': 'pie',
                'names': 'AssetStatusLabel',
                'values': 'count',
                'title': 'Assets por Estado'
            }
        ]
