"""Integration tests for blame-based GitHub integration."""

import pytest
from unittest.mock import Mock, patch
import json
import tempfile
import os

from blarify.integrations.github_creator import GitHubCreator
from blarify.repositories.version_control.github import GitHub
from blarify.graph.graph_environment import GraphEnvironment
from blarify.prebuilt.graph_builder import GraphBuilder
from blarify.repositories.graph_db_manager.neo4j_manager import Neo4jManager


@pytest.mark.integration
class TestBlameBasedIntegration:
    """Integration tests for blame-based GitHub integration workflow."""
    
    @pytest.fixture
    def test_repo_path(self):
        """Create a temporary test repository."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create sample Python files
            src_dir = os.path.join(tmpdir, "src")
            os.makedirs(src_dir)
            
            # Create main.py with functions
            main_content = '''
def authenticate(username: str, password: str) -> bool:
    """Authenticate a user."""
    if not username or not password:
        return False
    # Check credentials
    return username == "admin" and password == "secret"

def process_data(data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Process input data."""
    result = {}
    for item in data:
        key = item.get("key")
        value = item.get("value")
        if key and value:
            result[key] = value
    return result

class DataProcessor:
    """Main data processing class."""
    
    def __init__(self):
        self.data = []
    
    def add(self, item):
        self.data.append(item)
    
    def process(self):
        return process_data(self.data)
'''
            with open(os.path.join(src_dir, "main.py"), "w") as f:
                f.write(main_content)
            
            # Create utils.py
            utils_content = '''
def validate(value: Any) -> bool:
    """Validate input value."""
    return value is not None and value != ""

def format_output(data: Dict) -> str:
    """Format data for output."""
    return json.dumps(data, indent=2)
'''
            with open(os.path.join(src_dir, "utils.py"), "w") as f:
                f.write(utils_content)
            
            yield tmpdir
    
    @pytest.fixture
    def mock_db_manager(self):
        """Create mock database manager."""
        mock = Mock(spec=Neo4jManager)
        mock.query = Mock(return_value=[])
        mock.save_graph = Mock()
        return mock
    
    def test_blame_based_integration_workflow(self, test_repo_path, mock_db_manager):
        """Test complete blame-based GitHub integration workflow."""
        # Step 1: Build code graph
        builder = GraphBuilder(root_path=test_repo_path)
        graph = builder.build()
        
        assert graph.nodes
        assert any(n.label == "FUNCTION" and n.name == "authenticate" for n in graph.nodes)
        assert any(n.label == "FUNCTION" and n.name == "process_data" for n in graph.nodes)
        assert any(n.label == "CLASS" and n.name == "DataProcessor" for n in graph.nodes)
        
        # Convert nodes to format expected by GitHubCreator
        test_nodes = []
        for node in graph.nodes:
            if node.label in ["FUNCTION", "CLASS"]:
                test_nodes.append({
                    "id": node.hashed_id,
                    "path": node.path,
                    "start_line": node.start_line,
                    "end_line": node.end_line,
                    "name": node.name,
                    "label": node.label
                })
        
        # Step 2: Mock GitHub blame responses
        def mock_blame_response(file_path: str, start_line: int, end_line: int, ref: str = "HEAD"):
            """Generate mock blame response based on file and lines."""
            if "main.py" in file_path:
                if start_line <= 7:  # authenticate function
                    return [{
                        "sha": "abc123",
                        "message": "Implement authentication system",
                        "author": "Alice Developer",
                        "author_email": "alice@example.com",
                        "author_login": "alice",
                        "timestamp": "2024-01-01T10:00:00Z",
                        "url": "https://github.com/test/repo/commit/abc123",
                        "line_ranges": [{"start": start_line, "end": min(end_line, 7)}],
                        "pr_info": {
                            "number": 42,
                            "title": "Add authentication feature",
                            "url": "https://github.com/test/repo/pull/42",
                            "author": "alice",
                            "merged_at": "2024-01-01T11:00:00Z",
                            "state": "MERGED"
                        }
                    }]
                elif start_line <= 17:  # process_data function
                    return [{
                        "sha": "def456",
                        "message": "Add data processing functionality",
                        "author": "Bob Developer",
                        "author_email": "bob@example.com",
                        "timestamp": "2024-01-02T10:00:00Z",
                        "url": "https://github.com/test/repo/commit/def456",
                        "line_ranges": [{"start": max(start_line, 9), "end": min(end_line, 17)}],
                        "pr_info": None
                    }]
                else:  # DataProcessor class
                    return [{
                        "sha": "ghi789",
                        "message": "Refactor into DataProcessor class",
                        "author": "Charlie Developer",
                        "author_email": "charlie@example.com",
                        "author_login": "charlie",
                        "timestamp": "2024-01-03T10:00:00Z",
                        "url": "https://github.com/test/repo/commit/ghi789",
                        "line_ranges": [{"start": max(start_line, 19), "end": end_line}],
                        "pr_info": {
                            "number": 55,
                            "title": "Refactor data processing",
                            "url": "https://github.com/test/repo/pull/55",
                            "author": "charlie",
                            "merged_at": "2024-01-03T11:00:00Z"
                        }
                    }]
            else:  # utils.py
                return [{
                    "sha": "jkl012",
                    "message": "Add utility functions",
                    "author": "Dana Developer",
                    "author_email": "dana@example.com",
                    "timestamp": "2024-01-04T10:00:00Z",
                    "url": "https://github.com/test/repo/commit/jkl012",
                    "line_ranges": [{"start": start_line, "end": end_line}],
                    "pr_info": None
                }]
        
        # Step 3: Run blame-based GitHub integration
        with patch('blarify.integrations.github_creator.GitHub') as mock_github_class:
            mock_github = Mock(spec=GitHub)
            mock_github.blame_commits_for_range = Mock(side_effect=mock_blame_response)
            mock_github.blame_commits_for_nodes = Mock(
                side_effect=lambda nodes: {
                    node["id"]: mock_blame_response(
                        node["path"], 
                        node["start_line"], 
                        node["end_line"]
                    )
                    for node in nodes
                }
            )
            mock_github_class.return_value = mock_github
            
            creator = GitHubCreator(
                db_manager=mock_db_manager,
                graph_environment=GraphEnvironment(environment="test", diff_identifier="test_diff", root_path=test_repo_path),
                github_token="test_token",
                repo_owner="test",
                repo_name="repo"
            )
            creator.github_repo = mock_github
            
            result = creator.create_github_integration_from_nodes(
                nodes=test_nodes,
                save_to_database=True
            )
        
        # Step 4: Verify results
        assert result.error is None
        assert result.total_commits == 4  # abc123, def456, ghi789, jkl012
        assert result.total_prs == 2  # PR 42 and PR 55
        
        # Verify PR nodes
        pr_numbers = [pr.external_id for pr in result.pr_nodes]
        assert "42" in pr_numbers
        assert "55" in pr_numbers
        
        # Verify commit nodes
        commit_shas = [c.external_id for c in result.commit_nodes]
        assert "abc123" in commit_shas
        assert "def456" in commit_shas
        assert "ghi789" in commit_shas
        assert "jkl012" in commit_shas
        
        # Verify relationships
        assert len(result.relationships) > 0
        
        # Check for MODIFIED_BY relationships with blame attribution
        modified_by_rels = [r for r in result.relationships if r.get("type") == "MODIFIED_BY"]
        assert len(modified_by_rels) > 0
        
        # Verify blame attribution in relationships
        for rel in modified_by_rels:
            props = rel.get("properties", {})
            assert props.get("attribution_method") == "blame"
            assert props.get("attribution_accuracy") == "exact"
            assert "blamed_lines" in props
            assert props.get("total_lines_affected") > 0
        
        # Verify database save was called
        mock_db_manager.save_graph.assert_called_once()
    
    def test_blame_accuracy_vs_patch_parsing(self, mock_db_manager):
        """Test that blame provides more accurate attribution than patch parsing."""
        # Create nodes representing a file with multiple functions
        test_nodes = [
            {
                "id": "func1",
                "path": "src/api.py",
                "start_line": 10,
                "end_line": 20,
                "name": "get_user",
                "label": "FUNCTION"
            },
            {
                "id": "func2",
                "path": "src/api.py",
                "start_line": 22,
                "end_line": 35,
                "name": "update_user",
                "label": "FUNCTION"
            },
            {
                "id": "func3",
                "path": "src/api.py",
                "start_line": 37,
                "end_line": 50,
                "name": "delete_user",
                "label": "FUNCTION"
            }
        ]
        
        # Mock blame results showing different commits for each function
        blame_results = {
            "func1": [{
                "sha": "commit1",
                "message": "Initial get_user implementation",
                "author": "Alice",
                "timestamp": "2024-01-01T00:00:00Z",
                "line_ranges": [{"start": 10, "end": 20}],
                "pr_info": None
            }],
            "func2": [{
                "sha": "commit2",
                "message": "Add update_user functionality",
                "author": "Bob",
                "timestamp": "2024-01-02T00:00:00Z",
                "line_ranges": [{"start": 22, "end": 35}],
                "pr_info": None
            }],
            "func3": [{
                "sha": "commit3",
                "message": "Add delete_user functionality",
                "author": "Charlie",
                "timestamp": "2024-01-03T00:00:00Z",
                "line_ranges": [{"start": 37, "end": 50}],
                "pr_info": None
            }]
        }
        
        with patch('blarify.integrations.github_creator.GitHub') as mock_github_class:
            mock_github = Mock(spec=GitHub)
            mock_github.blame_commits_for_nodes = Mock(return_value=blame_results)
            mock_github_class.return_value = mock_github
            
            creator = GitHubCreator(
                db_manager=mock_db_manager,
                graph_environment=GraphEnvironment(environment="test", diff_identifier="test_diff", root_path=test_repo_path),
                github_token="test_token",
                repo_owner="test",
                repo_name="repo"
            )
            creator.github_repo = mock_github
            
            result = creator.create_github_integration_from_nodes(
                nodes=test_nodes,
                save_to_database=False
            )
        
        # Verify each function is correctly attributed to its own commit
        assert result.total_commits == 3
        
        # Check that each function has exactly one MODIFIED_BY relationship
        modified_by_rels = [r for r in result.relationships if r.get("type") == "MODIFIED_BY"]
        assert len(modified_by_rels) == 3
        
        # Verify exact line attribution
        for rel in modified_by_rels:
            props = rel.get("properties", {})
            blamed_lines = json.loads(props.get("blamed_lines", "[]"))
            assert len(blamed_lines) == 1  # Each function modified by exactly one range
            
            # Check that the line range matches the function boundaries
            node_id = rel.get("start_node_id")
            node = next(n for n in test_nodes if n["id"] == node_id)
            line_range = blamed_lines[0]
            assert line_range["start"] == node["start_line"]
            assert line_range["end"] == node["end_line"]
    
    def test_pr_association_through_blame(self, mock_db_manager):
        """Test that PRs are correctly associated through blame results."""
        test_nodes = [{
            "id": "node1",
            "path": "src/feature.py",
            "start_line": 1,
            "end_line": 50,
            "name": "Feature",
            "label": "CLASS"
        }]
        
        # Mock blame showing multiple commits from same PR
        blame_results = {
            "node1": [
                {
                    "sha": "commit1",
                    "message": "Start feature implementation",
                    "author": "Dev",
                    "timestamp": "2024-01-01T00:00:00Z",
                    "line_ranges": [{"start": 1, "end": 25}],
                    "pr_info": {
                        "number": 100,
                        "title": "Implement new feature",
                        "url": "https://github.com/test/repo/pull/100"
                    }
                },
                {
                    "sha": "commit2",
                    "message": "Complete feature implementation",
                    "author": "Dev",
                    "timestamp": "2024-01-01T01:00:00Z",
                    "line_ranges": [{"start": 26, "end": 50}],
                    "pr_info": {
                        "number": 100,
                        "title": "Implement new feature",
                        "url": "https://github.com/test/repo/pull/100"
                    }
                }
            ]
        }
        
        with patch('blarify.integrations.github_creator.GitHub') as mock_github_class:
            mock_github = Mock(spec=GitHub)
            mock_github.blame_commits_for_nodes = Mock(return_value=blame_results)
            mock_github_class.return_value = mock_github
            
            creator = GitHubCreator(
                db_manager=mock_db_manager,
                graph_environment=GraphEnvironment(environment="test", diff_identifier="test_diff", root_path=test_repo_path),
                github_token="test_token",
                repo_owner="test",
                repo_name="repo"
            )
            creator.github_repo = mock_github
            
            result = creator.create_github_integration_from_nodes(
                nodes=test_nodes,
                save_to_database=False
            )
        
        # Should create one PR node despite multiple commits
        assert result.total_prs == 1
        assert result.pr_nodes[0].external_id == "100"
        
        # Both commits should be linked to the PR
        assert result.total_commits == 2
        
        # Check PR → Commit relationships
        pr_commit_rels = [
            r for r in result.relationships 
            if r.rel_type.name == "INTEGRATION_SEQUENCE"
        ]
        assert len(pr_commit_rels) == 2