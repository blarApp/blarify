from dataclasses import dataclass
from statistics import stdev, mean
from tree_sitter import Node


from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from blarify.code_hierarchy.languages.language_definitions import LanguageDefinitions


@dataclass
class NestingStats:
    max_indentation: int
    min_indentation: int
    average_indentation: float
    sd: float


class CodeComplexityCalculator:
    DEFAULT_INDENTATION = 4

    @staticmethod
    def calculate_nesting_stats(node: Node, extension: str) -> NestingStats:
        # Import here to avoid circular import
        from blarify.code_references.lsp_helper import LspQueryHelper
        language_definitions = LspQueryHelper.get_language_definition_for_extension(extension)

        indentation_per_line = CodeComplexityCalculator.__get_nesting_levels(node, language_definitions)

        if indentation_per_line == []:
            return NestingStats(0, 0, 0, 0)

        max_indentation = max(indentation_per_line)
        min_indentation = min(indentation_per_line)
        average_indentation = mean(indentation_per_line)
        sd = stdev(indentation_per_line) if len(indentation_per_line) > 1 else 0

        return NestingStats(max_indentation, min_indentation, average_indentation, sd)

    @staticmethod
    def __get_nesting_levels(node: Node, language_definitions: "LanguageDefinitions") -> list[int]:
        depths = []

        for child in node.named_children:
            if not language_definitions.should_create_node(child):
                depths.append(CodeComplexityCalculator.__calculate_max_nesting_depth(child, language_definitions))

        return depths

    @staticmethod
    def __calculate_max_nesting_depth(node: Node, language_definitions: "LanguageDefinitions") -> int:
        consequence_statements = language_definitions.CONSEQUENCE_STATEMENTS
        control_flow_statements = language_definitions.CONTROL_FLOW_STATEMENTS

        depths = []
        depth = 0
        for child in node.named_children:
            if language_definitions.should_create_node(child):
                continue

            if child.type in control_flow_statements or child.type in consequence_statements:
                depth += CodeComplexityCalculator.__calculate_max_nesting_depth(child, language_definitions)
                if child.type in consequence_statements:
                    depth += 1

            depths.append(depth)
            depth = 0

        return max(depths) if depths else 0
    
    @staticmethod
    def calculate_parameter_count(node: Node) -> int:
        """
        Calculate the number of parameters in a function definition node.
        """
        if node is None:
            return 0
        
        if parameters_node := node.child_by_field_name("parameters"):
            return len(parameters_node.named_children)
        return 0


if __name__ == "__main__":
    code = """
def foo():
    if True:
        print("Hello")
    else:
        print("World")
"""
    stats = CodeComplexityCalculator.calculate_nesting_stats(code)
    print(stats)
