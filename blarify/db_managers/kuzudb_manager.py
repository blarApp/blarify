import os
from typing import List, Dict
import logging

from dotenv import load_dotenv
import kuzu

logger = logging.getLogger(__name__)

load_dotenv()

class KuzuDBManager:
    db: kuzu.Database
    conn: kuzu.Connection

    def __init__(self, db_path: str = None):
        # Initialize the database connection
        db_path = db_path or os.getenv("KUZUDB_PATH", "kuzu_db")
        self.db = kuzu.Database(db_path)
        self.conn = kuzu.Connection(self.db)

    def close(self):
        # Close the connection if necessary
        pass

    def save_graph(self, nodes: List[Dict], edges: List[Dict]):
        self.create_nodes(nodes)
        self.create_edges(edges)

    def create_nodes(self, node_list: List[Dict]):
        if not node_list:
            return
        
        first_batch = []
        last_batch = []
        for node in node_list:
            if node["attributes"].get("start_line"):
                first_batch.append(node)
            else:
                last_batch.append(node)
            
        for nodes in [first_batch, last_batch]:
            for node in nodes:
                attributes = ", ".join(f"{k}: ${k}" for k in node["attributes"].keys())
                cypher_query = f"""
                CREATE (n: NODE {{{attributes}}})
                """
                params = node["attributes"]
                self.conn.execute(cypher_query, params)

    def create_edges(self, edge_list: List[Dict]):
        if not edge_list:
            return

        # Prepare the UNWIND query for creating edges
        cypher_query = """
        UNWIND $edges AS edge
        MATCH (a {node_id: edge.sourceId}), (b {node_id: edge.targetId})
        CREATE (a)-[r:`${edge.type}` {scopeText: edge.scopeText}]->(b)
        """
        params = {"edges": edge_list}
        self.conn.execute(cypher_query, params)

    def detach_delete_nodes_with_path(self, path: str):
        cypher_query = "MATCH (n {path: $path}) DETACH DELETE n"
        params = {"path": path}
        self.conn.execute(cypher_query, params)
