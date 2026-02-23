# Causística Framework - Guía de Uso

## 📋 Descripción

El **Causística Framework** es un sistema modular para gestionar scripts complejos que detectan múltiples escenarios de negocio (causísticas) con sus propios conjuntos de datos, métricas y validaciones.

Esta arquitectura fue diseñada para ser:
- ✅ **Mantenible**: Código organizado y fácil de entender
- ✅ **Escalable**: Agregar nuevos escenarios es sencillo
- ✅ **Retrocompatible**: Scripts simples siguen funcionando sin cambios
- ✅ **Reutilizable**: La lógica de validación se puede compartir entre causísticas

## 🏗️ Arquitectura

### Componentes Principales

```
core/
├── causistica.py          # Framework de causísticas
├── base_script.py         # BaseScript actualizado con soporte causísticas
└── execution_engine.py    # Motor de ejecución actualizado

pages/
└── script_execution.py    # UI con soporte para múltiples datasets

scripts/
├── contrato_reenganche_v3_completo.py  # Ejemplo completo con 15+ causísticas
└── premises_multiple_sp_same_energy.py # Ejemplo simple con causísticas
```

### Clases Clave

#### `CausisticaDefinition`
Define una causística con su código, nombre, descripción y funciones de validación.

```python
CausisticaDefinition(
    code="A1",
    name="SC En Curso con Asset Incorrecto",
    description="Solicitud en curso pero asset no tiene el status esperado",
    severity="warning",  # "info", "warning", "error", "critical"
    validator=my_validator_function,  # Optional
    processor=my_processor_function   # Optional
)
```

#### `CausisticaResult`
Contiene los resultados de una causística: datos, métricas y metadata.

```python
CausisticaResult(
    code="A1",
    name="...",
    data=pd.DataFrame(...),  # Registros encontrados
    description="...",
    severity="warning",
    custom_metrics={...}  # Métricas específicas
)
```

#### `CausisticaManager`
Gestiona el registro y procesamiento de múltiples causísticas.

## 🚀 Cómo Usar

### Opción 1: Script Simple (Sin Causísticas)

Scripts simples funcionan igual que siempre, sin cambios necesarios:

```python
@register_script
class MiScriptSimple(BaseScript):
    name = "Mi Script"
    description = "Descripción"
    category = "Categoría"
    
    def get_queries(self, preview: bool = False) -> list[str]:
        return ["SELECT ..."]
    
    def process(self, query_results: dict) -> ScriptResult:
        df = query_results['query_0']
        # ... procesar
        return ScriptResult(success=True, data=df, metrics=...)
```

### Opción 2: Script con Causísticas

Para scripts complejos con múltiples escenarios:

```python
@register_script
class MiScriptConCausisticas(BaseScript):
    name = "Mi Script Complejo"
    description = "Detecta múltiples causísticas"
    category = "Detección de inconsistencias"
    
    # ¡IMPORTANTE: Activar el framework!
    uses_causisticas = True
    
    def get_queries(self, preview: bool = False) -> list[str]:
        return ["SELECT ...", "SELECT ..."]
    
    def setup_causisticas(self):
        """Define las causísticas del script."""
        from core.causistica import CausisticaDefinition
        
        # Registrar causística A1
        self._causistica_manager.register(CausisticaDefinition(
            code="A1",
            name="Primera Causística",
            description="Detecta cuando...",
            severity="warning"
        ))
        
        # Registrar causística A2
        self._causistica_manager.register(CausisticaDefinition(
            code="A2",
            name="Segunda Causística",
            description="Detecta cuando...",
            severity="error"
        ))
        
        # ... más causísticas
    
    def process(self, query_results: dict) -> ScriptResult:
        """Procesa los datos y genera resultados por causística."""
        df_data1 = query_results['query_0']
        df_data2 = query_results['query_1']
        
        # Procesar y detectar registros por causística
        registros_a1 = []
        registros_a2 = []
        
        for record in df_data1.to_dict('records'):
            if self._cumple_condicion_a1(record):
                registros_a1.append(record)
            elif self._cumple_condicion_a2(record):
                registros_a2.append(record)
        
        # Crear resultados de causísticas
        from core.causistica import CausisticaResult
        
        if registros_a1:
            self._causistica_manager.results['A1'] = CausisticaResult(
                code='A1',
                name=self._causistica_manager.definitions['A1'].name,
                description=self._causistica_manager.definitions['A1'].description,
                severity='warning',
                data=pd.DataFrame(registros_a1)
            )
        
        if registros_a2:
            self._causistica_manager.results['A2'] = CausisticaResult(
                code='A2',
                name=self._causistica_manager.definitions['A2'].name,
                description=self._causistica_manager.definitions['A2'].description,
                severity='error',
                data=pd.DataFrame(registros_a2)
            )
        
        # Obtener todas las causísticas
        causisticas_results = self.get_causistica_results()
        
        # Calcular métricas globales
        total_records = sum(c.count for c in causisticas_results.values())
        metrics = ScriptMetrics(total_records=total_records)
        metrics.add_metric('total_causisticas', len(causisticas_results), 
                          'Causísticas Detectadas', '📊')
        
        # Crear resumen para vista rápida
        summary_data = [
            {
                'Causistica': code,
                'Nombre': caus.name,
                'Registros': caus.count,
                'Severidad': caus.severity
            }
            for code, caus in causisticas_results.items()
        ]
        summary_df = pd.DataFrame(summary_data)
        
        return ScriptResult(
            success=True,
            data=summary_df,  # Resumen
            metrics=metrics,
            causisticas=causisticas_results,  # Datos detallados
            has_causisticas=True
        )
    
    def _cumple_condicion_a1(self, record):
        """Lógica de validación para A1."""
        # ... tu lógica
        return False
    
    def _cumple_condicion_a2(self, record):
        """Lógica de validación para A2."""
        # ... tu lógica
        return False
```

## 📊 Interfaz de Usuario

### Vista con Causísticas

Cuando un script usa el framework de causísticas, la UI automáticamente muestra:

1. **Métricas Globales**: Resumen de todas las causísticas
2. **Tabla Resumen**: Vista rápida de todas las causísticas con contadores
3. **Exportación Completa**: 
   - CSV con todas las causísticas combinadas
   - Excel con una hoja por causística
4. **Pestañas por Causística**: Cada causística tiene su propia pestaña con:
   - Datos filtrados
   - Gráficos automáticos
   - Exportación individual (CSV/Excel)
   - Métricas específicas

### Ejemplo de Visualización

```
┌─────────────────────────────────────────────────────────┐
│ 📊 Resumen de Causísticas                               │
├────────┬──────────────────────────┬───────────┬─────────┤
│ Código │ Nombre                   │ Registros │ Severi. │
├────────┼──────────────────────────┼───────────┼─────────┤
│ A0     │ Contratos sin Assets     │ 45        │ ⚠️ Error│
│ A1     │ SC En Curso Incorrecto   │ 123       │ ⚠️ Warn │
│ A2     │ SC Activada Incorrecto   │ 67        │ ❌ Error│
│ B      │ Assets Fuera Posición    │ 234       │ ⚠️ Warn │
│ C2     │ Elec En Curso            │ 89        │ ⚠️ Warn │
│ ...    │ ...                      │ ...       │ ...     │
└────────┴──────────────────────────┴───────────┴─────────┘

[📥 CSV Completo]  [📥 Excel Completo]

┌─────────────────────────────────────────────────────────┐
│ A0 (45)  │ A1 (123) │ A2 (67)  │ B (234)  │ C2 (89) ... │
└─────────────────────────────────────────────────────────┘
    ▼ Cada pestaña contiene:
    - Tabla de datos filtrada
    - Gráficos por columna
    - Exportación individual
```

## 🛠️ Funciones Auxiliares

### Validación de Assets

```python
from core.causistica import validate_asset_status

result = validate_asset_status(
    expected_status='08',  # Cortado
    actual_status=asset['Status'],
    context_message="SC Activada"
)

if result:  # Si hay error
    # result contiene: error_detectado, status_esperado, status_actual, alerta
    pass
```

### Obtener Registro Más Reciente

```python
from core.causistica import get_most_recent_asset, get_most_recent_solicitud

asset_reciente = get_most_recent_asset(lista_assets, date_field='CreatedDate')
sc_reciente = get_most_recent_solicitud(lista_solicitudes, date_field='CreatedDate')
```

### Contexto Compartido

```python
# En setup_causisticas() o al inicio de process()
self._causistica_manager.set_context('contratos_map', contratos_dict)
self._causistica_manager.set_context('division_negocio', 'Electricidad')

# Luego en funciones de validación
contratos = self._causistica_manager.get_context('contratos_map')
division = self._causistica_manager.get_context('division_negocio')
```

## 📝 Ejemplo Completo: ContratoReenganche V3

Ver `scripts/contrato_reenganche_v3_completo.py` para un ejemplo completo que implementa:

- **15+ causísticas** (A0, A1, A2, B, C1-A0, C1-A1, C1-A2, C2-C14, D2-D14)
- **Validaciones modulares** reutilizables
- **Procesamiento por categorías** (solo cortado, reenganche, múltiples reenganches)
- **Todas las reglas de negocio** preservadas del notebook original

### Estructura del Script

```python
class ContratoReengancheCompleto(BaseScript):
    uses_causisticas = True
    
    def get_queries(self, preview):
        # Consulta solicitudes y assets
        return [query_solicitudes, query_assets]
    
    def setup_causisticas(self):
        # Registra las 15+ causísticas
        self._causistica_manager.register(...)
    
    def process(self, query_results):
        # 1. Clasificar contratos por tipo
        # 2. Agrupar assets por contrato
        # 3. Procesar cada categoría de causísticas
        self._process_causistica_a(...)
        self._process_causistica_b(...)
        self._process_causistica_c1(...)
        self._process_causistica_c(...)
        self._process_causistica_d(...)
        # 4. Retornar resultado consolidado
        return ScriptResult(has_causisticas=True, ...)
    
    # Funciones de procesamiento por causística
    def _process_causistica_a(self, ...):
        # Lógica específica para causísticas A
        pass
    
    # Funciones de validación reutilizables
    def _validar_cortado(self, sc, assets, prefix):
        # Validación modular
        pass
    
    def _validar_reenganche(self, sc, assets, scs_cortado, prefix):
        # Validación modular
        pass
```

## 🎯 Ventajas del Framework

### 1. Mantenibilidad
- Cada causística está claramente definida y documentada
- La lógica de validación está separada y es reutilizable
- Fácil de entender qué hace cada parte del código

### 2. Escalabilidad
- Agregar una nueva causística es agregar una definición y su procesamiento
- No afecta a las causísticas existentes
- Código modular permite crecer sin complejidad exponencial

### 3. Reutilización
- Funciones de validación se pueden compartir entre causísticas
- Mismo código de validación para C y D (con diferente prefijo)
- Helpers en `causistica.py` disponibles para todos losscripts

### 4. UI Automática
- El framework genera automáticamente la UI multiTab
- Exportación a CSV/Excel incluida
- Gráficos y métricas sin código adicional

### 5. Preservación Completa de Lógica
- TODO el código del notebook está en el script Python
- Sin simplificaciones ni pérdida de funcionalidad
- Mismo resultado, mejor organización

## 📚 Mejores Prácticas

### 1. Nombrar Causísticas
- Usa códigos cortos y descriptivos: `A1`, `C2`, `ELEC`
- Nombres claros y específicos
- Descripción detallada de qué detecta

### 2. Organizar Validaciones
- Funciones de validación separadas y reutilizables
- Una función por tipo de validación compleja
- Retornar diccionarios con estructura consistente

### 3. Métricas Personalizadas
- Agregar métricas específicas a cada causística
- Métricas globales en el ScriptResult
- Usar iconos descriptivos (⚠️, ❌, ✅, 📊, etc.)

### 4. Datos Base Comunes
- Extraer campos comunes en una función helper
- Agregar campos específicos según la causística
- Mantener estructura de datos consistente

### 5. Documentación
- Documentar qué detecta cada causística
- Comentar la lógica de validación compleja
- Incluir ejemplos en docstrings

## 🔧 Migración desde Notebooks

### Pasos para Migrar un Notebook

1. **Identificar Causísticas**: Lista todas las causísticas/escenarios del notebook
2. **Crear Script Base**: Usar `uses_causisticas = True`
3. **Definir Queries**: Extraer las consultas SOQL
4. **Registrar Causísticas**: En `setup_causisticas()`
5. **Implementar Validaciones**: Funciones modulares de validación
6. **Procesar por Causística**: Una función `_process_causistica_X()` por grupo
7. **Probar y Validar**: Comparar resultados con el notebook

### Ejemplo de Migración

```python
# ANTES (Notebook)
contratos_error = []
for contrato in contratos:
    if condicion_a1(contrato):
        contratos_error.append({...})

df = pd.DataFrame(contratos_error)
df.to_excel('resultados.xlsx')

# DESPUÉS (Script con Framework)
registros_a1 = []
for contrato in contratos:
    if condicion_a1(contrato):
        registros_a1.append({...})

if registros_a1:
    self._causistica_manager.results['A1'] = CausisticaResult(
        code='A1',
        name="...",
        description="...",
        severity='warning',
        data=pd.DataFrame(registros_a1)
    )
# UI y exportación automáticas
```

## ❓ FAQ

**P: ¿Scripts simples siguen funcionando?**  
R: Sí, completamente retrocompatibles. No necesitas cambiar nada.

**P: ¿Puedo mezclar causísticas y datos simples?**  
R: Sí, `ScriptResult` tiene tanto `data` (simple) como `causisticas` (framework).

**P: ¿Cuántas causísticas puedo tener?**  
R: Sin límite. El ejemplo ContratoReenganche tiene 15+ y funciona perfectamente.

**P: ¿Cómo exporto los resultados?**  
R: La UI genera botones automáticos para CSV y Excel, por causística y combinados.

**P: ¿Funciona con los gráficos existentes?**  
R: Sí, cada causística tiene sus propios gráficos automáticos.

## 📖 Referencias

- `core/causistica.py` - Documentación completa de clases
- `scripts/contrato_reenganche_v3_completo.py` - Ejemplo completo
- `scripts/premises_multiple_sp_same_energy.py` - Ejemplo simple
- `docs/SCRIPT_CREATION_GUIDE.md` - Guía general de scripts

---

**Versión**: 1.0  
**Fecha**: Febrero 2026  
**Autor**: PanelScripts Team
