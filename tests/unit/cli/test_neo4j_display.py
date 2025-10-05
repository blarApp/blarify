"""Unit tests for Neo4j container information display."""

from io import StringIO
from unittest.mock import patch
from rich.console import Console

from blarify.cli.commands import create


class TestNeo4jDisplay:
    """Test user display for Neo4j container information."""

    def test_displays_new_container_info(self):
        """Test display for newly spawned container."""
        # Capture console output without color codes
        output = StringIO()
        test_console = Console(file=output, force_terminal=False, width=80, no_color=True)

        with patch("blarify.cli.commands.create.Console", return_value=test_console):
            create.display_neo4j_connection_info(
                uri="bolt://localhost:7687",
                username="neo4j",
                password="Kx9mP2nL5qR8vT3w",
                is_new=True,
                http_uri="http://localhost:7688",
            )

        captured = output.getvalue()

        # Check all required information is displayed with exact values
        assert "Neo4j Container Started" in captured
        assert "bolt://localhost:7687" in captured  # Exact URI
        assert "http://localhost:7688" in captured  # Exact browser URL
        assert "neo4j" in captured
        assert "Kx9mP2nL5qR8vT3w" in captured
        assert "Container will persist after exit" in captured
        assert "To stop: blarify create --stop-neo4j" in captured

    def test_displays_existing_container_info(self):
        """Test display for existing container."""
        # Capture console output without color codes
        output = StringIO()
        test_console = Console(file=output, force_terminal=False, width=80, no_color=True)

        with patch("blarify.cli.commands.create.Console", return_value=test_console):
            create.display_neo4j_connection_info(
                uri="bolt://localhost:7687",
                username="neo4j",
                password="Kx9mP2nL5qR8vT3w",
                is_new=False,
                http_uri="http://localhost:7688",
            )

        captured = output.getvalue()

        # Check correct header for existing container with exact values
        assert "Using Existing Neo4j Container" in captured
        assert "bolt://localhost:7687" in captured  # Exact URI
        assert "http://localhost:7688" in captured  # Exact browser URL
        assert "neo4j" in captured
        assert "Kx9mP2nL5qR8vT3w" in captured

        # Should not show "Container Started" for existing
        assert "Neo4j Container Started" not in captured

    def test_does_not_display_index_creation(self):
        """Test that index creation details are not shown to user."""
        # Capture console output
        output = StringIO()
        test_console = Console(file=output, force_terminal=True, width=80)

        with patch("blarify.cli.commands.create.Console", return_value=test_console):
            # Display connection info
            create.display_neo4j_connection_info(
                uri="bolt://localhost:7687",
                username="neo4j",
                password="test123",
                is_new=True,
                http_uri="http://localhost:7688",
            )

        captured = output.getvalue()

        # Should not contain any index-related terms
        assert "index" not in captured.lower()
        assert "constraint" not in captured.lower()
        assert "vector" not in captured.lower()
        assert "fulltext" not in captured.lower()

    def test_displays_custom_port_correctly(self):
        """Test that custom ports are displayed correctly."""
        # Capture console output without color codes
        output = StringIO()
        test_console = Console(file=output, force_terminal=False, width=80, no_color=True)

        with patch("blarify.cli.commands.create.Console", return_value=test_console):
            create.display_neo4j_connection_info(
                uri="bolt://localhost:8687",
                username="neo4j",
                password="test123",
                is_new=True,
                http_uri="http://localhost:8688",
            )

        captured = output.getvalue()

        # Check custom port is shown with exact values
        assert "bolt://localhost:8687" in captured  # Exact custom URI
        assert "http://localhost:8688" in captured  # Browser port should match allocated HTTP port

    def test_display_formatting_is_consistent(self):
        """Test that display formatting is consistent and well-structured."""
        # Capture console output for new container
        output_new = StringIO()
        console_new = Console(file=output_new, force_terminal=True, width=80)

        with patch("blarify.cli.commands.create.Console", return_value=console_new):
            create.display_neo4j_connection_info(
                uri="bolt://localhost:7687",
                username="neo4j",
                password="test123",
                is_new=True,
                http_uri="http://localhost:7688",
            )

        # Capture console output for existing container
        output_existing = StringIO()
        console_existing = Console(file=output_existing, force_terminal=True, width=80)

        with patch("blarify.cli.commands.create.Console", return_value=console_existing):
            create.display_neo4j_connection_info(
                uri="bolt://localhost:7687",
                username="neo4j",
                password="test123",
                is_new=False,
                http_uri="http://localhost:7688",
            )

        captured_new = output_new.getvalue()
        captured_existing = output_existing.getvalue()

        # Both should have box characters
        assert "╔" in captured_new
        assert "║" in captured_new
        assert "╚" in captured_new

        assert "╔" in captured_existing
        assert "║" in captured_existing
        assert "╚" in captured_existing

        # Both should have URI and credentials sections
        assert "URI:" in captured_new
        assert "Username:" in captured_new
        assert "Password:" in captured_new

        assert "URI:" in captured_existing
        assert "Username:" in captured_existing
        assert "Password:" in captured_existing

    def test_handles_long_passwords_in_display(self):
        """Test that long passwords are displayed correctly."""
        # Capture console output
        output = StringIO()
        test_console = Console(file=output, force_terminal=True, width=80)

        long_password = "A" * 32  # Very long password

        with patch("blarify.cli.commands.create.Console", return_value=test_console):
            create.display_neo4j_connection_info(
                uri="bolt://localhost:7687",
                username="neo4j",
                password=long_password,
                is_new=True,
                http_uri="http://localhost:7688",
            )

        captured = output.getvalue()

        # Password should be displayed (not truncated)
        assert long_password in captured

        # Display should still be formatted correctly
        assert "╔" in captured
        assert "║" in captured
        assert "╚" in captured
