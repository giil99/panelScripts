"""
KPIs - Key Performance Indicators panel.
"""
import streamlit as st
import pandas as pd
from typing import Union, Optional
from dataclasses import dataclass


@dataclass
class KPI:
    """Definition of a KPI to display."""
    label: str
    value: Union[int, float, str]
    icon: str = "📊"
    delta: Optional[Union[int, float]] = None
    delta_color: str = "normal"  # "normal", "inverse", "off"
    help_text: Optional[str] = None
    format_str: str = None  # e.g., "{:,.0f}", "{:.2%}"


def render_kpis(
    kpis: list[KPI],
    columns: int = 4,
    key_prefix: str = "kpi"
):
    """
    Render a panel of KPIs using Streamlit metrics.
    
    Args:
        kpis: List of KPI objects
        columns: Number of columns
        key_prefix: Prefix for component keys
    """
    if not kpis:
        return
    
    # Create columns
    cols = st.columns(columns)
    
    for idx, kpi in enumerate(kpis):
        col_idx = idx % columns
        
        with cols[col_idx]:
            # Format value if format string provided
            if kpi.format_str and isinstance(kpi.value, (int, float)):
                display_value = kpi.format_str.format(kpi.value)
            else:
                display_value = str(kpi.value)
            
            # Format delta if present
            delta_str = None
            if kpi.delta is not None:
                if kpi.format_str and isinstance(kpi.delta, (int, float)):
                    delta_str = kpi.format_str.format(kpi.delta)
                else:
                    delta_str = str(kpi.delta)
            
            # Using the `help` attribute on st.metric natively provides a tooltip on hover.
            st.metric(
                label=f"{kpi.icon} {kpi.label}",
                value=display_value,
                delta=delta_str,
                delta_color=kpi.delta_color,
                help=kpi.help_text or kpi.label
            )


class KPIPanel:
    """
    Panel for displaying KPIs with automatic calculation from DataFrame.
    """
    
    def __init__(self, df: pd.DataFrame = None):
        """
        Initialize KPI panel.
        
        Args:
            df: Optional DataFrame for automatic KPI calculation
        """
        self.df = df
        self.kpis: list[KPI] = []
    
    def add(
        self,
        label: str,
        value: Union[int, float, str],
        icon: str = "📊",
        delta: Optional[Union[int, float]] = None,
        delta_color: str = "normal",
        help_text: Optional[str] = None,
        format_str: str = None
    ) -> 'KPIPanel':
        """Add a KPI to the panel."""
        self.kpis.append(KPI(
            label=label,
            value=value,
            icon=icon,
            delta=delta,
            delta_color=delta_color,
            help_text=help_text,
            format_str=format_str
        ))
        return self
    
    def add_count(
        self,
        label: str = "Total Registros",
        icon: str = "📋"
    ) -> 'KPIPanel':
        """Add total record count KPI."""
        if self.df is None:
            return self
        
        self.add(
            label=label,
            value=len(self.df),
            icon=icon,
            format_str="{:,.0f}"
        )
        return self
    
    def add_unique_count(
        self,
        column: str,
        label: str = None,
        icon: str = "🔢"
    ) -> 'KPIPanel':
        """Add unique value count KPI for a column."""
        if self.df is None or column not in self.df.columns:
            return self
        
        self.add(
            label=label or f"Únicos ({column})",
            value=self.df[column].nunique(),
            icon=icon,
            format_str="{:,.0f}"
        )
        return self
    
    def add_sum(
        self,
        column: str,
        label: str = None,
        icon: str = "➕"
    ) -> 'KPIPanel':
        """Add sum KPI for a numeric column."""
        if self.df is None or column not in self.df.columns:
            return self
        
        self.add(
            label=label or f"Suma ({column})",
            value=self.df[column].sum(),
            icon=icon,
            format_str="{:,.2f}"
        )
        return self
    
    def add_average(
        self,
        column: str,
        label: str = None,
        icon: str = "📈"
    ) -> 'KPIPanel':
        """Add average KPI for a numeric column."""
        if self.df is None or column not in self.df.columns:
            return self
        
        self.add(
            label=label or f"Media ({column})",
            value=self.df[column].mean(),
            icon=icon,
            format_str="{:,.2f}"
        )
        return self
    
    def add_percentage(
        self,
        column: str,
        value: str,
        label: str = None,
        icon: str = "📊"
    ) -> 'KPIPanel':
        """Add percentage KPI for a value in a column."""
        if self.df is None or column not in self.df.columns:
            return self
        
        total = len(self.df)
        if total == 0:
            pct = 0
        else:
            count = len(self.df[self.df[column] == value])
            pct = count / total
        
        self.add(
            label=label or f"% {value}",
            value=pct,
            icon=icon,
            format_str="{:.1%}"
        )
        return self
    
    def add_top_value(
        self,
        column: str,
        label: str = None,
        icon: str = "🏆"
    ) -> 'KPIPanel':
        """Add most common value KPI for a column."""
        if self.df is None or column not in self.df.columns:
            return self
        
        if self.df[column].empty:
            return self
        
        top_value = self.df[column].mode()
        if len(top_value) > 0:
            self.add(
                label=label or f"Top ({column})",
                value=str(top_value.iloc[0]),
                icon=icon
            )
        return self
    
    def add_from_metrics(
        self,
        metrics: dict,
        icon_map: dict = None
    ) -> 'KPIPanel':
        """
        Add KPIs from a metrics dictionary.
        
        Args:
            metrics: Dictionary with metric key -> {value, label, icon}
            icon_map: Optional mapping of keys to icons
        """
        icon_map = icon_map or {}
        
        for key, metric in metrics.items():
            if isinstance(metric, dict):
                self.add(
                    label=metric.get('label', key),
                    value=metric.get('value', 0),
                    icon=metric.get('icon', icon_map.get(key, '📊'))
                )
            else:
                self.add(
                    label=key,
                    value=metric,
                    icon=icon_map.get(key, '📊')
                )
        return self
    
    def render(self, columns: int = 4):
        """Render the KPI panel."""
        render_kpis(self.kpis, columns=columns)
    
    def clear(self) -> 'KPIPanel':
        """Clear all KPIs."""
        self.kpis = []
        return self
