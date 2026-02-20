"""
Script Registry - Central registry for all available scripts.
"""
from typing import Type, Optional
from .base_script import BaseScript


class ScriptRegistry:
    """
    Singleton registry for managing available scripts.
    Scripts register themselves and can be retrieved by name or category.
    """
    
    _instance = None
    _scripts: dict[str, Type[BaseScript]] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._scripts = {}
        return cls._instance
    
    def register(self, script_class: Type[BaseScript], override: bool = False):
        """
        Register a script class.
        
        Args:
            script_class: Class that inherits from BaseScript
            override: If True, allows overriding existing registration
        """
        if not issubclass(script_class, BaseScript):
            raise TypeError(f"{script_class} must inherit from BaseScript")
        
        key = script_class.name
        if key in self._scripts and not override:
            raise ValueError(f"Script '{key}' already registered. Use override=True to replace.")
        
        self._scripts[key] = script_class
    
    def unregister(self, name: str):
        """Remove a script from the registry."""
        if name in self._scripts:
            del self._scripts[name]
    
    def get(self, name: str) -> Optional[Type[BaseScript]]:
        """Get a script class by name."""
        return self._scripts.get(name)
    
    def get_all(self) -> list[Type[BaseScript]]:
        """Get all registered scripts."""
        return list(self._scripts.values())
    
    def get_by_category(self, category: str) -> list[Type[BaseScript]]:
        """Get all scripts in a category."""
        return [s for s in self._scripts.values() if s.category == category]
    
    def get_categories(self) -> list[str]:
        """Get all unique categories."""
        return list(set(s.category for s in self._scripts.values()))
    
    def list_scripts(self) -> list[dict]:
        """Get list of script info for UI display."""
        return [
            {
                "name": s.name,
                "description": s.description,
                "category": s.category,
                "version": s.version,
                "author": s.author,
                "supports_update": s.supports_update,
                "supports_preview": s.supports_preview
            }
            for s in self._scripts.values()
        ]
    
    def clear(self):
        """Clear all registrations (mainly for testing)."""
        self._scripts.clear()


def get_registry() -> ScriptRegistry:
    """Get the global script registry instance."""
    return ScriptRegistry()


def register_script(cls: Type[BaseScript]) -> Type[BaseScript]:
    """
    Decorator to register a script class.
    
    Usage:
        @register_script
        class MyScript(BaseScript):
            name = "My Script"
            ...
    """
    get_registry().register(cls)
    return cls
