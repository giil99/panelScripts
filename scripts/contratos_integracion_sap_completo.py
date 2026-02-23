"""
Script: Contratos Activos - Integración SAP (COMPLETO)

PRESERVA 100% DE LA LÓGICA DEL NOTEBOOK ContratosActivosIntegracionSAP.ipynb

Este script:
1. Consulta contratos activos (Status='02')
2. Consulta integraciones SAP de la tabla NewCo_SAP_Integration__c
3. Agrupa integraciones SAP por contrato
4. Identifica 3 causísticas:
   - Sin Integración SAP: Contratos sin registros de integración SAP
   - Algún status vacío y un KO: Tiene integraciones con status vacío y al menos un KO (no OK)
   - Solo tiene KO: Todas las integraciones son KO (no vacías, no OK)
"""
import pandas as pd
from collections import defaultdict
from core.base_script import BaseScript, ScriptResult, ScriptMetrics, ColumnConfig, ColumnType
from core.script_registry import register_script
from core.causistica import CausisticaManager, CausisticaDefinition, CausisticaResult
from config import CONTRACT_STATUS_MAP


@register_script
class ContratosActivosIntegracionSAPCompleto(BaseScript):
    """
    Detecta contratos activos con problemas de integración SAP.
    Preserva 100% de la lógica del notebook ContratosActivosIntegracionSAP.ipynb.
    """
    
    name = "Contratos - Integración SAP (Completo)"
    description = "Analiza integraciones SAP de contratos activos (3 causísticas)"
    category = "Extracción de datos"
    version = "2.0"
    author = "AG"
    
    supports_preview = True
    supports_update = False
    requires_confirmation = False
    uses_causisticas = True
    
    def setup_causisticas(self):
        """Define las causísticas según el notebook."""
        self._causistica_manager.register(CausisticaDefinition(
            code="SIN_SAP",
            name="Sin Integración SAP",
            description="Contratos activos sin registros de integración SAP",
            severity="Alta"
        ))
        
        self._causistica_manager.register(CausisticaDefinition(
            code="VACIO_Y_KO",
            name="Algún status vacío y un KO",
            description="Tiene integraciones SAP con algún status vacío y al menos un KO",
            severity="Media"
        ))
        
        self._causistica_manager.register(CausisticaDefinition(
            code="SOLO_KO",
            name="Solo tiene KO",
            description="Todas las integraciones SAP tienen status KO (ninguna OK ni vacía)",
            severity="Alta"
        ))
    
    def get_queries(self, preview: bool = False) -> list[str]:
        """Retorna queries según el notebook:
        1. Contratos activos (Status='02')
        2. Integraciones SAP de contratos activos
        """
        limit_contracts = "LIMIT 5000" if preview else ""
        limit_sap = "LIMIT 10000" if preview else ""
        
        # Query 1: Contratos activos (igual que notebook)
        query_contracts = f"""
            SELECT Id, ContractNumber, Status, 
                   NewCo_ServiceAccount__c, NewCo_ServiceAccount__r.Name,
                   acn_fld_CUPS__c, acn_fld_CUPS__r.Name,
                   acn_fld_BusinessDivision__c,
                   NewCo_IntegracionSAP__c, NewCo_FechaEnvioSAP__c,
                   CreatedDate, StartDate, ActivatedDate
            FROM Contract
            WHERE Status = '02'
            {limit_contracts}
        """
        
        # Query 2: Integraciones SAP (igual que notebook)
        query_sap = f"""
            SELECT Id, NewCo_fld_StatusSap__c, NewCo_fld_Contract__c
            FROM NewCo_SAP_Integration__c
            WHERE NewCo_fld_Contract__r.Status = '02'
            {limit_sap}
        """
        
        return [query_contracts, query_sap]
    
    def process(self, query_results: dict[str, pd.DataFrame]) -> ScriptResult:
        """Procesa contratos e integraciones SAP según lógica del notebook."""
        contracts_df = query_results.get('query_0', pd.DataFrame())
        sap_df = query_results.get('query_1', pd.DataFrame())
        
        if contracts_df.empty:
            return ScriptResult(
                success=True,
                data=pd.DataFrame(),
                metrics=ScriptMetrics(total_records=0, message="No hay contratos activos")
            )
        
        # Enrich contracts with status label
        contracts_df['StatusLabel'] = contracts_df['Status'].map(CONTRACT_STATUS_MAP)
        
        # LÓGICA DEL NOTEBOOK: Agrupar integraciones SAP por contrato
        sap_by_contract = self._group_sap_by_contract(sap_df)
        
        # CAUSÍSTICA 1: Contratos sin integración SAP
        self._process_sin_integracion_sap(contracts_df, sap_by_contract)
        
        # CAUSÍSTICAS 2 y 3: Contratos con integraciones SAP problemáticas
        self._process_integraciones_problematicas(contracts_df, sap_by_contract)
        
        # Combinar todas las causísticas para métricas globales
        all_results = []
        for causistica in self._causistica_manager.get_all():
            result = self._causistica_manager.get_result(causistica.code)
            if result and not result.data.empty:
                all_results.append(result.data)
        
        total_affected = sum(len(r) for r in all_results)
        
        metrics = ScriptMetrics(
            total_records=len(contracts_df),
            affected_records=total_affected,
            message=f"{len(contracts_df)} contratos activos, {total_affected} con problemas SAP"
        )
        
        return ScriptResult(
            success=True,
            data=contracts_df,  # Retornar todos los contratos para contexto
            metrics=metrics,
            has_causisticas=True
        )
    
    def _group_sap_by_contract(self, sap_df: pd.DataFrame) -> dict:
        """Agrupa integraciones SAP por contrato (lógica del notebook)."""
        if sap_df.empty:
            return {}
        
        sap_by_contract = defaultdict(list)
        
        # Limpiar y filtrar
        sap_clean = sap_df[['Id', 'NewCo_fld_StatusSap__c', 'NewCo_fld_Contract__c']].dropna(
            subset=['NewCo_fld_Contract__c']
        )
        
        for _, row in sap_clean.iterrows():
            contract_id = row['NewCo_fld_Contract__c']
            sap_by_contract[contract_id].append({
                'Id': row['Id'],
                'NewCo_fld_StatusSap__c': row['NewCo_fld_StatusSap__c']
            })
        
        return dict(sap_by_contract)
    
    def _process_sin_integracion_sap(self, contracts_df: pd.DataFrame, sap_by_contract: dict):
        """CAUSÍSTICA 1: Contratos sin integración SAP (lógica del notebook)."""
        # Contratos con integraciones SAP
        contracts_with_sap = set(sap_by_contract.keys())
        
        # Todos los contratos activos
        contracts_all = set(contracts_df['Id'].dropna())
        
        # Contratos SIN integraciones SAP
        contracts_no_sap = contracts_all - contracts_with_sap
        
        df_no_sap = contracts_df[contracts_df['Id'].isin(contracts_no_sap)].copy()
        
        if not df_no_sap.empty:
            df_no_sap['Causistica_Detalle'] = 'Sin registros de integración SAP'
        
        self._causistica_manager.set_result(
            "SIN_SAP",
            CausisticaResult(
                causistica_code="SIN_SAP",
                data=df_no_sap,
                total_records=len(df_no_sap),
                has_updates=False
            )
        )
    
    def _process_integraciones_problematicas(self, contracts_df: pd.DataFrame, sap_by_contract: dict):
        """CAUSÍSTICAS 2 y 3: Contratos con integraciones problemáticas (lógica del notebook)."""
        
        def _get_causistica(statuses):
            """Determina la causística según los status SAP (lógica exacta del notebook)."""
            # Verificar si tiene algún status vacío
            has_empty = any(
                s is None or (isinstance(s, str) and s.strip() == '') or pd.isna(s)
                for s in statuses
            )
            
            # Verificar si tiene algún KO (no vacío, no OK)
            has_ko = any(
                s not in (None, '', 'OK') and not pd.isna(s)
                for s in statuses
            )
            
            if has_empty and has_ko:
                return 'VACIO_Y_KO'
            elif has_ko and not has_empty:
                return 'SOLO_KO'
            return None
        
        contratos_vacio_y_ko = []
        contratos_solo_ko = []
        
        for contract_id, integrations in sap_by_contract.items():
            statuses = [i['NewCo_fld_StatusSap__c'] for i in integrations]
            
            # LÓGICA DEL NOTEBOOK: Excluir si tiene algún OK
            if any(s == 'OK' for s in statuses):
                continue
            
            # LÓGICA DEL NOTEBOOK: Excluir si todos los status están vacíos
            if all(
                s is None or (isinstance(s, str) and s.strip() == '') or pd.isna(s)
                for s in statuses
            ):
                continue
            
            # Determinar causística
            causistica = _get_causistica(statuses)
            
            if causistica == 'VACIO_Y_KO':
                contratos_vacio_y_ko.append(contract_id)
            elif causistica == 'SOLO_KO':
                contratos_solo_ko.append(contract_id)
        
        # Crear DataFrames para cada causística
        df_vacio_y_ko = contracts_df[contracts_df['Id'].isin(contratos_vacio_y_ko)].copy()
        df_solo_ko = contracts_df[contracts_df['Id'].isin(contratos_solo_ko)].copy()
        
        if not df_vacio_y_ko.empty:
            df_vacio_y_ko['Causistica_Detalle'] = 'Algún status vacío y un KO'
        
        if not df_solo_ko.empty:
            df_solo_ko['Causistica_Detalle'] = 'Solo tiene KO'
        
        # Guardar resultados
        self._causistica_manager.set_result(
            "VACIO_Y_KO",
            CausisticaResult(
                causistica_code="VACIO_Y_KO",
                data=df_vacio_y_ko,
                total_records=len(df_vacio_y_ko),
                has_updates=False
            )
        )
        
        self._causistica_manager.set_result(
            "SOLO_KO",
            CausisticaResult(
                causistica_code="SOLO_KO",
                data=df_solo_ko,
                total_records=len(df_solo_ko),
                has_updates=False
            )
        )
    
    def get_column_config(self) -> list[ColumnConfig]:
        """Define column configuration."""
        return [
            ColumnConfig('ContractNumber', 'Nº Contrato', ColumnType.TEXT),
            ColumnConfig('StatusLabel', 'Estado', ColumnType.STATUS),
            ColumnConfig('NewCo_ServiceAccount__r.Name', 'Service Account', ColumnType.TEXT),
            ColumnConfig('acn_fld_CUPS__r.Name', 'CUPS', ColumnType.TEXT),
            ColumnConfig('acn_fld_BusinessDivision__c', 'División', ColumnType.TEXT),
            ColumnConfig('Causistica_Detalle', 'Problema Integración', ColumnType.TEXT),
            ColumnConfig('ActivatedDate', 'Fecha Activación', ColumnType.DATETIME),
            ColumnConfig('NewCo_FechaEnvioSAP__c', 'Enviado SAP', ColumnType.DATETIME),
        ]
    
    def get_groupby_options(self) -> list[str]:
        """Return columns for grouping."""
        return ['acn_fld_BusinessDivision__c', 'Causistica_Detalle']
