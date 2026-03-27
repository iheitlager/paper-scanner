"""
General configuration loader for paper-scanner projects.

Handles loading project-level configuration from YAML definitions
into the executor's general_config dictionary.
"""

from datetime import datetime, timezone
from typing import Any, Dict


class GeneralConfigLoader:
    """
    Loader for general project configuration from YAML definitions.

    Maps YAML definition keys to internal general_config keys.
    Provides sensible defaults for optional fields.
    """

    # Mapping from internal config key -> YAML definition key
    FIELD_MAPPING = {
        "project_name": "name",
        "description": "description",
        "created_at": "created_at",
        "researcher": "researcher",
        "research_question": "research_question",
        "research_dimensions": "research_dimensions",
        "email": "email",
    }

    @staticmethod
    def get_defaults() -> Dict[str, Any]:
        """
        Get default values for general_config fields.

        Returns:
            Dictionary with default values
        """
        return {
            "project_name": "unknown",
            "description": "",
            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "researcher": "",
            "research_question": "",
            "research_dimensions": [],
            "email": "",
        }

    @staticmethod
    def load(general_config: Dict[str, Any], project_config: Dict[str, Any]) -> None:
        """
        Load configuration from project definition into general_config.

        Updates general_config in-place with values from project_config.
        Only updates fields that are present in project_config.

        Args:
            general_config: The general_config dict to update (modified in-place)
            project_config: The "project" section from YAML definition
        """
        for key, def_key in GeneralConfigLoader.FIELD_MAPPING.items():
            if def_key in project_config:
                general_config[key] = project_config[def_key]
