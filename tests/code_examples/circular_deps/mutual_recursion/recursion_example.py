"""Module demonstrating mutual recursion - real cycles that should be detected."""


def is_even(n):
    """Check if a number is even using mutual recursion with is_odd."""
    if n == 0:
        return True
    elif n < 0:
        return is_even(-n)
    else:
        return is_odd(n - 1)


def is_odd(n):
    """Check if a number is odd using mutual recursion with is_even."""
    if n == 0:
        return False
    elif n < 0:
        return is_odd(-n)
    else:
        return is_even(n - 1)


def count_down_even(n):
    """Count down from n, calling count_down_odd for odd numbers."""
    if n <= 0:
        return []
    if n % 2 == 0:
        return [n] + count_down_odd(n - 1)
    else:
        return count_down_odd(n)


def count_down_odd(n):
    """Count down from n, calling count_down_even for even numbers."""
    if n <= 0:
        return []
    if n % 2 == 1:
        return [n] + count_down_even(n - 1)
    else:
        return count_down_even(n)


def tree_traversal_left(node):
    """Traverse tree left-first, switching to right traversal."""
    if node is None:
        return []
    if node.get("left"):
        return [node["value"]] + tree_traversal_right(node["left"])
    elif node.get("right"):
        return [node["value"]] + tree_traversal_right(node["right"])
    else:
        return [node["value"]]


def tree_traversal_right(node):
    """Traverse tree right-first, switching to left traversal."""
    if node is None:
        return []
    if node.get("right"):
        return [node["value"]] + tree_traversal_left(node["right"])
    elif node.get("left"):
        return [node["value"]] + tree_traversal_left(node["left"])
    else:
        return [node["value"]]


# Non-recursive helper functions for testing
def test_even_odd():
    """Test the even/odd functions - not part of recursion."""
    results = []
    for i in range(10):
        results.append((i, is_even(i), is_odd(i)))
    return results


def create_sample_tree():
    """Create a sample tree for testing - not part of recursion."""
    return {
        "value": 1,
        "left": {"value": 2, "left": {"value": 4}, "right": {"value": 5}},
        "right": {"value": 3, "left": {"value": 6}, "right": {"value": 7}}
    }