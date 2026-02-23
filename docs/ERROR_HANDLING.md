# 🛡️ Sistema de Manejo Robusto de Errores

## Objetivo

Garantizar que **cualquier error o excepción no controlada** durante la ejecución de un script se capture automáticamente y se guarde en el historial como **"Fallido"**, visible en el dashboard.

---

## 🔧 Implementación

### Nivel 1: Captura de Errores en `process()`
**Ubicación**: `core/execution_engine.py` línea ~125

```python
try:
    result = script.process(query_results)
except Exception as proc_error:
    error_msg = f"Error en process(): {str(proc_error)}\n{traceback.format_exc()}"
    result = ScriptResult(
        success=False,
        error_message=error_msg,
        execution_time=time.time() - start_time,
        warnings=script._warnings
    )
    self._save_to_history(script, result, preview)
    return result
```

**Captura**:
- Errores de lógica en `process()`
- División por cero
- Variables no definidas
- Acceso a columnas inexistentes en DataFrames
- Cualquier excepción durante el procesamiento de datos

---

### Nivel 2: Captura de Errores Generales
**Ubicación**: `core/execution_engine.py` línea ~220

```python
except Exception as e:
    # Catch any unhandled exceptions (queries, validation, etc.)
    error_msg = f"Error no controlado: {str(e)}\n{traceback.format_exc()}"
    self._update_progress("error", 0.0, f"Error crítico: {str(e)}")
    result = ScriptResult(
        success=False,
        error_message=error_msg,
        execution_time=time.time() - start_time,
        warnings=script._warnings if script else []
    )
    if script:
        self._save_to_history(script, result, preview)
    return result
```

**Captura**:
- Errores en queries SOQL
- Errores de validación de prerequisitos
- Errores de conexión a Salesforce
- Cualquier error fuera de `process()`

---

### Nivel 3: Captura en Thread de Ejecución
**Ubicación**: `pages/script_execution.py` línea ~815

```python
except Exception as e:
    # Store error and save to history
    import traceback
    error_msg = f"{str(e)}\n{traceback.format_exc()}"
    st.session_state.execution_error = error_msg
    
    # Save failed execution to persistent history
    history_manager.add(
        script_name=script_name,
        script_category=script_class.category,
        success=False,
        record_count=0,
        execution_time=0,
        error_message=error_msg,
        warnings_count=0,
        preview=False,
        env=env
    )
```

**Captura**:
- Errores en el thread de ejecución
- Errores antes/después de llamar al engine
- Errores de inicialización
- Cualquier excepción no capturada por los niveles anteriores

---

## 📊 Flujo de Manejo de Errores

```
┌─────────────────────────────────────────┐
│  Usuario ejecuta script                 │
└─────────────┬───────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│  run_script_in_background()             │
│  ┌───────────────────────────────────┐  │
│  │ TRY (Nivel 3)                     │  │
│  │   ExecutionEngine.execute()       │  │
│  │   ┌─────────────────────────────┐ │  │
│  │   │ TRY (Nivel 2)               │ │  │
│  │   │   Queries                   │ │  │
│  │   │   ┌───────────────────────┐ │ │  │
│  │   │   │ TRY (Nivel 1)         │ │ │  │
│  │   │   │   script.process()    │ │ │  │
│  │   │   │                       │ │ │  │
│  │   │   └───────┬───────────────┘ │ │  │
│  │   │           │ Error?          │ │  │
│  │   │           └─►ScriptResult   │ │  │
│  │   │              success=False  │ │  │
│  │   └─────────────────────────────┘ │  │
│  │                                   │  │
│  │   history_manager.add()           │  │
│  │   (success, error_message)        │  │
│  └───────────────────────────────────┘  │
└─────────────┬───────────────────────────┘
              │ Error en thread?
              └─►history_manager.add()
                 success=False
              
              ▼
┌─────────────────────────────────────────┐
│  Historial Persistente (JSON)           │
│  ✓ success: false                       │
│  ✓ error_message: [traceback completo]  │
│  ✓ execution_time: X.XX s               │
└─────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│  Dashboard - Historial de Ejecuciones   │
│  Status: ❌ Error                        │
│  [Detalles del error disponibles]       │
└─────────────────────────────────────────┘
```

---

## ✅ Beneficios

1. **Visibilidad Total**: Todas las ejecuciones fallidas aparecen en el dashboard
2. **Trazabilidad**: Captura el traceback completo para debugging
3. **Sin Pérdida de Información**: Ningún error pasa desapercibido
4. **Métricas Precisas**: Tasa de éxito/fallo calculada correctamente
5. **Debugging Facilitado**: Error message completo guardado persistentemente

---

## 🧪 Pruebas

Ejecuta el script `test_error_handling.py` para validar diferentes escenarios:

```bash
# El script incluye 5 casos de prueba:
1. Error en queries (SOQL inválido)
2. División por cero
3. Variable no definida
4. Acceso a columna inexistente en DataFrame
5. Error en operación de pandas
```

Descomenta las líneas indicadas para simular cada error y verifica que se guarde en el historial como "Fallido".

---

## 📝 Notas Importantes

- **Traceback completo**: Se guarda el stack trace para facilitar el debugging
- **Persistencia**: Los errores se guardan en `data/execution_history.json`
- **Double Safety**: Incluso si falla el guardado en historial, el error se loggea en consola
- **Backward Compatibility**: Se mantiene el session_state para compatibilidad con código existente

---

## 🔍 Verificación en Dashboard

Para verificar que funciona correctamente:

1. Ve a **Historial de Ejecuciones**
2. Busca la ejecución fallida
3. Verás:
   - Status: **Error** (rojo)
   - Record Count: **0**
   - Error Message: Mensaje completo con traceback
   - Execution Time: Tiempo hasta el fallo

---

## 🚀 Mejoras Futuras (Opcional)

- [ ] Notificaciones por email de ejecuciones fallidas
- [ ] Retry automático con exponential backoff
- [ ] Categorización de errores (Query, Logic, Connection, etc.)
- [ ] Dashboard separado para análisis de errores
- [ ] Alertas en Slack/Teams para errores críticos
