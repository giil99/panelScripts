"""
Script: Contact Mobile Number Bad

Detecta contactos con números de móvil en formato incorrecto
que pueden causar problemas en comunicaciones y facturación.
"""
import pandas as pd
import re
from core.base_script import BaseScript, ScriptResult, ScriptMetrics, ColumnConfig, ColumnType
from core.script_registry import register_script


@register_script
class ContactMobileNumberBad(BaseScript):
    """
    Detecta contactos con números de móvil incorrectos.
    """
    
    name = "Contactos - Móvil Incorrecto"
    description = "Detecta contactos con formato de móvil inválido"
    category = "Detección de inconsistencias"
    version = "1.0"
    author = "AG"
    
    supports_preview = True
    supports_update = True
    requires_confirmation = True
    
    # Spanish mobile pattern: 6XX XXX XXX or 7XX XXX XXX (9 digits starting with 6 or 7)
    MOBILE_PATTERN = r'^[67]\d{8}$'
    
    def get_queries(self, preview: bool = False) -> list[str]:
        """Return query for contacts with mobile numbers."""
        limit_clause = "LIMIT 2000" if preview else ""
        
        query = f"""
            SELECT Id, Name, Email, MobilePhone, Phone,
                   AccountId, Account.Name, CreatedDate
            FROM Contact
            WHERE MobilePhone != null
            {limit_clause}
        """
        
        return [query]
    
    def process(self, query_results: dict[str, pd.DataFrame]) -> ScriptResult:
        """Process contacts to find invalid mobile numbers."""
        df = query_results.get('query_0', pd.DataFrame())
        
        if df.empty:
            return ScriptResult(
                success=True,
                data=pd.DataFrame(),
                metrics=ScriptMetrics(total_records=0)
            )
        
        self.store_intermediate('contacts_raw', df)
        
        # Clean and validate mobile numbers
        def clean_phone(phone):
            if pd.isna(phone):
                return ''
            # Remove spaces, dashes, dots, and country code
            cleaned = re.sub(r'[\s\-\.]', '', str(phone))
            # Remove +34 or 0034
            cleaned = re.sub(r'^(\+34|0034)', '', cleaned)
            return cleaned
        
        def is_valid_mobile(phone):
            cleaned = clean_phone(phone)
            return bool(re.match(self.MOBILE_PATTERN, cleaned))
        
        # Find invalid mobiles
        df['CleanedMobile'] = df['MobilePhone'].apply(clean_phone)
        df['IsValid'] = df['MobilePhone'].apply(is_valid_mobile)
        
        invalid_df = df[~df['IsValid']].copy()
        
        # Categorize issues
        def categorize_issue(phone):
            cleaned = clean_phone(phone)
            if not cleaned:
                return 'Vacío después de limpiar'
            if len(cleaned) < 9:
                return 'Muy corto'
            if len(cleaned) > 9:
                return 'Muy largo'
            if not cleaned[0] in ['6', '7']:
                return 'No empieza por 6 o 7'
            if not cleaned.isdigit():
                return 'Contiene caracteres no numéricos'
            return 'Formato inválido'
        
        if not invalid_df.empty:
            invalid_df['Issue'] = invalid_df['MobilePhone'].apply(categorize_issue)
        
        # Calculate metrics
        metrics = ScriptMetrics(total_records=len(invalid_df))
        
        metrics.add_metric(
            'invalid_mobiles',
            len(invalid_df),
            'Móviles Inválidos',
            '🔴' if len(invalid_df) > 0 else '✅'
        )
        
        metrics.add_metric(
            'total_checked',
            len(df),
            'Contactos Verificados',
            '📊'
        )
        
        if len(df) > 0:
            valid_rate = ((len(df) - len(invalid_df)) / len(df)) * 100
            metrics.add_metric(
                'valid_rate',
                round(valid_rate, 1),
                '% Válidos',
                '📈'
            )
        
        # Count by issue type
        if not invalid_df.empty:
            issue_counts = invalid_df['Issue'].value_counts()
            for issue, count in issue_counts.items():
                metrics.add_metric(
                    f'issue_{issue[:10]}',
                    count,
                    issue[:20],
                    '⚠️'
                )
        
        return ScriptResult(
            success=True,
            data=invalid_df,
            metrics=metrics
        )
    
    def get_column_config(self) -> list[ColumnConfig]:
        """Define column configuration."""
        return [
            ColumnConfig('Name', 'Nombre', ColumnType.TEXT),
            ColumnConfig('MobilePhone', 'Móvil Original', ColumnType.TEXT),
            ColumnConfig('CleanedMobile', 'Móvil Limpio', ColumnType.TEXT),
            ColumnConfig('Issue', 'Problema', ColumnType.TEXT),
            ColumnConfig('Account.Name', 'Cuenta', ColumnType.TEXT),
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
