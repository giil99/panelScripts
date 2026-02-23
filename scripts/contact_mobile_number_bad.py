"""
Script: Contact Mobile Number Bad (COMPLETO)

PRESERVA 100% DE LA LÓGICA DEL NOTEBOOK ContactMobileNumberBad.ipynb

Detecta contactos con números de móvil que NO tienen exactamente 12 caracteres.
"""
import pandas as pd
from core.base_script import BaseScript, ScriptResult, ScriptMetrics, ColumnConfig, ColumnType
from core.script_registry import register_script


@register_script
class ContactMobileNumberBad(BaseScript):
    """
    Detecta contactos con números de móvil incorrectos.
    Preserva 100% de la lógica del notebook: len(mobile) != 12 caracteres.
    """
    
    name = "Contactos - Móvil Incorrecto"
    description = "Detecta contactos con móvil ≠ 12 caracteres (lógica notebook)"
    category = "Detección de inconsistencias"
    version = "2.0"
    author = "AG"
    
    supports_preview = True
    supports_update = True
    requires_confirmation = True
    
    # LÓGICA DEL NOTEBOOK: Exactamente 12 caracteres
    EXPECTED_LENGTH = 12
    
    def get_queries(self, preview: bool = False) -> list[str]:
        """Return query for contacts with mobile numbers (QUERY DEL NOTEBOOK)."""
        limit_clause = "LIMIT 2000" if preview else ""
        
        # QUERY EXACTA DEL NOTEBOOK
        query = f"""
            SELECT Id, Name, MobilePhone, AccountId, Account.Name,
                   Email, Phone, CreatedDate
            FROM Contact
            WHERE MobilePhone != null
            {limit_clause}
        """
        
        return [query]
    
    def process(self, query_results: dict[str, pd.DataFrame]) -> ScriptResult:
        """Process contacts to find invalid mobile numbers (LÓGICA DEL NOTEBOOK)."""
        df = query_results.get('query_0', pd.DataFrame())
        
        if df.empty:
            return ScriptResult(
                success=True,
                data=pd.DataFrame(),
                metrics=ScriptMetrics(total_records=0)
            )
        
        self.store_intermediate('contacts_raw', df)
        
        # LÓGICA EXACTA DEL NOTEBOOK: len(mobile) != 12
        def is_valid_mobile(mobile):
            if pd.isna(mobile) or mobile is None:
                return False
            return len(str(mobile)) == self.EXPECTED_LENGTH
        
        # Filtrar contactos con móvil incorrecto
        df['MobileLength'] = df['MobilePhone'].apply(lambda x: len(str(x)) if x and not pd.isna(x) else 0)
        df['IsValid'] = df['MobilePhone'].apply(is_valid_mobile)
        
        # NOTEBOOK: Solo contactos con len != 12
        incorrect_df = df[~df['IsValid']].copy()
        
        # Categorizar problemas por longitud
        def categorize_length_issue(length):
            if length == 0:
                return 'Vacío o nulo'
            elif length < self.EXPECTED_LENGTH:
                return f'Muy corto ({length} < {self.EXPECTED_LENGTH})'
            else:
                return f'Muy largo ({length} > {self.EXPECTED_LENGTH})'
        
        if not incorrect_df.empty:
            incorrect_df['Issue'] = incorrect_df['MobileLength'].apply(categorize_length_issue)
        
        # Calculate metrics
        metrics = ScriptMetrics(
            total_records=len(incorrect_df),
            message=f"Analizados: {len(df)}, Incorrectos: {len(incorrect_df)}, Correctos: {len(df) - len(incorrect_df)}"
        )
        
        metrics.add_metric(
            'incorrect_mobiles',
            len(incorrect_df),
            f'≠ {self.EXPECTED_LENGTH} caracteres',
            '🔴' if len(incorrect_df) > 0 else '✅'
        )
        
        metrics.add_metric(
            'total_checked',
            len(df),
            'Contactos Verificados',
            '📊'
        )
        
        if len(df) > 0:
            valid_rate = ((len(df) - len(incorrect_df)) / len(df)) * 100
            metrics.add_metric(
                'valid_rate',
                round(valid_rate, 1),
                '% Válidos',
                '📈'
            )
        
        # Count by issue type (longitud)
        if not incorrect_df.empty:
            issue_counts = incorrect_df['Issue'].value_counts()
            for issue, count in issue_counts.items():
                metrics.add_metric(
                    f'issue_{issue[:10]}',
                    count,
                    issue[:30],
                    '⚠️'
                )
        
        return ScriptResult(
            success=True,
            data=incorrect_df,
            metrics=metrics
        )
    
    def get_column_config(self) -> list[ColumnConfig]:
        """Define column configuration."""
        return [
            ColumnConfig('Name', 'Nombre', ColumnType.TEXT),
            ColumnConfig('MobilePhone', 'Móvil Original', ColumnType.TEXT),
            ColumnConfig('MobileLength', 'Longitud', ColumnType.NUMBER),
            ColumnConfig('Issue', 'Problema', ColumnType.TEXT),
            ColumnConfig('Account.Name', 'Cuenta', ColumnType.TEXT),
            ColumnConfig('AccountId', 'Account ID', ColumnType.LINK),
            ColumnConfig('Email', 'Email', ColumnType.TEXT),
        ]
    
    def get_groupby_options(self) -> list[str]:
        """Return columns for grouping."""
        return ['Issue']
    
    def detect_anomalies(self, data: pd.DataFrame) -> pd.DataFrame:
        """All invalid mobiles are anomalies."""
        if data.empty:
            return pd.DataFrame()
        
        anomalies = data.copy()
        anomalies['anomaly_type'] = 'Móvil Formato Incorrecto'
        anomalies['anomaly_severity'] = 'Media'
        
        return anomalies
    
    def get_chart_recommendations(self) -> list[dict]:
        """Recommend charts."""
        return [
            {
                'type': 'pie',
                'names': 'Issue',
                'title': 'Distribución por Tipo de Error'
            }
        ]
