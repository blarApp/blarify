"""Module 2 utilities."""

def helper():
    """Helper function in module2."""
    return "module2"

def another_helper():
    """Another helper in module2."""
    return "extra"

class Config:
    """Configuration class for module2."""
    name = "module2_config"
    
    def get_settings(self):
        """Get module2 settings."""
        return {"module": "module2", "extra": True}