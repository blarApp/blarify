"""
Tests for code complexity calculation.
"""
import unittest
from typing import Optional
import tree_sitter_python as tspython
from tree_sitter import Language, Parser, Node as TreeSitterNode

from blarify.stats.complexity import CodeComplexityCalculator, NestingStats


class TestCodeComplexityCalculator(unittest.TestCase):
    """Test code complexity calculations."""
    
    def setUp(self) -> None:
        """Set up test fixtures."""
        self.calculator: CodeComplexityCalculator = CodeComplexityCalculator()  # type: ignore[reportUninitializedInstanceVariable]
        # Set up tree-sitter for Python
        self.py_language: Language = Language(tspython.language())  # type: ignore[reportUninitializedInstanceVariable]
        self.parser: Parser = Parser(self.py_language)  # type: ignore[reportUninitializedInstanceVariable]
        
    def parse_code(self, code: str) -> TreeSitterNode:
        """Parse Python code and return tree."""
        return self.parser.parse(bytes(code, "utf8")).root_node
        
        
    def test_calculate_nesting_stats(self) -> None:
        """Test nesting depth calculation."""
        code = """
def nested_function():
    if True:
        for i in range(10):
            while i > 0:
                if i % 2:
                    print(i)
                i -= 1
"""
        
        tree = self.parse_code(code)
        func_node = self.find_node_by_type(tree, "function_definition")
        
        if func_node is None:
            self.fail("Could not find function definition node")
        
        # Get the body of the function
        body_node = None
        for child in func_node.children:
            if child.type == "block":
                body_node = child
                break
        
        if body_node:
            stats = CodeComplexityCalculator.calculate_nesting_stats(body_node, ".py")
            
            self.assertIsInstance(stats, NestingStats)
            self.assertGreaterEqual(stats.max_indentation, 3)  # At least 3 levels nested
            self.assertGreaterEqual(stats.average_indentation, 1)
            
    def test_calculate_nesting_stats_empty_body(self) -> None:
        """Test nesting stats for empty function body."""
        code = """
def empty_function():
    pass
"""
        
        tree = self.parse_code(code)
        func_node = self.find_node_by_type(tree, "function_definition")
        
        if func_node is None:
            self.fail("Could not find function definition node")
        
        # Get the body
        body_node = None
        for child in func_node.children:
            if child.type == "block":
                body_node = child
                break
                
        if body_node:
            stats = CodeComplexityCalculator.calculate_nesting_stats(body_node, ".py")
            
            self.assertIsInstance(stats, NestingStats)
            # Empty or simple body should have minimal nesting
            self.assertEqual(stats.max_indentation, 0)
            self.assertEqual(stats.min_indentation, 0)
            
    def test_calculate_parameter_count(self) -> None:
        """Test parameter counting."""
        code = """
def function_with_params(a, b, c=None, *args, **kwargs):
    pass
"""
        
        tree = self.parse_code(code)
        func_node = self.find_node_by_type(tree, "function_definition")
        
        if func_node is None:
            self.fail("Could not find function definition node")
        
        param_count = CodeComplexityCalculator.calculate_parameter_count(func_node)
        
        # Should count all parameters including *args and **kwargs
        self.assertEqual(param_count, 5)
        
    def test_calculate_parameter_count_no_params(self) -> None:
        """Test parameter counting for parameterless function."""
        code = """
def no_params():
    pass
"""
        
        tree = self.parse_code(code)
        func_node = self.find_node_by_type(tree, "function_definition")
        
        if func_node is None:
            self.fail("Could not find function definition node")
        
        param_count = CodeComplexityCalculator.calculate_parameter_count(func_node)
        
        self.assertEqual(param_count, 0)
        
        
    def find_node_by_type(self, node: TreeSitterNode, node_type: str) -> Optional[TreeSitterNode]:
        """Helper to find first node of given type."""
        if node.type == node_type:
            return node
            
        for child in node.children:
            result = self.find_node_by_type(child, node_type)
            if result:
                return result
                
        return None


class TestComplexityMetrics(unittest.TestCase):
    """Test various complexity metric calculations."""
    
    def setUp(self) -> None:
        """Set up test fixtures."""
        self.calculator: CodeComplexityCalculator = CodeComplexityCalculator()  # type: ignore[reportUninitializedInstanceVariable]
        
    def test_nesting_stats_dataclass(self) -> None:
        """Test NestingStats dataclass."""
        stats = NestingStats(
            max_indentation=4,
            min_indentation=0,
            average_indentation=2.5,
            sd=1.2
        )
        
        self.assertEqual(stats.max_indentation, 4)
        self.assertEqual(stats.min_indentation, 0)
        self.assertEqual(stats.average_indentation, 2.5)
        self.assertEqual(stats.sd, 1.2)
        
    def test_empty_nesting_stats(self) -> None:
        """Test empty nesting stats."""
        stats = NestingStats(0, 0, 0, 0)
        
        self.assertEqual(stats.max_indentation, 0)
        self.assertEqual(stats.min_indentation, 0)
        self.assertEqual(stats.average_indentation, 0)
        self.assertEqual(stats.sd, 0)


if __name__ == '__main__':
    unittest.main()