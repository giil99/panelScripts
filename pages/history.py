"""
History Page - View execution history (persistent).
"""
import streamlit as st
import pandas as pd
import plotly.express as px

from core.history_manager import get_history_manager


def render():
    """Render the history page."""
    st.markdown('<div class="hero-title" style="font-size:1.6rem;">Historial de Ejecuciones</div>', unsafe_allow_html=True)

    history_manager = get_history_manager()
    history = history_manager.get_all()

    if not history:
        st.info("No hay ejecuciones registradas.")
        if st.button("Ir a Ejecutar Scripts", type="primary"):
            st.session_state.current_page = 'script_execution'
            st.rerun()
        return

    df = pd.DataFrame(history)
    df['executed_at'] = pd.to_datetime(df['executed_at'])
    df['status'] = df['success'].map({True: 'OK', False: 'Error'})

    # ── Summary Metrics ─────────────────────────────────────────────────
    stats = history_manager.get_stats()
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Ejecuciones", stats['total_executions'])
    with col2:
        st.metric("Tasa de Éxito", f"{stats['success_rate']}%")
    with col3:
        st.metric("Tiempo Promedio", f"{stats['avg_execution_time']}s")
    with col4:
        st.metric("Registros Totales", f"{stats['total_records_processed']:,}")

    st.divider()

    # ── Filters ─────────────────────────────────────────────────────────
    col1, col2, col3 = st.columns(3)
    with col1:
        scripts_list = ['Todos'] + df['script_name'].unique().tolist()
        selected_script = st.selectbox("Filtrar por Script", options=scripts_list, key="history_script_filter")
    with col2:
        status_filter = st.selectbox("Filtrar por Estado", options=['Todos', 'Exitosos', 'Con Errores'], key="history_status_filter")
    with col3:
        env_list = ['Todos'] + [e for e in df['env'].dropna().unique().tolist() if e]
        selected_env = st.selectbox("Filtrar por Entorno", options=env_list, key="history_env_filter")

    filtered_df = df.copy()
    if selected_script != 'Todos':
        filtered_df = filtered_df[filtered_df['script_name'] == selected_script]
    if status_filter == 'Exitosos':
        filtered_df = filtered_df[filtered_df['success'] == True]
    elif status_filter == 'Con Errores':
        filtered_df = filtered_df[filtered_df['success'] == False]
    if selected_env != 'Todos':
        filtered_df = filtered_df[filtered_df['env'] == selected_env]

    filtered_df = filtered_df.sort_values('executed_at', ascending=False)

    # ── Table ───────────────────────────────────────────────────────────
    st.markdown('<div class="section-header">Detalle de Ejecuciones</div>', unsafe_allow_html=True)

    display_cols = ['executed_at', 'script_name', 'status', 'record_count', 'execution_time', 'env']
    display_cols = [c for c in display_cols if c in filtered_df.columns]
    
    st.dataframe(
        filtered_df[display_cols].rename(columns={
            'executed_at': 'Fecha/Hora',
            'script_name': 'Script',
            'status': 'Estado',
            'record_count': 'Registros',
            'execution_time': 'Tiempo (s)',
            'env': 'Entorno'
        }),
        use_container_width=True,
        hide_index=True
    )

    st.divider()

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("Limpiar Historial", type="secondary", use_container_width=True):
                history_manager.clear()
                st.rerun()
        with col_b:
            if st.button("Borrar +30 días", type="secondary", use_container_width=True):
                history_manager.delete_old(30)
                st.rerun()

    # ── Stats Charts ────────────────────────────────────────────────────
    st.divider()
    st.markdown('<div class="section-header">Estadísticas</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Ejecuciones por Script**")
        script_counts = df['script_name'].value_counts().sort_values(ascending=True)
        fig1 = px.bar(
            x=script_counts.values,
            y=script_counts.index,
            orientation='h',
            labels={'x': 'Ejecuciones', 'y': 'Script'},
            text=script_counts.values
        )
        fig1.update_traces(textposition='outside')
        fig1.update_xaxes(dtick=1)  # Show only integer ticks
        fig1.update_layout(height=max(300, len(script_counts) * 40), showlegend=False, margin=dict(l=0, r=0, t=0, b=0))
        st.plotly_chart(fig1, use_container_width=True, key="hist_scripts_chart")
    with col2:
        st.markdown("**Resultados**")
        status_counts = df['success'].value_counts()
        status_counts.index = status_counts.index.map({True: 'Exitosos', False: 'Errores'})
        fig2 = px.bar(
            x=status_counts.values,
            y=status_counts.index,
            orientation='h',
            labels={'x': 'Cantidad', 'y': 'Estado'},
            text=status_counts.values,
            color=status_counts.index,
            color_discrete_map={'Exitosos': '#10B981', 'Errores': '#EF4444'}
        )
        fig2.update_traces(textposition='outside')
        fig2.update_xaxes(dtick=1)  # Show only integer ticks
        fig2.update_layout(height=200, showlegend=False, margin=dict(l=0, r=0, t=0, b=0))
        st.plotly_chart(fig2, use_container_width=True, key="hist_status_chart")
