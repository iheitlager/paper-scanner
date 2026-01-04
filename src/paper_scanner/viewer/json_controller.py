"""JSON tree controller - manages navigation and manipulation of JSON data."""

import json
import os
import subprocess
from typing import Any, List, Optional

# Disable tokenizers parallelism to avoid fork deadlocks
# (happens when viewing papers with text chunks that use embedding models)
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")


class JSONNode:
    """Represents a node in the JSON tree."""

    def __init__(
        self,
        key: Optional[str],
        value: Any,
        parent: Optional["JSONNode"] = None,
        depth: int = 0,
    ):
        self.key = key
        self.value = value
        self.parent = parent
        self.depth = depth
        self.expanded = True if depth < 1 else False  # Auto-expand first level
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
                if node.key.startswith("["):
                    path_parts.insert(0, node.key)
                else:
                    path_parts.insert(0, f".{node.key}")
            node = node.parent

        path = "".join(path_parts)
        return path or "(root)"

    def get_value_str(self) -> str:
        """Get value as string for clipboard."""
        if self.is_leaf:
            return json.dumps(self.value)
        return json.dumps(self.value, indent=2)


class JSONController:
    """Controller for JSON navigation and search."""

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

    def copy_to_clipboard(self, text: str) -> bool:
        """Copy text to macOS clipboard using pbcopy."""
        try:
            process = subprocess.Popen(
                ["pbcopy"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            process.communicate(text.encode("utf-8"))
            return process.returncode == 0
        except Exception:
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
            self.set_status(f"Found {len(self.search_results)} matches")
        else:
            self.set_status("No matches found")

    def next_search_result(self):
        """Jump to next search result."""
        if not self.search_results:
            self.set_status("No search results")
            return

        self.search_index = (self.search_index + 1) % len(self.search_results)
        self.cursor = self.search_results[self.search_index]
        self.set_status(f"Match {self.search_index + 1}/{len(self.search_results)}")

    def prev_search_result(self):
        """Jump to previous search result."""
        if not self.search_results:
            self.set_status("No search results")
            return

        self.search_index = (self.search_index - 1) % len(self.search_results)
        self.cursor = self.search_results[self.search_index]
        self.set_status(f"Match {self.search_index + 1}/{len(self.search_results)}")

    def set_status(self, message: str):
        """Set status message."""
        self.status_message = message

    def navigate_up(self):
        """Move cursor up."""
        self.cursor = max(0, self.cursor - 1)

    def navigate_down(self):
        """Move cursor down."""
        self.cursor = min(len(self.flat_nodes) - 1, self.cursor + 1)

    def navigate_to_top(self):
        """Move cursor to top."""
        self.cursor = 0

    def navigate_to_bottom(self):
        """Move cursor to bottom."""
        self.cursor = len(self.flat_nodes) - 1

    def expand_current(self):
        """Expand current node."""
        if self.cursor < len(self.flat_nodes):
            node = self.flat_nodes[self.cursor]
            if not node.is_leaf:
                node.expanded = True
                self._rebuild_flat_list()

    def collapse_current(self):
        """Collapse current node or move to parent."""
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

    def toggle_expand_current(self):
        """Toggle expand/collapse of current node."""
        if self.cursor < len(self.flat_nodes):
            node = self.flat_nodes[self.cursor]
            if not node.is_leaf:
                node.expanded = not node.expanded
                self._rebuild_flat_list()

    def get_current_node(self) -> Optional[JSONNode]:
        """Get the currently selected node."""
        if self.cursor < len(self.flat_nodes):
            return self.flat_nodes[self.cursor]
        return None

    def get_current_value_for_clipboard(self) -> Optional[str]:
        """Get current node's value as string for clipboard."""
        node = self.get_current_node()
        if node:
            return node.get_value_str()
        return None

    def get_current_key(self) -> Optional[str]:
        """Get current node's key."""
        node = self.get_current_node()
        if node:
            return node.key
        return None

    def get_current_path(self) -> Optional[str]:
        """Get current node's full path."""
        node = self.get_current_node()
        if node:
            return node.get_full_path()
        return None

    def update_scroll_offset(self, max_visible: int):
        """Update scroll offset to keep cursor visible."""
        if self.cursor < self.scroll_offset:
            self.scroll_offset = self.cursor
        elif self.cursor >= self.scroll_offset + max_visible:
            self.scroll_offset = self.cursor - max_visible + 1
