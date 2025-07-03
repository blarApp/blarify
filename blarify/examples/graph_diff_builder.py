from blarify.prebuilt.graph_builder import GraphBuilder
from blarify.db_managers.neo4j_manager import Neo4jManager
from blarify.db_managers.falkordb_manager import FalkorDBManager

import dotenv
import os

from blarify.prebuilt.graph_diff_builder import GraphDiffBuilder
from blarify.project_graph_diff_creator import ChangeType, FileDiff, PreviousNodeState


def build(root_path: str = None):
    graph_builder = GraphDiffBuilder(
        root_path=root_path,
        file_diffs=get_file_diffs(),
        previous_node_states=get_previous_node_states(),
        extensions_to_skip=[".json"],
        names_to_skip=["__pycache__", ".venv", ".git", ".env", "node_modules"],
    )
    graph = graph_builder.build()

    relationships = graph.get_relationships_as_objects()
    nodes = graph.get_nodes_as_objects()

    save_to_neo4j(relationships, nodes)


def make_file_uri(relative_path: str) -> str:
    """Safely constructs a file URI from the root path and a relative path."""
    root = os.getenv("ROOT_PATH", "").rstrip("/")
    full_path = os.path.join(root, relative_path.lstrip("/"))
    # Ensure forward slashes for URI format
    return f"file://{full_path.replace(os.path.sep, '/')}"


def get_previous_node_states():
    # Example previous node states from db
    return [
        PreviousNodeState(
            node_path="/blarify/repo/one-line-code/src/utils/helpers.py",
            code_text="import re\n\ndef validate_email(email):\n  # Code replaced for brevity, see node: 57594c53249e1bbcdbb5555bdceeca5b\n\ndef format_name(first_name, last_name):\n   # Code replaced for brevity, see node: d76c383185fa6eb50005322ffe64e2d1\ndef sanitize_string(input_string):\n    # Code replaced for brevity, see node: 8b6d119db616ebdc9561363201f653d9\ndef generate_username(name, email):\n    # Code replaced for brevity, see node: 7ca279add313cdaa0061b07492e82530\n",
        ),
        PreviousNodeState(
            node_path="/blarify/repo/one-line-code/src/utils/helpers.py.validate_email",
            code_text='''def validate_email(email):
    """Validate email format using regex"""
    if not email or not isinstance(email, str):
        return False
    
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None''',
        ),
        PreviousNodeState(
            node_path="/blarify/repo/one-line-code/src/utils/helpers.py.format_name",
            code_text='''def format_name(first_name, last_name):
    """Format full name with proper capitalization"""
    if not first_name or not last_name:
        return ""
    return f"{first_name.strip().capitalize()} {last_name.strip().capitalize()}"''',
        ),
        PreviousNodeState(
            node_path="/blarify/repo/one-line-code/src/utils/helpers.py.sanitize_string",
            code_text='''def sanitize_string(input_string):
    """Remove extra whitespace and special characters"""
    if not input_string:
        return ""
    return " ".join(input_string.strip().split())''',
        ),
        PreviousNodeState(
            code_text='''def generate_username(name, email):
    """Generate a username from name and email"""
    if not name or not email:
        return ""
    
    # Take first part of email and first name
    email_part = email.split('@')[0]
    name_part = name.lower().replace(' ', '')
    
    return f"{name_part}_{email_part}".lower()''',
            node_path="/blarify/repo/one-line-code/src/utils/helpers.py.generate_username",
        ),
    ]


def get_file_diffs():
    # Example file diffs from PR
    file_diffs = [
        FileDiff(
            path=make_file_uri("src/services/user_service.py"),
            diff_text=r'''@@ -47,4 +47,22 @@ def delete_user(self, user_id):
    
    def get_user_count(self):
        """Get total number of users"""
-        return len(self.users)
+        return len(self.users)
+    
+    def update_user(self, user_id, name=None, email=None):
+        """Update user information by ID"""
+        user = self.get_user_by_id(user_id)
+        if not user:
+            raise ValueError(f"User with ID {user_id} not found")
+        
+        if name is not None:
+            user.update_name(name)
+        
+        if email is not None:
+            # Check if new email already exists (excluding current user)
+            existing_user = self.get_user_by_email(email)
+            if existing_user and existing_user.id != user_id:
+                raise ValueError(f"User with email {email} already exists")
+            user.update_email(email)
+        
+        return user\ No newline at end of file''',
            change_type=ChangeType.MODIFIED,
        ),
        FileDiff(
            path=make_file_uri("src/utils/helpers.py"),
            diff_text=r'''@@ -14,19 +14,15 @@ def format_name(first_name, last_name):
        return ""
    return f"{first_name.strip().capitalize()} {last_name.strip().capitalize()}"

-def sanitize_string(input_string):
-    """Remove extra whitespace and special characters"""
-    if not input_string:
-        return ""
-    return " ".join(input_string.strip().split())
-
def generate_username(name, email):
    """Generate a username from name and email"""
    if not name or not email:
        return ""
    
-    # Take first part of email and first name
-    email_part = email.split('@')[0]
-    name_part = name.lower().replace(' ', '')
+    # Take first letter of first name and last name, plus email prefix
+    name_parts = name.strip().split()
+    first_initial = name_parts[0][0].lower() if name_parts else ""
+    last_initial = name_parts[-1][0].lower() if len(name_parts) > 1 else ""
+    email_prefix = email.split('@')[0][:3]  # First 3 chars of email
    
-    return f"{name_part}_{email_part}".lower()\ No newline at end of file
+    return f"{first_initial}{last_initial}{email_prefix}".lower()\ No newline at end of file''',
            change_type=ChangeType.MODIFIED,
        ),
    ]
    return file_diffs


def save_to_neo4j(relationships, nodes):
    graph_manager = Neo4jManager(repo_id="repo", entity_id="organization")

    print(f"Saving graph with {len(nodes)} nodes and {len(relationships)} relationships")
    graph_manager.save_graph(nodes, relationships)
    graph_manager.close()


def save_to_falkordb(relationships, nodes):
    graph_manager = FalkorDBManager(repo_id="repo", entity_id="organization")

    print(f"Saving graph with {len(nodes)} nodes and {len(relationships)} relationships")
    graph_manager.save_graph(nodes, relationships)
    graph_manager.close()


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.INFO)

    dotenv.load_dotenv()
    root_path = os.getenv("ROOT_PATH")
    build(root_path=root_path)
