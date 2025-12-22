"""
Unified StepExecutor for definition-based pipeline execution

Encapsulates definition loading, template expansion, checkpoint management,
step execution, and session state. Provides both single-step (REPL) and
batch execution (workflow) modes with explicit checkpoint control.

Three-level configuration model:
1. general_config: Project-level settings (project_name, cache_dir, etc.)
2. step_config: Step-specific parameters from YAML or runtime
3. Runtime flags: verbose, dry_run, debug (passed during execution)

Self-contained with integrated step discovery and lazy loading.
"""

import hashlib
import importlib
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Type

import yaml

from paper_scanner.cli import STEP_REGISTRY_PATHS
from paper_scanner.core.database import PapersDatabase
from paper_scanner.core.exceptions import (CheckpointError, ConfigurationError,
                                           PipelineExecutionError, StepError)
from paper_scanner.steps.base import BaseStep
from paper_scanner.steps.halt import HaltException
from paper_scanner.core.enum import StepStatus


class LazyStepRegistry(dict):
    """Dictionary that lazy-loads step classes on access"""
    
    def __init__(self, registry_paths: Dict[str, str]):
        """
        Initialize registry with module paths.
        
        Args:
            registry_paths: Dict mapping step_name -> "module_path:ClassName"
        """
        self._paths = registry_paths
        self._loaded: Dict[str, Type[BaseStep]] = {}
        # Initialize dict with keys from paths (but don't load values yet)
        super().__init__({key: None for key in registry_paths.keys()})
    
    def __getitem__(self, key: str) -> Type[BaseStep]:
        """Get a step class, lazy-loading if necessary"""
        if key not in self._paths:
            raise KeyError(f"Unknown step: {key}")
        
        # Return cached version if already loaded
        if key in self._loaded:
            return self._loaded[key]
        
        # Load and cache the step class
        path_str = self._paths[key]
        module_path, class_name = path_str.split(":")
        module = importlib.import_module(module_path)
        step_class = getattr(module, class_name)
        self._loaded[key] = step_class
        # Update the dict value too
        super().__setitem__(key, step_class)
        return step_class
    
    def get(self, key: str, default=None):
        """Get with default value, lazy-loading if necessary"""
        try:
            return self[key]
        except KeyError:
            return default
    
    def items(self):
        """Return items, lazy-loading all values first"""
        for key in self._paths.keys():
            yield key, self[key]
    
    def values(self):
        """Return values, lazy-loading all values first"""
        for key in self._paths.keys():
            yield self[key]


class StepExecutor:
    """
    Unified executor for pipeline definitions with template support.
    
    Manages:
    - Definition loading and template validation
    - Session state (database, results, execution history)
    - Step execution (single or batch mode)
    - Checkpoint management (local files only)
    - Statistics and timing collection
    - Step discovery and lazy instantiation
    
    Self-contained with no external step executor dependencies.
    """
    
    # Class-level lazy registry (created on first access)
    _step_registry: Optional[LazyStepRegistry] = None

    def __init__(
        self,
        general_config: Dict[str, Any],
        cache_dir: Optional[Path] = None,
        verbose: bool = False,
        debug: bool = False,
    ):
        """
        Initialize executor with project configuration.

        Args:
            general_config: Project-level config (must include 'project_name')
            cache_dir: Cache directory for checkpoints (default: ~/.paper-scanner)
            verbose: Enable verbose output
            debug: Enable debug output
        """
        self.general_config = general_config
        self.cache_dir = cache_dir or Path.home() / ".paper-scanner"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.verbose = verbose
        self.debug = debug

        # Session state
        self.papers_db = PapersDatabase()
        self.definition: Dict[str, Any] = {}
        self.templates: Dict[str, List[Dict[str, Any]]] = {}
        self.steps: List[Dict[str, Any]] = []
        
        # Execution tracking
        self.results: Dict[str, Any] = {}
        self.step_history: List[Dict[str, Any]] = []
        self.current_step_index: int = 0
        
        # Statistics
        self.start_time: Optional[float] = None
        self.step_timings: List[Dict[str, Any]] = []
    
    # =========================================================================
    # Step Navigation Properties (for REPL/CLI convenience)
    # =========================================================================
    
    @property
    def has_steps(self) -> bool:
        """Check if definition has any steps loaded."""
        return len(self.steps) > 0
    
    @property
    def has_next_step(self) -> bool:
        """Check if there is a next step to execute."""
        return self.current_step_index < len(self.steps)
    
    @property
    def step_progress(self) -> Tuple[int, int]:
        """Get current progress as (current_index, total_steps)."""
        return (self.current_step_index, len(self.steps))
    
    def describe_next_step(self) -> Optional[Dict[str, Any]]:
        """
        Get details about the next step to execute.
        
        Returns:
            Dict with step details or None if no next step:
            {
                "index": int,
                "name": str,           # builtin step name
                "description": str,    # human-readable description
                "is_template": bool,   # whether it's a run-template step
                "template_name": str,  # template name if is_template
                "config": Dict,        # raw step config
            }
        """
        if not self.has_next_step:
            return None
        
        step_config = self.steps[self.current_step_index]
        step_name, step_params, description = self.parse_step_config(step_config)
        
        result = {
            "index": self.current_step_index,
            "name": step_name,
            "description": description or step_config.get('step', ''),
            "is_template": step_name == "run-template",
            "config": step_config,
        }
        
        if result["is_template"]:
            result["template_name"] = step_params.get('template', 'unknown')
        
        return result


    def describe_last_step(self) -> Optional[Dict[str, Any]]:
        """
        Get details about the last step executed.

        Returns:
            Dict with step details or None if no next step:
            {
                "index": int,
                "name": str,           # builtin step name
                "description": str,    # human-readable description
                "is_template": bool,   # whether it's a run-template step
                "template_name": str,  # template name if is_template
                "config": Dict,        # raw step config
            }
        """
        if self.current_step_index == 0:
            return None
        
        step_config = self.steps[self.current_step_index-1]
        step_name, step_params, description = self.parse_step_config(step_config)
        
        result = {
            "index": self.current_step_index - 1,
            "name": step_name,
            "description": description or step_config.get('step', ''),
            "is_template": step_name == "run-template",
            "config": step_config,
        }
        
        if result["is_template"]:
            result["template_name"] = step_params.get('template', 'unknown')
        
        return result


    def execute_next_step(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Execute the next step in the pipeline.
        
        Convenience wrapper around execute_step() that uses current_step_index.
        
        Args:
            dry_run: Don't actually execute the step
            
        Returns:
            Step result dictionary, or error dict if no next step
        """
        if not self.has_next_step:
            return {
                "status": StepStatus.ERROR,
                "error": "No more steps to execute",
                "count": 0,
            }
        
        return self.execute_step(self.current_step_index, dry_run=dry_run)
    
    # =========================================================================
    # Step Registry
    # =========================================================================
    
    @classmethod
    def get_builtin_steps(cls) -> Dict[str, Type[BaseStep]]:
        """
        Get the lazy-loading step registry.
        
        Steps are only imported when actually accessed.
        This significantly speeds up CLI commands that don't use all steps.
        
        Returns:
            LazyStepRegistry that loads steps on demand
        """
        if cls._step_registry is None:
            cls._step_registry = LazyStepRegistry(STEP_REGISTRY_PATHS)
        return cls._step_registry
    
    def get_step(self, step_name: str) -> BaseStep:
        """
        Get a step instance by name.

        Args:
            step_name: Name of the step (e.g., "bibtex_import")

        Returns:
            Instantiated step object (BaseStep subclass instance)
            
        Raises:
            StepError: If step not found or instantiation fails
        """
        builtin_steps = self.get_builtin_steps()

        if step_name not in builtin_steps:
            available = list(builtin_steps._paths.keys())
            raise StepError(f"Unknown step: {step_name}. Available: {available}")

        step_class = builtin_steps[step_name]
        try:
            # Instantiate the step with required dependencies
            return step_class(
                general_config=self.general_config,
                db=self.papers_db,
                cache_dir=self.cache_dir
            )
        except Exception as e:
            raise StepError(f"Failed to instantiate step '{step_name}': {e}") from e
    
    @staticmethod
    def parse_step_config(step_config: Dict[str, Any]) -> Tuple[str, Dict[str, Any], Optional[str]]:
        """
        Parse Ansible-style step configuration.

        Args:
            step_config: Raw step configuration from YAML

        Returns:
            Tuple of (step_name, step_params, description)
            
        Raises:
            ConfigurationError: If step configuration is invalid
        """
        step_value = step_config.get("step")
        if not step_value:
            raise ConfigurationError("Step configuration missing 'step' key")

        description = step_config.get("description", "")

        # Find the builtin key to determine actual step name
        builtin_key = None
        for key in step_config.keys():
            if key.startswith("builtin."):
                builtin_key = key
                break

        if not builtin_key:
            raise ConfigurationError(f"Step configuration missing 'builtin.<step>' key")

        # Extract step name from builtin key
        step_name = builtin_key.replace("builtin.", "")

        # If step_value contains spaces or is not a valid step name, use it as description
        builtin_steps = StepExecutor.get_builtin_steps()
        if " " in step_value or step_value not in builtin_steps._paths:
            if not description:
                description = step_value
        else:
            step_name = step_value

        # Get step params from builtin key
        step_params = step_config.get(builtin_key, {})

        # Also accept step-specific params at root level for convenience
        if not step_params:
            step_params = {
                k: v
                for k, v in step_config.items()
                if k not in ("step", "description") and not k.startswith("builtin.")
            }

        return step_name, step_params, description

    def load_definition(self, definition_file: Path) -> bool:
        """
        Load and validate a YAML definition file.
        
        Parses project metadata, templates, and steps.
        Validates all template references early.

        Args:
            definition_file: Path to YAML definition file

        Returns:
            True on success, False on error
        """
        if not definition_file.exists():
            raise FileNotFoundError(f"Definition file not found: {definition_file}")

        with open(definition_file, "r", encoding="utf-8") as f:
            self.definition = yaml.safe_load(f)

        if not self.definition:
            raise ValueError("Definition file is empty")

        # Update general config from definition
        project_config = self.definition.get("project", {})
        if "name" in project_config:
            self.general_config["project_name"] = project_config["name"]

        # Load templates section (optional, v1: static sequences only)
        self.templates = {}
        for template in self.definition.get("templates", []):
            template_name = template.get("template")
            if not template_name:
                raise ValueError("Template missing 'template' key")
            template_steps = template.get("steps", [])
            self.templates[template_name] = template_steps

        # Load main steps section
        self.steps = self.definition.get("steps", [])

        # Validate all template references (fail early)
        self._validate_template_references()

        # Initialize checkpoint directory
        checkpoints_dir = self.cache_dir / "checkpoints"
        checkpoints_dir.mkdir(parents=True, exist_ok=True)

        return True


    def _validate_template_references(self) -> None:
        """
        Validate that all referenced templates exist.
        
        Raises:
            ValueError: If a referenced template is not defined
        """
        def check_step_templates(step: Dict[str, Any]) -> None:
            """Recursively check for template references in a step"""
            # Check for run-template references
            step_name, step_params, _ = self.parse_step_config(step)
            if step_name == "run-template":
                template_name = step_params.get("template")
                if template_name and template_name not in self.templates:
                    raise ValueError(
                        f"Referenced template '{template_name}' not found. "
                        f"Available templates: {list(self.templates.keys())}"
                    )

        for step in self.steps:
            check_step_templates(step)

    def load_checkpoint(self, skip_checkpoint: bool = False, clear_checkpoint: bool = False) -> None:
        """
        Manage checkpoint state (load, skip, or clear).

        Args:
            skip_checkpoint: Don't load from checkpoints
            clear_checkpoint: Clear all existing checkpoints
        """
        checkpoints_dir = self.cache_dir / "checkpoints"

        if clear_checkpoint and checkpoints_dir.exists():
            import shutil
            shutil.rmtree(checkpoints_dir)
            return

        if skip_checkpoint:
            return

        # Find latest checkpoint
        latest_index, latest_file = self._find_latest_checkpoint()
        if latest_index is not None and latest_file:
            try:
                self._load_checkpoint_file(latest_file)
                self.current_step_index = latest_index
            except CheckpointError:
                raise
            except FileNotFoundError as e:
                raise CheckpointError(f"Checkpoint file disappeared: {latest_file}") from e

    def _find_latest_checkpoint(self) -> Tuple[Optional[int], Optional[Path]]:
        """
        Find the latest checkpoint file.

        Returns:
            Tuple of (resume_step_index, checkpoint_file) or (None, None)
        """
        checkpoints_dir = self.cache_dir / "checkpoints"
        if not checkpoints_dir.exists():
            return None, None

        project_hash = self._get_project_hash()
        latest_index = None
        latest_file = None

        for i in range(len(self.steps)):
            checkpoint_name = f"checkpoint_{project_hash}_step_{i:03d}.json"
            checkpoint_file = checkpoints_dir / checkpoint_name

            if checkpoint_file.exists():
                latest_index = i
                latest_file = checkpoint_file

        if latest_index is not None:
            return latest_index + 1, latest_file

        return None, None

    def _load_checkpoint_file(self, checkpoint_file: Path) -> None:
        """
        Load papers from checkpoint JSON file.
        
        Raises:
            CheckpointError: If checkpoint file is corrupt or invalid
            FileNotFoundError: If checkpoint file doesn't exist
        """
        try:
            with open(checkpoint_file, "r") as f:
                data = json.load(f)
        except FileNotFoundError:
            raise
        except json.JSONDecodeError as e:
            raise CheckpointError(f"Corrupt checkpoint file: {checkpoint_file}") from e
        except IOError as e:
            raise CheckpointError(f"Cannot read checkpoint file: {checkpoint_file}") from e
        
        # Restore papers from checkpoint
        papers = data.get("papers", [])
        if papers:
            try:
                from paper_scanner.core.models import Paper
                paper_objects = [Paper(**p) for p in papers]
                self.papers_db.from_list(paper_objects)
            except (TypeError, ValueError) as e:
                raise CheckpointError(f"Invalid paper data in checkpoint: {checkpoint_file}") from e

    def _get_project_hash(self) -> str:
        """Get deterministic project hash for checkpoint naming"""
        project_name = self.general_config.get("project_name", "unknown")
        return hashlib.md5(project_name.encode()).hexdigest()[:8]

    def execute_step(
        self,
        step_index: int,
        step_config: Optional[Dict[str, Any]] = None,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Execute a single step from the definition.

        Args:
            step_index: Index in self.steps to execute
            step_config: Override step config (default: use from definition)
            dry_run: Don't actually execute

        Returns:
            Step result dictionary with status, count, etc.
        """
        if step_index < 0 or step_index >= len(self.steps):
            return {
                "status": "error",
                "error": f"Step index {step_index} out of range",
                "count": 0,
            }

        if step_config is None:
            step_config = self.steps[step_index]

        step_start = time.time()
        result = {}

        try:
            # Parse step config to get step name
            # Let ConfigurationError propagate for invalid config
            step_name, step_params, description = self.parse_step_config(step_config)

            # Handle run-template: recursively execute template steps
            if step_name == "run-template":
                result = self._execute_template(
                    step_params, description, dry_run
                )
            else:
                # Execute regular step
                result = self._execute_builtin_step(
                    step_name, step_params, description, dry_run
                )

            # Track timing
            duration = time.time() - step_start
            self.step_timings.append({
                "step": step_name,
                "duration_seconds": round(duration, 2),
                "duration_ms": round(duration * 1000, 0),
            })

            # Update history
            self.step_history.append({
                "index": step_index,
                "step": step_name,
                "status": result.get("status", "unknown"),
                "duration_seconds": round(duration, 2),
            })

            self.results = result
            self.current_step_index = step_index + 1

            return result

        except (ConfigurationError, StepError):
            # Configuration/step errors are caught and returned as error dicts
            # (letting the REPL decide how to display them)
            return {
                "status": "error",
                "error": str(e),
                "count": 0,
            }
        except HaltException as e:
            return {
                "status": "halted",
                "message": str(e),
                "count": 0,
            }
        except PipelineExecutionError as e:
            # Step execution errors are caught and returned as error dicts
            return {
                "status": "error",
                "error": str(e),
                "count": 0,
            }
        except Exception as e:
            # Other unexpected exceptions are caught and returned
            return {
                "status": "error",
                "error": str(e),
                "count": 0,
            }

    def _execute_builtin_step(
        self,
        step_name: str,
        step_params: Dict[str, Any],
        description: Optional[str],
        dry_run: bool,
    ) -> Dict[str, Any]:
        """Execute a builtin step"""
        # Get step instance
        step_instance = self.get_step(step_name)

        # For checkpoint steps, inject metadata
        if step_name == "checkpoint":
            step_params = dict(step_params)
            step_params["cache_dir"] = str(self.cache_dir)
            step_params["step_index"] = self.current_step_index
            step_params["project_name"] = self.general_config.get("project_name")

        # Execute step
        result = step_instance.execute(
            step_params,
            verbose=self.verbose,
            dry_run=dry_run,
            debug=self.debug,
        )

        # Ensure standard fields
        result["step"] = step_name
        if description:
            result["description"] = description

        return result

    def _execute_template(
        self,
        step_params: Dict[str, Any],
        description: Optional[str],
        dry_run: bool,
    ) -> Dict[str, Any]:
        """Execute a template (recursively expand and run template steps)"""
        template_name = step_params.get("template")
        if not template_name:
            return {
                "status": "error",
                "error": "run-template missing 'template' parameter",
                "count": 0,
            }

        if template_name not in self.templates:
            return {
                "status": "error",
                "error": f"Template '{template_name}' not found",
                "count": 0,
            }

        template_steps = self.templates[template_name]
        template_results = []
        total_count = 0

        try:
            for template_step in template_steps:
                # Parse and execute each template step
                step_name, step_params, step_desc = self.parse_step_config(template_step)

                if step_name == "run-template":
                    # Nested template call
                    result = self._execute_template(step_params, step_desc, dry_run)
                else:
                    result = self._execute_builtin_step(
                        step_name, step_params, step_desc, dry_run
                    )

                template_results.append(result)
                total_count += result.get("count", 0)

                if result.get("status") == "error":
                    return {
                        "status": "error",
                        "error": f"Template '{template_name}' failed at step {step_name}: {result.get('error')}",
                        "count": total_count,
                        "template_results": template_results,
                    }

            return {
                "status": "ok",
                "count": total_count,
                "template": template_name,
                "template_results": template_results,
            }

        except (ConfigurationError, StepError):
            # Configuration/step errors propagate (caller can catch them)
            raise
        except Exception as e:
            raise PipelineExecutionError(f"Template '{template_name}' execution failed: {e}") from e

    def run_all(
        self,
        dry_run: bool = False,
        on_step_start: Optional[callable] = None,
        on_step_end: Optional[callable] = None,
    ) -> Dict[str, Any]:
        """
        Execute all remaining steps sequentially.

        Args:
            dry_run: Don't actually execute steps
            on_step_start: Optional callback called before each step.
                Signature: (step_index: int, step_config: Dict, total_steps: int) -> None
            on_step_end: Optional callback called after each step.
                Signature: (step_index: int, step_config: Dict, result: Dict) -> None

        Returns:
            Aggregated results dictionary
        """
        self.start_time = time.time()
        results_summary = {
            "status": "ok",
            "steps_executed": 0,
            "steps_failed": 0,
            "total_duration_seconds": 0,
            "step_results": [],
        }

        total_steps = len(self.steps)

        try:
            for i in range(self.current_step_index, total_steps):
                step_config = self.steps[i]
                
                # Call start callback if provided
                if on_step_start:
                    on_step_start(i, step_config, total_steps)
                
                result = self.execute_step(i, dry_run=dry_run)

                # Call end callback if provided
                if on_step_end:
                    on_step_end(i, step_config, result)

                results_summary["step_results"].append(result)

                if result.get("status") == "error":
                    results_summary["status"] = StepStatus.ERROR
                    results_summary["steps_failed"] += 1
                    break
                elif result.get("status") == "halted":
                    results_summary["status"] = "halted"
                    break
                else:
                    results_summary["steps_executed"] += 1

        except (ConfigurationError, StepError, PipelineExecutionError, CheckpointError):
            # Let paper-scanner errors propagate
            raise

        # Add timing information
        if self.start_time:
            results_summary["total_duration_seconds"] = round(
                time.time() - self.start_time, 2
            )

        return results_summary

    def checkpoint(self) -> Dict[str, Any]:
        """
        Save current database state as checkpoint.

        Returns:
            Checkpoint result dictionary
        """
        try:
            checkpoints_dir = self.cache_dir / "checkpoints"
            checkpoints_dir.mkdir(parents=True, exist_ok=True)

            project_hash = self._get_project_hash()
            checkpoint_name = f"checkpoint_{project_hash}_step_{self.current_step_index:03d}.json"
            checkpoint_file = checkpoints_dir / checkpoint_name

            # Serialize papers to JSON - use model_dump() for proper Pydantic serialization
            papers_data = []
            for p in self.papers_db.papers:
                paper_dict = p.model_dump(mode='json')
                papers_data.append(paper_dict)

            checkpoint_data = {
                "project_name": self.general_config.get("project_name"),
                "step_index": self.current_step_index,
                "timestamp": datetime.now().isoformat(),
                "papers_count": len(self.papers_db.papers),
                "papers": papers_data,
            }

            try:
                with open(checkpoint_file, "w") as f:
                    json.dump(checkpoint_data, f, indent=2)
            except (IOError, OSError) as e:
                raise CheckpointError(f"Cannot write checkpoint to {checkpoint_file}: {e}") from e
            except (TypeError, ValueError) as e:
                raise CheckpointError(f"Cannot serialize checkpoint data: {e}") from e

            return {
                "status": "ok",
                "checkpoint_file": str(checkpoint_file),
                "papers_count": len(self.papers_db.papers),
            }

        except CheckpointError:
            raise
        except Exception as e:
            raise CheckpointError(f"Checkpoint operation failed: {e}") from e

    def get_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive execution statistics and inventory.

        Returns:
            Statistics dictionary with timings, counts, and inventory
        """
        # Get available steps from the lazy registry
        available_steps = list(self.get_builtin_steps()._paths.keys())

        stats = {
            "project_name": self.general_config.get("project_name"),
            "papers_total": self.papers_db.count(primary_only=False),
            "papers_unique": self.papers_db.count(primary_only=True),
            "papers_duplicates": (
                self.papers_db.count(primary_only=False) - 
                self.papers_db.count(primary_only=True)
            ),
            "current_step_index": self.current_step_index,
            "total_steps": len(self.steps),
            "steps_executed": len(self.step_history),
            "step_timings": self.step_timings,
            "step_history": self.step_history,
            "templates": {
                "count": len(self.templates),
                "names": list(self.templates.keys()),
            },
            "inventory": {
                "builtin_steps": available_steps,
                "templates": list(self.templates.keys()),
            },
        }

        if self.start_time:
            stats["total_duration_seconds"] = round(
                time.time() - self.start_time, 2
            )

        return stats

    def get_session_state(self) -> Dict[str, Any]:
        """Get current session state for REPL or status display"""
        state = {
            "papers_db": self.papers_db,
            "papers_count": self.papers_db.count(),
            "current_step_index": self.current_step_index,
            "total_steps": len(self.steps),
            "step_history": self.step_history,
            "results": self.results,
            "general_config": self.general_config,
        }
        
        last_step_info = self.describe_last_step()
        if last_step_info:
            state["last_step"] = {
                "name": last_step_info["name"],
                "description": last_step_info["description"],
                "step_text": self.steps[self.current_step_index - 1].get("step", ""),
                "is_template": last_step_info["is_template"],
                "template_name": last_step_info.get("template_name"),
            }
        # Add current step details if there's a next step to execute
        if self.has_next_step:
            step_info = self.describe_next_step()
            if step_info:
                state["current_step"] = {
                    "name": step_info["name"],
                    "description": step_info["description"],
                    "step_text": self.steps[self.current_step_index].get("step", ""),
                    "is_template": step_info["is_template"],
                    "template_name": step_info.get("template_name"),
                }
        
        return state
