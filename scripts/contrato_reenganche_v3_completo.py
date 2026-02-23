"""
Script: Contratos - Reenganche Completo (V3)

Detecta y clasifica múltiples causísticas de inconsistencias en contratos
relacionados con procesos de corte y reenganche.

Este script preserva TODA la lógica del notebook ContratoReengancheV3.ipynb,
organizando las múltiples causísticas de forma mantenible y escalable.

Causísticas detectadas:
- A0, A1, A2: Contratos sólo cortado con diferentes problemas
- B: Assets con status problemático fuera de posición
- C1-A0, C1-A1, C1-A2: Cor

te más reciente que reenganche
- C2-C14: Reenganche con diferentes validaciones (Electricidad/Gas)
- D2-D14: Múltiples reenganches con validaciones similares a C
"""
import pandas as pd
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional

from core.base_script import BaseScript, ScriptResult, ScriptMetrics
from core.script_registry import register_script
from core.causistica import (
    CausisticaManager, 
    CausisticaDefinition, 
    CausisticaResult
)


@register_script
class ContratoReengancheCompleto(BaseScript):
    """
    Script completo para detectar inconsistencias en contratos de corte/reenganche.
    Implementa todas las causísticas del proceso de negocio.
    """
    
    name = "Contratos - Reenganche V3 Completo"
    description = "Análisis completo de cortes y reenganches con múltiples causísticas"
    category = "Detección de inconsistencias"
    version = "3.0"
    author = "AG"
    
    supports_preview = True
    supports_update = False
    requires_confirmation = False
    uses_causisticas = True  # Activa el framework de causísticas
    
    # Status constants
    ASSET_STATUS_CORTADO = '08'
    ASSET_STATUS_CORTE_EN_CURSO = '07'
    ASSET_STATUS_REENGANCHE_EN_CURSO = '09'
    ASSET_STATUS_ACTIVADO = '03'
    ASSET_STATUS_SUSPENDIDO = '09'
    
    SC_STATUS_NUEVO = '01'
    SC_STATUS_EN_CURSO = '02'
    SC_STATUS_ACEPTADO_DIST = '03'
    SC_STATUS_RECHAZO = '04'
    SC_STATUS_CANCELADO = '05'
    SC_STATUS_ACTIVADO = '06'
    SC_STATUS_ACEPTADO_COMER = '10'
    
    SC_TYPE_CORTE_REENGANCHE = '21'
    SC_TYPE_BAJA = '02'
    SC_TYPE_CORTADO = '08'
    SC_TYPE_REENGANCHE = '09'
    
    SC_CATEGORY_CORTADO = '18'
    SC_CATEGORY_REENGANCHE = '17'
    
    def get_queries(self, preview: bool = False) -> list[str]:
        """
        Retorna las consultas necesarias.
        
        Query 0: Solicitudes de contratación (cortado/reenganche)
        Query 1: Assets de contratos activos
        """
        
        limit_clause = "LIMIT 5000" if preview else ""
        
        # Query 0: Solicitudes de Contratación
        query_solicitudes = f"""
            SELECT Id, CreatedDate, acn_fld_Contract__c, acn_fld_Contract__r.status, 
                   acn_fld_Sctype__c, acn_fld_Category__c, acn_fld_Status__c, 
                   acn_fld_Contract__r.acn_fld_BusinessDivision__c,
                   acn_fld_Contract__r.acn_fld_ContractCode2__c,
                   acn_fld_Contract__r.acn_fld_CUPS__r.Name,
                   acn_fld_resultreasondef__c
            FROM acn_obj_ContractRequest__c 
            WHERE 
                (acn_fld_Sctype__c = '21' OR acn_fld_Sctype__c = '09' 
                 OR acn_fld_Sctype__c = '08' OR acn_fld_Sctype__c = '02') 
                AND acn_fld_Contract__r.status = '02'
            {limit_clause}
        """
        
        # Query 1: Assets de contratos activos
        query_assets = f"""
            SELECT vlocity_cmt__ContractId__c, 
                   vlocity_cmt__ContractId__r.acn_fld_ContractCode2__c,
                   vlocity_cmt__ContractId__r.acn_fld_CUPS__r.Name,
                   vlocity_cmt__ContractId__r.acn_fld_BusinessDivision__c,
                   Id, 
                   Status, 
                   acn_fld_StartDateVersion__c, 
                   CreatedDate 
            FROM Asset 
            WHERE vlocity_cmt__ContractId__c IN (
                SELECT Id FROM Contract 
                WHERE Status = '02' 
                AND NewCo_ServiceAccount__c != null
            ) 
            AND vlocity_cmt__ParentItemId__c = null
            {limit_clause}
        """
        
        return [query_solicitudes, query_assets]
    
    def setup_causisticas(self):
        """Configura todas las causísticas del script."""
        
        # Causísticas A (solo cortado)
        self._causistica_manager.register(CausisticaDefinition(
            code="A0",
            name="Contratos sin Assets (solo cortado)",
            description="Contratos con SC cortado pero sin assets",
            severity="error"
        ))
        
        self._causistica_manager.register(CausisticaDefinition(
            code="A1",
            name="SC Corte En Curso - Asset Incorrecto",
            description="SC en curso/aceptado pero asset no está en estado correcto",
            severity="warning"
        ))
        
        self._causistica_manager.register(CausisticaDefinition(
            code="A2",
            name="SC Corte Activada - Asset Incorrecto",
            description="SC activada pero asset no está cortado",
            severity="error"
        ))
        
        # Causística B
        self._causistica_manager.register(CausisticaDefinition(
            code="B",
            name="Assets con Status Problemático Fuera de Posición",
            description="Assets con status 07/08/09 que no están en posición más reciente",
            severity="warning"
        ))
        
        # Causísticas C1 (corte más reciente)
        self._causistica_manager.register(CausisticaDefinition(
            code="C1-A0",
            name="Sin Assets - Corte Más Reciente",
            description="Corte más reciente que reenganche, sin assets",
            severity="error"
        ))
        
        self._causistica_manager.register(CausisticaDefinition(
            code="C1-A1",
            name="SC Corte En Curso - Corte Más Reciente",
            description="Corte más reciente, SC en curso con asset incorrecto",
            severity="warning"
        ))
        
        self._causistica_manager.register(CausisticaDefinition(
            code="C1-A2",
            name="SC Corte Activada - Corte Más Reciente",
            description="Corte más reciente, SC activada con asset incorrecto",
            severity="error"
        ))
        
        # Causísticas C (reenganche) - Electricidad
        for code, name, desc in [
            ("C2", "Electricidad: SC En Curso - Asset No Reenganche", 
             "Electricidad, SC en curso pero asset no está en reenganche en curso"),
            ("C3", "Electricidad: Rechazo Definitivo - Asset en Reenganche",
             "Electricidad, rechazo definitivo pero asset sigue en reenganche"),
            ("C4", "Electricidad: Rechazo No Definitivo - Asset No Reenganche",
             "Electricidad, rechazo no definitivo pero asset no está en reenganche"),
            ("C5", "Electricidad: Aceptado Dist - Asset No Activado",
             "Electricidad, aceptado distribuidora pero asset no activado"),
            ("C12", "Electricidad: SC Activada - Asset No Activado",
             "Electricidad, SC activada pero asset no activado"),
        ]:
            self._causistica_manager.register(CausisticaDefinition(
                code=code, name=name, description=desc, severity="warning"
            ))
        
        # Causísticas C (reenganche) - Gas
        for code, name, desc in [
            ("C6", "Gas: SC En Curso - Asset No Reenganche",
             "Gas, SC en curso pero asset no está en reenganche en curso"),
            ("C7", "Gas: Aceptado Dist - Asset No Reenganche",
             "Gas, aceptado distribuidora pero asset no está en reenganche"),
            ("C8", "Gas: Rechazo Definitivo - Asset en Reenganche",
             "Gas, rechazo definitivo pero asset sigue en reenganche"),
            ("C9", "Gas: Rechazo No Definitivo - Asset No Reenganche",
             "Gas, rechazo no definitivo pero asset no está en reenganche"),
            ("C10", "Gas: SC Activada - Asset No Activado",
             "Gas, SC activada pero asset no activado"),
        ]:
            self._causistica_manager.register(CausisticaDefinition(
                code=code, name=name, description=desc, severity="warning"
            ))
        
        # Causísticas comunes C
        self._causistica_manager.register(CausisticaDefinition(
            code="C11",
            name="SC Cancelada - Asset en Reenganche",
            description="SC cancelada pero asset sigue en reenganche en curso",
            severity="error"
        ))
        
        self._causistica_manager.register(CausisticaDefinition(
            code="C13",
            name="Reenganche Cancelado + Corte Activado - Asset No Cortado",
            description="Reenganche cancelado con corte activado pero asset no está cortado",
            severity="error"
        ))
        
        self._causistica_manager.register(CausisticaDefinition(
            code="C14",
            name="Reenganche Cancelado + Corte En Curso - Asset No En Curso",
            description="Reenganche cancelado con corte en curso pero asset no está en corte en curso",
            severity="error"
        ))
        
        # Causísticas D (múltiples reenganches) - usa mismos códigos con prefijo D
        for code_c in ["D2", "D3", "D4", "D5", "D6", "D7", "D8", "D9", "D10", "D11", "D12", "D13", "D14"]:
            # Reusar definiciones de C pero con prefijo D
            code_num = code_c[1:]
            original_def = self._causistica_manager.definitions.get(f"C{code_num}")
            if original_def:
                self._causistica_manager.register(CausisticaDefinition(
                    code=f"D{code_num}",
                    name=original_def.name.replace("Electricidad:", "D-Electricidad:").replace("Gas:", "D-Gas:").replace("SC", "D-SC"),
                    description=f"Múltiples reenganches: {original_def.description}",
                    severity=original_def.severity
                ))
    
    def process(self, query_results: dict[str, pd.DataFrame]) -> ScriptResult:
        """
        Procesa las consultas y ejecuta todas las causísticas.
        """
        df_solicitudes = query_results.get('query_0', pd.DataFrame())
        df_assets = query_results.get('query_1', pd.DataFrame())
        
        if df_solicitudes.empty:
            return ScriptResult(
                success=True,
                data=pd.DataFrame(),
                metrics=ScriptMetrics(total_records=0),
                has_causisticas=False
            )
        
        # Convertir a lista de diccionarios para procesamiento
        solicitudes = df_solicitudes.to_dict('records')
        assets_raw = df_assets.to_dict('records')
        
        # ==================== PASO 1: CLASIFICAR SOLICITUDES ====================
        print(f"\n📊 Total solicitudes obtenidas: {len(solicitudes)}")
        
        # Detectar contratos con baja
        contratos_con_baja = set()
        for sol in solicitudes:
            if sol.get('acn_fld_Sctype__c') == self.SC_TYPE_BAJA:
                contrato_id = sol.get('acn_fld_Contract__c')
                if contrato_id:
                    contratos_con_baja.add(contrato_id)
        
        print(f"⛔ Contratos ignorados por Baja: {len(contratos_con_baja)}")
        
        # Agrupar solicitudes por contrato
        contratos_agrupados = defaultdict(lambda: {'cortado': [], 'reenganche': []})
        
        for sol in solicitudes:
            contrato_id = sol.get('acn_fld_Contract__c')
            if not contrato_id or contrato_id in contratos_con_baja:
                continue
            
            sctype = sol.get('acn_fld_Sctype__c')
            category = sol.get('acn_fld_Category__c')
            
            if sctype == self.SC_TYPE_CORTE_REENGANCHE:
                if category == self.SC_CATEGORY_CORTADO:
                    contratos_agrupados[contrato_id]['cortado'].append(sol)
                elif category == self.SC_CATEGORY_REENGANCHE:
                    contratos_agrupados[contrato_id]['reenganche'].append(sol)
            elif sctype == self.SC_TYPE_CORTADO:
                contratos_agrupados[contrato_id]['cortado'].append(sol)
            elif sctype == self.SC_TYPE_REENGANCHE:
                contratos_agrupados[contrato_id]['reenganche'].append(sol)
        
        # Clasificar contratos
        contratos_solo_cortado_ids = set()
        contratos_con_reenganche = []
        contratos_skipped_corte_reciente = set()
        contratos_skipped_multiples_reenganche = set()
        
        for contrato_id, tipos in contratos_agrupados.items():
            tiene_cortado = len(tipos['cortado']) > 0
            tiene_reenganche = len(tipos['reenganche']) > 0
            
            if tiene_cortado and not tiene_reenganche:
                # Solo cortado
                contratos_solo_cortado_ids.add(contrato_id)
            elif tiene_reenganche:
                # Ordenar todas las solicitudes por fecha
                todas_solicitudes = tipos['cortado'] + tipos['reenganche']
                todas_solicitudes_ordenadas = sorted(
                    todas_solicitudes,
                    key=lambda x: x.get('CreatedDate', '1900-01-01'),
                    reverse=True
                )
                
                solicitud_mas_reciente = todas_solicitudes_ordenadas[0]
                es_cortado_mas_reciente = solicitud_mas_reciente in tipos['cortado']
                
                if es_cortado_mas_reciente:
                    # C1: Corte más reciente
                    contratos_skipped_corte_reciente.add(contrato_id)
                elif len(tipos['reenganche']) == 1:
                    # C: Un solo reenganche
                    contratos_con_reenganche.append({
                        'contrato_id': contrato_id,
                        'sc_reenganche': tipos['reenganche'][0],
                        'scs_cortado': tipos['cortado']
                    })
                else:
                    # D: Múltiples reenganches
                    contratos_skipped_multiples_reenganche.add(contrato_id)
        
        print(f"\n📊 Clasificación:")
        print(f"   - Solo cortado: {len(contratos_solo_cortado_ids)}")
        print(f"   - Con reenganche (C): {len(contratos_con_reenganche)}")
        print(f"   - Corte más reciente (C1): {len(contratos_skipped_corte_reciente)}")
        print(f"   - Múltiples reenganches (D): {len(contratos_skipped_multiples_reenganche)}")
        
        # ==================== PASO 2: AGRUPAR ASSETS POR CONTRATO ====================
        assets_por_contrato = defaultdict(list)
        
        for asset in assets_raw:
            contrato_id = asset.get('vlocity_cmt__ContractId__c')
            if contrato_id:
                # Normalizar campos
                asset['acn_fld_Contract__c'] = contrato_id
                assets_por_contrato[contrato_id].append(asset)
        
        # Ordenar assets de cada contrato por CreatedDate (más nuevo primero)
        for contrato_id in assets_por_contrato:
            assets_por_contrato[contrato_id].sort(
                key=lambda x: x.get('CreatedDate', '1900-01-01T00:00:00.000+0000'),
                reverse=True
            )
        
        print(f"\n📊 Assets cargados:")
        print(f"   - Contratos con assets: {len(assets_por_contrato)}")
        print(f"   - Total assets: {sum(len(a) for a in assets_por_contrato.values())}")
        
        # ==================== PASO 3: PROCESAR CAUSÍSTICAS ====================
        
        # Guardar contexto compartido
        self._causistica_manager.set_context('contratos_agrupados', contratos_agrupados)
        self._causistica_manager.set_context('assets_por_contrato', assets_por_contrato)
        
        # Causística A: Contratos solo cortado
        self._process_causistica_a(contratos_solo_cortado_ids, contratos_agrupados, assets_por_contrato)
        
        #  Causística B: Assets fuera de posición
        self._process_causistica_b(assets_por_contrato)
        
        # Causística C1: Corte más reciente
        self._process_causistica_c1(contratos_skipped_corte_reciente, contratos_agrupados, assets_por_contrato)
        
        # Causística C: Reenganche
        self._process_causistica_c(contratos_con_reenganche, assets_por_contrato)
        
        # Causística D: Múltiples reenganches
        self._process_causistica_d(contratos_skipped_multiples_reenganche, contratos_agrupados, assets_por_contrato)
        
        # ==================== PASO 4: GENERAR RESULTADO ====================
        
        # Obtener todas las causísticas procesadas
        causisticas_results = self.get_causistica_results()
        
        print(f"\n📊 Causísticas Detectadas: {len(causisticas_results)}")
        for code, caus in sorted(causisticas_results.items()):
            print(f"   - {code}: {caus.name} ({caus.count} registros)")
        
        # DEBUG: Verificar estructura del resultado
        print(f"\n🔍 DEBUG - Verificando resultado:")
        print(f"   - causisticas_results tipo: {type(causisticas_results)}")
        print(f"   - causisticas_results vacío: {len(causisticas_results) == 0}")
        print(f"   - causisticas_results keys: {list(causisticas_results.keys())}")
        
        # Calcular métricas globales
        total_records = sum(caus.count for caus in causisticas_results.values())
        
        metrics = ScriptMetrics(total_records=total_records)
        metrics.add_metric(
            'total_causisticas',
            len(causisticas_results),
            'Causísticas Detectadas',
            '📊'
        )
        metrics.add_metric(
            'total_errores',
            total_records,
            'Total Registros con Error',
            '⚠️'
        )
        metrics.add_metric(
            'contratos_solo_cortado',
            len(contratos_solo_cortado_ids),
            'Contratos Solo Cortado',
            '✂️'
        )
        metrics.add_metric(
            'contratos_con_reenganche',
            len(contratos_con_reenganche) + len(contratos_skipped_corte_reciente) + len(contratos_skipped_multiples_reenganche),
            'Contratos con Reenganche',
            '🔄'
        )
        
        # Si hay causísticas, return con has_causisticas=True
        if causisticas_results:
            print(f"\n✅ RETORNANDO CON CAUSÍSTICAS:")
            print(f"   - has_causisticas=True")
            print(f"   - causisticas={len(causisticas_results)} items")
            print(f"   - script_instance={type(self).__name__}")
            
            return ScriptResult(
                success=True,
                data=pd.DataFrame(),  # No usado cuando has_causisticas=True
                metrics=metrics,
                causisticas=causisticas_results,
                has_causisticas=True,
                script_instance=self
            )
        else:
            print(f"\n⚠️ SIN CAUSÍSTICAS - Retornando resultado vacío")
            
            # Sin causísticas detectadas
            return ScriptResult(
                success=True,
                data=pd.DataFrame([{
                    'Mensaje': 'No se detectaron inconsistencias',
                    'Contratos_Analizados': len(contratos_agrupados),
                    'Contratos_Solo_Cortado': len(contratos_solo_cortado_ids),
                    'Contratos_Con_Reenganche': len(contratos_con_reenganche)
                }]),
                metrics=metrics,
                has_causisticas=False,
                script_instance=self
            )
    
    def _process_causistica_a(self, contratos_ids: set, contratos_agrupados: dict, assets_por_contrato: dict):
        """Procesa causística A: Contratos solo cortado."""
        
        registros_a0 = []
        registros_a1 = []
        registros_a2 = []
        
        print(f"\n🔍 Procesando Causística A: {len(contratos_ids)} contratos solo cortado")
        
        for contrato_id in contratos_ids:
            solicitudes_contrato = contratos_agrupados[contrato_id]
            assets = assets_por_contrato.get(contrato_id, [])
            
            for sol in solicitudes_contrato['cortado']:
                validacion = self._validar_cortado(sol, assets, 'A')
                
                if not validacion['error_detectado']:
                    continue
                
                # Datos base comunes
                datos_base = self._crear_datos_base_solicitud(sol, contrato_id, validacion)
                
                # Agregar a la lista correspondiente según causística
                if validacion['causistica_code'] == 'A0':
                    registros_a0.append(datos_base)
                elif validacion['causistica_code'] == 'A1':
                    datos_base.update(self._agregar_datos_asset(validacion))
                    registros_a1.append(datos_base)
                elif validacion['causistica_code'] == 'A2':
                    datos_base.update(self._agregar_datos_asset(validacion))
                    registros_a2.append(datos_base)
        
        # Crear resultados de causística
        if registros_a0:
            print(f"  ✅ A0: {len(registros_a0)} registros")
            self._causistica_manager.results['A0'] = CausisticaResult(
                code='A0',
                name=self._causistica_manager.definitions['A0'].name,
                description=self._causistica_manager.definitions['A0'].description,
                severity='error',
                data=pd.DataFrame(registros_a0)
            )
        
        if registros_a1:
            print(f"  ✅ A1: {len(registros_a1)} registros")
            self._causistica_manager.results['A1'] = CausisticaResult(
                code='A1',
                name=self._causistica_manager.definitions['A1'].name,
                description=self._causistica_manager.definitions['A1'].description,
                severity='warning',
                data=pd.DataFrame(registros_a1)
            )
        
        if registros_a2:
            print(f"  ✅ A2: {len(registros_a2)} registros")
            self._causistica_manager.results['A2'] = CausisticaResult(
                code='A2',
                name=self._causistica_manager.definitions['A2'].name,
                description=self._causistica_manager.definitions['A2'].description,
                severity='error',
                data=pd.DataFrame(registros_a2)
            )
    
    def _process_causistica_b(self, assets_por_contrato: dict):
        """Procesa causística B: Assets con status problemático fuera de posición."""
        
        registros_b = []
        status_problematicos = [self.ASSET_STATUS_CORTE_EN_CURSO, 
                               self.ASSET_STATUS_CORTADO, 
                               self.ASSET_STATUS_REENGANCHE_EN_CURSO]
        
        print(f"\n🔍 Procesando Causística B: Assets fuera de posición")
        
        for contrato_id, assets in assets_por_contrato.items():
            if len(assets) <= 1:
                continue
            
            # Revisar assets desde posición 1 en adelante
            for i, asset in enumerate(assets[1:], start=1):
                status = asset.get('Status')
                
                if status in status_problematicos:
                    asset_mas_reciente = assets[0]
                    
                    registros_b.append({
                        'Id_Contrato': contrato_id,
                        'Codigo_Contrato': asset.get('vlocity_cmt__ContractId__r.acn_fld_ContractCode2__c', ''),
                        'CUPS': asset.get('vlocity_cmt__ContractId__r.acn_fld_CUPS__r.Name', ''),
                        'Division_Negocio': asset.get('vlocity_cmt__ContractId__r.acn_fld_BusinessDivision__c', ''),
                        'Id_Asset_Problematico': asset.get('Id'),
                        'Status_Asset_Problematico': status,
                        'Posicion_Asset_Problematico': i,
                        'Fecha_Asset_Problematico': asset.get('CreatedDate'),
                        'Id_Asset_Mas_Reciente': asset_mas_reciente.get('Id'),
                        'Status_Asset_Mas_Reciente': asset_mas_reciente.get('Status'),
                        'Fecha_Asset_Mas_Reciente': asset_mas_reciente.get('CreatedDate'),
                        'Total_Assets': len(assets),
                        'Alerta': f'⚠️ Asset con status {status} en posición {i}'
                    })
        
        if registros_b:
            print(f"  ✅ B: {len(registros_b)} registros")
            self._causistica_manager.results['B'] = CausisticaResult(
                code='B',
                name=self._causistica_manager.definitions['B'].name,
                description=self._causistica_manager.definitions['B'].description,
                severity='warning',
                data=pd.DataFrame(registros_b)
            )
    
    def _process_causistica_c1(self, contratos_ids: set, contratos_agrupados: dict, assets_por_contrato: dict):
        """Procesa causística C1: Corte más reciente que reenganche."""
        
        print(f"\n🔍 Procesando Causística C1: {len(contratos_ids)} contratos con corte más reciente")
        
        registros_c1_a0 = []
        registros_c1_a1 = []
        registros_c1_a2 = []
        
        for contrato_id in contratos_ids:
            solicitudes_contrato = contratos_agrupados[contrato_id]
            assets = assets_por_contrato.get(contrato_id, [])
            
            scs_cortado = solicitudes_contrato['cortado']
            if not scs_cortado:
                continue
            
            # Obtener solo la SC de cortado más reciente
            sc_cortado_mas_reciente = sorted(
                scs_cortado,
                key=lambda x: x.get('CreatedDate', '1900-01-01'),
                reverse=True
            )[0]
            
            validacion = self._validar_cortado(sc_cortado_mas_reciente, assets, 'C1-A')
            
            if not validacion['error_detectado']:
                continue
            
            datos_base = self._crear_datos_base_solicitud(sc_cortado_mas_reciente, contrato_id, validacion)
            
            if validacion['causistica_code'] == 'C1-A0':
                datos_base['Alerta'] = f"❌ [C1-A0] Contrato sin assets (corte más reciente que reenganche)"
                registros_c1_a0.append(datos_base)
            elif validacion['causistica_code'] == 'C1-A1':
                datos_base.update(self._agregar_datos_asset(validacion))
                registros_c1_a1.append(datos_base)
            elif validacion['causistica_code'] == 'C1-A2':
                datos_base.update(self._agregar_datos_asset(validacion))
                datos_base['Alerta'] = '[C1-A2] Asset NO está en status 08 (Cortado) - corte más reciente'
                registros_c1_a2.append(datos_base)
        
        # Crear resultados
        for code, registros in [('C1-A0', registros_c1_a0), ('C1-A1', registros_c1_a1), ('C1-A2', registros_c1_a2)]:
            if registros:
                print(f"  ✅ {code}: {len(registros)} registros")
                self._causistica_manager.results[code] = CausisticaResult(
                    code=code,
                    name=self._causistica_manager.definitions[code].name,
                    description=self._causistica_manager.definitions[code].description,
                    severity=self._causistica_manager.definitions[code].severity,
                    data=pd.DataFrame(registros)
                )
    
    def _process_causistica_c(self, contratos_con_reenganche: list, assets_por_contrato: dict):
        """Procesa causística C: Reenganche."""
        
        print(f"\n🔍 Procesando Causística C: {len(contratos_con_reenganche)} contratos con reenganche único")
        
        registros_por_code = defaultdict(list)
        
        for item in contratos_con_reenganche:
            contrato_id = item['contrato_id']
            sc_reenganche = item['sc_reenganche']
            scs_cortado = item.get('scs_cortado', [])
            
            assets = assets_por_contrato.get(contrato_id, [])
            
            resultado = self._validar_reenganche(sc_reenganche, assets, scs_cortado, 'C')
            
            if resultado['error_detectado']:
                datos = self._crear_datos_base_solicitud(sc_reenganche, contrato_id, resultado)
                datos.update({
                    'Rechazo_Definitivo': resultado.get('rechazo_definitivo', False),
                    'Id_Asset': assets[0].get('Id') if assets else None,
                    'Status_Asset': resultado['status_asset'],
                    'Fecha_Asset': assets[0].get('CreatedDate') if assets else None,
                    'Total_Assets': len(assets),
                    'Causistica': resultado['causistica_code']
                })
                
                registros_por_code[resultado['causistica_code']].append(datos)
        
        # Crear resultados para cada causística C detectada
        for code, registros in registros_por_code.items():
            if registros and code in self._causistica_manager.definitions:
                print(f"  ✅ {code}: {len(registros)} registros")
                self._causistica_manager.results[code] = CausisticaResult(
                    code=code,
                    name=self._causistica_manager.definitions[code].name,
                    description=self._causistica_manager.definitions[code].description,
                    severity=self._causistica_manager.definitions[code].severity,
                    data=pd.DataFrame(registros)
                )
    
    def _process_causistica_d(self, contratos_ids: set, contratos_agrupados: dict, assets_por_contrato: dict):
        """Procesa causística D: Múltiples reenganches."""
        
        print(f"\n🔍 Procesando Causística D: {len(contratos_ids)} contratos con múltiples reenganches")
        
        registros_por_code = defaultdict(list)
        
        for contrato_id in contratos_ids:
            solicitudes_contrato = contratos_agrupados[contrato_id]
            scs_reenganche = solicitudes_contrato['reenganche']
            scs_cortado = solicitudes_contrato['cortado']
            
            if not scs_reenganche:
                continue
            
            # Obtener reenganche más reciente
            sc_reenganche = sorted(scs_reenganche, key=lambda x: x['CreatedDate'], reverse=True)[0]
            
            # Obtener corte más reciente (si existe)
            sc_corte_reciente_list = []
            if scs_cortado:
                sc_corte_reciente = sorted(scs_cortado, key=lambda x: x['CreatedDate'], reverse=True)[0]
                sc_corte_reciente_list = [sc_corte_reciente]
            
            assets = assets_por_contrato.get(contrato_id, [])
            
            resultado = self._validar_reenganche(sc_reenganche, assets, sc_corte_reciente_list, 'D')
            
            if resultado['error_detectado']:
                datos = self._crear_datos_base_solicitud(sc_reenganche, contrato_id, resultado)
                datos.update({
                    'Rechazo_Definitivo': resultado.get('rechazo_definitivo', False),
                    'Id_Asset': assets[0].get('Id') if assets else None,
                    'Status_Asset': resultado['status_asset'],
                    'Fecha_Asset': assets[0].get('CreatedDate') if assets else None,
                    'Total_Assets': len(assets),
                    'Total_Reenganches': len(scs_reenganche),
                    'Total_Cortes': len(scs_cortado),
                    'Causistica': resultado['causistica_code']
                })
                
                registros_por_code[resultado['causistica_code']].append(datos)
        
        # Crear resultados para cada causística D detectada
        for code, registros in registros_por_code.items():
            if registros and code in self._causistica_manager.definitions:
                print(f"  ✅ {code}: {len(registros)} registros")
                self._causistica_manager.results[code] = CausisticaResult(
                    code=code,
                    name=self._causistica_manager.definitions[code].name,
                    description=self._causistica_manager.definitions[code].description,
                    severity=self._causistica_manager.definitions[code].severity,
                    data=pd.DataFrame(registros)
                )
    
    # ==================== FUNCIONES DE VALIDACIÓN ====================
    
    def _validar_cortado(self, sc_cortado: dict, assets: list, causistica_prefix: str) -> dict:
        """
        Valida contratos con solicitudes de cortado.
        
        Retorna dict con: error_detectado, causistica_code, alerta, status_asset, etc.
        """
        estado_sc = sc_cortado.get('acn_fld_Status__c')
        division_negocio = sc_cortado.get('acn_fld_Contract__r.acn_fld_BusinessDivision__c', '')
        
        # CASO 0: Sin assets
        if not assets:
            return {
                'error_detectado': True,
                'causistica_code': f'{causistica_prefix}0',
                'alerta': f'❌ [{causistica_prefix}0] Contrato sin assets',
                'status_asset': None,
                'estado_sc': estado_sc,
                'division_negocio': division_negocio
            }
        
        asset_mas_reciente = assets[0]
        status_asset = asset_mas_reciente.get('Status')
        
        # CASO 1: SC En Curso/Aceptado
        if estado_sc in [self.SC_STATUS_EN_CURSO, self.SC_STATUS_ACEPTADO_DIST, self.SC_STATUS_ACEPTADO_COMER]:
            if estado_sc == self.SC_STATUS_ACEPTADO_DIST:
                if division_negocio == 'Gas':
                    status_esperado = self.ASSET_STATUS_CORTE_EN_CURSO
                    alerta = f'[{causistica_prefix}1] SC Aceptado Dist Gas - Asset debería ser 07'
                else:
                    status_esperado = self.ASSET_STATUS_CORTADO
                    alerta = f'[{causistica_prefix}1] SC Aceptado Dist Elec - Asset debería ser 08'
            else:
                status_esperado = self.ASSET_STATUS_CORTE_EN_CURSO
                alerta = f'[{causistica_prefix}1] SC En Curso - Asset debería ser 07'
            
            if status_asset != status_esperado:
                return {
                    'error_detectado': True,
                    'causistica_code': f'{causistica_prefix}1',
                    'alerta': alerta,
                    'status_asset': status_asset,
                    'status_esperado': status_esperado,
                    'estado_sc': estado_sc,
                    'division_negocio': division_negocio,
                    'asset_mas_reciente': asset_mas_reciente,
                    'total_assets': len(assets)
                }
        
        # CASO 2: SC Activado
        elif estado_sc == self.SC_STATUS_ACTIVADO:
            if status_asset != self.ASSET_STATUS_CORTADO:
                return {
                    'error_detectado': True,
                    'causistica_code': f'{causistica_prefix}2',
                    'alerta': f'[{causistica_prefix}2] Asset NO está en status 08 (Cortado)',
                    'status_asset': status_asset,
                    'status_esperado': self.ASSET_STATUS_CORTADO,
                    'estado_sc': estado_sc,
                    'division_negocio': division_negocio,
                    'asset_mas_reciente': asset_mas_reciente,
                    'total_assets': len(assets)
                }
        
        return {'error_detectado': False}
    
    def _validar_reenganche(self, sc_reenganche: dict, assets: list, scs_cortado: Optional[list], causistica_prefix: str) -> dict:
        """
        Valida contratos con solicitudes de reenganche.
        
        Implementa todas las reglas C2-C14 / D2-D14.
        """
        estado_sc = sc_reenganche.get('acn_fld_Status__c')
        division_negocio = sc_reenganche.get('acn_fld_Contract__r.acn_fld_BusinessDivision__c', '')
        rechazo_definitivo_str = sc_reenganche.get('acn_fld_resultreasondef__c', 'false')
        rechazo_definitivo = rechazo_definitivo_str.lower() == 'true' if rechazo_definitivo_str else False
        
        if not assets:
            return {
                'error_detectado': True,
                'causistica_code': f'{causistica_prefix}-SIN_ASSETS',
                'alerta': 'Contrato sin assets',
                'status_asset': None,
                'estado_sc': estado_sc,
                'division_negocio': division_negocio,
                'rechazo_definitivo': rechazo_definitivo
            }
        
        asset_reciente = assets[0]
        status_asset = asset_reciente.get('Status')
        
        # C11/D11: SC Cancelado pero asset en reenganche
        if estado_sc == self.SC_STATUS_CANCELADO and status_asset == self.ASSET_STATUS_REENGANCHE_EN_CURSO:
            return {
                'error_detectado': True,
                'causistica_code': f'{causistica_prefix}11',
                'alerta': 'SC Cancelado pero Asset está en Reenganche en curso',
                'status_asset': status_asset,
                'estado_sc': estado_sc,
                'division_negocio': division_negocio,
                'rechazo_definitivo': rechazo_definitivo
            }
        
        # Validaciones Electricidad
        if division_negocio == 'Electricidad':
            # C2/D2: En Curso
            if estado_sc == self.SC_STATUS_EN_CURSO and status_asset != self.ASSET_STATUS_REENGANCHE_EN_CURSO:
                return self._crear_resultado_error(f'{causistica_prefix}2', 'SC En Curso pero Asset no está en Reenganche',
                                                   estado_sc, division_negocio, status_asset, rechazo_definitivo)
            
            # C3/D3: Rechazo definitivo
            elif estado_sc == self.SC_STATUS_RECHAZO and rechazo_definitivo and status_asset == self.ASSET_STATUS_REENGANCHE_EN_CURSO:
                return self._crear_resultado_error(f'{causistica_prefix}3', 'SC Rechazo Definitivo pero Asset en Reenganche',
                                                   estado_sc, division_negocio, status_asset, rechazo_definitivo)
            
            # C4/D4: Rechazo no definitivo
            elif estado_sc == self.SC_STATUS_RECHAZO and not rechazo_definitivo and status_asset != self.ASSET_STATUS_REENGANCHE_EN_CURSO:
                return self._crear_resultado_error(f'{causistica_prefix}4', 'SC Rechazo No Definitivo pero Asset no en Reenganche',
                                                   estado_sc, division_negocio, status_asset, rechazo_definitivo)
            
            # C5/D5: Aceptado Distribuidora
            elif estado_sc == self.SC_STATUS_ACEPTADO_DIST and status_asset != self.ASSET_STATUS_ACTIVADO:
                return self._crear_resultado_error(f'{causistica_prefix}5', 'SC Aceptado Dist pero Asset no Activado',
                                                   estado_sc, division_negocio, status_asset, rechazo_definitivo)
            
            # C12/D12: Activada
            elif estado_sc == self.SC_STATUS_ACTIVADO and status_asset != self.ASSET_STATUS_ACTIVADO:
                return self._crear_resultado_error(f'{causistica_prefix}12', 'SC Activada Elec pero Asset no Activado',
                                                   estado_sc, division_negocio, status_asset, rechazo_definitivo)
        
        # Validaciones Gas
        elif division_negocio == 'Gas':
            # C6/D6: En Curso
            if estado_sc == self.SC_STATUS_EN_CURSO and status_asset != self.ASSET_STATUS_REENGANCHE_EN_CURSO:
                return self._crear_resultado_error(f'{causistica_prefix}6', 'SC En Curso Gas pero Asset no en Reenganche',
                                                   estado_sc, division_negocio, status_asset, rechazo_definitivo)
            
            # C7/D7: Aceptado Distribuidora
            elif estado_sc == self.SC_STATUS_ACEPTADO_DIST and status_asset != self.ASSET_STATUS_REENGANCHE_EN_CURSO:
                return self._crear_resultado_error(f'{causistica_prefix}7', 'SC Aceptado Dist Gas pero Asset no en Reenganche',
                                                   estado_sc, division_negocio, status_asset, rechazo_definitivo)
            
            # C8/D8: Rechazo definitivo
            elif estado_sc == self.SC_STATUS_RECHAZO and rechazo_definitivo and status_asset == self.ASSET_STATUS_REENGANCHE_EN_CURSO:
                return self._crear_resultado_error(f'{causistica_prefix}8', 'SC Rechazo Definitivo Gas pero Asset en Reenganche',
                                                   estado_sc, division_negocio, status_asset, rechazo_definitivo)
            
            # C9/D9: Rechazo no definitivo
            elif estado_sc == self.SC_STATUS_RECHAZO and not rechazo_definitivo and status_asset != self.ASSET_STATUS_REENGANCHE_EN_CURSO:
                return self._crear_resultado_error(f'{causistica_prefix}9', 'SC Rechazo No Definitivo Gas pero Asset no en Reenganche',
                                                   estado_sc, division_negocio, status_asset, rechazo_definitivo)
            
            # C10/D10: Activada
            elif estado_sc == self.SC_STATUS_ACTIVADO and status_asset != self.ASSET_STATUS_ACTIVADO:
                return self._crear_resultado_error(f'{causistica_prefix}10', 'SC Activada Gas pero Asset no Activado',
                                                   estado_sc, division_negocio, status_asset, rechazo_definitivo)
        
        # C13/D13 y C14/D14: Reenganche cancelado con cortado
        if estado_sc == self.SC_STATUS_CANCELADO and scs_cortado:
            for sc_corte in scs_cortado:
                estado_corte = sc_corte.get('acn_fld_Status__c')
                
                # C13/D13: Corte activado/aceptado
                if division_negocio == 'Electricidad' and estado_corte in [self.SC_STATUS_ACEPTADO_DIST, self.SC_STATUS_ACTIVADO]:
                    if status_asset != self.ASSET_STATUS_CORTADO:
                        return self._crear_resultado_error(f'{causistica_prefix}13', 
                                                           f'Reenganche Cancelado + Corte Elec {estado_corte} pero Asset no Cortado',
                                                           estado_sc, division_negocio, status_asset, rechazo_definitivo)
                elif division_negocio == 'Gas' and estado_corte == self.SC_STATUS_ACTIVADO:
                    if status_asset != self.ASSET_STATUS_CORTADO:
                        return self._crear_resultado_error(f'{causistica_prefix}13',
                                                           'Reenganche Cancelado + Corte Gas Activado pero Asset no Cortado',
                                                           estado_sc, division_negocio, status_asset, rechazo_definitivo)
                
                # C14/D14: Corte en curso
                if estado_corte == self.SC_STATUS_EN_CURSO and status_asset != self.ASSET_STATUS_CORTE_EN_CURSO:
                    return self._crear_resultado_error(f'{causistica_prefix}14',
                                                       'Reenganche Cancelado + Corte En Curso pero Asset no en Corte en curso',
                                                       estado_sc, division_negocio, status_asset, rechazo_definitivo)
        
        return {'error_detectado': False}
    
    # ==================== FUNCIONES AUXILIARES ====================
    
    def _crear_resultado_error(self, code: str, alerta: str, estado_sc: str, 
                               division_negocio: str, status_asset: str, rechazo_definitivo: bool) -> dict:
        """Crea un diccionario de resultado de error."""
        return {
            'error_detectado': True,
            'causistica_code': code,
            'alerta': alerta,
            'status_asset': status_asset,
            'estado_sc': estado_sc,
            'division_negocio': division_negocio,
            'rechazo_definitivo': rechazo_definitivo
        }
    
    def _crear_datos_base_solicitud(self, sol: dict, contrato_id: str, validacion: dict) -> dict:
        """Crea diccionario con datos base de una solicitud."""
        return {
            'Id_Contrato': contrato_id,
            'Codigo_Contrato': sol.get('acn_fld_Contract__r.acn_fld_ContractCode2__c', ''),
            'CUPS': sol.get('acn_fld_Contract__r.acn_fld_CUPS__r.Name', ''),
            'Id_Solicitud': sol.get('Id'),
            'Estado_Contrato': sol.get('acn_fld_Contract__r.status', ''),
            'Tipo_SC': sol.get('acn_fld_Sctype__c'),
            'Categoria': sol.get('acn_fld_Category__c'),
            'Estado_SC': validacion['estado_sc'],
            'Division_Negocio': validacion['division_negocio'],
            'Alerta': validacion['alerta']
        }
    
    def _agregar_datos_asset(self, validacion: dict) -> dict:
        """Agrega datos del asset a un registro."""
        asset_reciente = validacion.get('asset_mas_reciente', {})
        return {
            'Id_Asset_Reciente': asset_reciente.get('Id'),
            'Status_Asset_Reciente': validacion['status_asset'],
            'Status_Asset_Esperado': validacion.get('status_esperado'),
            'Fecha_Asset_Reciente': asset_reciente.get('CreatedDate'),
            'Total_Assets': validacion.get('total_assets', 0)
        }
