"""Configuration management for MCP Server."""

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from blarify.cli.project_config import ProjectConfig


class MCPServerConfig(BaseModel):
    """Configuration for MCP Server."""

    # Database configuration
    neo4j_uri: str = Field(
        default="bolt://localhost:7687",
        description="Neo4j database URI",
    )
    neo4j_username: str = Field(
        default="neo4j",
        description="Neo4j username",
    )
    neo4j_password: str = Field(
        default="password",
        description="Neo4j password",
    )
    
    # Repository configuration
    root_path: str = Field(
        description="Repository path (used as repo_id)",
    )
    entity_id: str = Field(
        default="default",
        description="Entity identifier",
    )
    
    # Database type
    db_type: Literal["neo4j", "falkordb"] = Field(
        default="neo4j",
        description="Type of database to use",
    )
    
    # FalkorDB configuration (optional)
    falkor_host: Optional[str] = Field(
        default=None,
        description="FalkorDB host",
    )
    falkor_port: Optional[int] = Field(
        default=None,
        description="FalkorDB port",
    )
    
    @field_validator("neo4j_uri")
    @classmethod
    def validate_neo4j_uri(cls, v: str) -> str:
        """Validate Neo4j URI format."""
        if not v.startswith(("bolt://", "neo4j://", "neo4j+s://", "neo4j+ssc://")):
            raise ValueError("Invalid Neo4j URI format")
        return v
    
    @classmethod
    def from_project(cls, repo_id: Optional[str] = None) -> "MCPServerConfig":
        """Load configuration from stored project and credentials.

        Args:
            repo_id: Repository path/id. If None, tries to auto-detect from CWD.

        Returns:
            MCPServerConfig instance

        Raises:
            FileNotFoundError: If no projects or credentials found
            KeyError: If specified project not found
        """
        # Load project configuration
        project = ProjectConfig.load_project_config(repo_id)

        # Load Neo4j credentials
        creds = ProjectConfig.load_neo4j_credentials()

        # Create config from loaded data
        return cls(
            neo4j_uri=project["neo4j_uri"],
            neo4j_username=creds["username"],
            neo4j_password=creds["password"],
            root_path=project["repo_id"],
            entity_id=project["entity_id"],
            db_type="neo4j"  # Currently only Neo4j is auto-configured
        )
    
    def validate_for_db_type(self) -> None:
        """Validate configuration based on selected database type."""
        if self.db_type == "falkordb":
            if not self.falkor_host or not self.falkor_port:
                raise ValueError("FalkorDB requires falkor_host and falkor_port to be set")
        elif self.db_type == "neo4j":
            if not self.neo4j_uri or not self.neo4j_username or not self.neo4j_password:
                raise ValueError("Neo4j requires neo4j_uri, neo4j_username, and neo4j_password to be set")