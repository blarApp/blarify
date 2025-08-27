import os
import time
from typing import Any, List, Dict

from dotenv import load_dotenv
from neo4j import Driver, GraphDatabase, exceptions
import logging

from blarify.repositories.graph_db_manager.db_manager import AbstractDbManager
from blarify.repositories.graph_db_manager.dtos.node_found_by_name_type import NodeFoundByNameTypeDto

logger = logging.getLogger(__name__)

load_dotenv()


class Neo4jManager(AbstractDbManager):
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
            print(record)

    @staticmethod
    def _create_edges_txn(tx, edgesList: List[Any], batch_size: int, entityId: str, repoId: str):
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

    def get_node_by_name_and_type(
        self, name: str, type: str, company_id: str, repo_id: str, diff_identifier: str
    ) -> List[NodeFoundByNameTypeDto]:
        query = """
        MATCH (n:NODE {name: $name, entityId: $entity_id, repoId: $repo_id})
        WHERE (n.diff_identifier = $diff_identifier OR n.diff_identifier = "0") AND $type IN labels(n)
        AND NOT (n)-[:DELETED]->()
        AND NOT ()-[:MODIFIED]->(n)
        RETURN n.node_id as node_id, n.name as name, n.label as label,
               n.diff_text as diff_text, n.diff_identifier as diff_identifier,
               n.node_path as node_path, n.text as text

        LIMIT 100;
        """
        params = {
            "name": str(name),
            "entity_id": str(company_id),
            "repo_id": str(repo_id),
            "type": str(type),
            "diff_identifier": str(diff_identifier),
        }
        record = self.query(
            query,
            parameters=params,
            result_format="data",
        )

        if record is None:
            return []

        found_nodes = [
            NodeFoundByNameTypeDto(
                id=node.get("node_id"),
                name=node.get("name"),
                label=node.get("label"),
                diff_text=node.get("diff_text"),
                node_path=node.get("node_path"),
                text=node.get("text"),
                diff_identifier=node.get("diff_identifier"),
            )
            for node in record
        ]

        return found_nodes
