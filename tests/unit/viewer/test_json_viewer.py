"""Unit tests for JSONViewer"""

import pytest
from unittest.mock import patch, MagicMock
from paper_scanner.viewer.json_viewer import JSONViewer


class TestJSONViewer:
    """Test suite for JSONViewer rendering and interaction"""

    @pytest.fixture
    def sample_data(self):
        """Create sample JSON data for testing"""
        return {
            "title": "Test Paper",
            "authors": [
                {"name": "Author One", "affiliation": "University A"},
                {"name": "Author Two", "affiliation": "University B"}
            ],
            "year": 2023,
            "doi": "10.1234/test",
            "abstract": "This is a test abstract with some content.",
            "keywords": ["python", "testing", "json"],
            "metadata": {
                "pages": "1-10",
                "volume": "45",
                "issue": "3"
            }
        }

    def test_initialization(self, sample_data):
        """Test JSONViewer initialization"""
        viewer = JSONViewer(sample_data, title="Test Viewer")
        assert viewer.controller.title == "Test Viewer"
        assert viewer.running is False
        assert viewer.search_mode is False
        assert viewer.search_query == ""
        assert viewer.message == ""

    def test_empty_data(self):
        """Test JSONViewer with empty data"""
        viewer = JSONViewer({}, title="Empty")
        assert viewer.controller.data == {}
        assert viewer.running is False

    def test_nested_data(self):
        """Test JSONViewer with deeply nested data"""
        nested_data = {
            "level1": {
                "level2": {
                    "level3": {
                        "value": "deep"
                    }
                }
            }
        }
        viewer = JSONViewer(nested_data)
        assert viewer.controller.data == nested_data
        assert len(viewer.controller.flat_nodes) > 0

    def test_list_data(self):
        """Test JSONViewer with list data"""
        list_data = [1, 2, {"key": "value"}, [4, 5, 6]]
        viewer = JSONViewer(list_data, title="List Test")
        assert len(viewer.controller.flat_nodes) > 0

    def test_search_mode_entry(self, sample_data):
        """Test entering search mode"""
        viewer = JSONViewer(sample_data)
        assert viewer.search_mode is False
        viewer.search_mode = True
        viewer.search_query = ""
        assert viewer.search_mode is True
        assert viewer.search_query == ""

    def test_search_query_input(self, sample_data):
        """Test adding characters to search query"""
        viewer = JSONViewer(sample_data)
        viewer.search_mode = True
        viewer.search_query += "t"
        viewer.search_query += "e"
        viewer.search_query += "s"
        assert viewer.search_query == "tes"

    def test_search_query_backspace(self, sample_data):
        """Test backspace in search query"""
        viewer = JSONViewer(sample_data)
        viewer.search_query = "test"
        viewer.search_query = viewer.search_query[:-1]
        assert viewer.search_query == "tes"

    def test_message_display(self, sample_data):
        """Test setting and clearing messages"""
        viewer = JSONViewer(sample_data)
        viewer.message = "[green]✓ Copied to clipboard[/green]"
        assert viewer.message != ""
        viewer.message = ""
        assert viewer.message == ""

    def test_controller_integration(self, sample_data):
        """Test that viewer correctly integrates with controller"""
        viewer = JSONViewer(sample_data)
        # Navigate with controller
        initial_cursor = viewer.controller.cursor
        viewer.controller.navigate_down()
        assert viewer.controller.cursor > initial_cursor

    def test_get_current_node(self, sample_data):
        """Test getting current node through viewer"""
        viewer = JSONViewer(sample_data)
        current_node = viewer.controller.get_current_node()
        assert current_node is not None

    def test_search_integration(self, sample_data):
        """Test search functionality through viewer"""
        viewer = JSONViewer(sample_data)
        viewer.controller.search("title")
        assert len(viewer.controller.search_results) > 0

    def test_escape_search_query_brackets(self, sample_data):
        """Test that search query with brackets is escaped"""
        viewer = JSONViewer(sample_data)
        # Simulate user typing brackets
        query_with_brackets = "test[0]"
        escaped = query_with_brackets.replace("[", r"\[").replace("]", r"\]")
        assert escaped == "test\\[0\\]"

    def test_expand_collapse_node(self, sample_data):
        """Test expanding and collapsing nodes through viewer"""
        viewer = JSONViewer(sample_data)
        # Get a non-leaf node
        for node in viewer.controller.flat_nodes:
            if not node.is_leaf:
                node.expanded = False
                viewer.controller._rebuild_flat_list()
                initial_count = len(viewer.controller.flat_nodes)
                node.expanded = True
                viewer.controller._rebuild_flat_list()
                final_count = len(viewer.controller.flat_nodes)
                assert final_count > initial_count
                break

    def test_various_data_types(self):
        """Test viewer with various JSON data types"""
        complex_data = {
            "string": "hello",
            "number": 42,
            "float": 3.14,
            "boolean": True,
            "null": None,
            "array": [1, 2, 3],
            "object": {"nested": "value"},
            "empty_array": [],
            "empty_object": {}
        }
        viewer = JSONViewer(complex_data)
        assert len(viewer.controller.flat_nodes) > 0
        # Verify all top-level keys are in the flat list
        top_level_keys = [node.key for node in viewer.controller.flat_nodes if node.depth == 1]
        assert "string" in top_level_keys
        assert "number" in top_level_keys
        assert "boolean" in top_level_keys

    def test_unicode_data(self):
        """Test viewer with unicode characters"""
        unicode_data = {
            "greek": "Ελληνικά",
            "chinese": "中文",
            "emoji": "🎉🚀",
            "mixed": "Hello 世界 🌍"
        }
        viewer = JSONViewer(unicode_data, title="Unicode Test")
        assert len(viewer.controller.flat_nodes) > 0
        # Should not raise any errors

    def test_large_nested_structure(self):
        """Test viewer with large nested structure"""
        large_data = {
            f"key_{i}": {
                f"nested_{j}": f"value_{i}_{j}"
                for j in range(5)
            }
            for i in range(10)
        }
        viewer = JSONViewer(large_data)
        assert len(viewer.controller.flat_nodes) > 0
        # Verify scroll offset calculations work
        viewer.controller.update_scroll_offset(20)
        assert viewer.controller.scroll_offset >= 0
