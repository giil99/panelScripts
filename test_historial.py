"""
Script de prueba para verificar que el historial funciona correctamente.
Ejecutar con: streamlit run test_historial.py
"""
import streamlit as st
from datetime import datetime

st.title("🧪 Test de Historial")

# Initialize session state
if 'execution_history' not in st.session_state:
    st.session_state.execution_history = []

st.write(f"**Historial actual:** {len(st.session_state.execution_history)} ejecuciones")

# Botón para añadir una ejecución de prueba
if st.button("➕ Añadir ejecución de prueba"):
    st.session_state.execution_history.append({
        'script_name': f'Script de Prueba {len(st.session_state.execution_history) + 1}',
        'success': True,
        'record_count': 100,
        'execution_time': 5.5,
        'executed_at': datetime.now().isoformat()
    })
    st.rerun()

# Botón para limpiar
if st.button("🗑️ Limpiar historial"):
    st.session_state.execution_history = []
    st.rerun()

# Mostrar historial
st.markdown("---")
st.markdown("## 📜 Historial")

if len(st.session_state.execution_history) == 0:
    st.info("No hay ejecuciones en el historial")
else:
    import pandas as pd
    df = pd.DataFrame(st.session_state.execution_history)
    st.dataframe(df, use_container_width=True)
    
    st.markdown("### Estadísticas")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total", len(df))
    
    with col2:
        st.metric("Registros Totales", df['record_count'].sum())
    
    with col3:
        st.metric("Tiempo Promedio", f"{df['execution_time'].mean():.2f}s")
