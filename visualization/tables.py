"""
Tables - Dynamic table components for Streamlit.
"""
import streamlit as st
import pandas as pd
from typing import Optional, Callable
from config import ASSET_STATUS_MAP, CONTRACT_STATUS_MAP


def format_salesforce_link(record_id: str, instance_url: str) -> str:
    """Format a Salesforce record ID as a clickable link."""
    if not record_id:
        return ""
    url = f"https://{instance_url}/lightning/r/{record_id}/view"
    return f'<a href="{url}" target="_blank">{record_id}</a>'


def format_status(value: str, status_map: dict) -> str:
    """Format a status code with its label."""
    label = status_map.get(value, value)
    return f"{value} - {label}" if value != label else value


def render_dataframe(
    df: pd.DataFrame,
    column_config: dict = None,
    height: int = 400,
    use_container_width: bool = True,
    hide_index: bool = True,
    selection_mode: str = None,
    key: str = None
) -> Optional[pd.DataFrame]:
    """
    Render a DataFrame with Streamlit's data_editor.
    
    Args:
        df: DataFrame to display
        column_config: Column configuration dictionary
        height: Table height in pixels
        use_container_width: If True, use full width
        hide_index: If True, hide the index column
        selection_mode: None, 'single-row', or 'multi-row'
        key: Unique key for the component
        
    Returns:
        Selected rows if selection_mode is set, else None
    """
    if df.empty:
        st.info("No hay datos para mostrar")
        return None
    
    # Default column config
    if column_config is None:
        column_config = {}
    
    # Auto-configure date columns
    for col in df.columns:
        if 'Date' in col or 'date' in col:
            if col not in column_config:
                column_config[col] = st.column_config.DatetimeColumn(
                    col,
                    format="DD/MM/YYYY HH:mm"
                )
    
    if selection_mode:
        return st.dataframe(
            df,
            column_config=column_config,
            height=height,
            use_container_width=use_container_width,
            hide_index=hide_index,
            key=key,
            on_select="rerun",
            selection_mode=selection_mode
        )
    else:
        st.dataframe(
            df,
            column_config=column_config,
            height=height,
            use_container_width=use_container_width,
            hide_index=hide_index,
            key=key
        )
        return None


class DataTable:
    """
    Advanced data table component with sorting, filtering, and pagination.
    """
    
    def __init__(
        self,
        df: pd.DataFrame,
        page_size: int = 50,
        sortable: bool = True,
        filterable: bool = True
    ):
        """
        Initialize the data table.
        
        Args:
            df: DataFrame to display
            page_size: Rows per page
            sortable: Enable column sorting
            filterable: Enable column filtering
        """
        self.original_df = df
        self.df = df.copy()
        self.page_size = page_size
        self.sortable = sortable
        self.filterable = filterable
        self.current_page = 0
        self.sort_column = None
        self.sort_ascending = True
        self.filters = {}
    
    def apply_sort(self, column: str, ascending: bool = True):
        """Apply sorting to the table."""
        self.sort_column = column
        self.sort_ascending = ascending
        self.df = self.df.sort_values(column, ascending=ascending)
    
    def apply_filter(self, column: str, values: list):
        """Apply a filter to a column."""
        if values:
            self.filters[column] = values
        elif column in self.filters:
            del self.filters[column]
        
        # Rebuild filtered DataFrame
        self.df = self.original_df.copy()
        for col, vals in self.filters.items():
            self.df = self.df[self.df[col].isin(vals)]
        
        # Reapply sort
        if self.sort_column:
            self.df = self.df.sort_values(self.sort_column, ascending=self.sort_ascending)
    
    def clear_filters(self):
        """Clear all filters."""
        self.filters = {}
        self.df = self.original_df.copy()
        if self.sort_column:
            self.df = self.df.sort_values(self.sort_column, ascending=self.sort_ascending)
    
    def get_page(self, page: int) -> pd.DataFrame:
        """Get a specific page of data."""
        start = page * self.page_size
        end = start + self.page_size
        return self.df.iloc[start:end]
    
    @property
    def total_pages(self) -> int:
        """Get total number of pages."""
        return max(1, (len(self.df) + self.page_size - 1) // self.page_size)
    
    @property
    def total_records(self) -> int:
        """Get total records after filtering."""
        return len(self.df)
    
    def render(self, key_prefix: str = "table") -> Optional[list]:
        """
        Render the complete table with controls.
        
        Args:
            key_prefix: Prefix for component keys
            
        Returns:
            List of selected row indices if selection enabled
        """
        if self.df.empty:
            st.info("No hay datos para mostrar")
            return None
        
        # Info bar
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            st.caption(
                f"Mostrando {len(self.df)} de {len(self.original_df)} registros"
                + (f" (filtros activos: {len(self.filters)})" if self.filters else "")
            )
        with col2:
            if self.filters:
                if st.button("🗑️ Limpiar filtros", key=f"{key_prefix}_clear"):
                    self.clear_filters()
                    st.rerun()
        
        # Pagination controls
        if self.total_pages > 1:
            with col3:
                col_prev, col_page, col_next = st.columns([1, 2, 1])
                with col_prev:
                    if st.button("◀", key=f"{key_prefix}_prev", disabled=self.current_page == 0):
                        self.current_page -= 1
                        st.rerun()
                with col_page:
                    st.caption(f"Página {self.current_page + 1} de {self.total_pages}")
                with col_next:
                    if st.button("▶", key=f"{key_prefix}_next", disabled=self.current_page >= self.total_pages - 1):
                        self.current_page += 1
                        st.rerun()
        
        # Display table
        page_df = self.get_page(self.current_page)
        st.dataframe(
            page_df,
            use_container_width=True,
            hide_index=True
        )
        
        return None
    
    def to_csv(self) -> str:
        """Export current data (with filters applied) to CSV."""
        return self.df.to_csv(index=False, encoding='utf-8-sig')
    
    def to_excel(self) -> bytes:
        """Export current data to Excel."""
        from io import BytesIO
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            self.df.to_excel(writer, index=False, sheet_name='Datos')
        return output.getvalue()
