"""Unit tests for MCP Server configuration."""

import os
from typing import Dict
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from blarify.mcp_server.config import MCPServerConfig


class TestMCPServerConfig:
    """Test suite for MCPServerConfig."""
    
    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = MCPServerConfig()
        assert config.neo4j_uri == "bolt://localhost:7687"
        assert config.neo4j_username == "neo4j"
        assert config.neo4j_password == "password"
        assert config.repository_id == "default"
        assert config.entity_id == "default"
        assert config.db_type == "neo4j"
        assert config.falkor_host is None
        assert config.falkor_port is None
    
    def test_custom_config(self) -> None:
        """Test custom configuration values."""
        config = MCPServerConfig(
            neo4j_uri="neo4j://custom:7687",
            neo4j_username="custom_user",
            neo4j_password="custom_pass",
            repository_id="test_repo",
            entity_id="test_entity",
            db_type="falkordb",
            falkor_host="localhost",
            falkor_port=6379
        )
        assert config.neo4j_uri == "neo4j://custom:7687"
        assert config.neo4j_username == "custom_user"
        assert config.neo4j_password == "custom_pass"
        assert config.repository_id == "test_repo"
        assert config.entity_id == "test_entity"
        assert config.db_type == "falkordb"
        assert config.falkor_host == "localhost"
        assert config.falkor_port == 6379
    
    def test_invalid_neo4j_uri(self) -> None:
        """Test validation of invalid Neo4j URI."""
        with pytest.raises(ValidationError) as exc_info:
            MCPServerConfig(neo4j_uri="invalid://uri")
        
        assert "Invalid Neo4j URI format" in str(exc_info.value)
    
    def test_from_env(self) -> None:
        """Test loading configuration from environment variables."""
        env_vars: Dict[str, str] = {
            "NEO4J_URI": "bolt://env:7687",
            "NEO4J_USERNAME": "env_user",
            "NEO4J_PASSWORD": "env_pass",
            "REPOSITORY_ID": "env_repo",
            "ENTITY_ID": "env_entity",
            "DB_TYPE": "neo4j",
        }
        
        with patch.dict(os.environ, env_vars):
            config = MCPServerConfig.from_env()
            assert config.neo4j_uri == "bolt://env:7687"
            assert config.neo4j_username == "env_user"
            assert config.neo4j_password == "env_pass"
            assert config.repository_id == "env_repo"
            assert config.entity_id == "env_entity"
            assert config.db_type == "neo4j"
    
    def test_from_env_with_falkordb(self) -> None:
        """Test loading FalkorDB configuration from environment."""
        env_vars: Dict[str, str] = {
            "DB_TYPE": "falkordb",
            "FALKOR_HOST": "redis.example.com",
            "FALKOR_PORT": "6380",
        }
        
        with patch.dict(os.environ, env_vars):
            config = MCPServerConfig.from_env()
            assert config.db_type == "falkordb"
            assert config.falkor_host == "redis.example.com"
            assert config.falkor_port == 6380
    
    def test_validate_for_neo4j(self) -> None:
        """Test validation for Neo4j database type."""
        config = MCPServerConfig(
            db_type="neo4j",
            neo4j_uri="bolt://localhost:7687",
            neo4j_username="user",
            neo4j_password="pass"
        )
        # Should not raise
        config.validate_for_db_type()
        
        # Test missing Neo4j credentials - create config with valid URI first
        config_invalid = MCPServerConfig(
            db_type="neo4j",
            neo4j_uri="bolt://localhost:7687",  # Valid URI format
            neo4j_username="",
            neo4j_password=""
        )
        # Then clear the URI to test validation
        config_invalid.neo4j_uri = ""
        with pytest.raises(ValueError) as exc_info:
            config_invalid.validate_for_db_type()
        assert "Neo4j requires" in str(exc_info.value)
    
    def test_validate_for_falkordb(self) -> None:
        """Test validation for FalkorDB database type."""
        config = MCPServerConfig(
            db_type="falkordb",
            falkor_host="localhost",
            falkor_port=6379
        )
        # Should not raise
        config.validate_for_db_type()
        
        # Test missing FalkorDB configuration
        config_invalid = MCPServerConfig(
            db_type="falkordb",
            falkor_host=None,
            falkor_port=None
        )
        with pytest.raises(ValueError) as exc_info:
            config_invalid.validate_for_db_type()
        assert "FalkorDB requires" in str(exc_info.value)
    
    def test_valid_neo4j_uri_formats(self) -> None:
        """Test various valid Neo4j URI formats."""
        valid_uris = [
            "bolt://localhost:7687",
            "neo4j://localhost:7687",
            "neo4j+s://cloud.neo4j.io:7687",
            "neo4j+ssc://secure.neo4j.io:7687",
        ]
        
        for uri in valid_uris:
            config = MCPServerConfig(neo4j_uri=uri)
            assert config.neo4j_uri == uri