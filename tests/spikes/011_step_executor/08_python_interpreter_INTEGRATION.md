"""
Integration Guide: 08_python_interpreter.py for REPL Micro Mode

This document explains how 08_python_interpreter.py serves as the foundation
for the "micro mode" (direct Python execution) in the REPL.

ARCHITECTURE OVERVIEW
=====================

The REPL has TWO execution modes:

1. MACRO MODE (\\commands)
   - \\run, \\load, \\step, \\go, \\do, etc
   - Defined in repl.py's _handle_macro_command()
   - Controlled, structured operations

2. MICRO MODE (plain Python)
   - Direct Python code execution
   - Multiline support with "..." continuation prompt
   - Full namespace access
   - Uses PythonInterpreter class from 08_python_interpreter.py


KEY COMPONENTS
==============

PythonInterpreter Class:
- Handles Python code execution with proper eval/exec distinction
- Maintains session namespace with common objects
- Detects code completeness for multiline input
- Integrates with prompt_toolkit for history and completion

_is_code_complete() Function:
- Detects if code needs more input (returns False)
- Checks for:
  * Lines ending with colon (incomplete block)
  * Unclosed brackets/parentheses/braces
  * Proper bracket matching in string context
- Essential for "..." continuation prompts


INTEGRATION WITH REPL
=====================

In repl.py, the main loop would be:

    def run(self):
        namespace = self._create_namespace()
        session = PromptSession(...)
        
        while True:
            line = session.prompt(">>> ")
            
            if line.startswith("\\"):
                # Macro mode
                self._handle_macro_command(line)
            else:
                # Micro mode - use PythonInterpreter
                interpreter = PythonInterpreter(...)
                accumulated = line
                
                while not _is_code_complete(accumulated):
                    continuation = session.prompt("... ")
                    accumulated += "\n" + continuation
                
                interpreter._execute_code(accumulated)


NAMESPACE CONTENTS
==================

The namespace includes:
- Standard library: json, Path, datetime
- Session objects: papers_db, db, results, general_config
- Helper functions: run_step, show_papers, help_commands
- Paper_scanner imports: Definition, PapersDatabase, etc.

Users can directly access in micro mode:
    >>> papers_db.count()
    42
    >>> [p.title for p in papers_db.papers[:5]]
    ['Paper 1', 'Paper 2', ...]
    >>> results
    {'status': 'ok', 'count': 10, ...}


ADVANTAGES OVER READLINE
========================

prompt_toolkit advantages:
- Better history search (Ctrl+R)
- Syntax highlighting (PythonLexer)
- Auto-completion from namespace
- Multiline support
- Cross-platform (works on Windows too)
- Visual styles/colors

This avoids readline's limitations:
- readline is Unix-only
- Limited to single-line history
- No syntax highlighting
- Basic completion at best


CODE COMPLETION DETECTION
==========================

The _is_code_complete() function properly handles:

    [1, 2,          → incomplete (unclosed bracket)
    if x > 0:       → incomplete (colon ends)
    (1 + 2)         → complete
    def f():
        pass        → complete
    x = (          
        1 + 2       → complete (multiline OK)

Edge cases handled:
    "unclosed ( still in string"  → complete
    # Unclosed ( in comment       → complete


TESTING
=======

Run demos:
    python 08_python_interpreter.py --demo-basic
    python 08_python_interpreter.py --demo-multiline

Start interactive REPL:
    python 08_python_interpreter.py

Execute file:
    python 08_python_interpreter.py --file mycode.py

With debug:
    python 08_python_interpreter.py -d


DESIGN DECISIONS
================

1. Separate eval/exec handling
   - eval() for expressions (prints result)
   - exec() for statements (no output)
   - Last-line optimization for multiline code

2. Manual bracket counting
   - More reliable than compile() alone
   - Detects incomplete input immediately
   - Respects string/comment context

3. prompt_toolkit over readline
   - Better UX for Python REPL
   - Proper history and search
   - Syntax highlighting ready

4. Namespace separation
   - Each interpreter session has own namespace
   - Session state preserved across commands
   - Clean separation from macro commands
"""
