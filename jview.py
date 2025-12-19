#!/usr/bin/env python3
"""
Interactive JSON viewer - jless clone in Python with clipboard support.

Usage:
    python jview.py data.json
    
    # Or in Python REPL:
    from jview import view_json
    view_json(data)

Keybindings:
    ↑/↓ or j/k     - Navigate up/down
    ←/→ or h/l     - Collapse/expand node
    Space/Enter    - Toggle expand/collapse
    g/G            - Go to top/bottom
    /              - Search
    n/N            - Next/previous search result
    v              - Copy value to clipboard
    k              - Copy key to clipboard  
    c              - Copy key=value to clipboard
    q/Esc          - Quit
"""

import curses
import json
import sys
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional, Union


class JSONNode:
    """Represents a node in the JSON tree."""
    
    def __init__(self, key: Optional[str], value: Any, parent: Optional['JSONNode'] = None, depth: int = 0):
        self.key = key
        self.value = value
        self.parent = parent
        self.depth = depth
        self.expanded = True if depth < 2 else False  # Auto-expand first 2 levels
        self.children: List[JSONNode] = []
        self.is_leaf = not isinstance(value, (dict, list))
        
        if not self.is_leaf:
            self._build_children()
    
    def _build_children(self):
        """Build child nodes."""
        if isinstance(self.value, dict):
            for k, v in self.value.items():
                child = JSONNode(k, v, parent=self, depth=self.depth + 1)
                self.children.append(child)
        elif isinstance(self.value, list):
            for idx, v in enumerate(self.value):
                child = JSONNode(f"[{idx}]", v, parent=self, depth=self.depth + 1)
                self.children.append(child)
    
    def toggle_expand(self):
        """Toggle expansion state."""
        if not self.is_leaf:
            self.expanded = not self.expanded
    
    def get_display_value(self) -> str:
        """Get string representation of value."""
        if self.is_leaf:
            if isinstance(self.value, str):
                return f'"{self.value}"'
            elif self.value is None:
                return "null"
            elif isinstance(self.value, bool):
                return "true" if self.value else "false"
            else:
                return str(self.value)
        else:
            if isinstance(self.value, dict):
                count = len(self.value)
                return f"{{...}} ({count} {'key' if count == 1 else 'keys'})"
            elif isinstance(self.value, list):
                count = len(self.value)
                return f"[...] ({count} {'item' if count == 1 else 'items'})"
        return ""
    
    def get_full_path(self) -> str:
        """Get full JSON path to this node."""
        path_parts = []
        node = self
        while node.parent is not None:
            if node.key:
                # Handle array indices vs object keys
                if node.key.startswith('['):
                    path_parts.insert(0, node.key)
                else:
                    path_parts.insert(0, f'.{node.key}')
            node = node.parent
        
        path = ''.join(path_parts)
        return path if path else '(root)'
    
    def get_value_str(self) -> str:
        """Get value as string for clipboard."""
        if self.is_leaf:
            return json.dumps(self.value)
        else:
            return json.dumps(self.value, indent=2)


class JSONViewer:
    """Interactive JSON viewer with curses."""
    
    def __init__(self, data: Any, title: str = "JSON Viewer"):
        self.data = data
        self.title = title
        self.root = JSONNode(None, data)
        self.flat_nodes: List[JSONNode] = []
        self.cursor = 0
        self.scroll_offset = 0
        self.search_query = ""
        self.search_results: List[int] = []
        self.search_index = -1
        self.status_message = ""
        self.status_color = curses.COLOR_WHITE
        
        self._rebuild_flat_list()
    
    def _rebuild_flat_list(self):
        """Rebuild flat list of visible nodes."""
        self.flat_nodes = []
        self._traverse_visible(self.root)
    
    def _traverse_visible(self, node: JSONNode):
        """Recursively traverse and collect visible nodes."""
        if node.key is not None:  # Skip root
            self.flat_nodes.append(node)
        
        if node.expanded and not node.is_leaf:
            for child in node.children:
                self._traverse_visible(child)
    
    def copy_to_clipboard(self, text: str):
        """Copy text to macOS clipboard using pbcopy."""
        try:
            process = subprocess.Popen(
                ['pbcopy'],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            process.communicate(text.encode('utf-8'))
            return True
        except Exception as e:
            return False
    
    def search(self, query: str):
        """Search for query in keys and values."""
        self.search_query = query.lower()
        self.search_results = []
        
        for idx, node in enumerate(self.flat_nodes):
            # Search in key
            if node.key and self.search_query in node.key.lower():
                self.search_results.append(idx)
            # Search in value string
            elif self.search_query in node.get_display_value().lower():
                self.search_results.append(idx)
        
        if self.search_results:
            self.search_index = 0
            self.cursor = self.search_results[0]
            self.set_status(f"Found {len(self.search_results)} matches", curses.COLOR_GREEN)
        else:
            self.set_status("No matches found", curses.COLOR_RED)
    
    def next_search_result(self):
        """Jump to next search result."""
        if not self.search_results:
            self.set_status("No search results", curses.COLOR_RED)
            return
        
        self.search_index = (self.search_index + 1) % len(self.search_results)
        self.cursor = self.search_results[self.search_index]
        self.set_status(
            f"Match {self.search_index + 1}/{len(self.search_results)}",
            curses.COLOR_GREEN
        )
    
    def prev_search_result(self):
        """Jump to previous search result."""
        if not self.search_results:
            self.set_status("No search results", curses.COLOR_RED)
            return
        
        self.search_index = (self.search_index - 1) % len(self.search_results)
        self.cursor = self.search_results[self.search_index]
        self.set_status(
            f"Match {self.search_index + 1}/{len(self.search_results)}",
            curses.COLOR_GREEN
        )
    
    def set_status(self, message: str, color: int = curses.COLOR_WHITE):
        """Set status message."""
        self.status_message = message
        self.status_color = color
    
    def handle_keypress(self, key: int, max_y: int) -> bool:
        """Handle keypress. Returns False if should quit."""
        max_visible = max_y - 4  # Account for header/footer
        
        # Navigation
        if key in (curses.KEY_UP, ord('k')):
            self.cursor = max(0, self.cursor - 1)
        elif key in (curses.KEY_DOWN, ord('j')):
            self.cursor = min(len(self.flat_nodes) - 1, self.cursor + 1)
        elif key == ord('g'):  # Go to top
            self.cursor = 0
        elif key == ord('G'):  # Go to bottom
            self.cursor = len(self.flat_nodes) - 1
        
        # Expand/collapse
        elif key in (curses.KEY_RIGHT, ord('l'), curses.KEY_ENTER, ord('\n'), ord(' ')):
            if self.cursor < len(self.flat_nodes):
                node = self.flat_nodes[self.cursor]
                if not node.is_leaf:
                    node.expanded = True
                    self._rebuild_flat_list()
        elif key in (curses.KEY_LEFT, ord('h')):
            if self.cursor < len(self.flat_nodes):
                node = self.flat_nodes[self.cursor]
                if not node.is_leaf and node.expanded:
                    node.expanded = False
                    self._rebuild_flat_list()
                elif node.parent and node.parent.key is not None:
                    # Jump to parent
                    for idx, n in enumerate(self.flat_nodes):
                        if n == node.parent:
                            self.cursor = idx
                            break
        
        # Clipboard operations
        elif key == ord('v'):  # Copy value
            if self.cursor < len(self.flat_nodes):
                node = self.flat_nodes[self.cursor]
                value_str = node.get_value_str()
                if self.copy_to_clipboard(value_str):
                    self.set_status(f"Copied value to clipboard ({len(value_str)} chars)", curses.COLOR_GREEN)
                else:
                    self.set_status("Failed to copy to clipboard", curses.COLOR_RED)
        
        elif key == ord('k'):  # Copy key (changed from 'k' for navigation conflict)
            if self.cursor < len(self.flat_nodes):
                node = self.flat_nodes[self.cursor]
                if node.key:
                    if self.copy_to_clipboard(node.key):
                        self.set_status(f"Copied key: {node.key}", curses.COLOR_GREEN)
                    else:
                        self.set_status("Failed to copy to clipboard", curses.COLOR_RED)
        
        elif key == ord('c'):  # Copy key=value or path
            if self.cursor < len(self.flat_nodes):
                node = self.flat_nodes[self.cursor]
                path = node.get_full_path()
                value_str = node.get_value_str()
                combined = f"{path} = {value_str}"
                if self.copy_to_clipboard(combined):
                    self.set_status(f"Copied path=value to clipboard", curses.COLOR_GREEN)
                else:
                    self.set_status("Failed to copy to clipboard", curses.COLOR_RED)
        
        elif key == ord('p'):  # Copy full path
            if self.cursor < len(self.flat_nodes):
                node = self.flat_nodes[self.cursor]
                path = node.get_full_path()
                if self.copy_to_clipboard(path):
                    self.set_status(f"Copied path: {path}", curses.COLOR_GREEN)
                else:
                    self.set_status("Failed to copy to clipboard", curses.COLOR_RED)
        
        # Search
        elif key == ord('/'):
            self._search_prompt()
        elif key == ord('n'):
            self.next_search_result()
        elif key == ord('N'):
            self.prev_search_result()
        
        # Quit
        elif key in (ord('q'), 27):  # q or ESC
            return False
        
        # Auto-scroll to keep cursor visible
        if self.cursor < self.scroll_offset:
            self.scroll_offset = self.cursor
        elif self.cursor >= self.scroll_offset + max_visible:
            self.scroll_offset = self.cursor - max_visible + 1
        
        return True
    
    def _search_prompt(self):
        """Show search prompt (simplified version)."""
        # This would be better with a proper input prompt
        # For now, just set a status message
        self.set_status("Search: (type and press enter - TODO: implement input)", curses.COLOR_YELLOW)
    
    def draw(self, stdscr):
        """Main draw loop."""
        curses.curs_set(0)  # Hide cursor
        stdscr.timeout(100)  # Non-blocking input
        
        # Initialize colors
        curses.init_pair(1, curses.COLOR_CYAN, curses.COLOR_BLACK)    # Keys
        curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)   # Strings
        curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)  # Numbers
        curses.init_pair(4, curses.COLOR_MAGENTA, curses.COLOR_BLACK) # Booleans/null
        curses.init_pair(5, curses.COLOR_WHITE, curses.COLOR_BLUE)    # Highlight
        curses.init_pair(6, curses.COLOR_RED, curses.COLOR_BLACK)     # Errors
        curses.init_pair(7, curses.COLOR_GREEN, curses.COLOR_BLACK)   # Success
        curses.init_pair(8, curses.COLOR_BLACK, curses.COLOR_WHITE)   # Header
        
        while True:
            stdscr.clear()
            max_y, max_x = stdscr.getmaxyx()
            
            # Draw header
            header = f" {self.title} "
            stdscr.attron(curses.color_pair(8))
            stdscr.addstr(0, 0, header.ljust(max_x))
            stdscr.attroff(curses.color_pair(8))
            
            # Draw JSON tree
            visible_start = self.scroll_offset
            visible_end = min(len(self.flat_nodes), self.scroll_offset + max_y - 4)
            
            for i in range(visible_start, visible_end):
                y = i - self.scroll_offset + 1
                if y >= max_y - 2:
                    break
                
                node = self.flat_nodes[i]
                indent = "  " * node.depth
                
                # Highlight current line
                if i == self.cursor:
                    stdscr.attron(curses.color_pair(5))
                
                # Build line
                line_parts = []
                
                # Expand/collapse indicator
                if not node.is_leaf:
                    indicator = "▼ " if node.expanded else "▶ "
                    line_parts.append(indicator)
                else:
                    line_parts.append("  ")
                
                # Key
                if node.key:
                    if i == self.cursor:
                        key_str = f"{node.key}: "
                    else:
                        stdscr.attroff(curses.color_pair(5))
                        stdscr.attron(curses.color_pair(1))
                        key_str = f"{node.key}: "
                        line_parts.append(key_str)
                        stdscr.attroff(curses.color_pair(1))
                        if i == self.cursor:
                            stdscr.attron(curses.color_pair(5))
                    
                    if i != self.cursor:
                        line_parts = [indicator, key_str]
                    else:
                        line_parts = [indicator + key_str]
                
                # Value
                value_str = node.get_display_value()
                
                # Choose color based on type
                if node.is_leaf:
                    if isinstance(node.value, str):
                        value_color = 2  # Green for strings
                    elif isinstance(node.value, (int, float)):
                        value_color = 3  # Yellow for numbers
                    elif isinstance(node.value, bool) or node.value is None:
                        value_color = 4  # Magenta for bool/null
                    else:
                        value_color = 0  # Default
                else:
                    value_color = 0  # Default for objects/arrays
                
                # Build full line
                full_line = indent + ''.join(line_parts) + value_str
                
                # Truncate if too long
                if len(full_line) > max_x - 1:
                    full_line = full_line[:max_x-4] + "..."
                
                try:
                    if i == self.cursor:
                        stdscr.addstr(y, 0, full_line)
                        stdscr.attroff(curses.color_pair(5))
                    else:
                        # Draw indent
                        stdscr.addstr(y, 0, indent)
                        x_pos = len(indent)
                        
                        # Draw indicator
                        stdscr.addstr(y, x_pos, indicator)
                        x_pos += len(indicator)
                        
                        # Draw key
                        if node.key:
                            stdscr.attron(curses.color_pair(1))
                            stdscr.addstr(y, x_pos, f"{node.key}: ")
                            stdscr.attroff(curses.color_pair(1))
                            x_pos += len(node.key) + 2
                        
                        # Draw value
                        if value_color > 0:
                            stdscr.attron(curses.color_pair(value_color))
                        stdscr.addstr(y, x_pos, value_str[:max_x - x_pos - 1])
                        if value_color > 0:
                            stdscr.attroff(curses.color_pair(value_color))
                
                except curses.error:
                    pass  # Ignore errors from writing to edge of screen
            
            # Draw footer with status
            footer_y = max_y - 2
            
            # Current position info
            if self.cursor < len(self.flat_nodes):
                node = self.flat_nodes[self.cursor]
                path = node.get_full_path()
                pos_info = f" {self.cursor + 1}/{len(self.flat_nodes)} | {path} "
            else:
                pos_info = f" {self.cursor + 1}/{len(self.flat_nodes)} "
            
            try:
                stdscr.attron(curses.color_pair(8))
                stdscr.addstr(footer_y, 0, pos_info[:max_x-1].ljust(max_x-1))
                stdscr.attroff(curses.color_pair(8))
            except curses.error:
                pass
            
            # Status message
            if self.status_message:
                try:
                    if self.status_color == curses.COLOR_GREEN:
                        stdscr.attron(curses.color_pair(7))
                    elif self.status_color == curses.COLOR_RED:
                        stdscr.attron(curses.color_pair(6))
                    
                    stdscr.addstr(footer_y + 1, 0, f" {self.status_message} "[:max_x-1])
                    
                    if self.status_color in (curses.COLOR_GREEN, curses.COLOR_RED):
                        stdscr.attroff(curses.color_pair(7 if self.status_color == curses.COLOR_GREEN else 6))
                except curses.error:
                    pass
            else:
                # Show help
                help_text = " ↑↓:navigate  ←→:collapse/expand  v:copy-value  k:copy-key  c:copy-path  p:full-path  /:search  q:quit "
                try:
                    stdscr.addstr(footer_y + 1, 0, help_text[:max_x-1])
                except curses.error:
                    pass
            
            stdscr.refresh()
            
            # Handle input
            key = stdscr.getch()
            if key != -1:
                if not self.handle_keypress(key, max_y):
                    break
    
    def run(self):
        """Run the viewer."""
        curses.wrapper(self.draw)


def view_json(data: Any, title: str = "JSON Viewer"):
    """
    View JSON data interactively.
    
    Args:
        data: JSON-serializable data (dict, list, etc.)
        title: Window title
    """
    viewer = JSONViewer(data, title)
    viewer.run()


def main():
    """Command-line entry point."""
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <json-file>")
        print("\nKeybindings:")
        print("  ↑/↓ or j/k     - Navigate up/down")
        print("  ←/→ or h/l     - Collapse/expand node")
        print("  Space/Enter    - Toggle expand/collapse")
        print("  g/G            - Go to top/bottom")
        print("  v              - Copy value to clipboard")
        print("  k              - Copy key to clipboard")
        print("  c              - Copy path=value to clipboard")
        print("  p              - Copy full path to clipboard")
        print("  /              - Search (TODO)")
        print("  n/N            - Next/previous search result")
        print("  q/Esc          - Quit")
        sys.exit(1)
    
    json_file = Path(sys.argv[1])
    
    if not json_file.exists():
        print(f"Error: File not found: {json_file}")
        sys.exit(1)
    
    try:
        with open(json_file) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON: {e}")
        sys.exit(1)
    
    view_json(data, title=json_file.name)


if __name__ == "__main__":
    main()