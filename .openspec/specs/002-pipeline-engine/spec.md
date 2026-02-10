# Pipeline Engine Specification

**Domain:** Execution
**Version:** 1.0.0
**Status:** Implemented
**Date:** 2026-02-10

## Overview

The Pipeline Engine is the core execution platform for paper-scanner workflows. It orchestrates definition-driven, step-based processing through a YAML-configured pipeline. The engine manages the complete lifecycle of workflow execution: definition loading, step registration, checkpoint persistence, and result aggregation. It provides multiple execution modes (batch via `run_all()`, step-by-step via `execute_next_step()`, and interactive via REPL) with comprehensive error handling and statistical tracking.

### Philosophy

1. **Definition-First Design**: Workflows are declaratively defined in YAML with stepwise sequences, templates, and project metadata—the engine interprets and executes these definitions without modification.

2. **Three-Level Configuration Model**: Project settings (general_config), step-specific parameters (step_config), and runtime flags (verbose/dry_run/debug) are kept orthogonal and composable.

3. **Checkpoint-Driven Resilience**: Workflow state is automatically persisted to local checkpoints after each step, enabling safe resumption from interruption or failure without reprocessing.

### Key Capabilities

- **YAML Definition Loading** — Parse project metadata, templates, and steps from YAML with early validation
- **Lazy Step Registry** — On-demand step class loading with minimal startup overhead
- **Template System** — Nested template expansion for reusable step sequences
- **Step Execution & Lifecycle** — Standardized validate→execute pattern with config passing and runtime flags
- **Checkpoint Management** — Save/load/resume workflows from checkpoint files using MD5-hashed naming
- **Standardized Results** — StepResult dataclass with status enums (SUCCESS/WARNING/ERROR/HALTED/SKIPPED)
- **Event Reporting** — Observer pattern callbacks for step execution and timing collection

---

## RFC 2119 Keywords

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).

---

## Requirements

### Requirement: YAML Definition Loading

The system SHALL load YAML definition files containing project metadata, templates, and steps sequences.

#### Scenario: Load valid definition file
- GIVEN a YAML definition file at `/tmp/pipeline.yaml` with `project`, `templates`, and `steps` sections
- WHEN `executor.load_definition(Path("/tmp/pipeline.yaml"))` is called
- THEN `executor.definition` is populated, `executor.templates` contains expanded templates, and `executor.steps` contains step configurations

#### Scenario: Populate general_config from project section
- GIVEN a YAML definition with `project: { name: "my-project", researcher: "Alice", created_at: "2026-01-01" }`
- WHEN `load_definition()` is called
- THEN `GeneralConfigLoader.load(executor.general_config, definition["project"])` updates the executor's `general_config` with fields from FIELD_MAPPING: `project_name`, `description`, `created_at`, `researcher`, `research_question`, `research_dimensions`, `email`

#### Scenario: Raise error on missing definition file
- GIVEN a file path `/tmp/nonexistent.yaml` that does not exist
- WHEN `executor.load_definition(Path("/tmp/nonexistent.yaml"))` is called
- THEN `FileNotFoundError` is raised

#### Scenario: Raise error on empty definition file
- GIVEN a YAML file that parses to `None` or empty dict
- WHEN `load_definition()` is called
- THEN `ValueError` is raised with message "Definition file is empty"

#### Scenario: Validate template references early
- GIVEN a definition with steps containing `run-template: { template: "missing_template" }` but no matching `templates` section
- WHEN `load_definition()` is called
- THEN `ValueError` is raised with message containing "Referenced template 'missing_template' not found"

---

### Requirement: YAML Step Configuration Parsing

The system SHALL parse Ansible-style step configurations from YAML with builtin prefix and flexible parameter passing.

#### Scenario: Parse step with builtin.<name> key and params
- GIVEN a step configuration `{ step: "Import data", builtin.bibtex_import: { file: "refs.bib" } }`
- WHEN `StepExecutor.parse_step_config(step_config)` is called
- THEN it returns `("bibtex_import", { "file": "refs.bib" }, "Import data")`

#### Scenario: Use step value as step name when valid
- GIVEN a step configuration `{ step: "bibtex_import", builtin.bibtex_import: { file: "refs.bib" } }`
- WHEN `parse_step_config()` is called
- THEN `step_name` is set to `"bibtex_import"` (from step value, not from builtin key)

#### Scenario: Use step value as description when it contains spaces
- GIVEN a step configuration `{ step: "Import bibliography from local file", builtin.bibtex_import: { file: "refs.bib" } }`
- WHEN `parse_step_config()` is called
- THEN `step_name` is `"bibtex_import"` and `description` is `"Import bibliography from local file"`

#### Scenario: Raise error on missing step key
- GIVEN a step configuration `{ builtin.bibtex_import: { file: "refs.bib" } }` (no "step" key)
- WHEN `parse_step_config()` is called
- THEN `ConfigurationError` is raised with message "Step configuration missing 'step' key"

#### Scenario: Raise error on missing builtin key
- GIVEN a step configuration `{ step: "something" }` (no "builtin.*" key)
- WHEN `parse_step_config()` is called
- THEN `ConfigurationError` is raised with message "Step configuration missing 'builtin.<step>' key"

---

### Requirement: Template System

The system SHALL support template definitions with nested step sequences and recursive template execution.

#### Scenario: Store templates by name
- GIVEN a YAML definition with `templates: [{ template: "review_papers", steps: [...] }]`
- WHEN `load_definition()` is called
- THEN `executor.templates["review_papers"]` equals the `steps` list from the template

#### Scenario: Execute run-template step
- GIVEN a step `{ step: "Review workflow", builtin.run-template: { template: "review_papers" } }`
- WHEN `execute_step(index)` is called on this step
- THEN `_execute_template()` is invoked, which recursively executes all steps in `templates["review_papers"]` sequentially

#### Scenario: Support nested templates
- GIVEN a template "outer" that contains a step `builtin.run-template: { template: "inner" }`
- WHEN `_execute_template()` processes the "outer" template
- THEN it recursively calls `_execute_template()` for the "inner" template

#### Scenario: Return aggregated StepResult from template
- GIVEN a template with 3 steps that all return SUCCESS
- WHEN `_execute_template()` completes
- THEN it returns a StepResult with:
  - `status=StepStatus.SUCCESS`
  - `step="run-template"`
  - `stats["steps_executed"]=3`
  - `stats["count"]=sum of all step counts`
  - `step_results=[list of individual step results]`

#### Scenario: Halt template execution on ERROR status
- GIVEN a template where step 2 returns ERROR status
- WHEN `_execute_template()` processes step 2
- THEN `PipelineExecutionError` is raised with message containing the failed step name

---

### Requirement: Lazy Step Registry

The system SHALL support lazy-loading of step classes with on-demand imports to minimize startup overhead.

#### Scenario: Step registry initialized on first access
- GIVEN a new StepExecutor instance
- WHEN `StepExecutor.get_builtin_steps()` is called
- THEN it creates a `LazyStepRegistry(STEP_REGISTRY_PATHS)` if `_step_registry` is None, caches it, and returns it

#### Scenario: LazyStepRegistry initializes with step names only
- GIVEN `STEP_REGISTRY_PATHS = {"bibtex_import": "paper_scanner.steps.bibtex:BibtexImportStep", ...}`
- WHEN `LazyStepRegistry(STEP_REGISTRY_PATHS)` is constructed
- THEN the dict keys are populated but values remain `None` until accessed

#### Scenario: Step classes loaded on first access
- GIVEN a LazyStepRegistry and first access to `registry["bibtex_import"]`
- WHEN `__getitem__("bibtex_import")` is called
- THEN it parses `"paper_scanner.steps.bibtex:BibtexImportStep"` into module and class name, imports the module, retrieves the class, caches it in `self._loaded`, updates the dict, and returns the class

#### Scenario: Cached steps returned on subsequent access
- GIVEN a LazyStepRegistry where `"bibtex_import"` has been previously loaded
- WHEN `__getitem__("bibtex_import")` is called again
- THEN the cached class from `self._loaded["bibtex_import"]` is returned without reimporting

#### Scenario: KeyError raised for unknown steps
- GIVEN a LazyStepRegistry and a request for unknown step `"nonexistent_step"`
- WHEN `__getitem__("nonexistent_step")` is called
- THEN `KeyError("Unknown step: nonexistent_step")` is raised

#### Scenario: items() and values() trigger lazy loading
- GIVEN a LazyStepRegistry with multiple steps
- WHEN `registry.items()` or `registry.values()` is iterated
- THEN all steps are lazy-loaded (the iterator yields loaded step classes)

---

### Requirement: Step Lifecycle

The system SHALL enforce a validate→execute lifecycle for steps with standardized configuration passing.

#### Scenario: BaseStep.validate() called at parse time
- GIVEN a step class (e.g., `BibtexImportStep`) with `validate()` static method
- WHEN `load_definition()` processes steps (future: planned enhancement)
- THEN validation can be performed early without instantiation

#### Scenario: Step instantiation with general_config, db, cache_dir
- GIVEN a StepExecutor and step name `"bibtex_import"`
- WHEN `executor.get_step("bibtex_import")` is called
- THEN it instantiates `BibtexImportStep(general_config=executor.general_config, executor=executor, db=executor.papers_db, cache_dir=executor.cache_dir, on_event=callback)`

#### Scenario: execute() called with step_config and runtime flags
- GIVEN a step instance
- WHEN `step_instance.execute(config=step_params, dry_run=False)` is called
- THEN the step processes `step_params` and can access `self.general_config`, `self.db`, `self.cache_dir`

#### Scenario: Runtime flags passed to step execution
- GIVEN a step execution with `execute_step(..., dry_run=True)`
- WHEN `_execute_builtin_step()` invokes `step_instance.execute(config=..., dry_run=True)`
- THEN the step sees `dry_run=True` and skips persistence

#### Scenario: Step result converted to StepResult if dict
- GIVEN a step that returns `{"status": "success", "message": "Done", "count": 5}`
- WHEN `_execute_builtin_step()` processes the result
- THEN the dict is converted to `StepResult(status=StepStatus.SUCCESS, message="Done", stats={"count": 5})`

---

### Requirement: Step Execution & Error Handling

The system SHALL execute steps sequentially, catch HaltException as a signal, and propagate other exceptions.

#### Scenario: Execute single step by index
- GIVEN `executor.steps` with 5 steps and `step_index=2`
- WHEN `executor.execute_step(2)` is called
- THEN it parses `self.steps[2]`, instantiates the step, calls `execute()`, and returns a StepResult

#### Scenario: Disabled steps are skipped
- GIVEN a step configuration with `enabled: false`
- WHEN `execute_step(index)` processes the step
- THEN it returns `StepResult(status=StepStatus.SKIPPED, message="Step disabled, skipping execution")`

#### Scenario: Step index out of range raises StepError
- GIVEN `executor.steps` with 3 steps and `step_index=5`
- WHEN `execute_step(5)` is called
- THEN `StepError("Step index out of range: 5")` is raised

#### Scenario: HaltException returns HALTED status
- GIVEN a step that raises `HaltException("Workflow paused by user")`
- WHEN `execute_step()` catches it
- THEN it returns `StepResult(status=StepStatus.HALTED, message="Workflow paused by user")` and does NOT update `current_step_index`

#### Scenario: Other exceptions propagate to caller
- GIVEN a step that raises `RuntimeError("Database connection failed")`
- WHEN `execute_step()` executes the step
- THEN `RuntimeError` is caught and propagates to the CLI layer for handling

#### Scenario: Timing tracked and attached to result
- GIVEN a step execution with start time captured
- WHEN `execute_step()` completes
- THEN `result.timings = {"duration_ms": int(duration_ms)}` and duration is recorded in `step_history`

#### Scenario: Step history records execution metadata
- GIVEN a completed step execution
- WHEN step_history is updated
- THEN it appends `{"index": step_index, "step": step_name, "status": status_value, "duration_ms": ms}`

---

### Requirement: Batch Execution (run_all)

The system SHALL execute all remaining steps sequentially with early exit on ERROR or HALTED.

#### Scenario: Execute all remaining steps
- GIVEN `executor.current_step_index=0` and 4 total steps, all returning SUCCESS
- WHEN `executor.run_all()` is called
- THEN it loops from `current_step_index` to `len(steps)`, calling `execute_step()` for each

#### Scenario: Return aggregated summary
- GIVEN successful execution of 3 steps
- WHEN `run_all()` completes
- THEN it returns `StepResult(status=StepStatus.SUCCESS, step="run_all", step_results=[...], stats={"steps_executed": 3, "steps_failed": 0})`

#### Scenario: Stop on ERROR status
- GIVEN steps where step 2 returns ERROR
- WHEN `run_all()` processes step 2
- THEN it breaks out of the loop and returns `StepResult(status=StepStatus.ERROR, stats={"steps_failed": 1})`

#### Scenario: Stop on HALTED status
- GIVEN steps where step 2 returns HALTED
- WHEN `run_all()` processes step 2
- THEN it breaks out of the loop and returns `StepResult(status=StepStatus.HALTED)`

#### Scenario: Record total execution duration
- GIVEN `run_all()` execution spanning multiple steps
- WHEN it completes
- THEN `results.timings["total_duration_seconds"]` is set to the sum of all step durations in seconds

---

### Requirement: Checkpoint Management

The system SHALL save and load workflow state using MD5-hashed checkpoint files in the checkpoint directory.

#### Scenario: Checkpoint directory created on load_definition
- GIVEN `executor.cache_dir = Path("/tmp/cache")`
- WHEN `load_definition(...)` is called
- THEN `cache_dir / "checkpoints"` directory is created

#### Scenario: Checkpoint file naming convention
- GIVEN project name `"my-research"` (MD5 hash prefix: `abc12345`) and `step_index=3`
- WHEN a checkpoint is saved
- THEN the file is named `checkpoint_abc12345_step_003.json`

#### Scenario: Checkpoint JSON contains papers and metadata
- GIVEN `executor.papers_db` with 5 papers
- WHEN `executor.checkpoint()` is called
- THEN it writes JSON with keys: `project_name`, `step_index`, `timestamp`, `papers_count`, `papers` (list of Paper.model_dump())

#### Scenario: Find latest checkpoint and resume
- GIVEN checkpoint files `checkpoint_abc12345_step_000.json`, `step_001.json`, `step_002.json`
- WHEN `load_checkpoint()` is called
- THEN `_find_latest_checkpoint()` returns `(3, checkpoint_file_for_step_002)` (next step index and file)

#### Scenario: Load checkpoint restores papers database
- GIVEN a checkpoint file with 5 papers
- WHEN `_load_checkpoint_file(checkpoint_file)` is called
- THEN `executor.papers_db.from_list([Paper(...), ...])` is called with deserialized papers

#### Scenario: Skip checkpoint loading on flag
- GIVEN `skip_checkpoint=True`
- WHEN `load_checkpoint(skip_checkpoint=True)` is called
- THEN checkpoint loading is skipped and execution starts from step 0

#### Scenario: Clear all checkpoints before execution
- GIVEN `clear_checkpoint=True` and existing checkpoint directory
- WHEN `load_checkpoint(clear_checkpoint=True)` is called
- THEN the entire `checkpoints/` directory is removed with `shutil.rmtree()`

#### Scenario: Raise CheckpointError on corrupt file
- GIVEN a checkpoint file with invalid JSON
- WHEN `_load_checkpoint_file()` is called
- THEN `CheckpointError` is raised with message "Corrupt checkpoint file"

#### Scenario: Raise CheckpointError on invalid paper data
- GIVEN a checkpoint file where papers list contains invalid Pydantic data
- WHEN `_load_checkpoint_file()` is called
- THEN `CheckpointError` is raised with message "Invalid paper data in checkpoint"

---

### Requirement: Checkpoint Metadata

The system SHALL track project hash, step indices, and paper counts in checkpoints.

#### Scenario: Project hash derived from project_name
- GIVEN `general_config["project_name"] = "my-research"`
- WHEN `_get_project_hash()` is called
- THEN it returns `hashlib.md5("my-research".encode()).hexdigest()[:8]` (8-char prefix)

#### Scenario: Checkpoint includes step_index
- GIVEN `executor.current_step_index = 2` when checkpoint is saved
- WHEN checkpoint JSON is written
- THEN the `step_index` field in JSON equals 2

#### Scenario: Checkpoint timestamp in ISO format
- GIVEN checkpoint save operation
- WHEN checkpoint JSON is written
- THEN `timestamp` field is set to `datetime.now().isoformat()` (ISO 8601 string)

---

### Requirement: Step Progress & Navigation

The system SHALL provide methods to query current execution state without modifying it.

#### Scenario: has_steps property
- GIVEN executor with loaded definition containing 3 steps
- WHEN `executor.has_steps` is accessed
- THEN it returns `True`

#### Scenario: has_next_step property
- GIVEN `executor.current_step_index = 2` and 4 total steps
- WHEN `executor.has_next_step` is accessed
- THEN it returns `True`

#### Scenario: step_progress tuple
- GIVEN `executor.current_step_index = 1` and 4 total steps
- WHEN `executor.step_progress` is accessed
- THEN it returns `(1, 4)`

#### Scenario: describe_next_step returns step info
- GIVEN `executor.current_step_index = 0`
- WHEN `executor.describe_next_step()` is called
- THEN it returns a dict with `index`, `name`, `description`, `is_template`, `config`

#### Scenario: describe_last_step returns previous step info
- GIVEN `executor.current_step_index = 2` (step 1 has been executed)
- WHEN `executor.describe_last_step()` is called
- THEN it returns a dict for step 1 with the same structure

#### Scenario: execute_next_step convenience wrapper
- GIVEN `executor.has_next_step = True`
- WHEN `executor.execute_next_step(dry_run=False)` is called
- THEN it calls `execute_step(executor.current_step_index, dry_run=False)` and returns the result

#### Scenario: execute_next_step returns FINAL_STEP when no more steps
- GIVEN `executor.has_next_step = False`
- WHEN `executor.execute_next_step()` is called
- THEN it returns the predefined `FINAL_STEP` constant

---

### Requirement: Session State Management

The system SHALL manage session state (database, results, history) with reset capabilities.

#### Scenario: Reset execution state
- GIVEN executor with step_history and current_step_index > 0
- WHEN `executor.reset(scope="execution")` is called
- THEN `results`, `step_history`, `current_step_index`, `step_state`, and `papers_db` are cleared but `definition` and `templates` remain

#### Scenario: Reset definition state
- GIVEN executor with definition and templates loaded
- WHEN `executor.reset(scope="definition")` is called
- THEN `definition`, `templates`, and `steps` are cleared, and execution state is also reset

#### Scenario: Full reset
- GIVEN executor with all state populated
- WHEN `executor.reset(scope="all")` is called
- THEN all state is cleared to initialization state

#### Scenario: Raise ValueError on invalid reset scope
- GIVEN an invalid scope string `"invalid_scope"`
- WHEN `executor.reset(scope="invalid_scope")` is called
- THEN `ValueError` is raised with message containing valid scopes

#### Scenario: Step enable/disable
- GIVEN a step configuration with `enabled=True`
- WHEN `executor.disable_step(index)` is called
- THEN `executor.steps[index]["enabled"]` is set to `False`

#### Scenario: Get session state for REPL
- GIVEN executor with execution history
- WHEN `executor.get_session_state()` is called
- THEN it returns a dict with `papers_db`, `papers_count`, `current_step_index`, `total_steps`, `step_history`, `results`, `last_step`, `current_step`

---

### Requirement: Statistics & Reporting

The system SHALL collect and report comprehensive execution statistics.

#### Scenario: Collect step statistics
- GIVEN execution of 3 steps with 10, 5, and 3 papers processed
- WHEN `executor.get_stats()` is called
- THEN stats include `papers_total`, `papers_unique`, `papers_duplicates`, `current_step_index`, `steps_executed`

#### Scenario: Track available steps in inventory
- GIVEN a StepExecutor with lazy registry
- WHEN `get_stats()` is called
- THEN `stats["inventory"]["builtin_steps"]` lists all available step names

#### Scenario: Report template names in inventory
- GIVEN executor with templates `"review_papers"` and `"import_workflow"`
- WHEN `get_stats()` is called
- THEN `stats["inventory"]["templates"]` contains both names

#### Scenario: Calculate total duration from step history
- GIVEN step_history with durations `[100, 200, 150]` milliseconds
- WHEN `get_stats()` is called
- THEN `stats["total_duration_seconds"]` equals `0.45`

#### Scenario: Report step history with timing
- GIVEN completed step executions
- WHEN `get_stats()` is called
- THEN `stats["step_history"]` is a list of dicts with `index`, `step`, `status`, `duration_ms`

---

### Requirement: Event Reporting & Callbacks

The system SHALL invoke reporter callbacks for workflow and step lifecycle events.

#### Scenario: on_step_start called before step execution
- GIVEN `executor.step_reporter` set to an `AbstractStepReporter` implementation
- WHEN `execute_step()` processes a step
- THEN `step_reporter.on_step_start(current_step_index, step_config, total_steps)` is called

#### Scenario: on_step_end called after step execution
- GIVEN a completed step execution
- WHEN `execute_step()` finishes
- THEN `step_reporter.on_step_end(step_index, step_config, result)` is called

#### Scenario: on_step_event called during execution
- GIVEN step execution (e.g., template expansion)
- WHEN `_execute_template()` processes steps
- THEN `step_reporter.on_step_event(message)` is called with descriptive messages

#### Scenario: on_definition_loaded called when definition is loaded
- GIVEN a valid YAML definition
- WHEN `load_definition()` completes successfully
- THEN `step_reporter.on_definition_loaded(definition_file, definition)` is called

---

### Requirement: General Configuration Loading

The system SHALL load project-level configuration from YAML definition into general_config.

#### Scenario: GeneralConfigLoader.load() maps YAML to internal keys
- GIVEN YAML `project: { name: "my-project", researcher: "Alice", created_at: "2026-01-01" }`
- WHEN `GeneralConfigLoader.load(general_config, project)` is called
- THEN `general_config["project_name"] = "my-project"` and `general_config["researcher"] = "Alice"`

#### Scenario: FIELD_MAPPING defines YAML keys
- GIVEN `FIELD_MAPPING = {"project_name": "name", "researcher": "researcher", ...}`
- WHEN `load()` is called
- THEN only fields present in FIELD_MAPPING are updated

#### Scenario: Get defaults for all config fields
- GIVEN no prior configuration
- WHEN `GeneralConfigLoader.get_defaults()` is called
- THEN it returns a dict with all FIELD_MAPPING keys set to defaults (empty strings, empty lists, current ISO timestamp)

---

### Requirement: StepResult Standardization

The system SHALL represent step outcomes with a standardized StepResult dataclass.

#### Scenario: StepResult with required fields
- GIVEN a step that completes with status and message
- WHEN `StepResult(status=StepStatus.SUCCESS, message="Processed 5 papers")` is created
- THEN it has `status=StepStatus.SUCCESS` and `message="Processed 5 papers"`

#### Scenario: StepResult statistics dict
- GIVEN a step with multiple outcomes (processed, skipped, errors)
- WHEN `StepResult(..., stats={"count": 5, "processed": 4, "skipped": 1})` is created
- THEN `result.stats["count"]` equals 5

#### Scenario: StepResult status enums
- GIVEN StepResult construction with different statuses
- WHEN results are created with `StepStatus.SUCCESS`, `WARNING`, `ERROR`, `HALTED`, `SKIPPED`
- THEN `result.status` is the enum value, not a string

#### Scenario: StepResult aggregates sub-results
- GIVEN a template execution producing 3 step results
- WHEN `StepResult(..., step_results=[result1, result2, result3])` is created
- THEN `result.step_results` is the list

#### Scenario: Dict-like access for backward compatibility
- GIVEN a StepResult with `message="Success"`
- WHEN `result["message"]` is accessed (dict syntax)
- THEN it returns `"Success"` (via `__getitem__`)

#### Scenario: to_dict() serialization
- GIVEN a StepResult with all fields populated
- WHEN `result.to_dict()` is called
- THEN it returns a dict with all fields, with `status` as string value and nested `step_results` as dicts

#### Scenario: FINAL_STEP predefined constant
- GIVEN the predefined `FINAL_STEP` constant
- WHEN used as return value for `execute_next_step()` when no more steps
- THEN `FINAL_STEP.status == StepStatus.FINAL` and `FINAL_STEP.message == "No more steps to execute"`

---

### Requirement: CLI Run Command

The system SHALL execute a complete workflow with optional checkpoint, timing, and output options.

#### Scenario: Run with definition file argument
- GIVEN a YAML definition at `/tmp/pipeline.yaml`
- WHEN CLI command `paper-scanner run /tmp/pipeline.yaml` is invoked
- THEN `execute_run(Path("/tmp/pipeline.yaml"), ...)` is called

#### Scenario: Run with --verbose flag
- GIVEN CLI command with `--verbose`
- WHEN `execute_run(..., verbose=True)` is invoked
- THEN executor operates with `executor.verbose = True` and reporters show verbose output

#### Scenario: Run with --dry-run flag
- GIVEN CLI command with `--dry-run`
- WHEN steps are executed with `dry_run=True`
- THEN no persistent changes are made

#### Scenario: Run with --no-checkpoint flag
- GIVEN CLI command with `--no-checkpoint`
- WHEN `execute_run(..., skip_checkpoint=True)` is called
- THEN `load_checkpoint(skip_checkpoint=True)` skips loading prior checkpoints and starts from step 0

#### Scenario: Run with --clear-checkpoint flag
- GIVEN existing checkpoint files and CLI with `--clear-checkpoint`
- WHEN `execute_run(..., clear_checkpoint=True)` is called
- THEN `load_checkpoint(clear_checkpoint=True)` removes all checkpoint files and starts fresh

#### Scenario: Run with --timings flag
- GIVEN CLI command with `--timings`
- WHEN execution completes
- THEN timing information is displayed for each step

#### Scenario: Run with --debug flag
- GIVEN CLI command with `--debug`
- WHEN `execute_run(..., debug=True)` is called
- THEN executor sets `debug=True` and detailed debug output is produced

#### Scenario: Run with --cache-dir argument
- GIVEN CLI command with `--cache-dir /tmp/my-cache`
- WHEN `execute_run(..., cache_dir=Path("/tmp/my-cache"))` is called
- THEN executor uses that directory for checkpoints and cache

#### Scenario: Run with --output flag
- GIVEN CLI command with `-o results.json`
- WHEN execution completes
- THEN results are written to `results.json` in JSON format

---

### Requirement: CLI Validate Command

The system SHALL validate a definition file for correctness without executing steps.

#### Scenario: Validate definition file syntax
- GIVEN a YAML definition file
- WHEN `execute_validate(definition_file, ...)` is called
- THEN the definition is parsed and validated for structure (project, templates, steps sections)

#### Scenario: Validate all template references
- GIVEN a definition with steps referencing templates
- WHEN validation runs
- THEN all template references are checked against defined templates

#### Scenario: Validate step configurations
- GIVEN steps in the definition
- WHEN validation runs
- THEN each step's structure (step key, builtin key, params) is verified

#### Scenario: Return exit code 0 on success
- GIVEN a valid definition file
- WHEN validation completes
- THEN exit code is 0

#### Scenario: Return exit code 1 on validation failure
- GIVEN an invalid definition file
- WHEN validation encounters an error
- THEN exit code is 1 and error message is printed

---

### Requirement: CLI REPL Command

The system SHALL provide interactive step-by-step execution with command history and database inspection.

#### Scenario: REPL mode loads definition optionally
- GIVEN CLI command `paper-scanner repl -f pipeline.yaml`
- WHEN `execute_repl(args)` starts
- THEN the definition file is loaded and execution is set up in REPL mode

#### Scenario: REPL step command executes next step
- GIVEN REPL mode with steps available
- WHEN user enters `step` command
- THEN `executor.execute_next_step()` is invoked and result is displayed

#### Scenario: REPL info command shows state
- GIVEN REPL mode with execution history
- WHEN user enters `info` command
- THEN `executor.get_stats()` is called and state is displayed

#### Scenario: REPL db command inspects database
- GIVEN REPL mode with papers in database
- WHEN user enters `db` command
- THEN database statistics and paper count are displayed

#### Scenario: REPL quit command exits
- GIVEN REPL mode
- WHEN user enters `quit` or `exit`
- THEN REPL session terminates

#### Scenario: REPL with --no-autorun flag
- GIVEN CLI command with `-n` flag
- WHEN definition is loaded
- THEN REPL enters interactive mode immediately without auto-executing

#### Scenario: REPL with --quit flag exits after definition
- GIVEN CLI command with `-x` flag
- WHEN definition execution completes
- THEN REPL terminates immediately

---

### Requirement: CLI Cache Commands

The system SHALL manage caches for checkpoints, PDFs, and API responses.

#### Scenario: Cache info command
- GIVEN `paper-scanner cache info`
- WHEN `execute_cache_info(cache_dir=...)` is called
- THEN it displays checkpoint files, PDF cache contents, and file counts

#### Scenario: Cache clear checkpoints
- GIVEN `paper-scanner cache clear checkpoints`
- WHEN command runs
- THEN the checkpoint directory is removed and recreated (empty)

#### Scenario: Cache clear pdfs
- GIVEN `paper-scanner cache clear pdfs`
- WHEN command runs
- THEN all PDF files in the PDF cache are deleted

#### Scenario: Cache load PDFs from folder
- GIVEN `paper-scanner cache load ./papers --dry-run`
- WHEN `execute_cache_load(folder, dry_run=True)` is called
- THEN PDF files are scanned but not moved to cache (dry-run mode)

#### Scenario: Cache load PDFs without dry-run
- GIVEN `paper-scanner cache load ./papers`
- WHEN files are processed
- THEN PDFs are moved to the cache directory with MD5-hashed names

#### Scenario: Manual cache load bibtex
- GIVEN `paper-scanner cache manual load refs.bib`
- WHEN `execute_cache_load_manual(bibtex_file, ...)` is called
- THEN bibtex entries are parsed and cached

#### Scenario: Manual cache clear
- GIVEN `paper-scanner cache manual clear`
- WHEN command runs
- THEN the manual handler cache is cleared

---

### Requirement: CLI Database Commands

The system SHALL provide database inspection and manipulation commands.

#### Scenario: DB stats command
- GIVEN `paper-scanner db stats`
- WHEN `execute_db_stats(database_url=...)` is called
- THEN database statistics (table counts, record counts) are displayed

#### Scenario: DB clear all tables
- GIVEN `paper-scanner db clear`
- WHEN command runs (or with `--dry-run` to preview)
- THEN all tables are cleared of data

#### Scenario: DB clear specific table
- GIVEN `paper-scanner db clear papers`
- WHEN command runs
- THEN only the `papers` table is cleared

#### Scenario: DB with custom database URL
- GIVEN `paper-scanner db stats --database-url postgres://...`
- WHEN command runs
- THEN it connects to the specified PostgreSQL database

---

### Requirement: Exception Hierarchy & Error Handling

The system SHALL define a clear exception hierarchy for different error categories.

#### Scenario: ConfigurationError for invalid config
- GIVEN a malformed YAML or invalid step configuration
- WHEN parsing occurs
- THEN `ConfigurationError` is raised with descriptive message

#### Scenario: StepError for step discovery failures
- GIVEN a requested step that doesn't exist
- WHEN `get_step("unknown_step")` is called
- THEN `StepError("Unknown step: unknown_step...")` is raised

#### Scenario: CheckpointError for checkpoint I/O failures
- GIVEN a checkpoint file that cannot be read or parsed
- WHEN `_load_checkpoint_file()` is called
- THEN `CheckpointError` is raised with the specific I/O or parsing issue

#### Scenario: PipelineExecutionError for step execution failures
- GIVEN a step that returns ERROR status
- WHEN template execution detects the error
- THEN `PipelineExecutionError` is raised with context about which step failed

#### Scenario: PaperScannerError is base class
- GIVEN all custom exceptions
- WHEN caught as `PaperScannerError`
- THEN all pipeline-specific exceptions are subclasses of it

---

### Requirement: Three-Level Configuration Model

The system SHALL enforce orthogonal separation of project, step, and runtime configuration.

#### Scenario: General config persists across steps
- GIVEN `general_config = {"project_name": "my-project", "researcher": "Alice"}`
- WHEN multiple steps execute
- THEN each step has access to the same `general_config` (not modified per-step)

#### Scenario: Step config isolated to step execution
- GIVEN step 1 with `config = {"param": "value1"}` and step 2 with `config = {"param": "value2"}`
- WHEN steps execute sequentially
- THEN each step only sees its own config, not the previous step's config

#### Scenario: Runtime flags uniform across execution
- GIVEN `verbose=True`, `dry_run=False`, `debug=False` passed to execution
- WHEN all steps execute
- THEN each step sees the same runtime flag values

#### Scenario: Step config can reference general config values
- GIVEN general_config with `project_name="my-research"`
- WHEN a step executes with `executor.general_config`
- THEN the step can use `self.general_config["project_name"]` for dynamic behavior

---

## Metadata

### Implementation Files

- `/Users/iheitlager/wc/paper-scanner-worktree/agent-1/src/paper_scanner/core/executor.py` — StepExecutor class with definition loading, checkpoint management, step execution, and session state
- `/Users/iheitlager/wc/paper-scanner-worktree/agent-1/src/paper_scanner/core/cache.py` — JSONFileCache and PDFCache for API responses and PDF storage
- `/Users/iheitlager/wc/paper-scanner-worktree/agent-1/src/paper_scanner/core/general_config.py` — GeneralConfigLoader for project-level configuration
- `/Users/iheitlager/wc/paper-scanner-worktree/agent-1/src/paper_scanner/core/step_result.py` — StepResult dataclass and status enums
- `/Users/iheitlager/wc/paper-scanner-worktree/agent-1/src/paper_scanner/core/reporter.py` — AbstractStepReporter and AbstractControllerReporter callback interfaces
- `/Users/iheitlager/wc/paper-scanner-worktree/agent-1/src/paper_scanner/core/exceptions.py` — Exception hierarchy (ConfigurationError, StepError, CheckpointError, PipelineExecutionError)
- `/Users/iheitlager/wc/paper-scanner-worktree/agent-1/src/paper_scanner/cli/paper_processor.py` — CLI entry point with command handlers (run, validate, repl, info, cache, db)
- `/Users/iheitlager/wc/paper-scanner-worktree/agent-1/src/paper_scanner/steps/base.py` — BaseStep abstract class with lifecycle (validate, execute)

### Test Coverage

Test coverage for the Pipeline Engine would include:
- Unit tests for StepExecutor (definition loading, step parsing, checkpoint lifecycle)
- Unit tests for LazyStepRegistry (lazy loading, caching, error cases)
- Unit tests for template expansion (nesting, error propagation)
- Unit tests for checkpoint I/O (save, load, corruption handling)
- Integration tests for full workflow execution (run_all with multiple steps)
- CLI integration tests (run, validate, repl, cache, db commands)

### Related Specifications

- [001-data-models](../001-data-models/spec.md) — Paper, Database, and core data models
- [003-step-implementations](../003-step-implementations/spec.md) — Specific builtin step definitions (bibtex_import, checkpoint, etc.)

---

## References

- **RFC 2119**: https://datatracker.ietf.org/doc/html/rfc2119
- **Pydantic**: https://docs.pydantic.dev/
- **YAML Specification**: https://yaml.org/spec/

---

**License:** Apache-2.0
**Copyright:** 2026 Ilja Heitlager
