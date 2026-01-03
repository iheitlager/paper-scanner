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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Type, TYPE_CHECKING

import yaml

from paper_scanner.cli import STEP_REGISTRY_PATHS
from paper_scanner.core.database import PapersDatabase
from paper_scanner.core.enum import StepStatus
from paper_scanner.core.exceptions import CheckpointError, ConfigurationError, PipelineExecutionError, StepError
from paper_scanner.core.step_result import FINAL_STEP, StepResult
from paper_scanner.core.general_config import GeneralConfigLoader
from paper_scanner.steps.base import BaseStep
from paper_scanner.steps.halt import HaltException
from paper_scanner.core.reporter import NOOP

if TYPE_CHECKING:
    from paper_scanner.core.reporter import AbstractStepReporter

CHECKPOINT_DIR="checkpoints"

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
        step_reporter: "AbstractStepReporter",
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
        self.step_reporter = step_reporter

        self.verbose = verbose
        self.debug = debug

        # Session state
        self.papers_db = PapersDatabase()
        self.definition: Dict[str, Any] = {}
        self.templates: Dict[str, List[Dict[str, Any]]] = {}
        self.steps: List[Dict[str, Any]] = []
        self.step_state: Dict[str, Any] = {}  # Ephemeral state persisting between steps within a session

        # Execution tracking
        self.results: Dict[str, Any] = {}
        self.step_history: List[Dict[str, Any]] = []
        self.current_step_index: int = 0

        # Statistics
        self.start_time: Optional[float] = None

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
            "description": description or step_config.get("step", ""),
            "is_template": step_name == "run-template",
            "config": step_config,
        }

        if result["is_template"]:
            result["template_name"] = step_params.get("template", "unknown")

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

        step_config = self.steps[self.current_step_index - 1]
        step_name, step_params, description = self.parse_step_config(step_config)

        result = {
            "index": self.current_step_index - 1,
            "name": step_name,
            "description": description or step_config.get("step", ""),
            "is_template": step_name == "run-template",
            "config": step_config,
        }

        if result["is_template"]:
            result["template_name"] = step_params.get("template", "unknown")

        return result

    def execute_next_step(self, dry_run: bool = False) -> StepResult:
        """
        Execute the next step in the pipeline.

        Convenience wrapper around execute_step() that uses current_step_index.

        Args:
            dry_run: Don't actually execute the step

        Returns:
            Step result dictionary, or error dict if no next step
        """
        if not self.has_next_step:
            return FINAL_STEP

        return self.execute_step(self.current_step_index, dry_run=dry_run)

    # =========================================================================
    # Session Reset
    # =========================================================================

    def reset(self, scope: str = "execution") -> None:
        """
        Reset executor state to a clean state.

        Args:
            scope: Reset scope
                - "execution": Clear execution history, reset to start (keep definition & DB)
                - "definition": Clear definition, steps, templates (keep DB)
                - "all": Full reset to initialization state

        Raises:
            ValueError: If invalid scope provided
        """
        valid_scopes = {"execution", "definition", "all"}
        if scope not in valid_scopes:
            raise ValueError(f"Invalid reset scope: {scope}. Must be one of {valid_scopes}")

        if scope in ("execution", "all"):
            # Clear execution tracking only
            self.results = {}
            self.step_history = []
            self.current_step_index = 0
            self.start_time = None
            self.step_state = {}  # Clear step state on execution reset
            self.papers_db = PapersDatabase()

        if scope in ("definition", "all"):
            # Clear definition and steps
            self.definition = {}
            self.templates = {}
            self.steps = []
            # Also reset execution tracking when clearing definition
            if scope == "definition":
                self.reset("execution")

        self.step_reporter.on_step_event(f"Reset {scope} state", debug=True)

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
            on_event_callback = self.step_reporter.on_step_event if self.step_reporter else None
            return step_class(general_config=self.general_config, executor=self, db=self.papers_db, cache_dir=self.cache_dir, on_event=on_event_callback)
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
            raise ConfigurationError("Step configuration missing 'builtin.<step>' key")

        # Extract step name from builtin key
        # TODO: solve this so we can use external plugins too
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
                if k not in ("step", "description")
            }

        return step_name, step_params, description

    def enable_step(self, step_index: int) -> None:
        """
        Enable a disabled step by index.

        Args:
            step_index: Index of the step to enable

        Raises:
            IndexError: If step_index is out of range
        """
        if step_index < 0 or step_index >= len(self.steps):
            raise IndexError(f"Step index out of range: {step_index}")

        step_config = self.steps[step_index]
        step_config["enabled"] = True

    def disable_step(self, step_index: int) -> None:
        """
        Disable a step by index.

        Args:
            step_index: Index of the step to disable

        Raises:
            IndexError: If step_index is out of range
        """
        if step_index < 0 or step_index >= len(self.steps):
            raise IndexError(f"Step index out of range: {step_index}")

        step_config = self.steps[step_index]
        step_config["enabled"] = False
    # ========================================================================
    # Definition Loading and Validation
    # ========================================================================

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

        # Update general config from definition using GeneralConfigLoader
        project_config = self.definition.get("project", {})
        GeneralConfigLoader.load(self.general_config, project_config)

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
        for step in self.steps:
            step['command'] = tuple(set(step.keys()) - {"step", "description", "enabled"})[0]

        # Validate all template references (fail early)
        self._validate_template_references()

        # Initialize checkpoint directory
        checkpoints_dir = self.cache_dir / CHECKPOINT_DIR
        checkpoints_dir.mkdir(parents=True, exist_ok=True)

        if self.step_reporter:
            self.step_reporter.on_definition_loaded(definition_file, self.definition)

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

    def _get_project_hash(self) -> str:
        """Get deterministic project hash for checkpoint naming"""
        project_name = self.general_config.get("project_name", "unknown")
        return hashlib.md5(project_name.encode()).hexdigest()[:8]

    # =========================================================================
    # Checkpoint Management
    # =========================================================================
    def load_checkpoint(self, skip_checkpoint: bool = False, clear_checkpoint: bool = False) -> None:
        """
        Manage checkpoint state (load, skip, or clear).

        Args:
            skip_checkpoint: Don't load from checkpoints
            clear_checkpoint: Clear all existing checkpoints
        """
        checkpoints_dir = self.cache_dir / CHECKPOINT_DIR

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
        checkpoints_dir = self.cache_dir / CHECKPOINT_DIR
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

    def checkpoint(self) -> StepResult:
        """
        Save current database state as checkpoint.

        Returns:
            StepResult with checkpoint metadata in stats dict
        """
        try:
            checkpoints_dir = self.cache_dir / CHECKPOINT_DIR
            checkpoints_dir.mkdir(parents=True, exist_ok=True)

            project_hash = self._get_project_hash()
            checkpoint_name = f"checkpoint_{project_hash}_step_{self.current_step_index:03d}.json"
            checkpoint_file = checkpoints_dir / checkpoint_name

            # Serialize papers to JSON - use model_dump() for proper Pydantic serialization
            papers_data = []
            for p in self.papers_db.papers:
                paper_dict = p.model_dump(mode="json")
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

            return StepResult(
                status=StepStatus.SUCCESS,
                message="Checkpoint saved successfully",
                stats={
                    "checkpoint_file": str(checkpoint_file),
                    "papers_count": len(self.papers_db.papers),
                },
            )

        except CheckpointError:
            raise
        except Exception as e:
            raise CheckpointError(f"Checkpoint operation failed: {e}") from e

    # =========================================================================
    # Step Execution
    # =========================================================================
    def execute_step(
        self,
        step_index: int,
        step_config: Optional[Dict[str, Any]] = None,
        dry_run: bool = False,
    ) -> StepResult:
        """
        Execute a single step from the definition.

        Exceptions propagate to the caller (typically CLI layer) for proper
        error handling and recovery. Only HaltException is special-cased as
        it's an intentional signal, not an error.

        Args:
            step_index: Index in self.steps to execute
            step_config: Override step config (default: use from definition)
            dry_run: Don't actually execute

        Returns:
            StepResult for normal completion (SUCCESS/WARNING/ERROR/HALTED)

        Raises:
            StepError: If step index is out of range or step name invalid
            ConfigurationError: If step config is invalid
            PipelineExecutionError: If step execution fails
            Any other exception: Propagates for CLI to handle
        """
        if step_index < 0 or step_index >= len(self.steps):
            raise StepError(f"Step index out of range: {step_index}")

        if step_config is None:
            step_config = self.steps[step_index]

        step_start = time.time()

        try:
            # Parse step config to get step name
            # ConfigurationError propagates for invalid config
            step_name, step_params, description = self.parse_step_config(step_config)

            if self.step_reporter:
                self.step_reporter.on_step_start(self.current_step_index, step_config, total=len(self.steps))

            if step_config.get("enabled", True) != False:
                # Handle run-template: recursively execute template steps
                if step_name == "run-template":
                    result = self._execute_template(step_params, description, dry_run)
                else:
                    # Execute regular step
                    result = self._execute_builtin_step(step_name, step_params, description, dry_run)
            else:
                # Step is disabled
                result = StepResult(
                    status=StepStatus.SKIPPED,
                    step=step_name,
                    message="Step disabled, skipping execution",
                    stats={"count": 0},
                )
            # Track timing and history
            duration = time.time() - step_start
            self.step_history.append(
                {
                    "index": step_index,
                    "step": step_name,
                    "enabledd": step_config.get("enabled", True),
                    "status": result.get("status", "unknown"),
                    "duration_ms": int(duration * 1000),
                }
            )
            result.timings = {
                "duration_ms": int(duration * 1000)
            }
            result.stats["db_records"] = self.papers_db.count()
            self.results = result

            if self.step_reporter:
                self.step_reporter.on_step_end(self.current_step_index, step_params, result)
            self.current_step_index = step_index + 1
            return result

        except HaltException as e:
            # HaltException is an intentional signal, not an error
            # Return a halted status but don't propagate
            duration = time.time() - step_start
            result = StepResult(
                status=StepStatus.HALTED,
                message=str(e),
                stats={"count": 0},
            )
            # Don't update index on halt - stays at current step
            # But still record in history
            self.step_history.append(
                {
                    "index": step_index,
                    "step": "halted",
                    "status": StepStatus.HALTED,
                    "duration_seconds": round(duration, 2),
                }
            )
            return result
        # All other exceptions propagate to CLI layer

    def _execute_builtin_step(
        self,
        step_name: str,
        step_params: Dict[str, Any],
        description: Optional[str],
        dry_run: bool,
    ) -> StepResult:
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
            config=step_params,
            dry_run=dry_run
        )

        # TODO: Remove this once all steps are updated to return StepResult
        if isinstance(result, dict):
            # Convert string status to StepStatus enum if needed
            status = result.get("status", StepStatus.SUCCESS)
            if isinstance(status, str):
                # Map string to StepStatus enum
                status_map = {s.value: s for s in StepStatus}
                status = status_map.get(status, StepStatus.SUCCESS)
            
            result = StepResult(
                status=status,
                message=result.get("message", ""),
                details=result
            )

        # Ensure standard fields
        result.step = step_name
        result.description = description

        return result

    def _execute_template(
        self,
        step_params: Dict[str, Any],
        description: Optional[str],
        dry_run: bool,
    ) -> StepResult:
        """
        Execute a template (recursively expand and run template steps).

        Exceptions propagate to the caller for proper error handling.
        Template steps are executed sequentially; if any step returns
        ERROR status, raises PipelineExecutionError to propagate the failure.

        Args:
            step_params: Template parameters including 'template' name
            description: Human-readable description
            dry_run: Don't actually execute steps

        Returns:
            StepResult with status and aggregated results on success

        Raises:
            ConfigurationError: If template config is invalid
            StepError: If step not found or step instantiation fails
            PipelineExecutionError: If any template step returns ERROR status
            Any other exception: Propagates for CLI to handle
        """
        template_name = step_params.get("template")
        if not template_name:
            raise ConfigurationError("run-template missing 'template' parameter")
        if template_name not in self.templates:
            raise ConfigurationError(f"Template '{template_name}' not found")

        template_steps = self.templates[template_name]
        template_results = []
        total_count = 0

        for template_step in template_steps:
            # Parse and execute each template step
            # ConfigurationError propagates for invalid config
            step_name, step_params, step_desc = self.parse_step_config(template_step)

            self.step_reporter.on_step_event(f"Executing template '{template_name}' step: '{step_name}'") 
            if step_name == "run-template":
                # Nested template call
                result = self._execute_template(step_params, step_desc, dry_run)
            else:
                # Execute regular step
                # StepError propagates if step not found
                # PipelineExecutionError propagates if step execution fails
                result = self._execute_builtin_step(step_name, step_params, step_desc, dry_run)

            template_results.append(result)
            total_count += result.stats.get("count", 0) if result.stats else 0

            if result.status == StepStatus.ERROR:
                error_msg = f"Template '{template_name}' failed at step {step_name}: {result.get('error')}"
                raise PipelineExecutionError(error_msg)

            self.step_reporter.on_step_event(f"Template step: '{step_name}' - {result.message} (Status: {result.status.value})", debug=True)

        return StepResult(
            step="run-template",
            message=f"Template '{template_name}' executed successfully",
            description=description,
            status=StepStatus.SUCCESS,
            step_results=template_results,
            stats = {
                "count": total_count,
                "steps_executed": len(template_results),
            },
            details = [],
        )

    def run_all(
        self,
        dry_run: bool = False,
        on_step_start: Optional[callable] = NOOP,
        on_step_end: Optional[callable] = NOOP,
    ) -> StepResult:
        """
        Execute all remaining steps sequentially.

        Exceptions propagate to the caller for proper error handling.

        Args:
            dry_run: Don't actually execute steps
            on_step_start: Optional callback called before each step.
                Signature: (step_index: int, step_config: Dict, total_steps: int) -> None
            on_step_end: Optional callback called after each step.
                Signature: (step_index: int, step_config: Dict, result: Dict) -> None

        Returns:
            StepResult summary of execution

        Raises:
            ConfigurationError: If step config is invalid
            StepError: If step not found or step instantiation fails
            PipelineExecutionError: If step execution fails
            Any other exception: Propagates for caller to handle
        """
        self.start_time = time.time()
        results_summary = StepResult(
            status=StepStatus.SUCCESS,
            step="run_all",
            step_results=[],
            stats={
                "steps_executed": 0,
                "steps_failed": 0,
            },
        )

        total_steps = len(self.steps)

        for i in range(self.current_step_index, total_steps):
            # Call on_step_start callback if provided
            if on_step_start:
                on_step_start(i, self.steps[i], total_steps)

            # Execute step - exceptions propagate to caller
            result = self.execute_step(i, dry_run=dry_run)

            # Call on_step_end callback if provided
            if on_step_end:
                on_step_end(i, self.steps[i], result)

            results_summary.step_results.append(result)

            if result.status == StepStatus.ERROR:
                results_summary.status = StepStatus.ERROR
                results_summary.stats["steps_failed"] += 1
                break
            elif result.status == StepStatus.HALTED:
                results_summary.status = StepStatus.HALTED
                break
            else:
                results_summary.stats["steps_executed"] += 1

        # Add timing information
        if self.start_time:
            results_summary.timings = {"total_duration_seconds": round(time.time() - self.start_time, 2)}

        return results_summary

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
            "papers_duplicates": (self.papers_db.count(primary_only=False) - self.papers_db.count(primary_only=True)),
            "current_step_index": self.current_step_index,
            "total_steps": len(self.steps),
            "steps_executed": len(self.step_history),
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
            total_duration_seconds = sum(x.get("duration_ms", 0) for x in self.step_history) / 1000.0
            stats["total_duration_seconds"] = round(total_duration_seconds, 2)

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
