"""
History Manager - Persistent execution history storage.
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Optional


class HistoryManager:
    """
    Manages persistent execution history.
    Stores history in a JSON file that persists across sessions.
    """
    
    _instance: Optional['HistoryManager'] = None
    
    def __new__(cls, *args, **kwargs):
        """Singleton pattern to ensure single instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, history_file: Optional[Path] = None):
        """
        Initialize the history manager.
        
        Args:
            history_file: Path to the history JSON file
        """
        if self._initialized:
            return
            
        if history_file is None:
            base_dir = Path(__file__).parent.parent
            history_file = base_dir / "data" / "execution_history.json"
        
        self.history_file = history_file
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        self._history: list[dict] = []
        self._load()
        self._initialized = True
    
    def _load(self):
        """Load history from file."""
        try:
            if self.history_file.exists():
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    self._history = json.load(f)
            else:
                self._history = []
        except (json.JSONDecodeError, IOError):
            self._history = []
    
    def _save(self):
        """Save history to file."""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self._history, f, ensure_ascii=False, indent=2, default=str)
        except IOError as e:
            print(f"Error saving history: {e}")
    
    def add(
        self,
        script_name: str,
        script_category: str,
        success: bool,
        record_count: int,
        execution_time: float,
        error_message: Optional[str] = None,
        warnings_count: int = 0,
        preview: bool = False,
        env: Optional[str] = None
    ):
        """
        Add an execution record to history.
        
        Args:
            script_name: Name of the executed script
            script_category: Category of the script
            success: Whether execution was successful
            record_count: Number of records processed
            execution_time: Execution time in seconds
            error_message: Error message if failed
            warnings_count: Number of warnings
            preview: Whether this was a preview execution
            env: Salesforce environment (pre/pro)
        """
        record = {
            "id": len(self._history) + 1,
            "script_name": script_name,
            "script_category": script_category,
            "success": success,
            "record_count": record_count,
            "execution_time": round(execution_time, 2),
            "error_message": error_message,
            "warnings_count": warnings_count,
            "preview": preview,
            "env": env,
            "executed_at": datetime.now().isoformat()
        }
        self._history.append(record)
        self._save()
        return record
    
    def get_all(self, limit: Optional[int] = None) -> list[dict]:
        """
        Get all history records.
        
        Args:
            limit: Maximum number of records to return (most recent first)
            
        Returns:
            List of history records
        """
        if limit:
            return self._history[-limit:][::-1]
        return self._history[::-1]
    
    def get_by_script(self, script_name: str, limit: Optional[int] = None) -> list[dict]:
        """Get history for a specific script."""
        filtered = [r for r in self._history if r['script_name'] == script_name]
        if limit:
            return filtered[-limit:][::-1]
        return filtered[::-1]
    
    def get_stats(self) -> dict:
        """Get statistics from history."""
        if not self._history:
            return {
                'total_executions': 0,
                'success_rate': 0,
                'avg_execution_time': 0,
                'total_records_processed': 0,
                'scripts_executed': 0
            }
        
        success_count = sum(1 for r in self._history if r['success'])
        total_time = sum(r['execution_time'] for r in self._history)
        total_records = sum(r['record_count'] for r in self._history)
        unique_scripts = len(set(r['script_name'] for r in self._history))
        
        return {
            'total_executions': len(self._history),
            'success_rate': round((success_count / len(self._history)) * 100, 1),
            'avg_execution_time': round(total_time / len(self._history), 2),
            'total_records_processed': total_records,
            'scripts_executed': unique_scripts
        }
    
    def clear(self):
        """Clear all history."""
        self._history = []
        self._save()
    
    def delete_old(self, days: int = 30):
        """Delete records older than specified days."""
        cutoff = datetime.now().timestamp() - (days * 24 * 60 * 60)
        self._history = [
            r for r in self._history
            if datetime.fromisoformat(r['executed_at']).timestamp() > cutoff
        ]
        self._save()


def get_history_manager() -> HistoryManager:
    """Get the singleton history manager instance."""
    return HistoryManager()
