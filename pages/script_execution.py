"""
Script Execution Page - Run and monitor script execution.
"""
import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO
import threading
import time

from core.script_registry import get_registry
from core.execution_engine import ExecutionEngine
from core.history_manager import get_history_manager
from visualization.kpis import KPIPanel
from visualization.charts import (
    create_bar_chart,
    create_pie_chart,
    create_line_chart,
    create_timeline_chart,
    ChartBuilder
)


def render():
    """Render the script execution page."""
    st.markdown('<div class="hero-title" style="font-size:1.6rem;">Ejecutar Scripts</div>', unsafe_allow_html=True)

    # Check connection
    if not st.session_state.sf_client or not st.session_state.sf_client.is_authenticated:
        st.warning("Conecta a Salesforce primero desde la página de Inicio.")
        if st.button("Ir a Inicio", type="primary"):
            st.session_state.current_page = 'home'
            st.rerun()
        return

    # Check if script just finished executing (result available)
    if st.session_state.get('execution_result') is not None:
        result = st.session_state.execution_result
        st.session_state.current_result = result
        
        # Show success/error message
        if result.success:
            record_count = len(result.data) if result.data is not None else 0
            st.success(f"**Ejecución completada:** {record_count} registros procesados en {result.execution_time:.2f}s")
        else:
            st.error(f"**Error en la ejecución:** {result.error_message}")
        
        for warning in result.warnings:
            st.warning(warning)
        
        # Clear execution result from session
        st.session_state.execution_result = None
        st.session_state.execution_error = None
        
    # Check if there's an error
    elif st.session_state.get('execution_error') is not None:
        error = st.session_state.execution_error
        st.error(f"**Error durante la ejecución:** {error}")
        st.session_state.execution_error = None

    # Check if there's a script currently executing
    if st.session_state.get('script_executing', False):
        st.info("**Script en ejecución:** " + st.session_state.get('executing_script_name', 'Desconocido'))
        st.markdown("*El script se está ejecutando en segundo plano. Los resultados se mostrarán cuando finalice.*")
        
        # Show progress if available
        if st.session_state.get('execution_console_log'):
            st.markdown("### Consola de Ejecución")
            console_log = st.session_state.execution_console_log
            
            # Show progress bar
            execution_progress = st.session_state.get('execution_progress', 0.0)
            st.progress(execution_progress)
            
            st.markdown(
                f"""<div style="background: #1e1e1e; color: #d4d4d4; padding: 1rem; border-radius: 8px; 
                    font-family: 'Consolas', 'Monaco', monospace; font-size: 0.85rem; max-height: 400px; 
                    overflow-y: auto; line-height: 1.6;">
                    {'<br>'.join(console_log[-30:])}
                </div>""",
                unsafe_allow_html=True
            )
        
        # Auto-refresh while script is running (every 2 seconds)
        time.sleep(2)
        st.rerun()
        
        # Don't show script selection while a script is running
        return

    # Show recent results banner
    if st.session_state.current_result:
        result = st.session_state.current_result
        if result.script_instance:
            script_name = result.script_instance.name
            st.success(f"**Última ejecución:** {script_name} - {len(result.data) if result.data is not None else 0} registros en {result.execution_time:.2f}s")

    # Get available scripts
    registry = get_registry()
    scripts = registry.list_scripts()

    if not scripts:
        st.info("No hay scripts disponibles. Añade scripts en la carpeta `scripts/`.")
        return

    # ── Script Selection ────────────────────────────────────────────────
    st.markdown('<div class="section-header">Seleccionar Script</div>', unsafe_allow_html=True)

    col1, col2 = st.columns([2, 1])

    with col1:
        categories = sorted(set(s['category'] for s in scripts))
        selected_category = st.selectbox(
            "Categoría",
            options=["Todas"] + categories,
            key="exec_category"
        )

        filtered_scripts = [s for s in scripts if selected_category == "Todas" or s['category'] == selected_category]
        script_names = [s['name'] for s in filtered_scripts]

        default_idx = 0
        if st.session_state.selected_script and st.session_state.selected_script in script_names:
            default_idx = script_names.index(st.session_state.selected_script)

        selected_script_name = st.selectbox(
            "Script",
            options=script_names,
            index=default_idx,
            key="exec_script"
        )

    with col2:
        selected_script_info = next((s for s in scripts if s['name'] == selected_script_name), None)

        if selected_script_info:
            st.markdown(f"""
            <div class="info-card">
                <strong style="color: var(--text-primary);">{selected_script_info['name']}</strong><br>
                <span style="color: var(--text-muted); font-size: 0.8rem;">{selected_script_info['description']}</span>
                <div style="margin-top: 0.5rem;">
                    <span style="color: var(--text-muted); font-size: 0.75rem;">v{selected_script_info['version']} · {selected_script_info['author']}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

    st.divider()

    # ── Execution Options ───────────────────────────────────────────────
    col1, col2 = st.columns(2)

    with col1:
        execute_updates = st.checkbox(
            "Ejecutar Actualizaciones",
            value=False,
            help="Ejecuta las operaciones de actualización del script",
            disabled=not selected_script_info['supports_update'] if selected_script_info else True
        )

    with col2:
        if execute_updates:
            st.warning("Se modificarán datos en Salesforce")

    # ── Execute Button ──────────────────────────────────────────────────
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        script_executing = st.session_state.get('script_executing', False)
        execute_button = st.button(
            "Ejecutar Script",
            type="primary",
            use_container_width=True,
            disabled=(not selected_script_name) or script_executing
        )

    if execute_button:
        _execute_script(selected_script_name, execute_updates)

    # ── Show full results inline ────────────────────────────────────────
    if st.session_state.current_result:
        st.divider()
        _render_full_results(st.session_state.current_result)


def _render_full_results(result):
    """Render the full results inline with all tabs."""

    st.markdown('<div class="section-header">Resultados</div>', unsafe_allow_html=True)

    # ── Summary Metrics ─────────────────────────────────────────────────
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Registros", value=len(result.data) if result.data is not None else 0)
    with col2:
        st.metric("Tiempo", value=f"{result.execution_time:.2f}s")
    with col3:
        st.metric("Estado", value="OK" if result.success else "Error")
    with col4:
        st.metric("Anomalías", value=len(result.anomalies) if result.anomalies is not None else 0)

    # Custom metrics
    if result.metrics and result.metrics.custom_metrics:
        kpi_panel = KPIPanel()
        kpi_panel.add_from_metrics(result.metrics.custom_metrics)
        kpi_panel.render()

    if result.data is None or result.data.empty:
        if not result.success:
            st.error(f"Error: {result.error_message}")
        else:
            st.info("La ejecución no devolvió datos.")
        return

    df = result.data.copy()

    st.markdown("")  # spacing

    # ── Tabbed Results ──────────────────────────────────────────────────
    tab_data, tab_charts, tab_analysis, tab_anomalies = st.tabs([
        "Datos",
        "Gráficos",
        "Análisis",
        "Anomalías"
    ])

    # ── Tab: Data ───────────────────────────────────────────────────────
    with tab_data:
        _render_data_tab(df)

    # ── Tab: Charts ─────────────────────────────────────────────────────
    with tab_charts:
        _render_charts_tab(df)

    # ── Tab: Analysis ───────────────────────────────────────────────────
    with tab_analysis:
        _render_analysis_tab(df)

    # ── Tab: Anomalies ──────────────────────────────────────────────────
    with tab_anomalies:
        _render_anomalies_tab(result)


# ═══════════════════════════════════════════════════════════════════════
# Data Tab
# ═══════════════════════════════════════════════════════════════════════
def _render_data_tab(df: pd.DataFrame):
    """Render data table with filters and export."""

    with st.expander("Filtros", expanded=False):
        filter_columns = st.multiselect(
            "Columnas para filtrar",
            options=df.columns.tolist(),
            default=[],
            key="exec_filter_columns"
        )

        filters = {}
        if filter_columns:
            cols = st.columns(min(len(filter_columns), 4))
            for idx, col_name in enumerate(filter_columns):
                with cols[idx % len(cols)]:
                    unique_vals = df[col_name].dropna().unique().tolist()
                    if len(unique_vals) <= 50:
                        selected = st.multiselect(
                            col_name,
                            options=sorted(unique_vals, key=str),
                            key=f"exec_filter_{col_name}"
                        )
                        if selected:
                            filters[col_name] = selected

    filtered_df = df.copy()
    for col_name, vals in filters.items():
        filtered_df = filtered_df[filtered_df[col_name].isin(vals)]

    # Info & export
    col1, col2 = st.columns([3, 1])
    with col1:
        st.caption(f"Mostrando {len(filtered_df)} de {len(df)} registros")
    with col2:
        col_a, col_b = st.columns(2)
        with col_a:
            csv = filtered_df.to_csv(index=False, encoding='utf-8-sig')
            st.download_button(
                "Descargar CSV",
                data=csv,
                file_name=f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                key="exec_dl_csv"
            )
        with col_b:
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                filtered_df.to_excel(writer, index=False, sheet_name='Datos')
            st.download_button(
                "Descargar Excel",
                data=output.getvalue(),
                file_name=f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="exec_dl_xlsx"
            )

    st.dataframe(filtered_df, use_container_width=True, hide_index=True, height=500)


# ═══════════════════════════════════════════════════════════════════════
# Charts Tab
# ═══════════════════════════════════════════════════════════════════════
def _render_charts_tab(df: pd.DataFrame):
    """Render interactive charts."""

    # Auto-generate a default distribution chart first
    categorical_cols = [c for c in df.columns if df[c].nunique() <= 30 and df[c].nunique() > 1]

    if categorical_cols:
        # Show automatic distribution chart for the first good categorical column
        auto_col = categorical_cols[0]
        try:
            col1, col2 = st.columns(2)
            with col1:
                counts = df[auto_col].value_counts().reset_index()
                counts.columns = [auto_col, 'Cantidad']
                fig_bar = create_bar_chart(counts, x=auto_col, y='Cantidad', title=f"Distribución por {auto_col}")
                st.plotly_chart(fig_bar, use_container_width=True, key="exec_auto_bar")
            with col2:
                fig_pie = create_pie_chart(df, names=auto_col, title=f"Proporción por {auto_col}")
                st.plotly_chart(fig_pie, use_container_width=True, key="exec_auto_pie")
        except Exception:
            pass  # Auto-charts are best-effort

    st.divider()

    # Custom chart builder
    st.markdown("**Crear gráfico personalizado**")

    col1, col2, col3 = st.columns(3)

    with col1:
        chart_type = st.selectbox(
            "Tipo de gráfico",
            options=["Barras", "Pastel", "Histograma"],
            key="exec_chart_type"
        )
    with col2:
        x_col = st.selectbox("Columna", options=df.columns.tolist(), key="exec_chart_x")
    with col3:
        y_options = [None] + [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
        y_col = st.selectbox(
            "Valores (opcional)",
            options=y_options,
            format_func=lambda x: "Contar" if x is None else x,
            key="exec_chart_y"
        )

    try:
        fig = None
        if chart_type == "Barras":
            fig = create_bar_chart(df, x=x_col, y=y_col, title=f"Distribución por {x_col}")
        elif chart_type == "Pastel":
            fig = create_pie_chart(df, names=x_col, values=y_col, title=f"Proporción por {x_col}")
        elif chart_type == "Histograma":
            fig = ChartBuilder(df).histogram().x(x_col).title(f"Histograma de {x_col}").build()

        if fig:
            st.plotly_chart(fig, use_container_width=True, key="exec_custom_chart")
    except Exception as e:
        st.error(f"Error generando gráfico: {str(e)}")


# ═══════════════════════════════════════════════════════════════════════
# Analysis Tab
# ═══════════════════════════════════════════════════════════════════════
def _render_analysis_tab(df: pd.DataFrame):
    """Render data analysis."""

    # KPIs
    kpi_panel = KPIPanel(df)
    kpi_panel.add_count("Total Registros", "")
    for col in df.columns[:3]:
        if df[col].nunique() < len(df):
            kpi_panel.add_unique_count(col, f"Únicos {col}", "🔢")
    kpi_panel.render(columns=4)

    st.divider()

    # Group by analysis
    st.markdown("**Agrupación y Agregación**")

    groupable_cols = [c for c in df.columns if 1 < df[c].nunique() <= 50]

    if not groupable_cols:
        st.info("No hay columnas adecuadas para agrupar (todas tienen demasiados valores únicos).")
    else:
        col1, col2 = st.columns(2)
        with col1:
            groupby_col = st.selectbox("Agrupar por", options=groupable_cols, key="exec_analysis_groupby")
        with col2:
            agg_type = st.selectbox("Tipo", options=["Contar", "Suma", "Media", "Máximo", "Mínimo"], key="exec_analysis_agg")

        if agg_type == "Contar":
            grouped = df[groupby_col].value_counts().reset_index()
            grouped.columns = [groupby_col, "Cantidad"]
        else:
            numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
            if numeric_cols:
                agg_col = st.selectbox("Columna numérica", options=numeric_cols, key="exec_agg_col")
                agg_map = {"Suma": "sum", "Media": "mean", "Máximo": "max", "Mínimo": "min"}
                grouped = df.groupby(groupby_col)[agg_col].agg(agg_map[agg_type]).reset_index()
                grouped.columns = [groupby_col, f"{agg_type} de {agg_col}"]
            else:
                st.info("No hay columnas numéricas. Mostrando conteo.")
                grouped = df[groupby_col].value_counts().reset_index()
                grouped.columns = [groupby_col, "Cantidad"]

        col1, col2 = st.columns(2)
        with col1:
            st.dataframe(grouped.sort_values(by=grouped.columns[1], ascending=False),
                         use_container_width=True, hide_index=True)
        with col2:
            try:
                fig = create_bar_chart(
                    grouped, x=grouped.columns[0], y=grouped.columns[1],
                    title=f"{agg_type} por {groupby_col}", orientation='h'
                )
                st.plotly_chart(fig, use_container_width=True, key="exec_analysis_chart")
            except Exception as e:
                st.error(f"Error generando gráfico: {str(e)}")

    st.divider()

    with st.expander("Resumen Estadístico"):
        st.dataframe(df.describe(include='all'), use_container_width=True)

    with st.expander("Información de Columnas"):
        col_info = pd.DataFrame({
            'Columna': df.columns,
            'Tipo': [str(df[c].dtype) for c in df.columns],
            'No Nulos': [df[c].notna().sum() for c in df.columns],
            'Nulos': [df[c].isna().sum() for c in df.columns],
            'Únicos': [df[c].nunique() for c in df.columns]
        })
        st.dataframe(col_info, use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════════════
# Anomalies Tab
# ═══════════════════════════════════════════════════════════════════════
def _render_anomalies_tab(result):
    """Render anomalies section."""

    if result.anomalies is None or result.anomalies.empty:
        st.success("No se detectaron anomalías en los datos.")
        return

    anomalies_df = result.anomalies

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Anomalías", len(anomalies_df))
    with col2:
        pct = len(anomalies_df) / len(result.data) * 100 if result.data is not None and len(result.data) > 0 else 0
        st.metric("% del Total", f"{pct:.1f}%")
    with col3:
        if 'anomaly_type' in anomalies_df.columns:
            st.metric("Tipos", anomalies_df['anomaly_type'].nunique())

    st.divider()

    if 'anomaly_type' in anomalies_df.columns:
        try:
            fig = create_bar_chart(anomalies_df, x='anomaly_type', title="Anomalías por Tipo")
            st.plotly_chart(fig, use_container_width=True, key="exec_anomaly_chart")
        except Exception:
            pass

    st.dataframe(anomalies_df, use_container_width=True, hide_index=True, height=400)

    csv = anomalies_df.to_csv(index=False, encoding='utf-8-sig')
    st.download_button(
        "Exportar Anomalías (CSV)",
        data=csv,
        file_name=f"anomalias_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
        key="exec_dl_anomalies"
    )


# ═══════════════════════════════════════════════════════════════════════
# Script Execution
# ═══════════════════════════════════════════════════════════════════════
def _execute_script(script_name: str, execute_updates: bool):
    """Execute the selected script asynchronously in background thread."""
    registry = get_registry()
    script_class = registry.get(script_name)

    if not script_class:
        st.error(f"Script '{script_name}' no encontrado")
        return

    if execute_updates and script_class.requires_confirmation:
        if not st.session_state.get('confirm_update'):
            st.warning("Este script modificará datos en Salesforce.")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Confirmar"):
                    st.session_state.confirm_update = True
                    st.rerun()
            with col2:
                if st.button("Cancelar"):
                    return
            return
        else:
            st.session_state.confirm_update = False

    # Mark script as executing
    st.session_state.script_executing = True
    st.session_state.executing_script_name = script_name
    st.session_state.execution_console_log = []
    st.session_state.execution_progress = 0.0
    st.session_state.execution_result = None
    st.session_state.execution_error = None

    def run_script_in_background():
        """Background thread function to execute script."""
        try:
            engine = ExecutionEngine(sf_client=st.session_state.sf_client)
            history_manager = get_history_manager()
            
            log_messages = []
            
            def add_log(message: str, level: str = "info"):
                """Add a message to the console log."""
                timestamp = datetime.now().strftime("%H:%M:%S")
                icon = {"info": "•", "success": "✓", "warning": "!", "error": "×", "query": "Q", "process": "•"}.get(level, "•")
                log_messages.append(f"`{timestamp}` {icon} {message}")
                # Store in session state for persistence
                st.session_state.execution_console_log = log_messages.copy()
            
            def update_progress(step: str, progress: float, message: str):
                """Update progress bar and add log message."""
                st.session_state.execution_progress = progress
                level = "query" if "consulta" in message.lower() else "process" if "procesando" in message.lower() else "info"
                add_log(message, level)

            engine.set_progress_callback(update_progress)
            
            add_log(f"Iniciando script: **{script_name}**", "info")
            add_log(f"Entorno: {st.session_state.sf_client.env.upper()}", "info")
            add_log(f"Actualizaciones: {'Sí' if execute_updates else 'No'}", "info")

            # Execute script
            result = engine.execute(
                script_class,
                preview=False,
                execute_updates=execute_updates
            )

            # Save to persistent history
            env = st.session_state.sf_client.env if st.session_state.sf_client else None
            history_manager.add(
                script_name=script_name,
                script_category=script_class.category,
                success=result.success,
                record_count=len(result.data) if result.data is not None else 0,
                execution_time=result.execution_time,
                error_message=result.error_message,
                warnings_count=len(result.warnings),
                preview=False,
                env=env
            )

            # Also keep in session for backward compatibility
            st.session_state.execution_history.append({
                'script_name': script_name,
                'success': result.success,
                'record_count': len(result.data) if result.data is not None else 0,
                'execution_time': result.execution_time,
                'executed_at': result.executed_at.isoformat()
            })

            if result.success:
                record_count = len(result.data) if result.data is not None else 0
                add_log(f"Registros procesados: **{record_count}**", "success")
                add_log(f"Ejecución completada en **{result.execution_time:.2f}s**", "success")
            else:
                add_log(f"Error: {result.error_message}", "error")

            for warning in result.warnings:
                add_log(warning, "warning")

            # Store result
            st.session_state.execution_result = result
            st.session_state.execution_progress = 1.0

        except Exception as e:
            # Store error
            st.session_state.execution_error = str(e)
            log_messages.append(f"`{datetime.now().strftime('%H:%M:%S')}` × Excepción: {str(e)}")
            st.session_state.execution_console_log = log_messages.copy()
            
        finally:
            # Mark script execution as complete
            st.session_state.script_executing = False
            st.session_state.executing_script_name = None

    # Start background thread
    thread = threading.Thread(target=run_script_in_background, daemon=True)
    thread.start()
    
    # Trigger immediate rerun to show execution UI
    st.rerun()

