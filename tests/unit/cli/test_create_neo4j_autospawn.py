"""Unit tests for automatic Neo4j container spawning in create command."""

from argparse import Namespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from blarify.cli.commands import create
from neo4j_container_manager import Environment, Neo4jContainerConfig


class TestNeo4jAutoSpawn:
    """Test automatic Neo4j container spawning."""

    def test_detects_empty_neo4j_args(self):
        """Test that empty Neo4j args trigger container spawn."""
        args = Namespace(
            neo4j_uri=None,
            neo4j_username=None,
            neo4j_password=None,
            path="/test/path",
            entity_id="test",
        )

        should_spawn = create.should_spawn_neo4j(args)
        assert should_spawn is True

    def test_detects_partial_neo4j_args_as_empty(self):
        """Test that partial Neo4j args still trigger container spawn."""
        args = Namespace(
            neo4j_uri="bolt://localhost:7687",
            neo4j_username=None,
            neo4j_password=None,
            path="/test/path",
            entity_id="test",
        )

        should_spawn = create.should_spawn_neo4j(args)
        assert should_spawn is True

    def test_does_not_spawn_with_provided_args(self):
        """Test that provided Neo4j args prevent container spawn."""
        args = Namespace(
            neo4j_uri="bolt://localhost:7687",
            neo4j_username="neo4j",
            neo4j_password="mypassword",
        )

        should_spawn = create.should_spawn_neo4j(args)
        assert should_spawn is False

    @pytest.mark.asyncio
    async def test_reuses_existing_container(self):
        """Test that existing container is reused."""
        with patch("blarify.cli.commands.create.Neo4jContainerManager") as MockManager:
            manager = MockManager.return_value
            
            # Mock existing container
            existing = Mock()
            existing.is_running = AsyncMock(return_value=True)
            existing.uri = "bolt://localhost:7687"
            existing.config.username = "neo4j"
            existing.config.password = "existing123"
            
            # Mock get_existing_container to return the existing container
            with patch("blarify.cli.commands.create.get_existing_container", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = existing
                
                with patch("blarify.cli.commands.create.get_or_create_neo4j_credentials") as mock_creds:
                    mock_creds.return_value = {"username": "neo4j", "password": "existing123"}
                    
                    with patch("blarify.cli.commands.create.display_neo4j_connection_info") as mock_display:
                        result = await create.spawn_or_get_neo4j_container()
                        
                        assert result == existing
                        manager.start.assert_not_called()
                        mock_display.assert_called_once_with(
                            uri="bolt://localhost:7687",
                            username="neo4j",
                            password="existing123",
                            is_new=False,
                        )

    @pytest.mark.asyncio
    async def test_spawns_new_container_when_none_exists(self):
        """Test that new container is spawned when none exists."""
        with patch("blarify.cli.commands.create.Neo4jContainerManager") as MockManager:
            manager = MockManager.return_value
            
            # Mock get_existing_container to return None (no existing container)
            with patch("blarify.cli.commands.create.get_existing_container", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = None
                
                # Mock new container instance
                new_instance = Mock()
                new_instance.uri = "bolt://localhost:7687"
                new_instance.config.username = "neo4j"
                new_instance.config.password = "newpassword123"
                manager.start = AsyncMock(return_value=new_instance)
                
                with patch("blarify.cli.commands.create.get_or_create_neo4j_credentials") as mock_creds:
                    mock_creds.return_value = {"username": "neo4j", "password": "newpassword123"}
                    
                    with patch("blarify.cli.commands.create.display_neo4j_connection_info") as mock_display:
                        result = await create.spawn_or_get_neo4j_container()
                        
                        assert result == new_instance
                        manager.start.assert_called_once()
                        
                        # Verify the config passed to start
                        call_args = manager.start.call_args
                        config = call_args[0][0]
                        assert isinstance(config, Neo4jContainerConfig)
                        assert config.environment == Environment.DEVELOPMENT
                        assert config.password == "newpassword123"
                        assert config.username == "neo4j"
                        assert "apoc" in config.plugins
                        assert "graph-data-science" in config.plugins
                        
                        mock_display.assert_called_once_with(
                            uri="bolt://localhost:7687",
                            username="neo4j",
                            password="newpassword123",
                            is_new=True,
                        )

    @pytest.mark.asyncio
    async def test_container_config_includes_required_plugins(self):
        """Test that container configuration includes required plugins."""
        with patch("blarify.cli.commands.create.Neo4jContainerManager") as MockManager:
            manager = MockManager.return_value
            
            # Mock get_existing_container to return None
            with patch("blarify.cli.commands.create.get_existing_container", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = None
                
                new_instance = Mock()
                new_instance.uri = "bolt://localhost:7687"
                new_instance.config.username = "neo4j"
                new_instance.config.password = "test12345678"  # At least 8 chars
                manager.start = AsyncMock(return_value=new_instance)
                
                with patch("blarify.cli.commands.create.get_or_create_neo4j_credentials") as mock_creds:
                    mock_creds.return_value = {"username": "neo4j", "password": "test12345678"}  # At least 8 chars
                    
                    with patch("blarify.cli.commands.create.display_neo4j_connection_info"):
                        await create.spawn_or_get_neo4j_container()
                        
                        call_args = manager.start.call_args
                        config = call_args[0][0]
                        
                        # Check plugins
                        assert "apoc" in config.plugins
                        assert "graph-data-science" in config.plugins
                        
                        # Check custom configuration
                        assert "dbms.security.procedures.unrestricted" in config.custom_config
                        assert "apoc.*,gds.*" in config.custom_config["dbms.security.procedures.unrestricted"]