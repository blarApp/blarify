import os
from typing import Any, List, Dict
import logging

from dotenv import load_dotenv
from falkordb import FalkorDB

from blarify.repositories.graph_db_manager.db_manager import AbstractDbManager

logger = logging.getLogger(__name__)

load_dotenv()


class FalkorDBManager(AbstractDbManager):
    entity_id: str
    repo_id: str
    db: FalkorDB

    def __init__(
        self,
        repo_id: str = None,
        entity_id: str = None,
        uri: str = None,
        user: str = None,
        password: str = None,
    ):
        host = uri or os.getenv("FALKORDB_URI", "localhost")
        port = int(os.getenv("FALKORDB_PORT", 6379))
        user = user or os.getenv("FALKORDB_USERNAME")
        password = password or os.getenv("FALKORDB_PASSWORD")

        self.db = FalkorDB(host=host, port=port, username=user, password=password)

        self.repo_id = repo_id if repo_id is not None else "default_repo"
        self.entity_id = entity_id if entity_id is not None else "default_user"

    def close(self):
        pass

    def save_graph(self, nodes: List[Any], edges: List[Any]):
        self.create_nodes(nodes)
        self.create_edges(edges)

    def create_nodes(self, nodeList: List[dict]):
        graph = self.db.select_graph(self.repo_id)
        cypher_query = """
        UNWIND $nodes AS node
        CREATE (n)
        SET n = node.attributes
        WITH n AS created_node, node.extra_labels AS labels
        UNWIND labels AS label
        SET created_node:label
        RETURN created_node
        """
        graph.query(
            cypher_query,
            params={"nodes": nodeList},
        )

    def create_edges(self, edgesList: List[dict]):
        graph = self.db.select_graph(self.repo_id)
        
        # Process each edge individually since FalkorDB doesn't support dynamic relationship types in UNWIND
        for edge in edgesList:
            rel_type = edge.get("type", "UNKNOWN")
            cypher_query = f"""
            MATCH (a {{node_id: $sourceId}}), (b {{node_id: $targetId}})
            CREATE (a)-[r:{rel_type}]->(b)
            SET r.scopeText = $scopeText
            """
            
            # Add optional properties if they exist
            params = {
                "sourceId": edge["sourceId"],
                "targetId": edge["targetId"],
                "scopeText": edge.get("scopeText", "")
            }
            
            if edge.get("startLine") is not None:
                cypher_query += ", r.startLine = $startLine"
                params["startLine"] = edge["startLine"]
                
            if edge.get("referenceCharacter") is not None:
                cypher_query += ", r.referenceCharacter = $referenceCharacter"
                params["referenceCharacter"] = edge["referenceCharacter"]
            
            graph.query(cypher_query, params=params)

    def detach_delete_nodes_with_path(self, path: str):
        graph = self.db.select_graph(self.repo_id)
        cypher_query = "MATCH (n {path: $path}) DETACH DELETE n"
        result = graph.query(cypher_query, params={"path": path})
        return result.result_set

    def query(self, cypher_query: str, parameters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Execute a Cypher query and return the results.

        Args:
            cypher_query: The Cypher query string to execute
            parameters: Optional dictionary of parameters for the query

        Returns:
            List of dictionaries containing the query results
        """
        if parameters is None:
            parameters = {}

        try:
            graph = self.db.select_graph(self.repo_id)
            result = graph.query(cypher_query, params=parameters)

            # Convert FalkorDB result to dictionary format
            results = []
            if result.result_set:
                headers = result.header
                for row in result.result_set:
                    row_dict = {}
                    for i, header in enumerate(headers):
                        if i < len(row):
                            row_dict[header] = row[i]
                    results.append(row_dict)

            return results
        except Exception as e:
            logger.exception(f"Error executing FalkorDB query: {e}")
            logger.exception(f"Query: {cypher_query}")
            logger.exception(f"Parameters: {parameters}")
            raise
