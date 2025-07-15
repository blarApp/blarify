import os
import time
from typing import Any, List, Dict, Optional

from dotenv import load_dotenv
from neo4j import Driver, GraphDatabase, exceptions
import logging

from .dtos import NodeSearchResultDTO

logger = logging.getLogger(__name__)

load_dotenv()


class Neo4jManager:
    entity_id: str
    repo_id: str
    driver: Driver

    def __init__(
        self,
        repo_id: str = None,
        entity_id: str = None,
        max_connections: int = 50,
        uri: str = None,
        user: str = None,
        password: str = None,
    ):
        uri = uri or os.getenv("NEO4J_URI")
        user = user or os.getenv("NEO4J_USERNAME")
        password = password or os.getenv("NEO4J_PASSWORD")

        retries = 3
        for attempt in range(retries):
            try:
                self.driver = GraphDatabase.driver(uri, auth=(user, password), max_connection_pool_size=max_connections)
                break
            except exceptions.ServiceUnavailable as e:
                if attempt < retries - 1:
                    time.sleep(2**attempt)  # Exponential backoff
                else:
                    raise e

        self.repo_id = repo_id if repo_id is not None else "default_repo"
        self.entity_id = entity_id if entity_id is not None else "default_user"

    def close(self):
        # Close the connection to the database
        self.driver.close()

    def save_graph(self, nodes: List[Any], edges: List[Any]):
        self.create_nodes(nodes)
        self.create_edges(edges)

    def create_nodes(self, nodeList: List[Any]):
        # Function to create nodes in the Neo4j database
        with self.driver.session() as session:
            session.write_transaction(
                self._create_nodes_txn, nodeList, 100, repoId=self.repo_id, entityId=self.entity_id
            )

    def create_edges(self, edgesList: List[Any]):
        # Function to create edges between nodes in the Neo4j database
        with self.driver.session() as session:
            session.write_transaction(self._create_edges_txn, edgesList, 100, entityId=self.entity_id)

    @staticmethod
    def _create_nodes_txn(tx, nodeList: List[Any], batch_size: int, repoId: str, entityId: str):
        node_creation_query = """
        CALL apoc.periodic.iterate(
            "UNWIND $nodeList AS node RETURN node",
            "CALL apoc.merge.node(
            node.extra_labels + [node.type, 'NODE'],
            apoc.map.merge(node.attributes, {repoId: $repoId, entityId: $entityId}),
            {},
            {}
            )
            YIELD node as n RETURN count(n) as count",
            {batchSize: $batchSize, parallel: false, iterateList: true, params: {nodeList: $nodeList, repoId: $repoId, entityId: $entityId}}
        )
        YIELD batches, total, errorMessages, updateStatistics
        RETURN batches, total, errorMessages, updateStatistics
        """

        result = tx.run(node_creation_query, nodeList=nodeList, batchSize=batch_size, repoId=repoId, entityId=entityId)

        # Fetch the result
        for record in result:
            logger.info(f"Created {record['total']} nodes")
            print(record)

    @staticmethod
    def _create_edges_txn(tx, edgesList: List[Any], batch_size: int, entityId: str):
        # Cypher query using apoc.periodic.iterate for creating edges
        edge_creation_query = """
        CALL apoc.periodic.iterate(
            'WITH $edgesList AS edges UNWIND edges AS edgeObject RETURN edgeObject',
            'MATCH (node1:NODE {node_id: edgeObject.sourceId}) 
            MATCH (node2:NODE {node_id: edgeObject.targetId}) 
            CALL apoc.merge.relationship(
            node1, 
            edgeObject.type, 
            {scopeText: edgeObject.scopeText}, 
            {}, 
            node2, 
            {}
            ) 
            YIELD rel RETURN rel',
            {batchSize:$batchSize, parallel:false, iterateList: true, params:{edgesList: $edgesList, entityId: $entityId}}
        )
        YIELD batches, total, errorMessages, updateStatistics
        RETURN batches, total, errorMessages, updateStatistics
        """
        # Execute the query
        result = tx.run(edge_creation_query, edgesList=edgesList, batchSize=batch_size, entityId=entityId)

        # Fetch the result
        for record in result:
            logger.info(f"Created {record['total']} edges")

    def detatch_delete_nodes_with_path(self, path: str):
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (n {path: $path})
                DETACH DELETE n
                """,
                path=path,
            )
            return result.data()

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
            with self.driver.session() as session:
                result = session.run(cypher_query, parameters)
                return [record.data() for record in result]
        except Exception as e:
            logger.error(f"Error executing Neo4j query: {e}")
            logger.error(f"Query: {cypher_query}")
            logger.error(f"Parameters: {parameters}")
            raise

    def get_node_by_id_v2(
        self, node_id: str, company_id: str, diff_identifier: Optional[str] = None
    ) -> Optional[NodeSearchResultDTO]:
        """
        Get a node by its ID.

        Args:
            node_id: The ID of the node to retrieve
            company_id: Company ID to filter by
            diff_identifier: Optional diff identifier for PR context

        Returns:
            An instance of NodeSearchResultDTO containing the node data, or None if not found
        """
        query = """
        MATCH (n:NODE {node_id: $node_id})
        RETURN n
        """
        result = self.query(query, {"node_id": node_id})

        if result:
            node_data = result[0]["n"]
            # Create NodeSearchResultDTO with required fields
            # Note: You'll need to implement the logic to populate outbound_relations and inbound_relations
            return NodeSearchResultDTO(
                node_id=node_data.get("node_id", ""),
                node_name=node_data.get("node_name", ""),
                node_labels=node_data.get("node_labels", []),
                path=node_data.get("path", ""),
                node_path=node_data.get("node_path", ""),
                code=node_data.get("code", ""),
                diff_text=node_data.get("diff_text", ""),
                outbound_relations=[],  # TODO: Implement relationship queries
                inbound_relations=[],  # TODO: Implement relationship queries
                modified_node=node_data.get("modified_node", False),
            )
        else:
            return None
