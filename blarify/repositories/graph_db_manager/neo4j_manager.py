import os
import time
from typing import Any, List, Dict, LiteralString, Optional

from dotenv import load_dotenv
from neo4j import Driver, GraphDatabase, ManagedTransaction, exceptions
import logging

from blarify.repositories.graph_db_manager.adapters.node_search_result_adapter import Neo4jNodeSearchResultAdapter
from blarify.repositories.graph_db_manager.db_manager import AbstractDbManager
from blarify.repositories.graph_db_manager.dtos.node_search_result_dto import NodeSearchResultDTO
from blarify.repositories.graph_db_manager.dtos.node_found_by_name_type import NodeFoundByNameTypeDto
from blarify.repositories.graph_db_manager.queries import get_node_by_id_query, get_node_by_name_and_type_query

logger = logging.getLogger(__name__)

# Disable Neo4j warning logs
neo4j_logger = logging.getLogger("neo4j")
neo4j_logger.setLevel(logging.ERROR)

load_dotenv()


class Neo4jManager(AbstractDbManager):
    entity_id: str
    repo_id: str
    driver: Driver

    def __init__(
        self,
        repo_id: Optional[str] = None,
        entity_id: Optional[str] = None,
        uri: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        max_connections: int = 50,
    ):
        uri = uri or os.getenv("NEO4J_URI")
        user = user or os.getenv("NEO4J_USERNAME")
        password = password or os.getenv("NEO4J_PASSWORD")

        if not uri or not user or not password:
            raise ValueError("Missing required Neo4j connection parameters")

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
            session.execute_write(
                self._create_nodes_txn,
                nodeList,
                1000,
                repoId=self.repo_id,
                entityId=self.entity_id,
            )

    def create_edges(self, edgesList: List[Any]):
        # Function to create edges between nodes in the Neo4j database
        with self.driver.session() as session:
            session.execute_write(self._create_edges_txn, edgesList, 1000, entityId=self.entity_id, repoId=self.repo_id)

    @staticmethod
    def _create_nodes_txn(tx: ManagedTransaction, nodeList: List[Any], batch_size: int, repoId: str, entityId: str):
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

        result = tx.run(
            node_creation_query,
            nodeList=nodeList,
            batchSize=batch_size,
            repoId=repoId,
            entityId=entityId,
        )

        # Fetch the result
        for record in result:
            logger.info(f"Created {record['total']} nodes")
            if record["errorMessages"]:
                logger.error(f"Error creating nodes: {record['errorMessages']}")
            print(record)

    @staticmethod
    def _create_edges_txn(tx: ManagedTransaction, edgesList: List[Any], batch_size: int, entityId: str, repoId: str):
        # Cypher query using apoc.periodic.iterate for creating edges
        edge_creation_query = """
        CALL apoc.periodic.iterate(
            'WITH $edgesList AS edges UNWIND edges AS edgeObject RETURN edgeObject',
            'MATCH (node1:NODE {node_id: edgeObject.sourceId, repoId: $repoId, entityId: $entityId}) 
            MATCH (node2:NODE {node_id: edgeObject.targetId, repoId: $repoId, entityId: $entityId}) 
            CALL apoc.merge.relationship(
            node1, 
            edgeObject.type, 
            apoc.map.removeKeys(edgeObject, ["sourceId", "targetId", "type"]), 
            {}, 
            node2, 
            {}
            ) 
            YIELD rel RETURN rel',
            {batchSize:$batchSize, parallel:false, iterateList: true, params:{edgesList: $edgesList, entityId: $entityId, repoId: $repoId}}
        )
        YIELD batches, total, errorMessages, updateStatistics
        RETURN batches, total, errorMessages, updateStatistics
        """
        # Execute the query
        result = tx.run(
            edge_creation_query,
            edgesList=edgesList,
            batchSize=batch_size,
            entityId=entityId,
            repoId=repoId,
        )

        # Fetch the result
        for record in result:
            logger.info(f"Created {record['total']} edges")
            print(record)

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

    def query(self, cypher_query: LiteralString, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
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

        if "repo_id" not in parameters:
            parameters["repo_id"] = self.repo_id
        if "entity_id" not in parameters:
            parameters["entity_id"] = self.entity_id

        try:
            with self.driver.session() as session:
                result = session.run(cypher_query, parameters)
                return [record.data() for record in result]
        except Exception as e:
            logger.exception(f"Error executing Neo4j query: {e}")
            logger.exception(f"Query: {cypher_query}")
            logger.exception(f"Parameters: {parameters}")
            raise

    def get_node_by_id(
        self,
        node_id: str,
        company_id: str,
    ) -> NodeSearchResultDTO:
        """
        Retrieve a node by its ID with related inbound and outbound relationships.

        Args:
            node_id: Unique identifier of the node to retrieve
            company_id: Company identifier for data isolation
            diff_identifier: Optional identifier for diff-specific nodes (unused)

        Returns:
            NodeSearchResultDTO: Data transfer object containing node information

        Raises:
            ValueError: If the node cannot be found
        """

        # Query the database
        params = {"node_id": node_id, "entity_id": company_id, "repo_id": self.repo_id}
        records = self.query(cypher_query=get_node_by_id_query(), parameters=params)

        if not records:
            raise ValueError(f"Node with id {node_id} not found")

        # Process the query results
        record = records[0]
        node = record["n"]
        labels = record["labels"]

        # Filter relationships to ensure no null values
        outbound_relations = record["outbound_relations"]
        inbound_relations = record["inbound_relations"]
        documentation_nodes = record.get("documentation_nodes", [])

        node_info = {
            "node_id": node.get("node_id"),
            "node_name": node.get("name"),
            "file_path": node.get("path"),
            "node_path": node.get("node_path"),
            "start_line": node.get("start_line"),
            "end_line": node.get("end_line"),
            "text": node.get("text"),
            "file_node_id": node.get("file_node_id"),
            "labels": labels,
            "documentation_nodes": documentation_nodes,
        }

        # Convert to DTO
        node_result = Neo4jNodeSearchResultAdapter.adapt(node_data=(node_info, outbound_relations, inbound_relations))

        return node_result

    def get_node_by_name_and_type(
        self,
        name: str,
        node_type: str,
        company_id: str,
        repo_id: str,
        diff_identifier: str,
    ) -> list[NodeFoundByNameTypeDto]:
        """
        Retrieve nodes by name and type from the database.

        Args:
            name: Name of the node to search for
            node_type: Type/label of the node to search for
            company_id: Company identifier for data isolation
            repo_id: Repository identifier
            diff_identifier: Diff identifier for version control

        Returns:
            List of NodeFoundByNameTypeDto objects containing node information
        """
        # Query the database
        params = {
            "name": name,
            "node_type": node_type,
            "entity_id": company_id,
            "repo_id": repo_id,
        }
        records = self.query(cypher_query=get_node_by_name_and_type_query(), parameters=params)

        # Convert records to DTOs
        nodes = []
        for record in records:
            node = NodeFoundByNameTypeDto(
                node_id=record.get("node_id", ""),
                node_name=record.get("node_name", ""),
                node_type=record.get("node_type", []),
                file_path=record.get("file_path", ""),
                code=record.get("code"),
            )
            nodes.append(node)

        return nodes
