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
import math
import os
import re as _re
import html as _html
from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx

from core.script_registry import get_registry
from core.execution_engine import ExecutionEngine
from core.history_manager import get_history_manager
from core import result_store
from visualization.kpis import KPIPanel
from visualization.charts import (
    create_bar_chart,
    create_pie_chart,
    ChartBuilder
)

# ── Pagination Constants ────────────────────────────────────────────────
DATA_PAGE_SIZE = 500          # rows per page in data tables
MEMORY_LIMIT_MB = 150         # max MB per result before truncation
EXCEL_MAX_ROWS = 100_000      # max rows for Excel export (openpyxl limit)
CHART_SAMPLE_SIZE = 50_000    # max rows for chart rendering
CSV_MAX_ROWS = 100_000        # max rows for CSV export (keep under 200MB WebSocket limit)


def _format_log_line(raw: str) -> str:
    """Convert a raw log line to safe HTML with minimal styling."""
    # Escape all HTML entities first so injected content can't break the DOM
    escaped = _html.escape(raw)
    # backtick code spans: `text` → styled <code>
    escaped = _re.sub(
        r'`([^`]+)`',
        r'<code style="background:#1E293B;border-radius:3px;padding:0 3px 1px;'
        r'color:#7DD3FC;font-size:0.78rem;">\1</code>',
        escaped
    )
    # **bold** → <strong>
    escaped = _re.sub(r'\*\*([^*]+)\*\*', r'<strong style="color:#F8FAFC;">\1</strong>', escaped)
    return escaped


class PrintCapture(StringIO):
    """Capture print statements and redirect them to Streamlit console."""
    
    def __init__(self, add_log_func):
        super().__init__()
        self.add_log = add_log_func
    
    def write(self, text):
        """Intercept write calls from print statements."""
        if text is not None:
            # Handle bytes-like objects being written to stdout
            if isinstance(text, bytes):
                try:
                    text_str = text.decode('utf-8')
                except Exception:
                    text_str = str(text)
            else:
                text_str = str(text)
                
            if text_str.strip():  # Ignore empty lines
                clean_text = text_str.strip()
                
                # Send to Streamlit console
                clean_lower = clean_text.lower()
                if "error" in clean_lower:
                    self.add_log(clean_text, "error")
                elif "warning" in clean_lower:
                    self.add_log(clean_text, "warning")
                else:
                    self.add_log(clean_text, "info")
                    
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
    
    # Calculate elapsed time
    start_ts = st.session_state.get('execution_start_time')
    if start_ts and st.session_state.get('script_executing', False):
        elapsed = time.time() - start_ts
        elapsed_str = f"{int(elapsed)}s"
    else:
        elapsed_str = ""
    
    # Determine bar color based on progress: blue → cyan → green
    if progress_percent < 40:
        bar_color = "linear-gradient(90deg, #2563EB 0%, #0EA5E9 100%)"
        glow_color = "rgba(37,99,235,0.3)"
        text_color = "#60A5FA"
    elif progress_percent < 75:
        bar_color = "linear-gradient(90deg, #0EA5E9 0%, #10B981 100%)"
        glow_color = "rgba(14,165,233,0.3)"
        text_color = "#34D399"
    else:
        bar_color = "linear-gradient(90deg, #10B981 0%, #059669 100%)"
        glow_color = "rgba(16,185,129,0.35)"
        text_color = "#34D399"
    
    # Only show progress bar if script is still executing
    if st.session_state.get('script_executing', False):
        step_label = st.session_state.get('execution_step_label', 'Preparando...')
        st.markdown(
            f"""
            <style>
                @keyframes progressShimmer {{
                    0% {{ background-position: -200% 0; }}
                    100% {{ background-position: 200% 0; }}
                }}
            </style>
            <div style="
                background: #0F172A;
                border: 1px solid #1E293B;
                border-radius: 14px;
                padding: 1rem 1.25rem;
                margin-bottom: 1rem;
                box-shadow: 0 4px 16px rgba(0,0,0,0.15);
            ">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.6rem;">
                    <div style="display: flex; align-items: center; gap: 0.5rem;">
                        <div style="
                            width: 8px; height: 8px; border-radius: 50%;
                            background: {text_color};
                            box-shadow: 0 0 8px {glow_color};
                            animation: pulse 1.5s ease-in-out infinite;
                        "></div>
                        <span style="color: #94A3B8; font-size: 0.8rem; font-weight: 500;">{step_label}</span>
                    </div>
                    <div style="display: flex; align-items: center; gap: 0.75rem;">
                        <span style="color: #64748B; font-size: 0.75rem;">{elapsed_str}</span>
                        <span style="
                            color: {text_color};
                            font-weight: 800;
                            font-size: 1.05rem;
                            font-variant-numeric: tabular-nums;
                        ">{progress_percent}%</span>
                    </div>
                </div>
                <div style="
                    background: #1E293B;
                    border-radius: 10px;
                    height: 12px;
                    overflow: hidden;
                    position: relative;
                ">
                    <div style="
                        height: 100%;
                        width: {progress_percent}%;
                        background: {bar_color};
                        border-radius: 10px;
                        transition: width 0.4s ease;
                        position: relative;
                        overflow: hidden;
                    ">
                        <div style="
                            position: absolute;
                            top: 0; left: 0; right: 0; bottom: 0;
                            background: linear-gradient(
                                90deg,
                                transparent 0%,
                                rgba(255,255,255,0.2) 50%,
                                transparent 100%
                            );
                            background-size: 200% 100%;
                            animation: progressShimmer 2s linear infinite;
                        "></div>
                    </div>
                </div>
            </div>
            <style>
                @keyframes pulse {{
                    0%, 100% {{ opacity: 1; }}
                    50% {{ opacity: 0.4; }}
                }}
            </style>
            """,
            unsafe_allow_html=True
        )
    elif progress_percent >= 100:
        # Completed state — static green bar
        st.markdown(
            f"""
            <div style="
                background: #0F172A;
                border: 1px solid #1E293B;
                border-radius: 14px;
                padding: 1rem 1.25rem;
                margin-bottom: 1rem;
            ">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.6rem;">
                    <span style="color: #34D399; font-size: 0.8rem; font-weight: 600;">✅ Ejecución completada</span>
                    <span style="color: #34D399; font-weight: 800; font-size: 1.05rem;">100%</span>
                </div>
                <div style="background: #1E293B; border-radius: 10px; height: 12px; overflow: hidden;">
                    <div style="height: 100%; width: 100%; background: linear-gradient(90deg, #10B981, #059669); border-radius: 10px;"></div>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
    
    # Show console output
    if console_log:
        # Limit visible log lines to last 200 to prevent DOM bloat
        visible_log = console_log[-200:] if len(console_log) > 200 else console_log
        truncation_notice = (
            f'<div style="color:#64748B;font-size:0.75rem;padding:0.25rem 0;">'
            f'... {len(console_log) - 200} líneas anteriores omitidas</div>'
        ) if len(console_log) > 200 else ''
        # Escape each line before injecting into HTML
        formatted_lines = '<br>'.join(_format_log_line(line) for line in visible_log)
        st.markdown(
            f'<div style="background:#0F172A;color:#CBD5E1;padding:1rem;border-radius:10px;'
            f'font-family:\'Consolas\',\'Monaco\',\'Courier New\',monospace;font-size:0.82rem;'
            f'max-height:450px;overflow-y:auto;line-height:1.7;'
            f'border:1px solid #1E293B;box-shadow:0 2px 8px rgba(0,0,0,0.1);">'
            f'{truncation_notice}{formatted_lines}</div>',
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            """
            <div style="background: #0F172A; color: #CBD5E1; padding: 1.5rem; border-radius: 10px; 
                font-family: 'Consolas', 'Monaco', 'Courier New', monospace; font-size: 0.85rem; text-align: center; 
                border: 1px solid #1E293B;">
                <span style="color: #64748B;">⏳ Iniciando ejecución...</span>
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
            @st.fragment(run_every=2)  # Auto-update every 2 seconds (reduces flicker)
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
            record_count = st.session_state.get('result_total_rows', 0)
            if result.has_causisticas and result.causisticas:
                record_count = sum(caus.count for caus in result.causisticas.values())
            st.success(f"**Última ejecución:** {script_name} - {record_count:,} registros en {result.execution_time:.2f}s")

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


@st.cache_data(show_spinner=False, max_entries=5)
def _analyze_schema(db_path: str, columns: list, col_types: dict):
    """
    Scan schema once per result to identify categorical, numeric, and filterable columns.
    Returns: (numeric_cols, categorical_cols, groupable_cols, categorical_values_map, kpi_counts)
    """
    numeric_cols = []
    categorical_cols = []
    groupable_cols = []
    categorical_values = {}
    kpi_counts = {}
    
    # 1. Classify columns
    for col in columns:
        t = col_types.get(col, 'TEXT').upper()
        if t in ('INTEGER', 'REAL', 'NUMERIC'):
            numeric_cols.append(col)
        else:
            try:
                vals = result_store.get_categorical_values(db_path, col, max_vals=200)
                if vals is not None:
                    categorical_values[col] = vals
                    if len(vals) > 1:
                        categorical_cols.append(col)
                        groupable_cols.append(col)
            except Exception:
                pass

    # 2. Precompute the first 3 columns unique counts (for KPIs)
    for col in columns[:3]:
        try:
            kpi_counts[col] = result_store.column_unique_count(db_path, col)
        except Exception:
            pass

    return numeric_cols, categorical_cols, groupable_cols, categorical_values, kpi_counts



def _render_full_results(result):
    """Render the full results inline with all tabs."""

    st.markdown('<div class="section-header">Resultados</div>', unsafe_allow_html=True)

    # ── Multi-causística results ────────────────────────────────────────
    if result.has_causisticas and result.causisticas:
        _render_causistica_results(result)
        return

    # ── Metadata from session (set during execution) ────────────────────
    db_path = st.session_state.get('result_db_path')
    total_rows = st.session_state.get('result_total_rows', 0)
    columns = st.session_state.get('result_columns', [])
    col_types = st.session_state.get('result_col_types', {})

    no_data = (db_path is None or not os.path.exists(db_path)) and \
              (result.data is None or (hasattr(result.data, 'empty') and result.data.empty))

    # ── Summary Metrics ─────────────────────────────────────────────────
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Registros", value=f"{total_rows:,}")
    with col2:
        st.metric("Tiempo", value=f"{result.execution_time:.2f}s")
    with col3:
        st.metric("Estado", value="OK" if result.success else "Error")
    with col4:
        st.metric("Anomalías", value=len(result.anomalies) if result.anomalies is not None else 0)

    if result.metrics and result.metrics.custom_metrics:
        kpi_panel = KPIPanel()
        kpi_panel.add_from_metrics(result.metrics.custom_metrics)
        kpi_panel.render()

    if no_data:
        if not result.success:
            st.error(f"Error: {result.error_message}")
        else:
            st.info("La ejecución no devolvió datos.")
        return

    st.markdown("")

    # ── Tabbed Results ──────────────────────────────────────────────────
    tab_analysis, tab_data, tab_charts, tab_anomalies = st.tabs([
        "Análisis", "Datos", "Gráficos", "Anomalías"
    ])

    with tab_analysis:
        _render_analysis_tab(db_path=db_path, columns=columns, col_types=col_types, total_rows=total_rows)

    with tab_data:
        _render_data_tab(db_path=db_path, total_rows=total_rows)

    with tab_charts:
        _render_charts_tab(db_path=db_path, columns=columns, col_types=col_types)

    with tab_anomalies:
        _render_anomalies_tab(result, total_rows)


# ═══════════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════
# Data Tab  (SQLite-backed: O(1) pagination, no DataFrame in RAM)
# ═══════════════════════════════════════════════════════════════════════
def _render_data_tab(db_path: str, total_rows: int, key_prefix: str = "exec"):
    """Paginated data table backed by SQLite — instant for any dataset size."""

    if not db_path or not os.path.exists(db_path):
        st.info("No hay datos disponibles.")
        return

    columns = result_store.get_columns(db_path)
    col_types = st.session_state.get('result_col_types', {})
    _, _, _, cat_vals, _ = _analyze_schema(db_path, columns, col_types)

    # Use a highly specific key_prefix to avoid duplicate widgets across reruns
    safe_prefix = f"{key_prefix}_{hash(db_path)}" if db_path else key_prefix

    # ── Filters (distinct values via SQL — no Python scan) ────────────────
    with st.expander("Filtros", expanded=False):
        filter_columns = st.multiselect(
            "Columnas para filtrar", options=columns, default=[],
            key=f"{safe_prefix}_filter_columns_selector"
        )
        filters = {}
        if filter_columns:
            fcols = st.columns(min(len(filter_columns), 4))
            for idx, col_name in enumerate(filter_columns):
                with fcols[idx % len(fcols)]:
                    vals = cat_vals.get(col_name)
                    if vals is not None and len(vals) <= 50:
                        sel = st.multiselect(col_name, options=vals,
                                             key=f"{safe_prefix}_filter_val_{col_name}")
                        if sel:
                            filters[col_name] = sel
                    else:
                        st.caption("Demasiados valores únicos para filtrar")

    # ── Row count (filtered) ──────────────────────────────────────────────
    if filters:
        visible_rows = result_store.count_filtered(db_path, filters)
    else:
        visible_rows = total_rows
    total_pages = max(1, math.ceil(visible_rows / DATA_PAGE_SIZE))

    # ── Page state ────────────────────────────────────────────────────────
    page_key = f"{safe_prefix}_data_page"
    if page_key not in st.session_state:
        st.session_state[page_key] = 0
    if st.session_state[page_key] >= total_pages:
        st.session_state[page_key] = 0
    current_page = st.session_state[page_key]

    # ── Info + Pagination + Export ────────────────────────────────────────
    col_info, col_pagination, col_export = st.columns([2, 3, 2])

    with col_info:
        start_row = current_page * DATA_PAGE_SIZE + 1
        end_row = min((current_page + 1) * DATA_PAGE_SIZE, visible_rows)
        if visible_rows > DATA_PAGE_SIZE:
            st.caption(f"Filas {start_row:,}–{end_row:,} de {visible_rows:,} registros")
        else:
            st.caption(f"Mostrando {visible_rows:,} registros")

    with col_pagination:
        if total_pages > 1:
            p1, p2, p3, p4, p5 = st.columns([1, 1, 2, 1, 1])
            with p1:
                if st.button("⏮", key=f"{safe_prefix}_first", disabled=current_page == 0):
                    st.session_state[page_key] = 0; st.rerun()
            with p2:
                if st.button("◀", key=f"{safe_prefix}_prev", disabled=current_page == 0):
                    st.session_state[page_key] = current_page - 1; st.rerun()
            with p3:
                st.markdown(
                    f'<div style="text-align:center;color:var(--text-secondary);'
                    f'font-size:0.85rem;padding-top:0.35rem;">'
                    f'Pág. <strong>{current_page + 1}</strong> / {total_pages}</div>',
                    unsafe_allow_html=True)
            with p4:
                if st.button("▶", key=f"{safe_prefix}_next",
                             disabled=current_page >= total_pages - 1):
                    st.session_state[page_key] = current_page + 1; st.rerun()
            with p5:
                if st.button("⏭", key=f"{safe_prefix}_last",
                             disabled=current_page >= total_pages - 1):
                    st.session_state[page_key] = total_pages - 1; st.rerun()

    # ── Lazy export (no data generated until user clicks the button) ──────
    with col_export:
        csv_key = f"{safe_prefix}_csv_ready"
        xlsx_key = f"{safe_prefix}_xlsx_ready"

        e1, e2 = st.columns(2)
        with e1:
            if not st.session_state.get(csv_key):
                if st.button("📥 CSV", key=f"{safe_prefix}_btn_prepare_csv", use_container_width=True):
                    st.session_state[csv_key] = True; st.rerun()
            else:
                try:
                    export_df = result_store.get_data_batch(db_path, offset=0, limit=CSV_MAX_ROWS, filters=filters)
                    csv_bytes = export_df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
                    label = f"⬇ CSV ({len(export_df):,})"
                    st.download_button(
                        label, data=csv_bytes,
                        file_name=f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv", key=f"{safe_prefix}_dl_csv",
                        on_click=lambda: st.session_state.pop(csv_key, None),
                        use_container_width=True
                    )
                except Exception as e:
                    st.warning(f"Error CSV: {e}")
                    st.session_state.pop(csv_key, None)

        with e2:
            if not st.session_state.get(xlsx_key):
                if st.button("📥 Excel", key=f"{safe_prefix}_btn_prepare_xlsx", use_container_width=True):
                    st.session_state[xlsx_key] = True; st.rerun()
            else:
                try:
                    export_df = result_store.get_data_batch(db_path, offset=0, limit=EXCEL_MAX_ROWS, filters=filters)
                    out = BytesIO()
                    with pd.ExcelWriter(out, engine='openpyxl') as writer:
                        export_df.to_excel(writer, index=False, sheet_name='Datos')
                    label = f"⬇ Excel ({len(export_df):,})"
                    st.download_button(
                        label, data=out.getvalue(),
                        file_name=f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key=f"{safe_prefix}_dl_xlsx",
                        on_click=lambda: st.session_state.pop(xlsx_key, None),
                        use_container_width=True
                    )
                except Exception as e:
                    st.warning(f"Error Excel: {e}")
                    st.session_state.pop(xlsx_key, None)

    # ── Read only the current page (LIMIT/OFFSET — instant) ───────────────
    try:
        page_df = result_store.read_page(db_path, current_page, DATA_PAGE_SIZE,
                                         filters or None)
        st.dataframe(page_df, use_container_width=True, hide_index=True, height=500)
    except Exception as ex:
        st.error(f"Error mostrando datos: {ex}")


# ═══════════════════════════════════════════════════════════════════════
# Charts Tab  (SQL GROUP BY — all rows, no sampling)
# ═══════════════════════════════════════════════════════════════════════
def _render_charts_tab(db_path: str, columns: list, col_types: dict):
    """Charts backed by SQL aggregations — reflects ALL rows, no DataFrame needed."""

    if not db_path or not os.path.exists(db_path):
        st.info("No hay datos disponibles.")
        return

    numeric_cols, categorical_cols, groupable_cols, cat_vals, _ = _analyze_schema(db_path, columns, col_types)

    st.caption("📊 Gráficos basados en **todos** los registros via agregación SQL — sin muestreo.")

    # ── Auto chart (first categorical column) ─────────────────────────────
    if categorical_cols:
        auto_col = categorical_cols[0]
        try:
            counts = result_store.aggregate_counts(db_path, auto_col, top_n=50)
            col1, col2 = st.columns(2)
            with col1:
                fig = create_bar_chart(counts, x=auto_col, y='Cantidad',
                                       title=f"Distribución por {auto_col}")
                st.plotly_chart(fig, width='stretch', key=f'auto_bar_{auto_col}')
            with col2:
                fig2 = create_pie_chart(counts, names=auto_col, values='Cantidad',
                                        title=f"Proporción por {auto_col}")
                st.plotly_chart(fig2, width='stretch', key=f'auto_pie_{auto_col}')
        except Exception:
            pass
    elif numeric_cols:
        auto_num = numeric_cols[0]
        try:
            import plotly.express as px
            hist_df = result_store.aggregate_histogram(db_path, auto_num, bins=30)
            col1, col2 = st.columns(2)
            with col1:
                fig = px.bar(hist_df, x='BinCenter', y='Cantidad',
                             title=f"Distribución de {auto_num}")
                st.plotly_chart(fig, width='stretch', key=f'auto_hist_{auto_num}')
            with col2:
                stats = result_store.aggregate_numeric_stats(db_path, auto_num)
                st.metric("Mín", f"{stats['min']:.2f}" if stats['min'] else "N/A")
                st.metric("Media", f"{stats['mean']:.2f}" if stats['mean'] else "N/A")
                st.metric("Máx", f"{stats['max']:.2f}" if stats['max'] else "N/A")
        except Exception:
            pass

    st.divider()
    st.markdown("**Crear gráfico personalizado**")

    col1, col2, col3 = st.columns(3)
    with col1:
        chart_type = st.selectbox("Tipo de gráfico",
                                  options=["Barras", "Pastel", "Histograma"],
                                  key="exec_chart_type")
    with col2:
        x_col = st.selectbox("Columna", options=columns, key="exec_chart_x")
    with col3:
        y_options = [None] + numeric_cols
        y_col = st.selectbox("Valores (opcional)", options=y_options,
                             format_func=lambda x: "Contar" if x is None else x,
                             key="exec_chart_y")

    try:
        fig = None
        if chart_type == "Barras":
            if y_col is None:
                agg = result_store.aggregate_counts(db_path, x_col, top_n=100)
                fig = create_bar_chart(agg, x=x_col, y='Cantidad',
                                       title=f"Distribución por {x_col}")
            else:
                agg = result_store.groupby_agg(db_path, x_col, y_col, 'sum')
                fig = create_bar_chart(agg, x=agg.columns[0], y=agg.columns[1],
                                       title=f"Suma de {y_col} por {x_col}")
        elif chart_type == "Pastel":
            agg = result_store.aggregate_counts(db_path, x_col, top_n=50)
            fig = create_pie_chart(agg, names=x_col, values='Cantidad',
                                   title=f"Proporción por {x_col}")
        elif chart_type == "Histograma":
            hist_df = result_store.aggregate_histogram(db_path, x_col, bins=30)
            import plotly.express as px
            fig = px.bar(hist_df, x='BinCenter', y='Cantidad',
                         title=f"Histograma de {x_col}")
        if fig:
            st.plotly_chart(fig, width='stretch')
    except Exception as e:
        st.error(f"Error generando gráfico: {e}")


# ═══════════════════════════════════════════════════════════════════════
# Analysis Tab  (SQL aggregation — all rows)
# ═══════════════════════════════════════════════════════════════════════
def _render_analysis_tab(db_path: str, columns: list, col_types: dict, total_rows: int):
    """Analysis tab backed by SQL — works on any dataset size."""

    if not db_path or not os.path.exists(db_path):
        st.info("No hay datos disponibles.")
        return

    numeric_cols, categorical_cols, groupable_cols, cat_vals, kpi_counts = _analyze_schema(db_path, columns, col_types)

    # ── KPIs ──────────────────────────────────────────────────────────────
    kpi_cols = st.columns(4)
    kpi_cols[0].metric("Total Registros", f"{total_rows:,}")
    for i, col in enumerate(columns[:3], 1):
        if col in kpi_counts:
            kpi_cols[i % 4].metric(f"Únicos {col}", f"{kpi_counts[col]:,}")

    st.divider()

    # ── Group by ──────────────────────────────────────────────────────────
    st.markdown("**Agrupación y Agregación**")

    if not groupable_cols:
        st.info("No hay columnas adecuadas para agrupar.")
    else:
        c1, c2 = st.columns(2)
        with c1:
            groupby_col = st.selectbox("Agrupar por", options=groupable_cols,
                                       key="exec_analysis_groupby")
        with c2:
            agg_type = st.selectbox("Tipo",
                                    options=["Contar", "Suma", "Media", "Máximo", "Mínimo"],
                                    key="exec_analysis_agg")

        agg_map = {"Contar": "count", "Suma": "sum", "Media": "mean",
                   "Máximo": "max", "Mínimo": "min"}

        if agg_type == "Contar":
            grouped = result_store.aggregate_counts(db_path, groupby_col, top_n=100)
            grouped.columns = [groupby_col, "Cantidad"]
            val_col = "Cantidad"
        else:
            if numeric_cols:
                agg_col = st.selectbox("Columna numérica", options=numeric_cols,
                                       key="exec_agg_col")
                grouped = result_store.groupby_agg(
                    db_path, groupby_col, agg_col, agg_map[agg_type])
                val_col = grouped.columns[1]
            else:
                st.info("No hay columnas numéricas. Mostrando conteo.")
                grouped = result_store.aggregate_counts(db_path, groupby_col, top_n=100)
                grouped.columns = [groupby_col, "Cantidad"]
                val_col = "Cantidad"

        c1, c2 = st.columns(2)
        with c1:
            st.dataframe(grouped.sort_values(by=val_col, ascending=False),
                         width='stretch', hide_index=True)
        with c2:
            try:
                fig = create_bar_chart(grouped, x=groupby_col, y=val_col,
                                       title=f"{agg_type} por {groupby_col}",
                                       orientation='h')
                st.plotly_chart(fig, width='stretch')
            except Exception as e:
                st.error(f"Error generando gráfico: {e}")





# ═══════════════════════════════════════════════════════════════════════
# Anomalies Tab
# ═══════════════════════════════════════════════════════════════════════
def _render_anomalies_tab(result, total_rows: int):
    """Render anomalies section."""

    if result.anomalies is None or result.anomalies.empty:
        st.success("No se detectaron anomalías en los datos.")
        return

    anomalies_df = result.anomalies

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Anomalías", len(anomalies_df))
    with col2:
        pct = len(anomalies_df) / total_rows * 100 if total_rows > 0 else 0
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

    max_display = 100_000
    if len(anomalies_df) > max_display:
        st.warning(f"Mostrando las primeras {max_display:,} anomalías por rendimiento visual.")
        display_df = anomalies_df.head(max_display)
    else:
        display_df = anomalies_df

    st.dataframe(display_df, width='stretch', hide_index=True, height=400)

    # Lazy CSV to avoid writing huge strings to memory until requested
    if not st.session_state.get('anomalies_csv_ready'):
        if st.button("📥 Preparar CSV de Anomalías"):
            st.session_state['anomalies_csv_ready'] = True
            st.rerun()
    else:
        try:
            # We enforce a hard limit to avoid 200MB websocket crashes
            export_df = anomalies_df.head(100_000)
            csv_bytes = export_df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
            label = f"⬇ Descargar CSV ({len(export_df):,})"
            st.download_button(
                label,
                data=csv_bytes,
                file_name=f"anomalias_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                key="exec_dl_anomalies",
                on_click=lambda: st.session_state.pop('anomalies_csv_ready', None)
            )
        except Exception as e:
            st.warning(f"Error CSV: {e}")
            st.session_state.pop('anomalies_csv_ready', None)


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
            try:
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    # Write summary sheet
                    summary_df.to_excel(writer, index=False, sheet_name='Resumen')
                    
                    # Write each causística as a separate sheet (limit rows per sheet)
                    for code, caus in result.causisticas.items():
                        if not caus.data.empty:
                            # Sanitize sheet name (remove invalid chars, limit length)
                            sheet_name = _sanitize_sheet_name(f"{code}_{caus.name}")
                            export_data = caus.data.head(EXCEL_MAX_ROWS) if len(caus.data) > EXCEL_MAX_ROWS else caus.data
                            export_data.to_excel(writer, index=False, sheet_name=sheet_name)
                
                st.download_button(
                    "📥 Excel Completo",
                    data=output.getvalue(),
                    file_name=f"causisticas_all_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="exec_dl_causisticas_all_xlsx"
                )
            except Exception as e:
                st.warning(f"No se pudo generar el Excel: {e}")
    
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
    
    df = caus.data
    
    # Tabs for data, charts, analysis
    subtab_data, subtab_charts = st.tabs(["Datos", "Gráficos"])
    
    with subtab_data:
        # Reuse the paginated data tab renderer with a unique key prefix per causística
        _render_data_tab(df, key_prefix=f"caus_{code}")
    
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
    st.session_state.execution_start_time = time.time()
    st.session_state.execution_step_label = 'Preparando...'

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
                st.session_state.execution_step_label = message[:80]  # keep label short
                
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

            # ── Persist result to SQLite (frees RAM, enables fast pagination) ─
            if result.success and result.data is not None and not result.data.empty:
                try:
                    add_log(f"💾 Guardando {len(result.data):,} registros en disco...", "info")
                    db_path = result_store.save(result.data)
                    # Clean up old result files (keep last 5)
                    result_store.cleanup_old(max_files=5)
                    # Store metadata in session; free the big DataFrame
                    st.session_state.result_db_path = db_path
                    st.session_state.result_total_rows = len(result.data)
                    st.session_state.result_columns = result.data.columns.tolist()
                    st.session_state.result_col_types = result_store.get_column_types(db_path)
                    result.data = None  # free memory immediately
                    add_log("✓ Datos guardados — paginación instantánea activada", "success")
                except Exception as _e:
                    add_log(f"⚠ Error guardando en disco: {_e}. Los datos quedan en memoria.", "warning")
                    st.session_state.result_db_path = None
                    st.session_state.result_total_rows = len(result.data) if result.data is not None else 0
                    st.session_state.result_columns = result.data.columns.tolist() if result.data is not None else []
                    st.session_state.result_col_types = {}
            else:
                st.session_state.result_db_path = None
                st.session_state.result_total_rows = 0
                st.session_state.result_columns = []
                st.session_state.result_col_types = {}

            # Calculate record count
            if result.has_causisticas and result.causisticas:
                record_count = sum(caus.count for caus in result.causisticas.values())
            else:
                record_count = st.session_state.get('result_total_rows', 0)

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




