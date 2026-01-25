import os
from typing import Any, List, Optional
import logging
from pathlib import Path

from dotenv import load_dotenv
import kuzu

from .db_manager import AbstractDbManager

logger = logging.getLogger(__name__)

load_dotenv()


class KuzuManager(AbstractDbManager):
    """Kuzu embedded graph database manager.

    Kuzu is an embedded graph database that supports openCypher queries
    without requiring a separate server process. It stores data in a local
    directory and provides a lightweight alternative to Neo4j.

    Attributes:
        entity_id: Entity identifier for namespacing
        repo_id: Repository identifier for namespacing
        db: Kuzu database instance
        conn: Kuzu connection instance for queries
    """

    entity_id: str
    repo_id: str
    db: kuzu.Database
    conn: kuzu.Connection

    def __init__(
        self,
        repo_id: Optional[str] = None,
        entity_id: Optional[str] = None,
        db_path: Optional[str] = None,
    ):
        """Initialize Kuzu database manager.

        Args:
            repo_id: Repository identifier for namespacing
            entity_id: Entity identifier for namespacing
            db_path: Path to Kuzu database directory. Defaults to ~/.cue/kuzu_db
        """
        # Set default path if not provided
        if db_path is None:
            db_path = os.getenv("KUZU_DB_PATH", str(Path.home() / ".cue" / "kuzu_db"))

        # Ensure parent directory exists
        db_path_obj = Path(db_path)
        db_path_obj.parent.mkdir(parents=True, exist_ok=True)

        # Initialize database (Kuzu will create the database directory)
        self.db = kuzu.Database(str(db_path))
        self.conn = kuzu.Connection(self.db)

        self.repo_id = repo_id if repo_id is not None else "default_repo"
        self.entity_id = entity_id if entity_id is not None else "default_user"

        # Initialize schema
        self._initialize_schema()

    def _initialize_schema(self) -> None:
        """Initialize Kuzu schema with node and relationship tables."""
        try:
            # Create NODE table if it doesn't exist
            self.conn.execute("""
                CREATE NODE TABLE IF NOT EXISTS NODE(
                    node_id STRING,
                    name STRING,
                    path STRING,
                    repoId STRING,
                    entityId STRING,
                    node_type STRING,
                    PRIMARY KEY (node_id)
                )
            """)

            # Create relationship tables
            self.conn.execute("""
                CREATE REL TABLE IF NOT EXISTS CONTAINS(
                    FROM NODE TO NODE,
                    scopeText STRING
                )
            """)

            self.conn.execute("""
                CREATE REL TABLE IF NOT EXISTS CALLS(
                    FROM NODE TO NODE,
                    scopeText STRING
                )
            """)

            self.conn.execute("""
                CREATE REL TABLE IF NOT EXISTS REFERENCES(
                    FROM NODE TO NODE,
                    scopeText STRING
                )
            """)

            self.conn.execute("""
                CREATE REL TABLE IF NOT EXISTS IMPORTS(
                    FROM NODE TO NODE,
                    scopeText STRING
                )
            """)

            logger.debug("Kuzu schema initialized successfully")

        except Exception as e:
            # Schema might already exist - log but don't fail
            logger.debug(f"Schema initialization note: {e}")

    def close(self) -> None:
        """Close the Kuzu database connection."""
        # Kuzu connections are automatically closed when object is destroyed
        pass

    def save_graph(self, nodes: List[Any], edges: List[Any]) -> None:
        """Save nodes and edges to the Kuzu database.

        Args:
            nodes: List of node dictionaries to save
            edges: List of edge dictionaries to save
        """
        self.create_nodes(nodes)
        self.create_edges(edges)

    def create_nodes(self, nodeList: List[Any]) -> None:
        """Create nodes in the Kuzu database.

        Args:
            nodeList: List of node dictionaries with 'type' and 'attributes' keys
        """
        for node in nodeList:
            try:
                node_type = node.get("type", "UNKNOWN")
                attrs = node.get("attributes", {})

                # Extract node attributes
                node_id = attrs.get("node_id", attrs.get("id", ""))
                name = attrs.get("name", "")
                path = attrs.get("path", "")

                # Use MERGE to avoid duplicates
                query = """
                    MERGE (n:NODE {node_id: $node_id})
                    ON CREATE SET
                        n.name = $name,
                        n.path = $path,
                        n.repoId = $repoId,
                        n.entityId = $entityId,
                        n.node_type = $node_type
                """

                params = {
                    "node_id": node_id,
                    "name": name,
                    "path": path,
                    "repoId": self.repo_id,
                    "entityId": self.entity_id,
                    "node_type": node_type,
                }

                self.conn.execute(query, params)

            except Exception as e:
                logger.warning(f"Failed to create node {node.get('attributes', {}).get('node_id')}: {e}")

    def create_edges(self, edgesList: List[Any]) -> None:
        """Create edges between nodes in the Kuzu database.

        Args:
            edgesList: List of edge dictionaries with sourceId, targetId, and type
        """
        for edge in edgesList:
            try:
                source_id = edge.get("sourceId", "")
                target_id = edge.get("targetId", "")
                edge_type = edge.get("type", "UNKNOWN")
                scope_text = edge.get("scopeText", "")

                # Map edge types to relationship tables
                if edge_type in ["CONTAINS", "CALLS", "REFERENCES", "IMPORTS"]:
                    query = f"""
                        MATCH (source:NODE {{node_id: $source_id}})
                        MATCH (target:NODE {{node_id: $target_id}})
                        MERGE (source)-[r:{edge_type}]->(target)
                        SET r.scopeText = $scope_text
                    """

                    params = {
                        "source_id": source_id,
                        "target_id": target_id,
                        "scope_text": scope_text,
                    }

                    self.conn.execute(query, params)
                else:
                    logger.warning(f"Unknown edge type: {edge_type}")

            except Exception as e:
                logger.warning(f"Failed to create edge {edge.get('sourceId')} -> {edge.get('targetId')}: {e}")

    def detatch_delete_nodes_with_path(self, path: str) -> None:
        """Detach and delete nodes matching the given path.

        Args:
            path: File path to match for deletion
        """
        try:
            query = """
                MATCH (n:NODE {path: $path})
                DETACH DELETE n
            """
            self.conn.execute(query, {"path": path})
            logger.debug(f"Deleted nodes with path: {path}")
        except Exception as e:
            logger.error(f"Failed to delete nodes with path {path}: {e}")
