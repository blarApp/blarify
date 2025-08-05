def normalize_node_path(node_path: str) -> str:
    """
    Normalizes a node path by removing the environment name and the diff identifier
    """
    if not node_path.startswith("/"):
        return node_path

    parts = node_path.split("/")
    if len(parts) > 2:
        parts = parts[3:]

    return "/".join(parts)


def mark_deleted_or_added_lines(diff_text: str) -> str | None:
    if diff_text is None:
        return None

    lines = diff_text.splitlines()
    result = []

    for line in lines:
        if line.startswith("- "):
            result.append(f"[RM] -{line[1:]}")
        elif line.startswith("+ "):
            result.append(f"[ADD] +{line[1:]}")
        else:
            result.append(line)

    return "\n".join(result)