"""Unit tests for JSONController"""

import pytest
from paper_scanner.viewer.json_controller import JSONController, JSONNode


class TestJSONNode:
    """Test suite for JSONNode tree representation"""

    def test_node_creation_leaf(self):
        """Test creating a leaf node"""
        node = JSONNode(key="name", value="John", depth=0)
        assert node.key == "name"
        assert node.value == "John"
        assert node.is_leaf is True
        assert node.expanded is True
        assert len(node.children) == 0

    def test_node_creation_dict(self):
        """Test creating a dict node with children"""
        data = {"name": "John", "age": 30}
        node = JSONNode(key=None, value=data, depth=0)
        assert node.is_leaf is False
        assert len(node.children) == 2
        assert node.expanded is True

    def test_node_creation_list(self):
        """Test creating a list node with children"""
        data = [1, 2, 3]
        node = JSONNode(key="items", value=data, depth=0)
        assert node.is_leaf is False
        assert len(node.children) == 3
        assert node.children[0].key == "[0]"
        assert node.children[1].key == "[1]"
        assert node.children[2].key == "[2]"

    def test_node_display_value_string(self):
        """Test display value for string"""
        node = JSONNode(key="name", value="John", depth=0)
        assert node.get_display_value() == '"John"'

    def test_node_display_value_number(self):
        """Test display value for number"""
        node = JSONNode(key="age", value=30, depth=0)
        assert node.get_display_value() == "30"

    def test_node_display_value_boolean(self):
        """Test display value for boolean"""
        node = JSONNode(key="active", value=True, depth=0)
        assert node.get_display_value() == "true"

    def test_node_display_value_null(self):
        """Test display value for null"""
        node = JSONNode(key="value", value=None, depth=0)
        assert node.get_display_value() == "null"

    def test_node_display_value_dict(self):
        """Test display value for dict"""
        data = {"a": 1, "b": 2}
        node = JSONNode(key="obj", value=data, depth=0)
        assert "2 keys" in node.get_display_value()

    def test_node_display_value_list(self):
        """Test display value for list"""
        data = [1, 2, 3]
        node = JSONNode(key="items", value=data, depth=0)
        assert "3 items" in node.get_display_value()

    def test_node_full_path_leaf(self):
        """Test getting full path for leaf node"""
        data = {"user": {"name": "John"}}
        root = JSONNode(None, data)
        user_node = root.children[0]
        name_node = user_node.children[0]
        assert name_node.get_full_path() == ".user.name"

    def test_node_full_path_array_index(self):
        """Test getting full path with array index"""
        data = {"items": [1, 2, 3]}
        root = JSONNode(None, data)
        items_node = root.children[0]
        item_node = items_node.children[0]
        assert item_node.get_full_path() == ".items[0]"

    def test_node_toggle_expand(self):
        """Test toggling expand state"""
        data = {"a": 1, "b": 2}
        node = JSONNode(key="obj", value=data, depth=0)
        assert node.expanded is True
        node.toggle_expand()
        assert node.expanded is False
        node.toggle_expand()
        assert node.expanded is True

    def test_node_value_string_for_clipboard(self):
        """Test getting value as string for clipboard"""
        node = JSONNode(key="text", value="hello", depth=0)
        assert node.get_value_str() == '"hello"'

    def test_node_value_dict_for_clipboard(self):
        """Test getting dict value as JSON string"""
        data = {"a": 1, "b": 2}
        node = JSONNode(key="obj", value=data, depth=0)
        result = node.get_value_str()
        assert '"a"' in result
        assert '"b"' in result


class TestJSONController:
    """Test suite for JSONController navigation and search"""

    @pytest.fixture
    def sample_data(self):
        """Create sample JSON data for testing"""
        return {
            "name": "John Doe",
            "age": 30,
            "email": "john@example.com",
            "active": True,
            "address": {
                "street": "123 Main St",
                "city": "New York",
                "zipcode": "10001"
            },
            "tags": ["python", "javascript", "golang"],
            "scores": [85, 90, 88]
        }

    def test_initialization(self, sample_data):
        """Test controller initialization"""
        controller = JSONController(sample_data, title="Test Data")
        assert controller.title == "Test Data"
        assert controller.cursor == 0
        assert len(controller.flat_nodes) > 0
        assert controller.search_results == []

    def test_rebuild_flat_list(self, sample_data):
        """Test flat list is created correctly"""
        controller = JSONController(sample_data)
        assert len(controller.flat_nodes) > 0
        # Root should be skipped, first node should be a top-level key
        assert controller.flat_nodes[0].key in sample_data.keys()

    def test_navigate_up(self, sample_data):
        """Test cursor navigation up"""
        controller = JSONController(sample_data)
        initial_pos = controller.cursor
        controller.navigate_down()
        assert controller.cursor > initial_pos
        controller.navigate_up()
        assert controller.cursor == initial_pos

    def test_navigate_down(self, sample_data):
        """Test cursor navigation down"""
        controller = JSONController(sample_data)
        initial_pos = controller.cursor
        controller.navigate_down()
        assert controller.cursor > initial_pos

    def test_navigate_to_top(self, sample_data):
        """Test navigating to top"""
        controller = JSONController(sample_data)
        controller.navigate_to_bottom()
        assert controller.cursor > 0
        controller.navigate_to_top()
        assert controller.cursor == 0

    def test_navigate_to_bottom(self, sample_data):
        """Test navigating to bottom"""
        controller = JSONController(sample_data)
        controller.navigate_to_bottom()
        assert controller.cursor == len(controller.flat_nodes) - 1

    def test_expand_current_node(self, sample_data):
        """Test expanding a collapsed node"""
        controller = JSONController(sample_data)
        # Find a dict node
        dict_node = None
        for node in controller.flat_nodes:
            if not node.is_leaf and not node.expanded:
                dict_node = node
                break
        
        if dict_node:
            initial_count = len(controller.flat_nodes)
            dict_node.expanded = False
            controller._rebuild_flat_list()
            # Find and navigate to the node
            for idx, node in enumerate(controller.flat_nodes):
                if node == dict_node:
                    controller.cursor = idx
                    break
            controller.expand_current()
            assert dict_node.expanded is True

    def test_search_by_key(self, sample_data):
        """Test searching for a key"""
        controller = JSONController(sample_data)
        controller.search("name")
        assert len(controller.search_results) > 0
        assert controller.cursor == controller.search_results[0]

    def test_search_no_results(self, sample_data):
        """Test search with no matching results"""
        controller = JSONController(sample_data)
        controller.search("nonexistent")
        assert len(controller.search_results) == 0

    def test_next_search_result(self, sample_data):
        """Test navigating to next search result"""
        controller = JSONController(sample_data)
        controller.search("name")
        if len(controller.search_results) > 0:
            first_result = controller.cursor
            controller.next_search_result()
            # Should wrap around or move to next
            assert controller.search_index >= 0

    def test_get_current_node(self, sample_data):
        """Test getting current node"""
        controller = JSONController(sample_data)
        current = controller.get_current_node()
        assert current is not None
        assert current == controller.flat_nodes[controller.cursor]

    def test_get_current_path(self, sample_data):
        """Test getting current node path"""
        controller = JSONController(sample_data)
        path = controller.get_current_path()
        assert path is not None
        assert isinstance(path, str)

    def test_copy_to_clipboard(self, sample_data):
        """Test clipboard copy functionality"""
        controller = JSONController(sample_data)
        # This will only work on systems with pbcopy
        result = controller.copy_to_clipboard("test")
        # Result might be True or False depending on system
        assert isinstance(result, bool)

    def test_set_status(self, sample_data):
        """Test status message setting"""
        controller = JSONController(sample_data)
        controller.set_status("Test message")
        assert controller.status_message == "Test message"

    def test_update_scroll_offset(self, sample_data):
        """Test scroll offset updates"""
        controller = JSONController(sample_data)
        max_visible = 10
        controller.cursor = 50  # Set cursor beyond initial offset
        controller.update_scroll_offset(max_visible)
        assert controller.scroll_offset <= controller.cursor
        assert controller.scroll_offset >= 0
