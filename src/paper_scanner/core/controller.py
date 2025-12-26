# paper_scanner/core/controller.py

from abc import ABC, abstractmethod
from typing import Optional, Any, Type, Dict, TYPE_CHECKING, Callable
from pathlib import Path
from functools import wraps

from .executor import StepExecutor

if TYPE_CHECKING:
    from .reporter import AbstractStepReporter, AbstractControllerReporter


def macro_step(*names: str) -> Callable:
    """Decorator to register a function as a macro step command.

    Marks a method as a macro command with one or more aliases.
    The decorated method will be registered during controller initialization.

    Args:
        *names: Command name(s) and aliases (e.g., "step", "s" for step command and shortcut [list])

    Example:
        @macro_step("step", "s")
        def step_cmd(self):
            return StepResult(...)
    """

    def decorator(func: Callable) -> Callable:
        func._macro_names = names  # type: ignore
        return func

    return decorator

class AbstractController(ABC):
    def __init__(
        self,
        controller_reporter: "AbstractControllerReporter",
        step_reporter: "AbstractStepReporter",
        executor_class: Type[StepExecutor] = StepExecutor,
        args: Optional[Dict[str, Any]] = None,
    ):
        self.args = args or {}

        self.debug = args.debug or False
        self.verbose = args.verbose or False
        self.timings = args.timings or False
        self.quiet = args.quiet or False
        self.definition_file = args.definition
        self.dry_run = args.dry_run or False

        self.controller_reporter = controller_reporter
        self.controller_reporter.controller = self
        self.controller_reporter.debug = self.debug
        self.controller_reporter.verbose = self.verbose
        self.controller_reporter.timings = self.timings
        self.controller_reporter.quiet = self.quiet

        self.executor_class = executor_class
        self.step_reporter = step_reporter
        self.step_reporter.debug = self.debug
        self.step_reporter.verbose = self.verbose
        self.step_reporter.timings = self.timings
        self.step_reporter.quiet = self.quiet


    def initialize(self) -> bool:
        """Initialize controller and call reporter on_start"""
        try:
            # Call reporter hook FIRST
            self.controller_reporter.on_start()

            # First some generic stuff to handle
            self.cache_dir = self.args.cache_dir if hasattr(self.args, "cache_dir") else Path.home() / ".paper-scanner"
            self.cache_dir.mkdir(parents=True, exist_ok=True)

            self.executor = self.executor_class(
                general_config =  {},
                cache_dir = self.cache_dir,
                # TODO: remove these, all will be handled by reporter
                verbose = self.verbose,
                debug = self.debug,
            )
            # TODO: fix this, make implicit and do this better
            self.step_reporter.executor = self.executor
            self.executor.step_reporter = self.step_reporter

            # Then do your initialization logic
            result = self._do_initialize()
            self.controller_reporter.on_initialized()
            return result

        except Exception as e:
            self.controller_reporter.on_macro_error("initialize", e, 0)
            return False

    @abstractmethod
    def _do_initialize(self) -> bool:
        """Subclasses override this for their init logic"""
        pass

    def exec(self) -> int:
        """Execute the controller"""
        if self.definition_file:
            self.executor.load_definition(self.definition_file)

        return self._do_exec()

    @abstractmethod
    def _do_exec(self) -> int:
        """Subclasses override this for execution logic"""
        pass

    def shutdown(self) -> None:
        """Shutdown controller and call reporter on_close"""
        try:
            self._do_shutdown()
        finally:
            # ALWAYS call on_close, even if shutdown fails
            self.controller_reporter.on_close()

    @abstractmethod
    def _do_shutdown(self) -> None:
        """Subclasses override this for cleanup logic"""
        pass
