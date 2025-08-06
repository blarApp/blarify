"""
Data Management for Neo4j Container Testing.

This module handles test data import/export functionality for Neo4j containers,
supporting various formats (Cypher, JSON, CSV) and providing utilities for
quick test data setup and teardown.
"""

import asyncio
import csv
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, TYPE_CHECKING
import re

if TYPE_CHECKING:
    from .types import Neo4jContainerInstance

from .types import DataFormat, TestDataSpec, DataLoadError


class DataManager:
    """
    Manages test data import/export for Neo4j containers.
    
    Supports loading data from various formats and provides utilities for
    quick database setup, cleanup, and test data management.
    """
    
    def __init__(self, container_instance: 'Neo4jContainerInstance'):
        """
        Initialize the data manager.
        
        Args:
            container_instance: Neo4j container instance to manage data for
        """
        self.container = container_instance
    
    async def load_data_from_file(self, file_path: Path, 
                                 clear_before_load: bool = True,
                                 parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Load test data from a file.
        
        Args:
            file_path: Path to the data file
            clear_before_load: Whether to clear existing data first
            parameters: Parameters for parameterized queries
            
        Returns:
            Dictionary with load results and statistics
            
        Raises:
            DataLoadError: If data loading fails
        """
        if not file_path.exists():
            raise DataLoadError(f"Data file not found: {file_path}")
        
        # Determine format from file extension
        format_map = {
            '.cypher': DataFormat.CYPHER,
            '.cql': DataFormat.CYPHER,
            '.json': DataFormat.JSON,
            '.csv': DataFormat.CSV,
        }
        
        file_format = format_map.get(file_path.suffix.lower())
        if not file_format:
            raise DataLoadError(f"Unsupported file format: {file_path.suffix}")
        
        spec = TestDataSpec(
            file_path=file_path,
            format=file_format,
            clear_before_load=clear_before_load,
            parameters=parameters or {}
        )
        
        return await self.load_data_from_spec(spec)
    
    async def load_data_from_spec(self, spec: TestDataSpec) -> Dict[str, Any]:
        """
        Load test data based on a TestDataSpec.
        
        Args:
            spec: Test data specification
            
        Returns:
            Dictionary with load results and statistics
        """
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Clear existing data if requested
            if spec.clear_before_load:
                await self.clear_all_data()
            
            # Load data based on format
            if spec.format == DataFormat.CYPHER:
                result = await self._load_cypher_data(spec)
            elif spec.format == DataFormat.JSON:
                result = await self._load_json_data(spec)
            elif spec.format == DataFormat.CSV:
                result = await self._load_csv_data(spec)
            else:
                raise DataLoadError(f"Unsupported data format: {spec.format}")
            
            load_time = asyncio.get_event_loop().time() - start_time
            
            return {
                'success': True,
                'format': spec.format.value,
                'file_path': str(spec.file_path),
                'load_time_seconds': round(load_time, 3),
                'records_created': result.get('records_created', 0),
                'relationships_created': result.get('relationships_created', 0),
                'statements_executed': result.get('statements_executed', 0),
            }
            
        except Exception as e:
            load_time = asyncio.get_event_loop().time() - start_time
            raise DataLoadError(
                f"Failed to load data from {spec.file_path}: {e}. "
                f"Load time: {load_time:.3f}s"
            )
    
    async def _load_cypher_data(self, spec: TestDataSpec) -> Dict[str, Any]:
        """Load data from Cypher file."""
        cypher_content = spec.file_path.read_text(encoding='utf-8')
        
        # Split into individual statements (handling multi-line statements)
        statements = self._split_cypher_statements(cypher_content)
        
        records_created = 0
        relationships_created = 0
        statements_executed = 0
        
        for statement in statements:
            if statement.strip():
                try:
                    # Execute the statement
                    await self.container.execute_cypher(statement, spec.parameters)
                    
                    statements_executed += 1
                    
                    # Try to parse creation counts from result summary
                    # Note: This is a simplified approach - actual Neo4j drivers provide better stats
                    statement_lower = statement.lower()
                    if 'create' in statement_lower:
                        if '(' in statement and ')' in statement:
                            records_created += statement_lower.count('create (')
                        if '-[' in statement and ']->' in statement:
                            relationships_created += statement.count('-[')
                
                except Exception as e:
                    raise DataLoadError(f"Failed to execute Cypher statement: {statement[:100]}... Error: {e}")
        
        return {
            'records_created': records_created,
            'relationships_created': relationships_created,
            'statements_executed': statements_executed,
        }
    
    def _split_cypher_statements(self, cypher_content: str) -> List[str]:
        """Split Cypher content into individual statements."""
        # Remove comments
        lines = []
        for line in cypher_content.split('\n'):
            # Remove line comments
            if '//' in line:
                line = line[:line.index('//')]
            lines.append(line)
        
        content = '\n'.join(lines)
        
        # Remove block comments
        content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
        
        # Split by semicolon, but be careful about semicolons in strings
        statements = []
        current_statement = ""
        in_string = False
        escape_next = False
        
        for char in content:
            if escape_next:
                current_statement += char
                escape_next = False
                continue
            
            if char == '\\':
                current_statement += char
                escape_next = True
                continue
            
            if char == '"' or char == "'":
                current_statement += char
                in_string = not in_string
                continue
            
            if char == ';' and not in_string:
                if current_statement.strip():
                    statements.append(current_statement.strip())
                current_statement = ""
                continue
            
            current_statement += char
        
        # Add any remaining statement
        if current_statement.strip():
            statements.append(current_statement.strip())
        
        return statements
    
    async def _load_json_data(self, spec: TestDataSpec) -> Dict[str, Any]:
        """Load data from JSON file."""
        with open(spec.file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        records_created = 0
        relationships_created = 0
        statements_executed = 0
        
        # Support different JSON structures
        if isinstance(data, dict):
            # Structure: {"nodes": [...], "relationships": [...]}
            if 'nodes' in data:
                for node in data['nodes']:
                    await self._create_node_from_json(node, spec.parameters)
                    records_created += 1
                    statements_executed += 1
            
            if 'relationships' in data:
                for rel in data['relationships']:
                    await self._create_relationship_from_json(rel, spec.parameters)
                    relationships_created += 1
                    statements_executed += 1
                    
        elif isinstance(data, list):
            # Array of nodes
            for item in data:
                if 'type' in item and item['type'] == 'relationship':
                    await self._create_relationship_from_json(item, spec.parameters)
                    relationships_created += 1
                else:
                    await self._create_node_from_json(item, spec.parameters)
                    records_created += 1
                statements_executed += 1
        
        return {
            'records_created': records_created,
            'relationships_created': relationships_created,
            'statements_executed': statements_executed,
        }
    
    async def _create_node_from_json(self, node_data: Dict[str, Any], 
                                   parameters: Dict[str, Any]) -> None:
        """Create a node from JSON data."""
        # Extract labels and properties
        labels = node_data.get('labels', [])
        properties = {k: v for k, v in node_data.items() if k not in ['labels', 'id']}
        
        # Substitute parameters
        for key, value in properties.items():
            if isinstance(value, str) and value.startswith('$'):
                param_name = value[1:]
                if param_name in parameters:
                    properties[key] = parameters[param_name]
        
        # Build Cypher query
        labels_str = ':'.join(labels) if labels else ''
        if labels_str:
            labels_str = ':' + labels_str
        
        properties_str = ', '.join(f'{k}: ${k}' for k in properties.keys())
        
        query = f"CREATE (n{labels_str} {{{properties_str}}})"
        await self.container.execute_cypher(query, properties)
    
    async def _create_relationship_from_json(self, rel_data: Dict[str, Any],
                                           parameters: Dict[str, Any]) -> None:
        """Create a relationship from JSON data."""
        # Extract relationship components
        start_node = rel_data.get('start_node', {})
        end_node = rel_data.get('end_node', {})
        rel_type = rel_data.get('type', 'RELATED_TO')
        properties = {k: v for k, v in rel_data.items() 
                     if k not in ['start_node', 'end_node', 'type']}
        
        # Substitute parameters
        for key, value in properties.items():
            if isinstance(value, str) and value.startswith('$'):
                param_name = value[1:]
                if param_name in parameters:
                    properties[key] = parameters[param_name]
        
        # Build match conditions for start and end nodes
        start_match = self._build_node_match_condition(start_node, 'a')
        end_match = self._build_node_match_condition(end_node, 'b')
        
        # Build relationship properties
        rel_props = ', '.join(f'{k}: ${k}' for k in properties.keys()) if properties else ''
        rel_props_str = f' {{{rel_props}}}' if rel_props else ''
        
        query = f"""
        MATCH {start_match}
        MATCH {end_match}
        CREATE (a)-[r:{rel_type}{rel_props_str}]->(b)
        """
        
        await self.container.execute_cypher(query, properties)
    
    def _build_node_match_condition(self, node_spec: Dict[str, Any], var_name: str) -> str:
        """Build a MATCH condition for a node specification."""
        labels = node_spec.get('labels', [])
        properties = {k: v for k, v in node_spec.items() if k != 'labels'}
        
        labels_str = ':'.join(labels) if labels else ''
        if labels_str:
            labels_str = ':' + labels_str
        
        if properties:
            props_list = []
            for key, value in properties.items():
                if isinstance(value, str):
                    props_list.append(f'{key}: "{value}"')
                else:
                    props_list.append(f'{key}: {value}')
            props_str = ', '.join(props_list)
            return f"({var_name}{labels_str} {{{props_str}}})"
        else:
            return f"({var_name}{labels_str})"
    
    async def _load_csv_data(self, spec: TestDataSpec) -> Dict[str, Any]:
        """Load data from CSV file."""
        records_created = 0
        statements_executed = 0
        
        with open(spec.file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                # Create node from CSV row
                # Assume each row represents a node
                properties = {}
                labels = []
                
                for key, value in row.items():
                    if key.lower() == 'labels':
                        labels = [label.strip() for label in value.split(';') if label.strip()]
                    elif key.startswith('_'):
                        # Skip internal columns
                        continue
                    else:
                        # Convert values appropriately
                        if value.isdigit():
                            properties[key] = int(value)
                        elif value.replace('.', '').isdigit():
                            properties[key] = float(value)
                        elif value.lower() in ('true', 'false'):
                            properties[key] = value.lower() == 'true'
                        else:
                            properties[key] = value
                
                # Substitute parameters
                for key, value in properties.items():
                    if isinstance(value, str) and value.startswith('$'):
                        param_name = value[1:]
                        if param_name in spec.parameters:
                            properties[key] = spec.parameters[param_name]
                
                # Create the node
                labels_str = ':'.join(labels) if labels else 'Node'
                props_str = ', '.join(f'{k}: ${k}' for k in properties.keys())
                
                query = f"CREATE (n:{labels_str} {{{props_str}}})"
                await self.container.execute_cypher(query, properties)
                
                records_created += 1
                statements_executed += 1
        
        return {
            'records_created': records_created,
            'relationships_created': 0,
            'statements_executed': statements_executed,
        }
    
    async def export_data_to_file(self, file_path: Path, 
                                 format: DataFormat = DataFormat.JSON,
                                 query: Optional[str] = None) -> Dict[str, Any]:
        """
        Export data from the Neo4j database to a file.
        
        Args:
            file_path: Output file path
            format: Export format
            query: Custom query (default exports all data)
            
        Returns:
            Export statistics
        """
        start_time = asyncio.get_event_loop().time()
        
        if not query:
            query = "MATCH (n) RETURN n"
        
        try:
            results = await self.container.execute_cypher(query)
            
            if format == DataFormat.JSON:
                await self._export_to_json(file_path, results)
            elif format == DataFormat.CSV:
                await self._export_to_csv(file_path, results)
            elif format == DataFormat.CYPHER:
                await self._export_to_cypher(file_path, results)
            else:
                raise DataLoadError(f"Unsupported export format: {format}")
            
            export_time = asyncio.get_event_loop().time() - start_time
            
            return {
                'success': True,
                'format': format.value,
                'file_path': str(file_path),
                'export_time_seconds': round(export_time, 3),
                'records_exported': len(results),
            }
            
        except Exception as e:
            export_time = asyncio.get_event_loop().time() - start_time
            raise DataLoadError(
                f"Failed to export data to {file_path}: {e}. "
                f"Export time: {export_time:.3f}s"
            )
    
    async def _export_to_json(self, file_path: Path, results: List[Dict[str, Any]]) -> None:
        """Export results to JSON format."""
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, default=str)
    
    async def _export_to_csv(self, file_path: Path, results: List[Dict[str, Any]]) -> None:
        """Export results to CSV format."""
        if not results:
            return
        
        # Get all unique keys
        all_keys = set()
        for result in results:
            all_keys.update(result.keys())
        
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=sorted(all_keys))
            writer.writeheader()
            writer.writerows(results)
    
    async def _export_to_cypher(self, file_path: Path, results: List[Dict[str, Any]]) -> None:
        """Export results to Cypher format."""
        cypher_statements = []
        
        for result in results:
            # This is a simplified conversion - real implementation would need
            # more sophisticated Neo4j result parsing
            cypher_statements.append(f"// Result: {result}")
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(cypher_statements))
    
    async def clear_all_data(self) -> Dict[str, int]:
        """
        Clear all data from the database.
        
        Returns:
            Statistics about deleted data
        """
        # Get counts before deletion
        node_count_result = await self.container.execute_cypher("MATCH (n) RETURN count(n) as count")
        nodes_deleted = node_count_result[0]['count'] if node_count_result else 0
        
        rel_count_result = await self.container.execute_cypher("MATCH ()-[r]->() RETURN count(r) as count")
        relationships_deleted = rel_count_result[0]['count'] if rel_count_result else 0
        
        # Delete all data
        await self.container.execute_cypher("MATCH (n) DETACH DELETE n")
        
        return {
            'nodes_deleted': nodes_deleted,
            'relationships_deleted': relationships_deleted,
        }
    
    async def create_sample_data(self, dataset_name: str = 'basic') -> Dict[str, Any]:
        """
        Create sample data for testing.
        
        Args:
            dataset_name: Name of the sample dataset to create
            
        Returns:
            Statistics about created data
        """
        if dataset_name == 'basic':
            return await self._create_basic_sample_data()
        elif dataset_name == 'graph':
            return await self._create_graph_sample_data()
        else:
            raise DataLoadError(f"Unknown sample dataset: {dataset_name}")
    
    async def _create_basic_sample_data(self) -> Dict[str, Any]:
        """Create basic sample data."""
        queries = [
            "CREATE (p1:Person {name: 'Alice', age: 30})",
            "CREATE (p2:Person {name: 'Bob', age: 25})",
            "CREATE (c1:Company {name: 'TechCorp'})",
            "MATCH (p1:Person {name: 'Alice'}), (c1:Company {name: 'TechCorp'}) CREATE (p1)-[:WORKS_FOR]->(c1)",
            "MATCH (p1:Person {name: 'Alice'}), (p2:Person {name: 'Bob'}) CREATE (p1)-[:KNOWS]->(p2)",
        ]
        
        for query in queries:
            await self.container.execute_cypher(query)
        
        return {
            'nodes_created': 3,
            'relationships_created': 2,
            'statements_executed': len(queries),
        }
    
    async def _create_graph_sample_data(self) -> Dict[str, Any]:
        """Create a more complex graph sample data."""
        queries = [
            # Create nodes
            "CREATE (p1:Person {name: 'Alice', age: 30, department: 'Engineering'})",
            "CREATE (p2:Person {name: 'Bob', age: 25, department: 'Marketing'})",
            "CREATE (p3:Person {name: 'Charlie', age: 35, department: 'Engineering'})",
            "CREATE (c1:Company {name: 'TechCorp', industry: 'Technology'})",
            "CREATE (proj1:Project {name: 'Web Platform', status: 'active'})",
            "CREATE (proj2:Project {name: 'Mobile App', status: 'planning'})",
            
            # Create relationships
            "MATCH (p1:Person {name: 'Alice'}), (c1:Company {name: 'TechCorp'}) CREATE (p1)-[:WORKS_FOR {since: '2020-01-01'}]->(c1)",
            "MATCH (p2:Person {name: 'Bob'}), (c1:Company {name: 'TechCorp'}) CREATE (p2)-[:WORKS_FOR {since: '2021-06-01'}]->(c1)",
            "MATCH (p3:Person {name: 'Charlie'}), (c1:Company {name: 'TechCorp'}) CREATE (p3)-[:WORKS_FOR {since: '2019-03-15'}]->(c1)",
            "MATCH (p1:Person {name: 'Alice'}), (p3:Person {name: 'Charlie'}) CREATE (p1)-[:KNOWS {relationship: 'colleague'}]->(p3)",
            "MATCH (p1:Person {name: 'Alice'}), (proj1:Project {name: 'Web Platform'}) CREATE (p1)-[:ASSIGNED_TO {role: 'lead'}]->(proj1)",
            "MATCH (p3:Person {name: 'Charlie'}), (proj1:Project {name: 'Web Platform'}) CREATE (p3)-[:ASSIGNED_TO {role: 'developer'}]->(proj1)",
            "MATCH (p2:Person {name: 'Bob'}), (proj2:Project {name: 'Mobile App'}) CREATE (p2)-[:ASSIGNED_TO {role: 'coordinator'}]->(proj2)",
        ]
        
        for query in queries:
            await self.container.execute_cypher(query)
        
        return {
            'nodes_created': 6,
            'relationships_created': 7,
            'statements_executed': len(queries),
        }