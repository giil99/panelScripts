"""
Execution Engine - Orchestrates script execution.
"""
import time
import traceback
from datetime import datetime
from typing import Type, Optional
import pandas as pd

from .base_script import BaseScript, ScriptResult, ScriptMetrics


class ExecutionEngine:
    """
    Engine for executing scripts with proper error handling,
    progress tracking, and result management.
    """
    
    def __init__(self, sf_client=None):
        """
        Initialize the execution engine.
        
        Args:
            sf_client: SalesforceClient instance for API calls
        """
        self.sf_client = sf_client
        self.current_script: Optional[BaseScript] = None
        self.execution_history: list[dict] = []
        self._progress_callback = None
    
    def set_progress_callback(self, callback):
        """Set a callback function for progress updates."""
        self._progress_callback = callback
    
    def _update_progress(self, step: str, progress: float, message: str = ""):
        """Update progress via callback if set."""
        if self._progress_callback:
            self._progress_callback(step, progress, message)
    
    def execute(
        self,
        script_class: Type[BaseScript],
        preview: bool = False,
        execute_updates: bool = False
    ) -> ScriptResult:
        """
        Execute a script and return results.
        
        Args:
            script_class: Script class to instantiate and run
            preview: Run in preview mode (limited results)
            execute_updates: If True and script supports updates, execute them
            
        Returns:
            ScriptResult with data and metrics
        """
        start_time = time.time()
        
        # Instantiate script
        script = script_class(sf_client=self.sf_client)
        self.current_script = script
        
        try:
            # Validate prerequisites
            self._update_progress("validation", 0.05, "Validando requisitos...")
            is_valid, error_msg = script.validate_prerequisites()
            if not is_valid:
                return ScriptResult(
                    success=False,
                    error_message=error_msg,
                    execution_time=time.time() - start_time
                )
            
            # Get queries
            self._update_progress("queries", 0.1, "Obteniendo consultas...")
            queries = script.get_queries(preview=preview)
            
            if not queries:
                return ScriptResult(
                    success=False,
                    error_message="No queries defined",
                    execution_time=time.time() - start_time
                )
            
            # Execute queries
            query_results = {}
            total_queries = len(queries)
            
            for idx, query in enumerate(queries):
                progress = 0.1 + (0.5 * (idx + 1) / total_queries)
                self._update_progress(
                    "query",
                    progress,
                    f"Ejecutando consulta {idx + 1} de {total_queries}..."
                )
                
                try:
                    results = self.sf_client.bulk_query(query)
                    df = pd.DataFrame(results)
                    query_results[f"query_{idx}"] = df
                    
                    # Log query results
                    self._update_progress(
                        "query_result",
                        progress + 0.02,
                        f"Consulta {idx + 1}: {len(df)} registros obtenidos"
                    )
                    script.store_intermediate(f"query_{idx}_raw", df)
                except Exception as e:
                    self._update_progress(
                        "query_error",
                        progress,
                        f"Error en consulta {idx + 1}: {str(e)}"
                    )
                    script.add_warning(f"Error en consulta {idx + 1}: {str(e)}")
                    query_results[f"query_{idx}"] = pd.DataFrame()
            
            # Process data
            self._update_progress("processing", 0.70, "Procesando datos...")
            result = script.process(query_results)
            
            # Log processing result
            result_count = len(result.data) if result.data is not None else 0
            self._update_progress(
                "processing_done",
                0.75,
                f"Procesamiento completado: {result_count} registros"
            )
            
            # Detect anomalies
            if result.data is not None and not result.data.empty:
                self._update_progress("anomalies", 0.80, "Detectando anomalías...")
                anomalies = script.detect_anomalies(result.data)
                if not anomalies.empty:
                    result.anomalies = anomalies
                    self._update_progress(
                        "anomalies_done",
                        0.85,
                        f"Anomalías detectadas: {len(anomalies)}"
                    )
                else:
                    self._update_progress(
                        "anomalies_done",
                        0.85,
                        "Sin anomalías detectadas"
                    )
            else:
                self._update_progress(
                    "no_data",
                    0.85,
                    "Sin datos para analizar anomalías"
                )
            
            # Calculate metrics if not provided
            if result.metrics is None:
                result.metrics = ScriptMetrics(
                    total_records=len(result.data) if result.data is not None else 0
                )
            
            # Add warnings
            result.warnings.extend(script._warnings)
            
            # Store intermediate data and script reference
            result.intermediate_data = script._intermediate_data
            result.script_instance = script
            
            # Execute updates if requested
            if execute_updates and script.supports_update and result.data is not None:
                self._update_progress("updates", 0.9, "Ejecutando actualizaciones...")
                operations = script.get_update_operations()
                if operations:
                    for op in operations:
                        try:
                            success, failed = script.execute_update(
                                op['name'],
                                result.data
                            )
                            result.metrics.success_count = len(success)
                            result.metrics.error_count = len(failed)
                        except Exception as e:
                            result.warnings.append(f"Error en update '{op['name']}': {str(e)}")
            
            self._update_progress("complete", 1.0, "Completado")
            result.execution_time = time.time() - start_time
            result.executed_at = datetime.now()
            
            # Save to history
            self._save_to_history(script, result, preview)
            
            return result
            
        except Exception as e:
            error_msg = f"{str(e)}\n{traceback.format_exc()}"
            result = ScriptResult(
                success=False,
                error_message=error_msg,
                execution_time=time.time() - start_time,
                warnings=script._warnings
            )
            self._save_to_history(script, result, preview)
            return result
        
        finally:
            self.current_script = None
    
    def _save_to_history(self, script: BaseScript, result: ScriptResult, preview: bool):
        """Save execution to history."""
        self.execution_history.append({
            "script_name": script.name,
            "script_category": script.category,
            "preview": preview,
            "success": result.success,
            "record_count": len(result.data) if result.data is not None else 0,
            "execution_time": result.execution_time,
            "executed_at": result.executed_at.isoformat(),
            "error_message": result.error_message,
            "warnings_count": len(result.warnings)
        })
    
    def get_history(self, limit: int = 50) -> list[dict]:
        """Get recent execution history."""
        return self.execution_history[-limit:][::-1]
    
    def clear_history(self):
        """Clear execution history."""
        self.execution_history.clear()
