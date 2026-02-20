# Guía Rápida - Dashboard Simplificado

## 🎯 ¿Qué cambió en la última versión?

La aplicación ahora tiene **3 páginas en el menú**:
- ❌ **Eliminado**: Menú lateral de archivos (app, home, etc.)
- ❌ **Eliminado**: Modo Preview  
- ✅ **Restaurado**: Página de Historial independiente
- ✅ **Nuevo**: Navegación limpia solo con páginas relevantes

## 🚀 Cómo Usar la Nueva Versión

### Paso 1: Ejecutar la Aplicación

```bash
cd "c:\Users\agilsole@deloitte.es\Naturgy\Naturgy Bitbucket\manifest\Scripts AG\dashboard"
python -m streamlit run app.py
```

### Paso 2: Conectar a Salesforce

1. En la página **🏠 Inicio**:
   - Selecciona el entorno (Pre/Pro)
   - Verifica la ruta de credenciales
   - Haz clic en **🔗 Conectar**

### Paso 3: Ejecutar un Script

**Opción A: Desde Inicio**
- Busca el script en la lista
- Haz clic en el botón **▶️** junto al script

**Opción B: Desde Ejecutar Scripts**
- Ve a **▶️ Ejecutar Scripts** en el menú
- Selecciona categoría y script
- (Opcional) Marca "Ejecutar Actualizaciones" si el script puede modificar datos
- Haz clic en **▶️ Ejecutar Script**

### Paso 4: Ver y Analizar Resultados

Los resultados se muestran **automáticamente** debajo del botón de ejecución:

#### 📊 Métricas Principales
- **Registros**: Total de registros procesados
- **Tiempo**: Duración de la ejecución
- **Estado**: Éxito o error
- **Anomalías**: Registros marcados como anómalos

#### 📋 Pestaña "Datos"
- **Tabla completa** con todos los registros
- **Filtros**: Click en "🔍 Filtros" para filtrar por columnas
- **Exportar**: 
  - Botón **📥 CSV** para exportar a CSV
  - Botón **📥 Excel** para exportar a Excel

#### 📈 Pestaña "Análisis"
- **Gráficos**: Visualización de distribuciones por campo
- Selecciona campo para agrupar
- Elige tipo de gráfico (Barras o Circular)
- Tabla con estadísticas por grupo

#### ⚠️ Pestaña "Anomalías"
- Registros detectados como anómalos
- Útil para identificar casos que requieren atención

## 💡 Consejos

### Para Filtrar Datos
1. Haz clic en "🔍 Filtros"
2. Selecciona columnas para filtrar
3. Marca los valores que quieres ver
4. La tabla se actualiza automáticamente

### Para Exportar
1. Aplica filtros si quieres exportar solo un subconjunto
2. Haz clic en **📥 CSV** o **📥 Excel**
3. El archivo se descarga con fecha y hora en el nombre

### Para Analizar Distribuciones
1. Ve a la pestaña **📈 Análisis**
2. Selecciona el campo por el que quieres agrupar
3. El gráfico y la tabla se generan automáticamente

### Para Scripts con Actualizaciones
1. Marca el checkbox **"Ejecutar Actualizaciones"**
2. Confirma cuando se te pida
3. Los resultados indicarán cuántos registros se actualizaron

## ⚙️ Menú Simplificado

### 🏠 Inicio
- **Conexión** a Salesforce
- **Lista de scripts** disponibles
- **Estadísticas** generales

### ▶️ Ejecutar Scripts
- **Selección** de script
- **Ejecución**
- **Resultados** (inmediatos)

### 📜 Historial
- **Estadísticas** de todas las ejecuciones
- **Filtros** por script y estado
- **Tabla detallada** con historial completo

## 📜 Historial de Ejecuciones

El historial está ahora **en su propia página del menú**:

### Características del Historial
- ✅ **Página independiente**: Click en "📜 Historial" en el menú lateral
- ✅ **Estadísticas visibles**: Métricas en la parte superior
- ✅ **Filtros**: Por script específico o por estado (exitosos/errores)
- ✅ **Orden cronológico**: Los más recientes primero
- ✅ **Acción rápida**: Botón 🗑️ Limpiar para resetear el historial

### Información Mostrada
- **Fecha/Hora**: Cuándo se ejecutó
- **Script**: Nombre del script ejecutado
- **Estado**: ✅ OK o ❌ Error
- **Registros**: Cantidad de registros procesados
- **Tiempo (s)**: Duración de la ejecución

### Estadísticas Agregadas
- **Total Ejecuciones**: Cantidad de scripts ejecutados en la sesión
- **Tasa de Éxito**: Porcentaje de ejecuciones exitosas
- **Tiempo Promedio**: Duración promedio de ejecución
- **Registros Totales**: Suma de todos los registros procesados

### Cómo Acceder
1. Ejecuta algunos scripts desde "▶️ Ejecutar Scripts"
2. Ve al menú lateral y haz click en **"📜 Historial"**
3. Verás todas tus ejecuciones con estadísticas y filtros

## 🔍 Solución de Problemas

### "streamlit is not recognized..."
**Solución**: Usa `python -m streamlit run app.py` en lugar de `streamlit run app.py`

### "No hay scripts disponibles"
**Solución**: Verifica que los archivos en `scripts/` tienen el decorador `@register_script`

### "⚠️ No conectado"
**Solución**: Ve a 🏠 Inicio y haz clic en 🔗 Conectar

### Exportación Excel no funciona
**Solución**: Asegúrate de que openpyxl está instalado:
```bash
pip install openpyxl
```

### Script tarda mucho
**Normal**: Los scripts ahora procesan **todos** los datos (no preview limitado)
- Puedes ver el progreso en la barra de progreso
- El tiempo total se muestra en las métricas

## 📝 Notas Importantes

### ✅ La Lógica de los Scripts NO Cambió
- Todos los scripts funcionan exactamente igual
- Las queries son las mismas
- El procesamiento es idéntico
- Las actualizaciones funcionan igual

### ⚠️ Cambios Solo en la UI
- Eliminado modo preview (siempre ejecuta completo)
- Resultados integrados (no página separada)
- Sin historial de sesión

### 🔒 Seguridad
- Las actualizaciones **siempre** requieren confirmación
- Los scripts con `requires_confirmation=True` piden confirmación explícita
- Puedes revisar los resultados antes de ejecutar updates

## 🎯 Ejemplo de Uso Completo

**Caso: Regularizar Contratos Activos con Assets Cortados**

1. **Conectar**: 🏠 Inicio → Seleccionar "pre" → 🔗 Conectar
2. **Ejecutar**: ▶️ Ejecutar Scripts → Categoría "Regularización" → Script "Contratos Activos con Assets Cortados" → ▶️ Ejecutar
3. **Revisar**: Ver métricas (cuántos casos) y tabla de datos
4. **Analizar**: Ir a pestaña 📈 Análisis → Agrupar por "AssetStatusLabel"
5. **Filtrar**: 🔍 Filtros → Filtrar por "ContractStatusLabel" = "Activo"
6. **Exportar**: 📥 Excel para guardar lista de casos
7. **Actualizar** (opcional): Si quieres corregir → Marcar "Ejecutar Actualizaciones" → Re-ejecutar

---

**¿Preguntas o problemas?** Revisa el [CHANGELOG.md](CHANGELOG.md) para más detalles técnicos.
