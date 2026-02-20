"""
Filters - Dynamic filtering components for data exploration.
"""
import streamlit as st
import pandas as pd
from typing import Optional, Any
from datetime import date, datetime


def apply_filters(
    df: pd.DataFrame,
    filters: dict[str, Any]
) -> pd.DataFrame:
    """
    Apply a dictionary of filters to a DataFrame.
    
    Args:
        df: DataFrame to filter
        filters: Dictionary mapping column names to filter values
                 Values can be: list (isin), tuple (range), or single value
                 
    Returns:
        Filtered DataFrame
    """
    if not filters:
        return df
    
    result = df.copy()
    
    for column, value in filters.items():
        if column not in result.columns:
            continue
        
        if value is None or (isinstance(value, list) and len(value) == 0):
            continue
        
        if isinstance(value, list):
            # Multiple value selection
            result = result[result[column].isin(value)]
        elif isinstance(value, tuple) and len(value) == 2:
            # Range filter
            min_val, max_val = value
            if min_val is not None:
                result = result[result[column] >= min_val]
            if max_val is not None:
                result = result[result[column] <= max_val]
        else:
            # Single value
            result = result[result[column] == value]
    
    return result


class FilterPanel:
    """
    Dynamic filter panel for DataFrames.
    Creates appropriate filter widgets based on column types.
    """
    
    def __init__(
        self,
        df: pd.DataFrame,
        columns: list[str] = None,
        exclude_columns: list[str] = None,
        key_prefix: str = "filter"
    ):
        """
        Initialize filter panel.
        
        Args:
            df: DataFrame to create filters for
            columns: Specific columns to filter (if None, all columns)
            exclude_columns: Columns to exclude from filtering
            key_prefix: Prefix for Streamlit widget keys
        """
        self.df = df
        self.key_prefix = key_prefix
        self.filters: dict[str, Any] = {}
        
        # Determine filterable columns
        exclude = set(exclude_columns or [])
        if columns:
            self.columns = [c for c in columns if c in df.columns and c not in exclude]
        else:
            self.columns = [c for c in df.columns if c not in exclude]
    
    def _get_column_type(self, column: str) -> str:
        """Determine the filter type for a column."""
        dtype = self.df[column].dtype
        
        if pd.api.types.is_datetime64_any_dtype(dtype):
            return 'datetime'
        elif pd.api.types.is_numeric_dtype(dtype):
            unique_count = self.df[column].nunique()
            if unique_count <= 20:
                return 'categorical'
            return 'numeric'
        elif pd.api.types.is_bool_dtype(dtype):
            return 'boolean'
        else:
            unique_count = self.df[column].nunique()
            if unique_count <= 50:
                return 'categorical'
            return 'text'
    
    def _render_categorical_filter(self, column: str) -> Optional[list]:
        """Render a multiselect filter for categorical columns."""
        unique_values = self.df[column].dropna().unique().tolist()
        unique_values.sort(key=str)
        
        selected = st.multiselect(
            column,
            options=unique_values,
            default=[],
            key=f"{self.key_prefix}_{column}"
        )
        
        return selected if selected else None
    
    def _render_numeric_filter(self, column: str) -> Optional[tuple]:
        """Render a range slider for numeric columns."""
        min_val = float(self.df[column].min())
        max_val = float(self.df[column].max())
        
        if min_val == max_val:
            return None
        
        values = st.slider(
            column,
            min_value=min_val,
            max_value=max_val,
            value=(min_val, max_val),
            key=f"{self.key_prefix}_{column}"
        )
        
        # Only return if range is restricted
        if values[0] > min_val or values[1] < max_val:
            return values
        return None
    
    def _render_datetime_filter(self, column: str) -> Optional[tuple]:
        """Render a date range filter."""
        col_data = pd.to_datetime(self.df[column].dropna())
        
        if col_data.empty:
            return None
        
        min_date = col_data.min().date()
        max_date = col_data.max().date()
        
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input(
                f"{column} (desde)",
                value=min_date,
                min_value=min_date,
                max_value=max_date,
                key=f"{self.key_prefix}_{column}_start"
            )
        with col2:
            end_date = st.date_input(
                f"{column} (hasta)",
                value=max_date,
                min_value=min_date,
                max_value=max_date,
                key=f"{self.key_prefix}_{column}_end"
            )
        
        # Only return if range is restricted
        if start_date > min_date or end_date < max_date:
            return (
                datetime.combine(start_date, datetime.min.time()),
                datetime.combine(end_date, datetime.max.time())
            )
        return None
    
    def _render_boolean_filter(self, column: str) -> Optional[bool]:
        """Render a radio filter for boolean columns."""
        options = ["Todos", "Sí", "No"]
        selected = st.radio(
            column,
            options=options,
            horizontal=True,
            key=f"{self.key_prefix}_{column}"
        )
        
        if selected == "Sí":
            return True
        elif selected == "No":
            return False
        return None
    
    def _render_text_filter(self, column: str) -> Optional[str]:
        """Render a text search filter."""
        value = st.text_input(
            f"{column} (contiene)",
            value="",
            key=f"{self.key_prefix}_{column}"
        )
        return value if value else None
    
    def render(self, layout: str = "sidebar") -> dict[str, Any]:
        """
        Render the filter panel.
        
        Args:
            layout: 'sidebar', 'columns', or 'expander'
            
        Returns:
            Dictionary of active filters
        """
        self.filters = {}
        
        if layout == "sidebar":
            container = st.sidebar
            st.sidebar.subheader("🔍 Filtros")
        elif layout == "expander":
            container = st.expander("🔍 Filtros", expanded=False)
        else:
            container = st
        
        with container:
            for column in self.columns:
                col_type = self._get_column_type(column)
                
                if col_type == 'categorical':
                    value = self._render_categorical_filter(column)
                elif col_type == 'numeric':
                    value = self._render_numeric_filter(column)
                elif col_type == 'datetime':
                    value = self._render_datetime_filter(column)
                elif col_type == 'boolean':
                    value = self._render_boolean_filter(column)
                else:
                    value = self._render_text_filter(column)
                
                if value is not None:
                    self.filters[column] = value
            
            # Show active filter count
            if self.filters:
                st.caption(f"Filtros activos: {len(self.filters)}")
                if st.button("🗑️ Limpiar filtros", key=f"{self.key_prefix}_clear"):
                    st.rerun()
        
        return self.filters
    
    def apply(self, df: pd.DataFrame = None) -> pd.DataFrame:
        """
        Apply current filters to a DataFrame.
        
        Args:
            df: DataFrame to filter (uses self.df if None)
            
        Returns:
            Filtered DataFrame
        """
        target_df = df if df is not None else self.df
        return apply_filters(target_df, self.filters)
    
    def get_filter_summary(self) -> str:
        """Get a text summary of active filters."""
        if not self.filters:
            return "Sin filtros activos"
        
        parts = []
        for col, value in self.filters.items():
            if isinstance(value, list):
                parts.append(f"{col}: {', '.join(str(v) for v in value)}")
            elif isinstance(value, tuple):
                parts.append(f"{col}: {value[0]} - {value[1]}")
            else:
                parts.append(f"{col}: {value}")
        
        return " | ".join(parts)


def render_quick_filters(
    df: pd.DataFrame,
    columns: list[str],
    key_prefix: str = "quick"
) -> dict[str, Any]:
    """
    Render quick filters in columns layout.
    
    Args:
        df: DataFrame to filter
        columns: Columns to create filters for
        key_prefix: Prefix for widget keys
        
    Returns:
        Dictionary of active filters
    """
    filters = {}
    cols = st.columns(len(columns))
    
    for idx, column in enumerate(columns):
        if column not in df.columns:
            continue
        
        with cols[idx]:
            unique_values = df[column].dropna().unique().tolist()
            unique_values.sort(key=str)
            
            selected = st.multiselect(
                column,
                options=unique_values,
                default=[],
                key=f"{key_prefix}_{column}"
            )
            
            if selected:
                filters[column] = selected
    
    return filters


def render_groupby_selector(
    df: pd.DataFrame,
    default_columns: list[str] = None,
    key: str = "groupby"
) -> Optional[str]:
    """
    Render a groupby column selector.
    
    Args:
        df: DataFrame
        default_columns: Suggested columns for grouping
        key: Streamlit widget key
        
    Returns:
        Selected column name or None
    """
    if default_columns:
        columns = [c for c in default_columns if c in df.columns]
    else:
        # Auto-detect good grouping columns
        columns = []
        for col in df.columns:
            if df[col].nunique() <= 50 and df[col].nunique() > 1:
                columns.append(col)
    
    if not columns:
        return None
    
    return st.selectbox(
        "Agrupar por",
        options=[None] + columns,
        format_func=lambda x: "Sin agrupación" if x is None else x,
        key=key
    )
