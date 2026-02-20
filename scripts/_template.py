"""
Template para crear nuevos scripts.

Copia este archivo y personalízalo según tu caso de uso.
Asegúrate de:
1. Usar el decorador @register_script
2. Definir name, description y category
3. Implementar get_queries() y process()
"""
import pandas as pd
from core.base_script import BaseScript, ScriptResult, ScriptMetrics, ColumnConfig, ColumnType
from core.script_registry import register_script


# Descomenta @register_script cuando el script esté listo
# @register_script
class ScriptTemplate(BaseScript):
    """
    Descripción detallada del script.
    
    ¿Qué hace este script?
    - Punto 1
    - Punto 2
    
    ¿Cuándo usarlo?
    - Caso de uso 1
    - Caso de uso 2
    """
    
    # ============== METADATA ==============
    # Estos atributos definen cómo se muestra el script en la UI
    
    name = "Nombre del Script"  # Nombre corto y descriptivo
    description = "Descripción breve de una línea"
    category = "Regularización"  # Categoría para agrupar scripts
    version = "1.0"
    author = "Tu nombre"
    
    # ============== OPCIONES ==============
    
    supports_preview = True      # Compatibilidad - ya no usado en UI
    supports_update = False      # ¿Puede hacer actualizaciones en SF?
    requires_confirmation = True # ¿Requiere confirmar antes de updates?
    
    # ============== CONSTANTES ==============
    # Define aquí códigos de estado, tipos, etc.
    
    EXAMPLE_STATUS = "02"
    
    # ============== MÉTODOS REQUERIDOS ==============
    
    def get_queries(self, preview: bool = False) -> list[str]:
        """
        Retorna las consultas SOQL necesarias.
        
        Args:
            preview: Parámetro legacy (siempre False en la UI actual)
            
        Returns:
            Lista de strings con las consultas SOQL
        """
        # Ya no aplicamos LIMIT - ejecutamos consultas completas
        
        # Query principal
        query1 = f"""
            SELECT Id, Name, Status, CreatedDate
            FROM Contract
            WHERE Status = '{self.EXAMPLE_STATUS}'
        """
        
        # Queries adicionales si necesitas datos relacionados
        # query2 = "SELECT Id, Name FROM Asset ..."
        
        return [query1]
    
    def process(self, query_results: dict[str, pd.DataFrame]) -> ScriptResult:
        """
        Procesa los resultados de las queries.
        
        Args:
            query_results: Diccionario con key 'query_0', 'query_1', etc.
                          y valores DataFrame con los resultados
                          
        Returns:
            ScriptResult con los datos procesados y métricas
        """
        # Obtener datos de las queries
        df = query_results.get('query_0', pd.DataFrame())
        
        # Caso: No hay datos
        if df.empty:
            return ScriptResult(
                success=True,
                data=pd.DataFrame(),
                metrics=ScriptMetrics(total_records=0)
            )
        
        # Guardar datos intermedios (para debugging)
        self.store_intermediate('raw_data', df)
        
        # ============== TU LÓGICA AQUÍ ==============
        
        # Ejemplo: filtrar, transformar, etc.
        df_processed = df.copy()
        
        # Añadir columnas calculadas
        # df_processed['NuevaColumna'] = df_processed['OtraColumna'].apply(...)
        
        # Detectar anomalías
        # df_anomalies = df_processed[df_processed['Status'] == 'X']
        
        # ============== MÉTRICAS ==============
        
        metrics = ScriptMetrics(
            total_records=len(df_processed),
            processed_records=len(df)
        )
        
        # Añadir métricas personalizadas
        metrics.add_metric(
            key='example_metric',
            value=len(df_processed),
            label='Registros Procesados',
            icon='📊'
        )
        
        # Añadir warnings si es necesario
        # self.add_warning("Mensaje de advertencia")
        
        return ScriptResult(
            success=True,
            data=df_processed,
            metrics=metrics
        )
    
    # ============== MÉTODOS OPCIONALES ==============
    
    def get_column_config(self) -> list[ColumnConfig]:
        """
        Define la configuración de columnas para la tabla.
        Omitir para auto-detección.
        """
        return [
            ColumnConfig('Name', 'Nombre', ColumnType.TEXT),
            ColumnConfig('Status', 'Estado', ColumnType.STATUS),
            ColumnConfig('CreatedDate', 'Fecha Creación', ColumnType.DATETIME),
        ]
    
    def get_groupby_options(self) -> list[str]:
        """Define columnas disponibles para agrupar en análisis."""
        return ['Status']
    
    def detect_anomalies(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Detecta anomalías en los datos.
        
        Returns:
            DataFrame con registros anómalos (añadir columnas anomaly_type, anomaly_severity)
        """
        # Ejemplo: detectar registros con cierta condición
        # anomalies = data[data['Status'] == 'X'].copy()
        # anomalies['anomaly_type'] = 'Descripción de la anomalía'
        # anomalies['anomaly_severity'] = 'Alta'  # Alta, Media, Baja
        # return anomalies
        
        return pd.DataFrame()  # Sin anomalías por defecto
    
    def get_update_operations(self) -> list[dict]:
        """
        Define operaciones de actualización disponibles.
        Solo si supports_update = True
        """
        return [
            {
                'name': 'operation_name',
                'description': 'Descripción de la operación',
                'fields': {
                    'Campo1': 'valor1',
                    'Campo2': 'valor2'
                }
            }
        ]
    
    def execute_update(self, operation: str, data: pd.DataFrame) -> tuple[list, list]:
        """
        Ejecuta una operación de actualización.
        
        Args:
            operation: Nombre de la operación (de get_update_operations)
            data: DataFrame con registros a actualizar
            
        Returns:
            Tupla (registros_exitosos, registros_fallidos)
        """
        if operation != 'operation_name':
            raise ValueError(f"Operación desconocida: {operation}")
        
        if data.empty:
            return [], []
        
        # Preparar registros para actualización
        records = [
            {'Id': row['Id'], 'Campo': 'valor'}
            for _, row in data.iterrows()
        ]
        
        # Ejecutar con Bulk API
        return self.sf_client.bulk_update('NombreObjeto', records)
    
    def validate_prerequisites(self) -> tuple[bool, str]:
        """
        Valida que se cumplan prerrequisitos antes de ejecutar.
        """
        # Validación por defecto (client configurado)
        is_valid, msg = super().validate_prerequisites()
        if not is_valid:
            return is_valid, msg
        
        # Validaciones adicionales
        # if not some_condition:
        #     return False, "Mensaje de error"
        
        return True, ""
