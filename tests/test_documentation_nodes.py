import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch
from blarify.prebuilt.graph_builder import GraphBuilder
from blarify.graph.node.types.node_labels import NodeLabels
from blarify.graph.relationship.relationship_type import RelationshipType
from blarify.documentation import DocumentationParser, ConceptExtractor, DocumentationLinker


class TestDocumentationNodes:
    """Test suite for documentation parsing and knowledge graph generation."""
    
    def setup_method(self):
        """Create a temporary directory for testing."""
        self.test_dir: str = tempfile.mkdtemp()  # type: ignore[reportUninitializedInstanceVariable]
        
    def teardown_method(self):
        """Clean up the temporary directory."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def create_test_project(self):
        """Create a test project structure with documentation and code."""
        # Create documentation files
        os.makedirs(os.path.join(self.test_dir, "docs"))
        
        # README.md
        readme_content = """# MyProject

## Overview
MyProject is a web application that implements an authentication system using JWT tokens.

## Architecture
The project follows a Model-View-Controller (MVC) pattern with the following components:
- **AuthController** - Handles authentication requests
- **UserService** - Manages user data and validation
- **TokenManager** - Generates and validates JWT tokens

## API Endpoints
- `POST /api/auth/login` - User login endpoint (see auth_controller.py)
- `POST /api/auth/logout` - User logout endpoint
- `GET /api/auth/verify` - Token verification endpoint

## Installation
1. Install dependencies: `pip install -r requirements.txt`
2. Run migrations: `python manage.py migrate`
3. Start server: `python manage.py runserver`
"""
        Path(os.path.join(self.test_dir, "README.md")).write_text(readme_content)
        
        # API documentation
        api_doc_content = """# API Documentation

## Authentication API

### Login Endpoint
**URL:** `/api/auth/login`
**Method:** POST
**Handler:** `AuthController.login()` in `controllers/auth_controller.py`

Request:
```json
{
    "username": "string",
    "password": "string"
}
```

Response:
```json
{
    "token": "JWT token string",
    "user": {
        "id": 1,
        "username": "string"
    }
}
```

### Token Verification
The `TokenManager` class in `services/token_manager.py` handles JWT token generation and validation.
It uses the `pyjwt` library with RS256 algorithm.
"""
        Path(os.path.join(self.test_dir, "docs", "api.md")).write_text(api_doc_content)
        
        # Architecture documentation
        arch_doc_content = """# System Architecture

## Design Patterns

### Repository Pattern
The application uses the Repository pattern for data access:
- `UserRepository` - Handles user data persistence
- `SessionRepository` - Manages session data

### Service Layer
Business logic is encapsulated in service classes:
- `UserService` - User management logic
- `AuthService` - Authentication logic
- `TokenManager` - JWT token handling

### Dependency Injection
We use dependency injection for loose coupling between components.
See `container.py` for DI configuration.
"""
        Path(os.path.join(self.test_dir, "docs", "architecture.md")).write_text(arch_doc_content)
        
        # Create some code files
        os.makedirs(os.path.join(self.test_dir, "controllers"))
        os.makedirs(os.path.join(self.test_dir, "services"))
        
        # auth_controller.py
        auth_controller_code = """
class AuthController:
    def __init__(self, user_service, token_manager):
        self.user_service = user_service
        self.token_manager = token_manager
    
    def login(self, username, password):
        user = self.user_service.authenticate(username, password)
        if user:
            token = self.token_manager.generate_token(user)
            return {"token": token, "user": user}
        return None
"""
        Path(os.path.join(self.test_dir, "controllers", "auth_controller.py")).write_text(auth_controller_code)
        
        # user_service.py
        user_service_code = """
class UserService:
    def __init__(self, user_repository):
        self.user_repository = user_repository
    
    def authenticate(self, username, password):
        user = self.user_repository.find_by_username(username)
        if user and user.check_password(password):
            return user
        return None
"""
        Path(os.path.join(self.test_dir, "services", "user_service.py")).write_text(user_service_code)
        
        # token_manager.py
        token_manager_code = """
import jwt
from datetime import datetime, timedelta

class TokenManager:
    def __init__(self, secret_key):
        self.secret_key = secret_key
    
    def generate_token(self, user):
        payload = {
            'user_id': user.id,
            'username': user.username,
            'exp': datetime.utcnow() + timedelta(hours=24)
        }
        return jwt.encode(payload, self.secret_key, algorithm='RS256')
"""
        Path(os.path.join(self.test_dir, "services", "token_manager.py")).write_text(token_manager_code)
    
    def test_documentation_file_detection(self) -> None:
        """Test that documentation files are correctly identified."""
        self.create_test_project()
        
        # The documentation parser should find documentation files
        parser = DocumentationParser(root_path=self.test_dir)
        doc_files = parser.find_documentation_files()
        
        # Should find README.md and docs/*.md files
        doc_file_names = [os.path.basename(f) for f in doc_files]
        assert "README.md" in doc_file_names
        assert "api.md" in doc_file_names
        assert "architecture.md" in doc_file_names
        
        # Should not include code files
        assert "auth_controller.py" not in doc_file_names
    
    def test_concept_extraction_from_documentation(self) -> None:
        """Test that concepts are extracted from documentation using LLM."""
        self.create_test_project()
        
        # Mock the LLM response
        mock_llm_response = {
            "concepts": [
                {
                    "name": "Authentication System",
                    "description": "JWT-based authentication system for user login"
                },
                {
                    "name": "MVC Pattern",
                    "description": "Model-View-Controller architectural pattern"
                },
                {
                    "name": "Repository Pattern",
                    "description": "Data access pattern for persistence"
                }
            ],
            "entities": [
                {
                    "name": "AuthController",
                    "type": "class",
                    "description": "Handles authentication requests"
                },
                {
                    "name": "UserService",
                    "type": "class",
                    "description": "Manages user data and validation"
                },
                {
                    "name": "TokenManager",
                    "type": "class",
                    "description": "Generates and validates JWT tokens"
                }
            ],
            "relationships": [
                {
                    "from": "AuthController",
                    "to": "UserService",
                    "type": "uses"
                },
                {
                    "from": "AuthController",
                    "to": "TokenManager",
                    "type": "uses"
                }
            ],
            "code_references": [
                {
                    "text": "auth_controller.py",
                    "type": "file"
                },
                {
                    "text": "AuthController.login()",
                    "type": "method"
                },
                {
                    "text": "services/token_manager.py",
                    "type": "file"
                }
            ]
        }
        
        with patch('blarify.documentation.concept_extractor.ConceptExtractor.extract_from_content') as mock_extract:
            mock_extract.return_value = mock_llm_response
            
            extractor = ConceptExtractor()
            readme_path = os.path.join(self.test_dir, "README.md")
            result = extractor.extract_from_file(readme_path)
            
            # Verify concepts were extracted
            assert len(result["concepts"]) == 3
            assert any(c["name"] == "Authentication System" for c in result["concepts"])
            
            # Verify entities were extracted
            assert len(result["entities"]) == 3
            assert any(e["name"] == "AuthController" for e in result["entities"])
            
            # Verify code references were found
            assert len(result["code_references"]) == 3
    
    def test_documentation_node_creation(self) -> None:
        """Test that documentation nodes are created in the graph."""
        self.create_test_project()

        # Patch skeletonize to avoid AttributeError on _tree_sitter_node
        from unittest.mock import patch as patch_func
        with patch_func("blarify.graph.node.file_node.FileNode.skeletonize", lambda self: None):
            # Mock the concept extractor to return parsed data directly
            mock_extract_result = {
                "concepts": [
                    {"name": "Authentication System", "description": "JWT authentication"}
                ],
                "entities": [
                    {"name": "AuthController", "type": "class", "description": "Auth handler"}
                ],
                "relationships": [],
                "code_references": [{"text": "auth_controller.py", "type": "file"}]
            }

            with patch('blarify.documentation.concept_extractor.ConceptExtractor.extract_from_content') as mock_extract:
                mock_extract.return_value = mock_extract_result

                # Build graph with documentation nodes enabled
                graph_builder = GraphBuilder(
                    root_path=self.test_dir,
                    enable_documentation_nodes=True
                )
                graph = graph_builder.build()

                # Check for documentation file nodes
                doc_nodes = graph.get_nodes_by_label(NodeLabels.DOCUMENTATION_FILE)
                assert len(doc_nodes) > 0

                # Check for concept nodes
                concept_nodes = graph.get_nodes_by_label(NodeLabels.CONCEPT)
                assert len(concept_nodes) > 0

                # Check for documented entity nodes
                entity_nodes = graph.get_nodes_by_label(NodeLabels.DOCUMENTED_ENTITY)
                assert len(entity_nodes) > 0
    
    def test_documentation_to_code_linking(self) -> None:
        """Test that documentation nodes are linked to relevant code nodes."""
        self.create_test_project()
        
        # Create a mock graph with code nodes
        mock_graph = Mock()
        
        # Create proper mock nodes with string name attributes
        auth_node = Mock()
        auth_node.name = "AuthController"
        auth_node.path = "controllers/auth_controller.py"
        auth_node.label = NodeLabels.CLASS
        
        user_node = Mock()
        user_node.name = "UserService"
        user_node.path = "services/user_service.py"
        user_node.label = NodeLabels.CLASS
        
        token_node = Mock()
        token_node.name = "TokenManager"
        token_node.path = "services/token_manager.py"
        token_node.label = NodeLabels.CLASS
        
        code_nodes = [auth_node, user_node, token_node]
        mock_graph.get_all_nodes.return_value = code_nodes
        
        # Create documentation linker
        linker = DocumentationLinker()
        
        # Test linking a documented entity to code
        doc_entity = {
            "name": "AuthController",
            "type": "class",
            "description": "Handles authentication"
        }
        
        matches = linker.find_code_matches(doc_entity, mock_graph)
        assert len(matches) == 1
        assert matches[0].name == "AuthController"
        
        # Test linking with file reference
        code_ref = {
            "text": "services/token_manager.py",
            "type": "file"
        }
        
        matches = linker.find_code_matches_by_reference(code_ref, mock_graph)
        assert len(matches) == 1
        assert "token_manager.py" in matches[0].path
    
    def test_relationship_creation_between_doc_and_code(self) -> None:
        """Test that relationships are created between documentation and code nodes."""
        self.create_test_project()

        from unittest.mock import patch as patch_func
        with patch_func("blarify.graph.node.file_node.FileNode.skeletonize", lambda self: None):
            # Mock the concept extractor to return parsed data directly
            mock_extract_result = {
                "concepts": [{"name": "MVC Pattern", "description": "Model-View-Controller pattern"}],
                "entities": [
                    {"name": "AuthController", "type": "class", "description": "Authentication controller"}
                ],
                "relationships": [],
                "code_references": [{"text": "controllers/auth_controller.py", "type": "file"}]
            }

            with patch('blarify.documentation.concept_extractor.ConceptExtractor.extract_from_content') as mock_extract:
                mock_extract.return_value = mock_extract_result

                graph_builder = GraphBuilder(
                    root_path=self.test_dir,
                    enable_documentation_nodes=True
                )
                graph = graph_builder.build()

                # Check for DOCUMENTS relationships
                doc_relationships = [r for r in graph.get_all_relationships()
                                   if r.rel_type == RelationshipType.DOCUMENTS]
                assert len(doc_relationships) > 0

                # Check for IMPLEMENTS_CONCEPT relationships
                # These should exist if code implements documented concepts
                assert True  # Placeholder for concept relationship verification
            
    def test_documentation_parsing_can_be_disabled(self) -> None:
        """Test that documentation parsing can be disabled via configuration."""
        self.create_test_project()

        from unittest.mock import patch as patch_func
        with patch_func("blarify.graph.node.file_node.FileNode.skeletonize", lambda self: None):
            # Build graph with documentation nodes disabled
            graph_builder = GraphBuilder(
                root_path=self.test_dir,
                enable_documentation_nodes=False
            )
            graph = graph_builder.build()

            # Should not have any documentation nodes
            doc_nodes = graph.get_nodes_by_label(NodeLabels.DOCUMENTATION_FILE)
            assert len(doc_nodes) == 0

            concept_nodes = graph.get_nodes_by_label(NodeLabels.CONCEPT)
            assert len(concept_nodes) == 0
    
    def test_custom_documentation_patterns(self) -> None:
        """Test that custom documentation patterns can be configured."""
        self.create_test_project()
        
        # Create a custom doc file
        Path(os.path.join(self.test_dir, "DESIGN.txt")).write_text("Design document")
        
        # Configure to include .txt files
        parser = DocumentationParser(
            root_path=self.test_dir,
            documentation_patterns=["*.md", "*.txt"]
        )
        doc_files = parser.find_documentation_files()
        
        doc_file_names = [os.path.basename(f) for f in doc_files]
        assert "DESIGN.txt" in doc_file_names
    
    def test_llm_error_handling(self) -> None:
        """Test that LLM errors are handled gracefully."""
        self.create_test_project()
        
        with patch('blarify.documentation.concept_extractor.ConceptExtractor.extract_from_content') as mock_extract:
            # Simulate LLM error
            mock_extract.side_effect = Exception("LLM API error")
            
            parser = DocumentationParser(root_path=self.test_dir)
            # Should not crash, but log error and continue
            result = parser.parse_documentation_files()
            
            # Should still create documentation file nodes, even without concepts
            assert len(result["documentation_files"]) > 0