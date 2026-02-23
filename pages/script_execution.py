"""
Script Execution Page - Run and monitor script execution.
"""
import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO, StringIO
import threading
import time
import sys
from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx

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


class PrintCapture(StringIO):
    """Capture print statements and redirect them to Streamlit console."""
    
    def __init__(self, add_log_func):
        super().__init__()
        self.add_log = add_log_func
        self.buffer = []
    
    def write(self, text):
        """Intercept write calls from print statements."""
        if text and text.strip():  # Ignore empty lines
            # Remove ANSI color codes if present
            clean_text = text.strip()
            
            # Send to Streamlit console immediately
            if clean_text:
                # Detect emojis and format accordingly
                if any(emoji in clean_text for emoji in ['📊', '✅', '⚠️', '❌', '🔍', '⛔']):
                    self.add_log(f"{clean_text}", "info")
                elif "Error" in clean_text or "error" in clean_text:
                    self.add_log(clean_text, "error")
                elif "Warning" in clean_text or "warning" in clean_text:
                    self.add_log(clean_text, "warning")
                else:
                    self.add_log(f"{clean_text}", "info")
                
                # Force immediate flush to console
                self.flush()
        
        # Must return number of characters written for compatibility
        return len(text) if text else 0
    
    def flush(self):
        """Flush method required by sys.stdout interface."""
        # Ensure logs are visible immediately
        pass


def _render_console_content():
    """Render the console content (shared between fragment and static view)."""
    st.markdown('<div class="section-header">📟 Consola de Ejecución</div>', unsafe_allow_html=True)
    
    console_log = st.session_state.get('execution_console_log', [])
    
    # Show progress bar with custom styling
    execution_progress = st.session_state.get('execution_progress', 0.0)
    progress_percent = int(execution_progress * 100)
    
    # Only show progress bar if script is still executing
    if st.session_state.get('script_executing', False):
        # Custom styled progress bar
        st.markdown(
            f"""
            <style>
                div[data-testid="stProgress"] > div > div > div > div {{
                    background: linear-gradient(90deg, #00c851 0%, #007E33 100%);
                }}
            </style>
            <div style="margin-bottom: 1rem;">
                <div style="display: flex; justify-content: space-between; margin-bottom: 0.25rem;">
                    <span style="color: #d4d4d4; font-weight: 600;">Progreso</span>
                    <span style="color: #00c851; font-weight: 700;">{progress_percent}%</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        st.progress(execution_progress)
    
    # Show console output
    if console_log:
        st.markdown(
            f"""<div style="background: #1e1e1e; color: #d4d4d4; padding: 1rem; border-radius: 8px; 
                font-family: 'Consolas', 'Monaco', monospace; font-size: 0.85rem; max-height: 500px; 
                overflow-y: auto; line-height: 1.6; border: 1px solid #333;">
                {'<br>'.join(console_log)}
            </div>""",
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            """
            <div style="background: #1e1e1e; color: #d4d4d4; padding: 1rem; border-radius: 8px; 
                font-family: 'Consolas', 'Monaco', monospace; font-size: 0.85rem; text-align: center; 
                border: 1px solid #333;">
                <span style="color: #888;">⏳ Iniciando ejecución...</span>
            </div>
            """,
            unsafe_allow_html=True
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
            st.success(f"**✅ Ejecución completada:** {record_count} registros procesados en {result.execution_time:.2f}s")
        else:
            st.error(f"**❌ Error en la ejecución**")
            
            # Show error details in expander
            if result.error_message:
                error_lines = result.error_message.split('\n')
                st.markdown(f"**Mensaje:** {error_lines[0]}")
                
                if len(error_lines) > 1:
                    with st.expander("🔍 Ver Detalles del Error", expanded=False):
                        st.code(result.error_message, language="python")
        
        for warning in result.warnings:
            st.warning(warning)
        
        # Clear execution result from session
        st.session_state.execution_result = None
        st.session_state.execution_error = None
        
    # Check if there's an error
    elif st.session_state.get('execution_error') is not None:
        error = st.session_state.execution_error
        error_lines = error.split('\n')
        
        # Show error message prominently
        st.error(f"**❌ Error durante la ejecución**")
        
        # Show main error message
        st.markdown(f"**Tipo:** `{error_lines[0]}`")
        
        # Show full traceback in expander
        with st.expander("🔍 Ver Traceback Completo", expanded=False):
            st.code(error, language="python")
        
        st.session_state.execution_error = None

    # Check if there's a script currently executing OR results waiting to be shown
    script_executing = st.session_state.get('script_executing', False)
    has_pending_result = st.session_state.get('execution_result') is not None
    
    # Show console if script is running OR if there are logs to show
    show_console = script_executing or has_pending_result or st.session_state.get('execution_console_log')
    
    if show_console:
        if script_executing:
            st.info("❗ **Script en ejecución:** " + st.session_state.get('executing_script_name', 'Desconocido'))
            st.markdown("*El script se está ejecutando en segundo plano. Los resultados se mostrarán cuando finalice.*")
        elif has_pending_result:
            st.success("✅ **Ejecución completada** - Revisa los resultados abajo")
        
        st.divider()
        
        # Use fragment for auto-updating console - only while executing
        if script_executing:
            @st.fragment(run_every=0.5)  # Auto-update every 0.5 seconds
            def render_execution_console():
                """Render execution console with auto-refresh."""
                
                # Check if execution finished and result is ready
                script_still_running = st.session_state.get('script_executing', False)
                result_ready = st.session_state.get('execution_result') is not None
                
                if not script_still_running and result_ready:
                    # Execution finished, trigger full page reload to show results
                    st.rerun()
                
                _render_console_content()
            
            render_execution_console()
        else:
            # Show static console after execution
            _render_console_content()
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Don't show script selection while a script is running
        if script_executing:
            return

    # Only show recent results banner if NOT executing
    if not st.session_state.get('script_executing', False) and st.session_state.current_result:
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
            width='stretch',
            disabled=(not selected_script_name) or script_executing
        )

    if execute_button:
        _execute_script(selected_script_name, execute_updates)

    # ── Show full results inline (only if not executing) ────────────────
    if st.session_state.current_result and not st.session_state.get('script_executing', False):
        st.divider()
        _render_full_results(st.session_state.current_result)


def _render_full_results(result):
    """Render the full results inline with all tabs."""

    st.markdown('<div class="section-header">Resultados</div>', unsafe_allow_html=True)

    # ── Check if this is a multi-causística result ─────────────────────
    if result.has_causisticas and result.causisticas:
        _render_causistica_results(result)
        return

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

    st.dataframe(filtered_df, width='stretch', hide_index=True, height=500)


# ═══════════════════════════════════════════════════════════════════════
# Charts Tab
# ═══════════════════════════════════════════════════════════════════════
def _render_charts_tab(df: pd.DataFrame):
    """Render interactive charts."""

    # Auto-generate a default distribution chart first
    # More flexible detection: up to 50 unique values for categorical
    categorical_cols = [c for c in df.columns if df[c].nunique() <= 50 and df[c].nunique() > 1]
    numeric_cols = df.select_dtypes(include=['int64', 'float64', 'Int64']).columns.tolist()

    if categorical_cols:
        # Show automatic distribution chart for the first good categorical column
        auto_col = categorical_cols[0]
        try:
            col1, col2 = st.columns(2)
            with col1:
                counts = df[auto_col].value_counts().reset_index()
                counts.columns = [auto_col, 'Cantidad']
                fig_bar = create_bar_chart(counts, x=auto_col, y='Cantidad', title=f"Distribución por {auto_col}")
                st.plotly_chart(fig_bar, width='stretch', key=f'auto_bar_{auto_col}')
            with col2:
                fig_pie = create_pie_chart(df, names=auto_col, title=f"Proporción por {auto_col}")
                st.plotly_chart(fig_pie, width='stretch', key=f'auto_pie_{auto_col}')
        except Exception:
            pass  # Auto-charts are best-effort
    elif numeric_cols:
        # Show numeric distribution if no categorical
        st.markdown("**📊 Distribución de Datos Numéricos**")
        try:
            import plotly.express as px
            auto_numeric = numeric_cols[0]
            col1, col2 = st.columns(2)
            with col1:
                fig_hist = px.histogram(df, x=auto_numeric, 
                                       title=f"Distribución de {auto_numeric}",
                                       nbins=30)
                fig_hist.update_layout(showlegend=False)
                st.plotly_chart(fig_hist, width='stretch', key=f'auto_hist_{auto_numeric}')
            with col2:
                fig_box = px.box(df, y=auto_numeric, 
                                title=f"Box Plot de {auto_numeric}")
                st.plotly_chart(fig_box, width='stretch', key=f'auto_box_{auto_numeric}')
        except Exception:
            pass

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
            st.plotly_chart(fig, width='stretch')
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
                         width='stretch', hide_index=True)
        with col2:
            try:
                fig = create_bar_chart(
                    grouped, x=grouped.columns[0], y=grouped.columns[1],
                    title=f"{agg_type} por {groupby_col}", orientation='h'
                )
                st.plotly_chart(fig, width='stretch')
            except Exception as e:
                st.error(f"Error generando gráfico: {str(e)}")

    st.divider()

    with st.expander("Resumen Estadístico"):
        st.dataframe(df.describe(include='all'), width='stretch')

    with st.expander("Información de Columnas"):
        col_info = pd.DataFrame({
            'Columna': df.columns,
            'Tipo': [str(df[c].dtype) for c in df.columns],
            'No Nulos': [df[c].notna().sum() for c in df.columns],
            'Nulos': [df[c].isna().sum() for c in df.columns],
            'Únicos': [df[c].nunique() for c in df.columns]
        })
        st.dataframe(col_info, width='stretch', hide_index=True)


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
            st.plotly_chart(fig, width='stretch')
        except Exception:
            pass

    st.dataframe(anomalies_df, width='stretch', hide_index=True, height=400)

    csv = anomalies_df.to_csv(index=False, encoding='utf-8-sig')
    st.download_button(
        "Exportar Anomalías (CSV)",
        data=csv,
        file_name=f"anomalias_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
        key="exec_dl_anomalies"
    )


# ═══════════════════════════════════════════════════════════════════════
# Causística Results Rendering
# ═══════════════════════════════════════════════════════════════════════
def _sanitize_sheet_name(name: str) -> str:
    r"""Sanitize a string to be used as an Excel sheet name.
    
    Excel sheet names cannot contain: []:*?/\ and must be <= 31 chars.
    
    Args:
        name: Original name
        
    Returns:
        Sanitized name safe for Excel
    """
    # Replace invalid characters
    invalid_chars = {'[', ']', ':', '*', '?', '/', '\\'}
    sanitized = ''.join(c if c not in invalid_chars else '_' for c in name)
    
    # Limit to 31 characters
    return sanitized[:31]


def _render_causistica_results(result):
    """Render results for scripts using the causística framework."""
    
    # ── Summary Metrics ─────────────────────────────────────────────────
    total_records = sum(caus.count for caus in result.causisticas.values())
    total_causisticas = len(result.causisticas)
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Causísticas", value=total_causisticas)
    with col2:
        st.metric("Total Registros", value=total_records)
    with col3:
        st.metric("Tiempo", value=f"{result.execution_time:.2f}s")
    with col4:
        st.metric("Estado", value="OK" if result.success else "Error")
    
    # Custom metrics from script (if any)
    if result.metrics and result.metrics.custom_metrics:
        kpi_panel = KPIPanel()
        kpi_panel.add_from_metrics(result.metrics.custom_metrics)
        kpi_panel.render()
    
    st.markdown("")  # spacing
    
    # ── Causística Summary Table ────────────────────────────────────────
    st.markdown("### 📊 Resumen de Causísticas")
    
    summary_data = []
    for code, caus in sorted(result.causisticas.items()):
        severity_icon = {
            "info": "ℹ️",
            "warning": "⚠️",
            "error": "❌",
            "critical": "🔴"
        }.get(caus.severity, "📌")
        
        summary_data.append({
            "Código": code,
            "Nombre": caus.name,
            "Registros": caus.count,
            "Severidad": f"{severity_icon} {caus.severity.title()}",
            "Descripción": caus.description[:80] + "..." if len(caus.description) > 80 else caus.description
        })
    
    summary_df = pd.DataFrame(summary_data)
    st.dataframe(summary_df, width='stretch', hide_index=True, height=200)
    
    st.divider()
    
    # ── Export All Causísticas ──────────────────────────────────────────
    col1, col2, col3, col4 = st.columns([2, 1, 1, 2])
    
    with col2:
        # Export all as single CSV
        all_data = []
        for code, caus in result.causisticas.items():
            if not caus.data.empty:
                temp_df = caus.data.copy()
                
                # Add causística columns if they don't exist
                if 'Causistica' not in temp_df.columns:
                    temp_df.insert(0, 'Causistica', code)
                if 'Causistica_Nombre' not in temp_df.columns:
                    temp_df.insert(1, 'Causistica_Nombre', caus.name)
                    
                all_data.append(temp_df)
        
        if all_data:
            combined_df = pd.concat(all_data, ignore_index=True)
            csv_all = combined_df.to_csv(index=False, encoding='utf-8-sig')
            st.download_button(
                "📥 CSV Completo",
                data=csv_all,
                file_name=f"causisticas_all_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                key="exec_dl_causisticas_all_csv"
            )
    
    with col3:
        # Export all as Excel with multiple sheets
        if all_data:
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                # Write summary sheet
                summary_df.to_excel(writer, index=False, sheet_name='Resumen')
                
                # Write each causística as a separate sheet
                for code, caus in result.causisticas.items():
                    if not caus.data.empty:
                        # Sanitize sheet name (remove invalid chars, limit length)
                        sheet_name = _sanitize_sheet_name(f"{code}_{caus.name}")
                        caus.data.to_excel(writer, index=False, sheet_name=sheet_name)
            
            st.download_button(
                "📥 Excel Completo",
                data=output.getvalue(),
                file_name=f"causisticas_all_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="exec_dl_causisticas_all_xlsx"
            )
    
    st.markdown("")  # spacing
    
    # ── Individual Causística Tabs ──────────────────────────────────────
    st.markdown("### 📋 Detalle por Causística")
    
    # Create tabs for each causística (max 10 tabs, then use accordion)
    causistica_items = sorted(result.causisticas.items())
    
    if len(causistica_items) <= 10:
        # Use tabs for small number of causísticas
        tab_names = [f"{code} ({caus.count})" for code, caus in causistica_items]
        tabs = st.tabs(tab_names)
        
        for idx, (code, caus) in enumerate(causistica_items):
            with tabs[idx]:
                _render_single_causistica(code, caus)
    else:
        # Use expanders for many causísticas
        for code, caus in causistica_items:
            with st.expander(f"**{code}** - {caus.name} ({caus.count} registros)", expanded=False):
                _render_single_causistica(code, caus)


def _render_single_causistica(code: str, caus):
    """Render a single causística with its data and metrics."""
    
    # Info header
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f"**{caus.name}**")
        if caus.description:
            st.caption(caus.description)
    with col2:
        severity_color = {
            "info": "blue",
            "warning": "orange",
            "error": "red",
            "critical": "red"
        }.get(caus.severity, "gray")
        st.markdown(f":{severity_color}[{caus.severity.upper()}]")
    
    # Custom metrics for this causística
    if caus.custom_metrics:
        cols = st.columns(min(len(caus.custom_metrics), 4))
        for idx, (key, metric_info) in enumerate(caus.custom_metrics.items()):
            with cols[idx % len(cols)]:
                icon = metric_info.get('icon', '📊')
                label = metric_info.get('label', key)
                value = metric_info.get('value', 0)
                st.metric(f"{icon} {label}", value)
    
    if caus.data is None or caus.data.empty:
        st.info(f"No hay registros para la causística {code}")
        return
    
    df = caus.data.copy()
    
    # Tabs for data, charts, analysis
    subtab_data, subtab_charts = st.tabs(["Datos", "Gráficos"])
    
    with subtab_data:
        # Show data table
        st.dataframe(df, width='stretch', hide_index=True, height=400)
        
        # Export buttons for this causística
        col1, col2 = st.columns(2)
        with col1:
            csv = df.to_csv(index=False, encoding='utf-8-sig')
            st.download_button(
                "Descargar CSV",
                data=csv,
                file_name=f"causistica_{code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                key=f"exec_dl_caus_{code}_csv"
            )
        with col2:
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                # Sanitize code for sheet name
                safe_sheet_name = _sanitize_sheet_name(code)
                df.to_excel(writer, index=False, sheet_name=safe_sheet_name)
            st.download_button(
                "Descargar Excel",
                data=output.getvalue(),
                file_name=f"causistica_{code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"exec_dl_caus_{code}_xlsx"
            )
    
    with subtab_charts:
        # Detectar columnas disponibles para visualización
        # Categóricas: hasta 50 valores únicos, incluye strings, booleans, y numéricos de baja cardinalidad
        categorical_cols = []
        for c in df.columns:
            unique_count = df[c].nunique()
            # Aceptar columnas con 2-50 valores únicos
            if 1 < unique_count <= 50:
                # Incluir todos los tipos: object (strings), bool, category, Int64
                if df[c].dtype in ['object', 'bool', 'category'] or df[c].dtype.name.startswith('Int'):
                    categorical_cols.append(c)
        
        # Numéricas: int64, float64, Int64 (pero solo las de alta cardinalidad)
        numeric_cols = df.select_dtypes(include=['int64', 'float64', 'Int64']).columns.tolist()
        # Remover numéricas que ya están en categóricas (baja cardinalidad)
        numeric_cols = [c for c in numeric_cols if c not in categorical_cols]
        
        # Crear pestañas para diferentes tipos de visualización
        if categorical_cols or numeric_cols:
            viz_tabs = []
            if categorical_cols:
                viz_tabs.append("📊 Categóricas")
            if numeric_cols:
                viz_tabs.append("📈 Numéricas")
            
            viz_tab_objects = st.tabs(viz_tabs)
            tab_idx = 0
            
            # Tab de categóricas
            if categorical_cols:
                with viz_tab_objects[tab_idx]:
                    st.markdown("**Selecciona las columnas que quieres visualizar:**")
                    
                    # Permitir seleccionar columna para graficar
                    chart_col = st.selectbox(
                        "Columna principal para visualizar",
                        options=categorical_cols,
                        key=f"exec_caus_{code}_chart_col",
                        help="Selecciona la columna para generar gráficos de barras y pie"
                    )
                    
                    try:
                        col1, col2 = st.columns(2)
                        with col1:
                            counts = df[chart_col].value_counts().reset_index()
                            counts.columns = [chart_col, 'Cantidad']
                            fig_bar = create_bar_chart(counts, x=chart_col, y='Cantidad', 
                                                       title=f"Distribución por {chart_col}")
                            st.plotly_chart(fig_bar, width='stretch', key=f"caus_{code}_bar_{chart_col}")
                        with col2:
                            fig_pie = create_pie_chart(df, names=chart_col, 
                                                       title=f"Proporción por {chart_col}")
                            st.plotly_chart(fig_pie, width='stretch', key=f"caus_{code}_pie_{chart_col}")
                        
                        # Mostrar tabla de frecuencias
                        st.markdown(f"**📋 Tabla de Frecuencias - {chart_col}**")
                        st.dataframe(counts, width='stretch', hide_index=True)
                        
                    except Exception as e:
                        st.error(f"Error generando gráficos categóricos: {str(e)}")
                    
                    # Opción adicional: visualizar otras columnas categóricas
                    if len(categorical_cols) > 1:
                        st.divider()
                        st.markdown("**🔍 Explorar otras columnas categóricas**")
                        
                        other_cols = [c for c in categorical_cols if c != chart_col]
                        selected_others = st.multiselect(
                            "Selecciona columnas adicionales para ver distribuciones",
                            options=other_cols,
                            key=f"exec_caus_{code}_other_cats",
                            help="Puedes seleccionar múltiples columnas"
                        )
                        
                        if selected_others:
                            for idx, col_name in enumerate(selected_others):
                                with st.expander(f"📊 Distribución de {col_name}", expanded=False):
                                    col_a, col_b = st.columns(2)
                                    with col_a:
                                        counts_other = df[col_name].value_counts().reset_index()
                                        counts_other.columns = [col_name, 'Cantidad']
                                        fig_bar_other = create_bar_chart(counts_other, x=col_name, y='Cantidad',
                                                                         title=f"Distribución por {col_name}")
                                        st.plotly_chart(fig_bar_other, width='stretch', 
                                                       key=f"caus_{code}_bar_other_{idx}_{col_name}")
                                    with col_b:
                                        fig_pie_other = create_pie_chart(df, names=col_name,
                                                                         title=f"Proporción por {col_name}")
                                        st.plotly_chart(fig_pie_other, width='stretch',
                                                       key=f"caus_{code}_pie_other_{idx}_{col_name}")
                                    
                                    # Tabla de frecuencias
                                    st.dataframe(counts_other, width='stretch', hide_index=True)
                
                tab_idx += 1
            
            # Tab de numéricas
            if numeric_cols:
                with viz_tab_objects[tab_idx]:
                    st.markdown("**Selecciona la columna numérica para analizar:**")
                    
                    selected_numeric = st.selectbox(
                        "Columna numérica",
                        options=numeric_cols,
                        key=f"exec_caus_{code}_numeric_col",
                        help="Visualiza distribuciones y estadísticas de columnas numéricas"
                    )
                    
                    try:
                        import plotly.express as px
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            # Histogram
                            fig_hist = px.histogram(df, x=selected_numeric, 
                                                   title=f"Distribución de {selected_numeric}",
                                                   nbins=30)
                            fig_hist.update_layout(showlegend=False)
                            st.plotly_chart(fig_hist, width='stretch', key=f"caus_{code}_hist_{selected_numeric}")
                        
                        with col2:
                            # Box plot
                            fig_box = px.box(df, y=selected_numeric, 
                                            title=f"Box Plot de {selected_numeric}")
                            st.plotly_chart(fig_box, width='stretch', key=f"caus_{code}_box_{selected_numeric}")
                        
                        # Statistics summary
                        st.markdown("**📈 Estadísticas Descriptivas**")
                        stats_df = df[selected_numeric].describe().to_frame().T
                        st.dataframe(stats_df, width='stretch', hide_index=True)
                        
                    except Exception as e:
                        st.error(f"Error generando gráficos numéricos: {str(e)}")
        else:
            # Sin columnas visualizables
            st.markdown("**📊 Resumen de Registros**")
            st.metric("Total de Registros", len(df))
            
            # Try to show any useful summary
            try:
                import plotly.graph_objects as go
                
                fig = go.Figure(data=[go.Indicator(
                    mode="number",
                    value=len(df),
                    title={"text": "Registros Detectados"},
                    domain={'x': [0, 1], 'y': [0, 1]}
                )])
                fig.update_layout(height=300)
                st.plotly_chart(fig, width='stretch')
            except:
                pass


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

    # Mark script as executing and clear all previous results
    st.session_state.script_executing = True
    st.session_state.executing_script_name = script_name
    st.session_state.execution_console_log = [f"`{datetime.now().strftime('%H:%M:%S')}` • Preparando ejecución..."]
    st.session_state.execution_progress = 0.0
    st.session_state.execution_result = None
    st.session_state.execution_error = None
    st.session_state.current_result = None  # Clear previous results

    def run_script_in_background():
        """Background thread function to execute script."""
        # Define add_log OUTSIDE try block so it's available in except
        def add_log(message: str, level: str = "info"):
            """Add a message to the console log."""
            timestamp = datetime.now().strftime("%H:%M:%S")
            icon = {"info": "•", "success": "✓", "warning": "!", "error": "×", "query": "Q", "process": "•"}.get(level, "•")
            
            # Get current log and append
            current_log = st.session_state.get('execution_console_log', [])
            current_log.append(f"`{timestamp}` {icon} {message}")
            st.session_state.execution_console_log = current_log
        
        # Initialize history_manager outside try for error handling
        history_manager = get_history_manager()
        
        try:
            # Ensure initial log is visible
            timestamp = datetime.now().strftime("%H:%M:%S")
            st.session_state.execution_console_log = [
                f"`{timestamp}` • Thread iniciado correctamente",
                f"`{timestamp}` • Inicializando motor de ejecución..."
            ]
            
            # Check if sf_client exists
            if not hasattr(st.session_state, 'sf_client') or st.session_state.sf_client is None:
                add_log("❌ Error: No hay conexión a Salesforce", "error")
                raise AttributeError("sf_client no está inicializado. Conecta a Salesforce primero.")
            
            engine = ExecutionEngine(sf_client=st.session_state.sf_client)
            
            def update_progress(step: str, progress: float, message: str):
                """Update progress bar and add log message."""
                st.session_state.execution_progress = progress
                
                # Determine level based on message content
                if "consulta" in message.lower() or "query" in message.lower():
                    level = "query"
                elif "procesando" in message.lower() or "process" in message.lower():
                    level = "process"
                elif "✓" in message or "éxito" in message.lower():
                    level = "success"
                elif "✗" in message or "error" in message.lower():
                    level = "error"
                elif "⚠" in message or "warning" in message.lower():
                    level = "warning"
                else:
                    level = "info"
                    
                add_log(message, level)

            engine.set_progress_callback(update_progress)
            
            add_log(f"Iniciando script: **{script_name}**", "info")
            add_log(f"Entorno: {st.session_state.sf_client.env.upper()}", "info")
            add_log(f"Actualizaciones: {'Sí' if execute_updates else 'No'}", "info")

            # Capture print statements from script
            print_capturer = PrintCapture(add_log)
            old_stdout = sys.stdout
            sys.stdout = print_capturer
            
            try:
                # Execute script
                result = engine.execute(
                    script_class,
                    preview=False,
                    execute_updates=execute_updates
                )
            finally:
                # Restore original stdout
                sys.stdout = old_stdout

            # Calculate record count (handle causísticas)
            if result.has_causisticas and result.causisticas:
                record_count = sum(caus.count for caus in result.causisticas.values())
            else:
                record_count = len(result.data) if result.data is not None else 0

            # Save to persistent history
            env = st.session_state.sf_client.env if st.session_state.sf_client else None
            history_record = history_manager.add(
                script_name=script_name,
                script_category=script_class.category,
                success=result.success,
                record_count=record_count,
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
                'record_count': record_count,
                'execution_time': result.execution_time,
                'executed_at': result.executed_at.isoformat()
            })

            if result.success:
                # Show appropriate success message
                if result.has_causisticas and result.causisticas:
                    total_causisticas = len(result.causisticas)
                    add_log(f"✓ Causísticas detectadas: **{total_causisticas}**", "success")
                    add_log(f"✓ Total registros: **{record_count:,}**", "success")
                else:
                    add_log(f"✓ Registros procesados: **{record_count:,}**", "success")
                add_log(f"✓ Ejecución completada en **{result.execution_time:.2f}s**", "success")
                add_log(f"✓ Guardado en historial (ID: {history_record['id']})", "info")
            else:
                add_log("", "error")
                add_log("═" * 60, "error")  
                add_log("❌ **EJECUCIÓN FALLIDA**", "error")
                add_log("═" * 60, "error")
                add_log(f"**Error:** {result.error_message.split(chr(10))[0]}", "error")
                if result.error_message and len(result.error_message.split(chr(10))) > 1:
                    add_log(f"**Traceback disponible** (expandir para ver detalles)", "error")
                add_log("═" * 60, "error")
                add_log("", "error")

            for warning in result.warnings:
                add_log(f"⚠ {warning}", "warning")

            # Store result
            st.session_state.execution_result = result
            st.session_state.execution_progress = 1.0

        except Exception as e:
            # Store error and save to history
            import traceback
            error_msg = f"{str(e)}\n{traceback.format_exc()}"
            error_lines = traceback.format_exc().split('\n')
            st.session_state.execution_error = error_msg
            
            # Enhanced error logging - show in console
            add_log("", "error")
            add_log("═" * 60, "error")
            add_log("❌ **EXCEPCIÓN NO CONTROLADA**", "error")
            add_log("═" * 60, "error")
            add_log(f"**Error:** {str(e)}", "error")
            add_log(f"**Tipo:** {type(e).__name__}", "error")
            add_log("", "error")
            
            # Add key traceback lines (last 5 lines are most relevant)
            add_log("**Traceback (últimas líneas):**", "error")
            for line in error_lines[-8:]:  # Show last 8 lines of traceback
                if line.strip():
                    add_log(f"  {line}", "error")
            
            add_log("═" * 60, "error")
            add_log("", "error")
            
            # Save failed execution to persistent history
            try:
                env = st.session_state.get('sf_client', {}).env if st.session_state.get('sf_client') else None
                history_record = history_manager.add(
                    script_name=script_name,
                    script_category=script_class.category if hasattr(script_class, 'category') else 'Unknown',
                    success=False,
                    record_count=0,
                    execution_time=0,
                    error_message=error_msg,
                    warnings_count=0,
                    preview=False,
                    env=env
                )
                
                # Also keep in session for backward compatibility
                st.session_state.execution_history.append({
                    'script_name': script_name,
                    'success': False,
                    'record_count': 0,
                    'execution_time': 0,
                    'executed_at': datetime.now().isoformat()
                })
                
                # Confirm history save
                add_log(f"✓ Error guardado en historial (ID: {history_record['id']})", "info")
                
            except Exception as hist_error:
                add_log(f"Error guardando historial: {str(hist_error)}", "error")
            
        finally:
            # Mark script execution as complete
            st.session_state.script_executing = False
            st.session_state.executing_script_name = None

    # Start background thread with Streamlit context
    thread = threading.Thread(target=run_script_in_background, daemon=True)
    
    # Add Streamlit context to thread to avoid "missing ScriptRunContext" warning
    ctx = get_script_run_ctx()
    if ctx:
        add_script_run_ctx(thread, ctx)
    
    thread.start()
    
    # Trigger immediate rerun to show execution UI
    st.rerun()




