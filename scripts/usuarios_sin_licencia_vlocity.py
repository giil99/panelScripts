"""
Script: Usuarios sin Licencia Vlocity

Detecta usuarios que deberían tener licencia Vlocity pero no la tienen asignada.
Esto puede causar problemas de acceso a funcionalidades CPQ.
"""
import pandas as pd
from core.base_script import BaseScript, ScriptResult, ScriptMetrics, ColumnConfig, ColumnType
from core.script_registry import register_script


@register_script
class UsuariosSinLicenciaVlocity(BaseScript):
    """
    Detecta usuarios sin licencia Vlocity.
    """
    
    name = "Usuarios sin Licencia Vlocity"
    description = "Detecta usuarios activos que necesitan licencia Vlocity"
    category = "Extracción de datos"
    version = "2.0"
    author = "AG"
    
    supports_preview = True
    supports_update = False
    requires_confirmation = False
    
    def get_queries(self, preview: bool = False) -> list[str]:
        """Return queries for users and license assignments."""
        limit_clause = "LIMIT 500" if preview else ""
        
        # Query 1: Active users with certain profiles
        query_users = f"""
            SELECT Id, Name, Username, Email, Profile.Name, IsActive, 
                   LastLoginDate, CreatedDate
            FROM User
            WHERE IsActive = true
            AND Profile.Name LIKE '%Naturgy%'
            {limit_clause}
        """
        
        # Query 2: Vlocity license assignments
        query_licenses = """
            SELECT Id, UserId, LicenseDefinitionKey
            FROM UserPackageLicense
            WHERE LicenseDefinitionKey LIKE '%vlocity%'
        """
        
        return [query_users, query_licenses]
    
    def process(self, query_results: dict[str, pd.DataFrame]) -> ScriptResult:
        """Process users and license assignments."""
        df_users = query_results.get('query_0', pd.DataFrame())
        df_licenses = query_results.get('query_1', pd.DataFrame())
        
        if df_users.empty:
            return ScriptResult(
                success=True,
                data=pd.DataFrame(),
                metrics=ScriptMetrics(total_records=0)
            )
        
        self.store_intermediate('users_raw', df_users)
        self.store_intermediate('licenses_raw', df_licenses)
        
        # Get users with Vlocity license
        users_with_license = set()
        if not df_licenses.empty:
            users_with_license = set(df_licenses['UserId'].dropna())
        
        # Find users without license
        df_users['HasVlocityLicense'] = df_users['Id'].isin(users_with_license)
        users_without = df_users[~df_users['HasVlocityLicense']].copy()
        
        # Calculate metrics
        metrics = ScriptMetrics(total_records=len(users_without))
        
        metrics.add_metric(
            'total_users_checked',
            len(df_users),
            'Usuarios Verificados',
            '📊'
        )
        
        metrics.add_metric(
            'users_with_license',
            len(df_users[df_users['HasVlocityLicense']]),
            'Con Licencia',
            '✅'
        )
        
        metrics.add_metric(
            'users_without_license',
            len(users_without),
            'Sin Licencia',
            '🔴' if len(users_without) > 0 else '✅'
        )
        
        # Count by profile
        if not users_without.empty and 'Profile.Name' in users_without.columns:
            profile_counts = users_without['Profile.Name'].value_counts()
            for profile, count in profile_counts.head(5).items():
                if profile:
                    metrics.add_metric(
                        f'profile_{profile[:15]}',
                        count,
                        f'{profile[:20]}',
                        '📋'
                    )
        
        return ScriptResult(
            success=True,
            data=users_without,
            metrics=metrics
        )
    
    def get_column_config(self) -> list[ColumnConfig]:
        """Define column configuration."""
        return [
            ColumnConfig('Name', 'Nombre', ColumnType.TEXT),
            ColumnConfig('Username', 'Usuario', ColumnType.TEXT),
            ColumnConfig('Email', 'Email', ColumnType.TEXT),
            ColumnConfig('Profile.Name', 'Perfil', ColumnType.TEXT),
            ColumnConfig('LastLoginDate', 'Último Login', ColumnType.DATETIME),
            ColumnConfig('CreatedDate', 'Creado', ColumnType.DATETIME),
        ]
    
    def get_groupby_options(self) -> list[str]:
        """Return columns for grouping."""
        return ['Profile.Name']
    
    def detect_anomalies(self, data: pd.DataFrame) -> pd.DataFrame:
        """Users without license are anomalies."""
        if data.empty:
            return pd.DataFrame()
        
        anomalies = data.copy()
        anomalies['anomaly_type'] = 'Usuario sin Licencia Vlocity'
        anomalies['anomaly_severity'] = 'Baja'
        
        return anomalies
    
    def get_chart_recommendations(self) -> list[dict]:
        """Recommend charts."""
        return [
            {
                'type': 'pie',
                'names': 'Profile.Name',
                'title': 'Sin Licencia por Perfil'
            }
        ]
