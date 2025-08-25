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


def mark_deleted_or_added_lines(diff_text: str | None) -> str | None:
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


def discover_keys_for_provider(provider: str) -> list[str]:
    """Discover all API keys for a given provider from environment variables.
    
    Args:
        provider: Provider name (e.g., 'openai', 'anthropic', 'google')
    
    Returns:
        List of discovered API keys
    """
    import os
    
    # Direct mapping - provider names match env var prefix
    base_key = f"{provider.upper()}_API_KEY"
    
    keys: list[str] = []
    
    # Check base key (e.g., OPENAI_API_KEY)
    if base_key in os.environ:
        keys.append(os.environ[base_key])
    
    # Check numbered keys (e.g., OPENAI_API_KEY_1, OPENAI_API_KEY_2, ...)
    i = 1
    while True:
        numbered_key = f"{base_key}_{i}"
        if numbered_key in os.environ:
            keys.append(os.environ[numbered_key])
            i += 1
        else:
            break
    
    return keys


def validate_key(key: str, provider: str) -> bool:
    """Validate API key format for provider.
    
    Args:
        key: The API key to validate
        provider: Provider name (e.g., 'openai', 'anthropic', 'google')
    
    Returns:
        True if key format is valid, False otherwise
    """
    if not key:
        return False
    
    # Provider-specific validation
    provider_lower = provider.lower()
    if provider_lower == "openai":
        return key.startswith("sk-") and len(key) > 20
    elif provider_lower == "anthropic":
        return key.startswith("sk-ant-") and len(key) > 20
    elif provider_lower == "google":
        return len(key) > 20  # Google keys don't have a specific prefix
    
    # Default: accept any non-empty string
    return True