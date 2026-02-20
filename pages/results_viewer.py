"""
Results Viewer Page - Detailed analysis and visualization of results.
Also accessible from sidebar navigation as a standalone view.
"""
import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO

from visualization.charts import (
    create_bar_chart,
    create_pie_chart,
    create_line_chart,
    create_timeline_chart,
    ChartBuilder
)
from visualization.kpis import KPIPanel


def render():
    """Render the results viewer page."""
    st.markdown('<div class="hero-title" style="font-size:1.6rem;">📊 Visualización de Resultados</div>', unsafe_allow_html=True)

    if st.session_state.current_result is None:
        st.info("No hay resultados para mostrar. Ejecuta un script primero.")
        if st.button("▶️ Ir a Ejecutar Scripts", type="primary"):
            st.session_state.current_page = 'script_execution'
            st.rerun()
        return

    result = st.session_state.current_result

    if result.data is None or result.data.empty:
        st.warning("El resultado no contiene datos.")
        return

    df = result.data.copy()

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Registros", len(df))
    with col2:
        st.metric("Tiempo", f"{result.execution_time:.2f}s")
    with col3:
        st.metric("Estado", "✅ OK" if result.success else "❌ Error")
    with col4:
        st.metric("Anomalías", len(result.anomalies) if result.anomalies is not None else 0)

    st.markdown("")

    tab1, tab2, tab3, tab4 = st.tabs([
        "📋 Datos",
        "📈 Gráficos",
        "🔍 Análisis",
        "⚠️ Anomalías"
    ])

    with tab1:
        _render_data_tab(df)
    with tab2:
        _render_charts_tab(df)
    with tab3:
        _render_analysis_tab(df)
    with tab4:
        _render_anomalies_tab(result)


def _render_data_tab(df: pd.DataFrame):
    """Render the data table tab."""

    with st.expander("🔍 Filtros", expanded=False):
        filter_columns = st.multiselect(
            "Columnas para filtrar",
            options=df.columns.tolist(),
            default=[],
            key="rv_filter_columns"
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
                            key=f"rv_filter_{col_name}"
                        )
                        if selected:
                            filters[col_name] = selected

    filtered_df = df.copy()
    for col_name, vals in filters.items():
        filtered_df = filtered_df[filtered_df[col_name].isin(vals)]

    col1, col2 = st.columns([3, 1])
    with col1:
        st.caption(f"Mostrando {len(filtered_df)} de {len(df)} registros")
    with col2:
        col_a, col_b = st.columns(2)
        with col_a:
            csv = filtered_df.to_csv(index=False, encoding='utf-8-sig')
            st.download_button(
                "📥 CSV",
                data=csv,
                file_name=f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                key="rv_dl_csv"
            )
        with col_b:
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                filtered_df.to_excel(writer, index=False, sheet_name='Datos')
            st.download_button(
                "📥 Excel",
                data=output.getvalue(),
                file_name=f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="rv_dl_xlsx"
            )

    st.dataframe(filtered_df, use_container_width=True, hide_index=True, height=500)


def _render_charts_tab(df: pd.DataFrame):
    """Render the charts tab."""

    # Auto-generate distribution charts
    categorical_cols = [c for c in df.columns if df[c].nunique() <= 30 and df[c].nunique() > 1]

    if categorical_cols:
        auto_col = categorical_cols[0]
        try:
            col1, col2 = st.columns(2)
            with col1:
                counts = df[auto_col].value_counts().reset_index()
                counts.columns = [auto_col, 'Cantidad']
                fig_bar = create_bar_chart(counts, x=auto_col, y='Cantidad', title=f"Distribución por {auto_col}")
                st.plotly_chart(fig_bar, use_container_width=True, key="rv_auto_bar")
            with col2:
                fig_pie = create_pie_chart(df, names=auto_col, title=f"Proporción por {auto_col}")
                st.plotly_chart(fig_pie, use_container_width=True, key="rv_auto_pie")
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
            key="rv_chart_type"
        )
    with col2:
        x_col = st.selectbox("Columna", options=df.columns.tolist(), key="rv_chart_x")
    with col3:
        y_options = [None] + [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
        y_col = st.selectbox(
            "Valores (opcional)",
            options=y_options,
            format_func=lambda x: "Contar" if x is None else x,
            key="rv_chart_y"
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
            st.plotly_chart(fig, use_container_width=True, key="rv_custom_chart")
    except Exception as e:
        st.error(f"Error generando gráfico: {str(e)}")


def _render_analysis_tab(df: pd.DataFrame):
    """Render the analysis tab."""

    kpi_panel = KPIPanel(df)
    kpi_panel.add_count("Total Registros", "📋")
    for col in df.columns[:3]:
        if df[col].nunique() < len(df):
            kpi_panel.add_unique_count(col, f"Únicos {col}", "🔢")
    kpi_panel.render(columns=4)

    st.divider()

    st.markdown("**Agrupación y Agregación**")

    groupable_cols = [c for c in df.columns if 1 < df[c].nunique() <= 50]

    if not groupable_cols:
        st.info("No hay columnas adecuadas para agrupar.")
    else:
        col1, col2 = st.columns(2)
        with col1:
            groupby_col = st.selectbox("Agrupar por", options=groupable_cols, key="rv_analysis_groupby")
        with col2:
            agg_type = st.selectbox("Tipo", options=["Contar", "Suma", "Media", "Máximo", "Mínimo"], key="rv_analysis_agg")

        if agg_type == "Contar":
            grouped = df[groupby_col].value_counts().reset_index()
            grouped.columns = [groupby_col, "Cantidad"]
        else:
            numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
            if numeric_cols:
                agg_col = st.selectbox("Columna numérica", options=numeric_cols, key="rv_agg_col")
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
                st.plotly_chart(fig, use_container_width=True, key="rv_analysis_chart")
            except Exception as e:
                st.error(f"Error: {str(e)}")

    st.divider()

    with st.expander("📊 Resumen Estadístico"):
        st.dataframe(df.describe(), use_container_width=True)

    with st.expander("ℹ️ Información de Columnas"):
        col_info = pd.DataFrame({
            'Columna': df.columns,
            'Tipo': [str(df[c].dtype) for c in df.columns],
            'No Nulos': [df[c].notna().sum() for c in df.columns],
            'Nulos': [df[c].isna().sum() for c in df.columns],
            'Únicos': [df[c].nunique() for c in df.columns]
        })
        st.dataframe(col_info, use_container_width=True, hide_index=True)


def _render_anomalies_tab(result):
    """Render the anomalies tab."""

    if result.anomalies is None or result.anomalies.empty:
        st.success("✅ No se detectaron anomalías en los datos.")
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
            st.plotly_chart(fig, use_container_width=True, key="rv_anomaly_chart")
        except Exception:
            pass

    st.dataframe(anomalies_df, use_container_width=True, hide_index=True, height=400)

    csv = anomalies_df.to_csv(index=False, encoding='utf-8-sig')
    st.download_button(
        "📥 Exportar Anomalías (CSV)",
        data=csv,
        file_name=f"anomalias_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
        key="rv_dl_anomalies"
    )
