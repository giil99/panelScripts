"""
Charts - Interactive chart components using Plotly.
"""
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from typing import Optional, Union
from config import CHART_THEME, CHART_COLORS


def create_bar_chart(
    df: pd.DataFrame,
    x: str,
    y: str = None,
    color: str = None,
    title: str = "Gráfico de Barras",
    orientation: str = "v",
    show_values: bool = True,
    height: int = 400
) -> go.Figure:
    """
    Create a bar chart.
    
    Args:
        df: DataFrame with data
        x: Column for x-axis (or categories)
        y: Column for y-axis (if None, counts x values)
        color: Column for color grouping
        title: Chart title
        orientation: 'v' for vertical, 'h' for horizontal
        show_values: Show values on bars
        height: Chart height
        
    Returns:
        Plotly Figure
    """
    if y is None:
        # Count occurrences
        chart_df = df[x].value_counts().reset_index()
        chart_df.columns = [x, 'count']
        y = 'count'
    else:
        chart_df = df
    
    fig = px.bar(
        chart_df,
        x=x if orientation == 'v' else y,
        y=y if orientation == 'v' else x,
        color=color,
        title=title,
        orientation=orientation,
        color_discrete_sequence=CHART_COLORS,
        template=CHART_THEME,
        text=y if show_values else None
    )
    
    fig.update_layout(height=height)
    if show_values:
        fig.update_traces(textposition='outside')
    
    return fig


def create_pie_chart(
    df: pd.DataFrame,
    names: str,
    values: str = None,
    title: str = "Distribución",
    hole: float = 0.3,
    height: int = 400
) -> go.Figure:
    """
    Create a pie/donut chart.
    
    Args:
        df: DataFrame with data
        names: Column with category names
        values: Column with values (if None, counts names)
        title: Chart title
        hole: Size of center hole (0 for pie, >0 for donut)
        height: Chart height
        
    Returns:
        Plotly Figure
    """
    if values is None:
        chart_df = df[names].value_counts().reset_index()
        chart_df.columns = [names, 'count']
        values = 'count'
    else:
        chart_df = df
    
    fig = px.pie(
        chart_df,
        names=names,
        values=values,
        title=title,
        hole=hole,
        color_discrete_sequence=CHART_COLORS,
        template=CHART_THEME
    )
    
    fig.update_layout(height=height)
    fig.update_traces(textposition='inside', textinfo='percent+label')
    
    return fig


def create_line_chart(
    df: pd.DataFrame,
    x: str,
    y: str,
    color: str = None,
    title: str = "Evolución Temporal",
    markers: bool = True,
    height: int = 400
) -> go.Figure:
    """
    Create a line chart.
    
    Args:
        df: DataFrame with data
        x: Column for x-axis (usually date)
        y: Column for y-axis
        color: Column for grouping lines
        title: Chart title
        markers: Show markers on data points
        height: Chart height
        
    Returns:
        Plotly Figure
    """
    fig = px.line(
        df,
        x=x,
        y=y,
        color=color,
        title=title,
        markers=markers,
        color_discrete_sequence=CHART_COLORS,
        template=CHART_THEME
    )
    
    fig.update_layout(height=height)
    
    return fig


def create_distribution_chart(
    df: pd.DataFrame,
    column: str,
    title: str = "Distribución",
    nbins: int = 30,
    height: int = 400
) -> go.Figure:
    """
    Create a histogram for distribution analysis.
    
    Args:
        df: DataFrame with data
        column: Column to analyze
        title: Chart title
        nbins: Number of bins
        height: Chart height
        
    Returns:
        Plotly Figure
    """
    fig = px.histogram(
        df,
        x=column,
        title=title,
        nbins=nbins,
        color_discrete_sequence=CHART_COLORS,
        template=CHART_THEME
    )
    
    fig.update_layout(
        height=height,
        bargap=0.1
    )
    
    return fig


def create_timeline_chart(
    df: pd.DataFrame,
    date_column: str,
    value_column: str = None,
    group_by: str = 'day',
    title: str = "Evolución Temporal",
    height: int = 400
) -> go.Figure:
    """
    Create a timeline chart aggregating by date.
    
    Args:
        df: DataFrame with data
        date_column: Column with dates
        value_column: Column to aggregate (if None, counts records)
        group_by: 'day', 'week', 'month', 'year'
        title: Chart title
        height: Chart height
        
    Returns:
        Plotly Figure
    """
    # Ensure date column is datetime
    df = df.copy()
    df[date_column] = pd.to_datetime(df[date_column])
    
    # Group by time period
    if group_by == 'day':
        df['period'] = df[date_column].dt.date
    elif group_by == 'week':
        df['period'] = df[date_column].dt.to_period('W').astype(str)
    elif group_by == 'month':
        df['period'] = df[date_column].dt.to_period('M').astype(str)
    elif group_by == 'year':
        df['period'] = df[date_column].dt.to_period('Y').astype(str)
    else:
        df['period'] = df[date_column].dt.date
    
    if value_column:
        chart_df = df.groupby('period')[value_column].sum().reset_index()
    else:
        chart_df = df.groupby('period').size().reset_index(name='count')
        value_column = 'count'
    
    fig = px.line(
        chart_df,
        x='period',
        y=value_column,
        title=title,
        markers=True,
        color_discrete_sequence=CHART_COLORS,
        template=CHART_THEME
    )
    
    fig.update_layout(
        height=height,
        xaxis_title="Período",
        yaxis_title=value_column
    )
    
    return fig


def create_grouped_bar_chart(
    df: pd.DataFrame,
    x: str,
    y: str,
    color: str,
    title: str = "Comparativa por Grupos",
    barmode: str = "group",
    height: int = 400
) -> go.Figure:
    """
    Create a grouped bar chart.
    
    Args:
        df: DataFrame (should be pre-aggregated)
        x: Column for x-axis
        y: Column for y-axis
        color: Column for grouping
        title: Chart title
        barmode: 'group' or 'stack'
        height: Chart height
        
    Returns:
        Plotly Figure
    """
    fig = px.bar(
        df,
        x=x,
        y=y,
        color=color,
        title=title,
        barmode=barmode,
        color_discrete_sequence=CHART_COLORS,
        template=CHART_THEME
    )
    
    fig.update_layout(height=height)
    
    return fig


class ChartBuilder:
    """
    Builder class for creating charts with a fluent interface.
    """
    
    def __init__(self, df: pd.DataFrame):
        """Initialize with a DataFrame."""
        self.df = df
        self._chart_type = 'bar'
        self._x = None
        self._y = None
        self._color = None
        self._title = "Gráfico"
        self._height = 400
        self._options = {}
    
    def bar(self) -> 'ChartBuilder':
        """Set chart type to bar."""
        self._chart_type = 'bar'
        return self
    
    def pie(self) -> 'ChartBuilder':
        """Set chart type to pie."""
        self._chart_type = 'pie'
        return self
    
    def line(self) -> 'ChartBuilder':
        """Set chart type to line."""
        self._chart_type = 'line'
        return self
    
    def histogram(self) -> 'ChartBuilder':
        """Set chart type to histogram."""
        self._chart_type = 'histogram'
        return self
    
    def x(self, column: str) -> 'ChartBuilder':
        """Set x-axis column."""
        self._x = column
        return self
    
    def y(self, column: str) -> 'ChartBuilder':
        """Set y-axis column."""
        self._y = column
        return self
    
    def color(self, column: str) -> 'ChartBuilder':
        """Set color grouping column."""
        self._color = column
        return self
    
    def title(self, title: str) -> 'ChartBuilder':
        """Set chart title."""
        self._title = title
        return self
    
    def height(self, height: int) -> 'ChartBuilder':
        """Set chart height."""
        self._height = height
        return self
    
    def options(self, **kwargs) -> 'ChartBuilder':
        """Set additional options."""
        self._options.update(kwargs)
        return self
    
    def build(self) -> go.Figure:
        """Build and return the chart."""
        if self._chart_type == 'bar':
            return create_bar_chart(
                self.df,
                x=self._x,
                y=self._y,
                color=self._color,
                title=self._title,
                height=self._height,
                **self._options
            )
        elif self._chart_type == 'pie':
            return create_pie_chart(
                self.df,
                names=self._x,
                values=self._y,
                title=self._title,
                height=self._height,
                **self._options
            )
        elif self._chart_type == 'line':
            return create_line_chart(
                self.df,
                x=self._x,
                y=self._y,
                color=self._color,
                title=self._title,
                height=self._height,
                **self._options
            )
        elif self._chart_type == 'histogram':
            return create_distribution_chart(
                self.df,
                column=self._x,
                title=self._title,
                height=self._height,
                **self._options
            )
        else:
            raise ValueError(f"Unknown chart type: {self._chart_type}")
