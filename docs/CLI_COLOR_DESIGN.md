"""
# CLI/REPL Color Design System

## Philosophy

The paper-scanner CLI uses a minimal, purposeful color palette to guide user attention without overwhelming. Each color has a specific meaning and context.

---

### White
**Context**: Primary content and actions (breaks up colored sections)  
**Usage**:
- Step names and descriptions (main content)
- User-facing action descriptions
- Primary information in mixed-color lines
- Readability breakpoint between colored elements

**Rationale**: White (uncolored text) provides visual breathing room and clarity. When combining cyan labels with content, use white for the content to create hierarchy.

**Examples**:
```
[cyan]Executing:[/cyan] [white]Export processed papers[/white] [dim](builtin.export)[/dim]
[cyan]Template:[/cyan] [white]Analysis Pipeline[/white]
[cyan]Step:[/cyan] [white]Deduplicate by DOI[/white] [dim](step 3)[/dim]
```

---

### Purple
**Context**: Secondary step/action color (accent for variety)  
**Usage**:
- Alternate with white for visual distinction between steps
- Highlight different step categories (builtin vs template)
- Create visual rhythm in batch mode output
- Secondary action descriptions

**Rationale**: Purple provides visual variety without adding semantic weight. Alternating between white and purple step names creates visual separation in longer step lists.

**Examples**:
```
[cyan]Executing:[/cyan] [white]Import bibtex[/white]
[cyan]Executing:[/cyan] [magenta]Deduplicate papers[/magenta]
[cyan]Executing:[/cyan] [white]Extract references[/white]
[cyan]Executing:[/cyan] [magenta]Generate report[/magenta]
```

Or for step categories:
```
[cyan]Template:[/cyan] [magenta]Analysis Pipeline[/magenta] [dim](3 steps)[/dim]
[cyan]Step 1:[/cyan] [white]Load files[/white] [dim](builtin.load_files)[/dim]
```

---

## Color Scheme

### Blue
**Context**: REPL/CLI interface elements  
**Usage**:
- Command prompts (`[{current}/{total}] > `)
- General informational messages
- Status updates that don't require action

**Examples**:
```
[bold blue][1/10] > [/bold blue]
[blue]ℹ Executing next step...[/blue]
[blue]✓ Step completed[/blue]
```

---

### Cyan
**Context**: Verbose/detailed information about steps  
**Usage**:
- Step names and descriptions (when verbose mode enabled)
- Field labels in output (Papers, Duration, Items processed)
- Detailed parameter information

**Examples**:
```
[cyan]Papers:[/cyan] 42 total ([green]35 unique[/green], [yellow]7 duplicates[/yellow])
[cyan]Duration:[/cyan] 3.45s
[bold cyan]Step Timings:[/bold cyan]
```

---

### Yellow
**Context**: Warnings and caution messages  
**Usage**:
- User actions already completed (e.g., "All steps already executed")
- Non-critical alerts
- Deprecation notices
- Status info that might surprise the user

**Examples**:
```
[yellow]⚠ All steps already completed![/yellow]
[yellow]⚠ Debug mode enabled[/yellow]
[yellow]⏸ halted[/yellow]
```

---

### Red
**Context**: Errors and failures  
**Usage**:
- Failed operations
- Error messages
- Invalid inputs
- Exceptions caught during execution

**Examples**:
```
[red]✗ Checkpoint failed: {error_msg}[/red]
[red]Error:[/red] Invalid step configuration
```

---

### Dim (Grey)
**Context**: Debug information and ancillary details  
**Usage**:
- **Debug-mode-only output** - ALL debug messages MUST use `[dim]` formatting
- Internal state information
- Metadata and context that may confuse casual users
- Less important information in complex output

**Rule**: When the `debug` flag is enabled, all debug messages are formatted with `[dim]` to visually indicate they are diagnostic output not intended for regular users.

**Examples**:
```
[dim]Debug: Executed from step 0 to 1 (1 step(s))[/dim]
[dim]Debug: Paper ID: 12345, DOI: 10.1234/test[/dim]
[dim]Debug: Cache hit for crossref lookup[/dim]
[dim](template: my_template)[/dim]
[dim](0.25s)[/dim]
```

---

### Green
**Context**: Success and completion (minimally used)  
**Usage**:
- Success indicators (✓)
- Completion of critical operations
- Only when explicitly confirming success

**Rationale**: Green is reserved for clear success states. Use sparingly to maintain impact. Blue messages can indicate completion without green.

**Examples**:
```
[green]✓ All steps completed![/green]
[green]✓[/green]
```

---

## Context-Specific Applications

### Single-Step Mode
```
[bold blue][3/10] > [/bold blue]                           # Prompt
[blue]ℹ Executing next step...[/blue]                      # Action message
[cyan]Executing:[/cyan] [white]Import data[/white]         # Step details (verbose)
[blue]✓ Step completed[/blue]                              # Completion
[cyan]Duration:[/cyan] [white]1.23s[/white]                # Timing info (with --timings)
```

### Batch Mode (run/go)
```
[blue]Running 7 remaining step(s)...[/blue]
  [1/7] [cyan]Executing:[/cyan] [white]Import bibtex[/white] [green]✓[/green] [dim](52 items, 0.45s)[/dim]
  [2/7] [cyan]Executing:[/cyan] [magenta]Deduplicate[/magenta] [green]✓[/green] [dim](47 items, 0.23s)[/dim]
  [3/7] [cyan]Executing:[/cyan] [white]Extract references[/white] [green]✓[/green] [dim](156 found, 0.67s)[/dim]
  [4/7] [cyan]Executing:[/cyan] [magenta]Categorize papers[/magenta] [green]✓[/green] [dim](47 categorized, 1.23s)[/dim]
[green]✓ All steps completed![/green]
[cyan]Total duration:[/cyan] [white]2.58s[/white]
```

### Error Scenarios
```
[blue]ℹ Executing next step...[/blue]
[red]✗ Step failed[/red]
[cyan]Step:[/cyan] [white]Analyze references[/white]
[red]Error:[/red] [white]Step configuration invalid[/white]
[dim]Details: Missing 'output_file' parameter[/dim]
```

### Debug Mode
```
[yellow]⚠ Debug mode enabled - verbose output will be shown[/yellow]
[dim]Debug: Executed from step 0 to 1 (1 step(s))[/dim]
[dim]Debug: Full result: {...}[/dim]
```

---

## Implementation Guidelines

1. **Label-Content Pattern**: Use `[cyan]Label:[/cyan] [white]content[/white]` for clarity
2. **Metadata**: Keep additional details in dim
3. **Consistency**: Use the same color for the same information type across the entire CLI
4. **Readability**: White text breaks up colored sections and provides visual breathing room
5. **Status**: Use blue for neutral status, yellow for warnings, red for errors
6. **Success**: Reserve green for completion of critical operations only
7. **Testing**: Test output with and without colors enabled

---

## Examples from Code

### Stats Command
```python
console.print(f"[cyan]Project:[/cyan] [white]{project_name}[/white]")
console.print(f"[cyan]Papers:[/cyan] [white]{papers_total} total[/white]")
console.print(f"[cyan]Progress:[/cyan] [white]{current_step}/{total_steps} steps[/white]")
```

### Step Execution (Verbose)
```python
step_info = executor.describe_next_step()
console.print(f"[cyan]Executing:[/cyan] [white]{step_info['description']}[/white] [dim](builtin.{step_info['name']})[/dim]")
```

### Step Completion
```python
if result.get('status') == 'ok':
    step_name = step_info["description"]
    console.print(f"[blue]✓[/blue] [white]{step_name}[/white] [dim](completed)[/dim]")
    console.print(f"  [cyan]Items:[/cyan] [white]{count}[/white]")
    console.print(f"  [cyan]Duration:[/cyan] [white]{duration:.2f}s[/white]")
```

### Error Reporting
```python
console.print(f"[red]✗ {step_name} failed[/red]")
console.print(f"  [cyan]Error:[/cyan] [white]{error_msg}[/white]")
```

---

## Backwards Compatibility

This design replaces the previous use of green for general success messages with a more intentional approach:
- Green is now reserved for completion of major milestones
- Blue/cyan are preferred for routine operations
- The overall visual feel is less "traffic light" and more purposeful

Users can still use `--no-color` or pipe output to disable colors if needed.
