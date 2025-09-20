"""Configuration management for MCP Server."""

import os
from typing import Literal, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator


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
    def from_env(cls) -> "MCPServerConfig":
        """Load configuration from environment variables."""
        load_dotenv()
        
        config_dict = {}
        
        # Map environment variables to config fields
        env_mapping = {
            "NEO4J_URI": "neo4j_uri",
            "NEO4J_USERNAME": "neo4j_username",
            "NEO4J_PASSWORD": "neo4j_password",
            "ROOT_PATH": "root_path",
            "ENTITY_ID": "entity_id",
            "DB_TYPE": "db_type",
            "FALKOR_HOST": "falkor_host",
            "FALKOR_PORT": "falkor_port",
        }
        
        for env_var, field_name in env_mapping.items():
            value = os.getenv(env_var)
            if value is not None:
                # Convert port to int if present
                if field_name == "falkor_port":
                    try:
                        value = int(value)
                    except ValueError:
                        pass
                config_dict[field_name] = value
        
        return cls(**config_dict)
    
    def validate_for_db_type(self) -> None:
        """Validate configuration based on selected database type."""
        if self.db_type == "falkordb":
            if not self.falkor_host or not self.falkor_port:
                raise ValueError("FalkorDB requires falkor_host and falkor_port to be set")
        elif self.db_type == "neo4j":
            if not self.neo4j_uri or not self.neo4j_username or not self.neo4j_password:
                raise ValueError("Neo4j requires neo4j_uri, neo4j_username, and neo4j_password to be set")