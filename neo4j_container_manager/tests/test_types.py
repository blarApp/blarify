"""
Tests for Neo4j container management type definitions.

These tests verify the behavior of data structures, enums, and validation
logic in the types module.
"""

import pytest
import time

from neo4j_container_manager.types import (
    Environment,
    ContainerStatus, 
    DataFormat,
    PortAllocation,
    VolumeInfo,
    Neo4jContainerConfig,
    Neo4jContainerInstance,
    TestDataSpec,
    Neo4jContainerError,
    ContainerStartupError,
    PortAllocationError,
)


class TestEnvironmentEnum:
    """Test Environment enum."""
    
    def test_environment_values(self):
        """Test enum values are correct."""
        assert Environment.TEST == "test"
        assert Environment.DEVELOPMENT == "development"
    
    def test_environment_string_comparison(self):
        """Test enum can be compared to strings."""
        assert Environment.TEST == "test"
        assert Environment.DEVELOPMENT != "test"


class TestContainerStatusEnum:
    """Test ContainerStatus enum."""
    
    def test_status_values(self):
        """Test all status values."""
        expected_statuses = {
            "starting", "running", "stopping", "stopped", "error"
        }
        actual_statuses = {status.value for status in ContainerStatus}
        assert actual_statuses == expected_statuses


class TestDataFormatEnum:
    """Test DataFormat enum."""
    
    def test_format_values(self):
        """Test supported data formats."""
        assert DataFormat.CYPHER == "cypher"
        assert DataFormat.JSON == "json"
        assert DataFormat.CSV == "csv"


class TestPortAllocation:
    """Test PortAllocation dataclass."""
    
    def test_port_allocation_creation(self):
        """Test basic port allocation creation."""
        allocation = PortAllocation(
            bolt_port=7687,
            http_port=7474,
            https_port=7473
        )
        
        assert allocation.bolt_port == 7687
        assert allocation.http_port == 7474
        assert allocation.https_port == 7473
        assert allocation.backup_port is None
    
    def test_port_allocation_with_backup(self):
        """Test port allocation with backup port."""
        allocation = PortAllocation(
            bolt_port=7687,
            http_port=7474,
            https_port=7473,
            backup_port=6362
        )
        
        assert allocation.backup_port == 6362
    
    def test_port_allocation_to_dict(self):
        """Test conversion to dictionary."""
        allocation = PortAllocation(
            bolt_port=7687,
            http_port=7474,
            https_port=7473
        )
        
        result = allocation.to_dict()
        expected = {
            "bolt": 7687,
            "http": 7474,
            "https": 7473,
        }
        assert result == expected
    
    def test_port_allocation_to_dict_with_backup(self):
        """Test dictionary conversion with backup port."""
        allocation = PortAllocation(
            bolt_port=7687,
            http_port=7474,
            https_port=7473,
            backup_port=6362
        )
        
        result = allocation.to_dict()
        assert result["backup"] == 6362
    
    def test_bolt_uri_property(self):
        """Test bolt URI generation."""
        allocation = PortAllocation(
            bolt_port=7690,
            http_port=7477,
            https_port=7476
        )
        
        assert allocation.bolt_uri == "bolt://localhost:7690"
    
    def test_http_uri_property(self):
        """Test HTTP URI generation."""
        allocation = PortAllocation(
            bolt_port=7690,
            http_port=7477,
            https_port=7476
        )
        
        assert allocation.http_uri == "http://localhost:7477"


class TestVolumeInfo:
    """Test VolumeInfo dataclass."""
    
    def test_volume_info_creation(self):
        """Test basic volume info creation."""
        volume = VolumeInfo(
            name="test-volume",
            mount_path="/data"
        )
        
        assert volume.name == "test-volume"
        assert volume.mount_path == "/data"
        assert volume.size_limit is None
        assert volume.cleanup_on_stop is True
    
    def test_volume_info_with_options(self):
        """Test volume info with all options."""
        volume = VolumeInfo(
            name="test-volume",
            mount_path="/data",
            size_limit="1G",
            cleanup_on_stop=False
        )
        
        assert volume.size_limit == "1G"
        assert volume.cleanup_on_stop is False
    
    def test_volume_info_to_dict(self):
        """Test conversion to dictionary."""
        volume = VolumeInfo(
            name="test-volume",
            mount_path="/data",
            size_limit="1G",
            cleanup_on_stop=False
        )
        
        result = volume.to_dict()
        expected = {
            "name": "test-volume",
            "mount_path": "/data",
            "size_limit": "1G",
            "cleanup_on_stop": False,
        }
        assert result == expected


class TestNeo4jContainerConfig:
    """Test Neo4jContainerConfig dataclass."""
    
    def test_basic_config_creation(self):
        """Test basic configuration creation."""
        config = Neo4jContainerConfig(
            environment=Environment.TEST,
            password="test-password"
        )
        
        assert config.environment == Environment.TEST
        assert config.password == "test-password"
        assert config.username == "neo4j"
        assert config.enable_auth is True
        assert config.startup_timeout == 120
    
    def test_config_with_custom_options(self):
        """Test configuration with custom options."""
        config = Neo4jContainerConfig(
            environment=Environment.DEVELOPMENT,
            password="dev-password",
            username="admin",
            memory="2G",
            plugins=["apoc", "gds"],
            custom_config={"dbms.security.auth_enabled": "false"}
        )
        
        assert config.environment == Environment.DEVELOPMENT
        assert config.username == "admin"
        assert config.memory == "2G"
        assert config.plugins == ["apoc", "gds"]
        assert "dbms.security.auth_enabled" in config.custom_config
    
    def test_test_id_auto_generation(self):
        """Test automatic test ID generation for test environment."""
        config = Neo4jContainerConfig(
            environment=Environment.TEST,
            password="test-password"
        )
        
        # test_id should be auto-generated in __post_init__
        assert config.test_id is not None
        assert config.test_id.startswith("test-")
        assert len(config.test_id) > 5  # "test-" + 8 hex chars
    
    def test_development_no_auto_test_id(self):
        """Test no auto test ID for development environment."""
        config = Neo4jContainerConfig(
            environment=Environment.DEVELOPMENT,
            password="dev-password"
        )
        
        # No auto-generation for development
        assert config.test_id is None
    
    def test_explicit_test_id(self):
        """Test explicit test ID is preserved."""
        config = Neo4jContainerConfig(
            environment=Environment.TEST,
            password="test-password",
            test_id="custom-test-id"
        )
        
        assert config.test_id == "custom-test-id"
    
    def test_invalid_memory_format(self):
        """Test validation of memory format."""
        with pytest.raises(ValueError, match="Invalid memory format"):
            Neo4jContainerConfig(
                environment=Environment.TEST,
                password="test-password",
                memory="invalid"
            )
    
    def test_valid_memory_formats(self):
        """Test valid memory formats."""
        valid_formats = ["512M", "1G", "2GB", "1024MB"]
        
        for memory_format in valid_formats:
            config = Neo4jContainerConfig(
                environment=Environment.TEST,
                password="test-password",
                memory=memory_format
            )
            assert config.memory == memory_format
    
    def test_startup_timeout_validation(self):
        """Test startup timeout validation."""
        with pytest.raises(ValueError, match="Startup timeout must be at least 30 seconds"):
            Neo4jContainerConfig(
                environment=Environment.TEST,
                password="test-password",
                startup_timeout=20
            )
        
        with pytest.raises(ValueError, match="cannot exceed 600 seconds"):
            Neo4jContainerConfig(
                environment=Environment.TEST,
                password="test-password",
                startup_timeout=700
            )
    
    def test_password_validation(self):
        """Test password validation."""
        # Too short password
        with pytest.raises(ValueError, match="Password must be at least 8 characters"):
            Neo4jContainerConfig(
                environment=Environment.TEST,
                password="short"
            )
        
        # Valid password with exactly 8 characters
        config = Neo4jContainerConfig(
            environment=Environment.TEST,
            password="12345678"
        )
        assert config.password == "12345678"
        
        # Password validation bypassed when auth disabled
        config = Neo4jContainerConfig(
            environment=Environment.TEST,
            password="short",
            enable_auth=False
        )
        assert config.password == "short"
    
    def test_health_check_interval_validation(self):
        """Test health check interval validation."""
        with pytest.raises(ValueError, match="Health check interval must be at least 1 second"):
            Neo4jContainerConfig(
                environment=Environment.TEST,
                password="test-password",
                health_check_interval=0
            )
        
        with pytest.raises(ValueError, match="Health check interval cannot exceed 60 seconds"):
            Neo4jContainerConfig(
                environment=Environment.TEST,
                password="test-password",
                health_check_interval=61
            )
    
    def test_neo4j_version_validation(self):
        """Test Neo4j version format validation."""
        # Valid versions
        valid_versions = ["5.25.1", "5.25", "5.25.1-enterprise", "4.4.0"]
        for version in valid_versions:
            config = Neo4jContainerConfig(
                environment=Environment.TEST,
                password="test-password",
                neo4j_version=version
            )
            assert config.neo4j_version == version
        
        # Invalid versions
        invalid_versions = ["invalid", "5", "5.a.1", "v5.25.1"]
        for version in invalid_versions:
            with pytest.raises(ValueError, match="Invalid Neo4j version format"):
                Neo4jContainerConfig(
                    environment=Environment.TEST,
                    password="test-password",
                    neo4j_version=version
                )
    
    def test_plugin_validation(self):
        """Test plugin name validation."""
        # Valid plugins
        config = Neo4jContainerConfig(
            environment=Environment.TEST,
            password="test-password",
            plugins=["apoc", "bloom", "streams"]
        )
        assert config.plugins == ["apoc", "bloom", "streams"]
        
        # Invalid plugin
        with pytest.raises(ValueError, match="Invalid plugin: invalid-plugin"):
            Neo4jContainerConfig(
                environment=Environment.TEST,
                password="test-password",
                plugins=["apoc", "invalid-plugin"]
            )
    
    def test_container_name_property(self):
        """Test container name generation."""
        # Test environment
        test_config = Neo4jContainerConfig(
            environment=Environment.TEST,
            password="test-password",
            test_id="test123"
        )
        assert test_config.container_name == "blarify-neo4j-test-test123"
        
        # Development environment
        dev_config = Neo4jContainerConfig(
            environment=Environment.DEVELOPMENT,
            password="dev-password"
        )
        assert dev_config.container_name == "blarify-neo4j-dev"
    
    def test_volume_name_property(self):
        """Test volume name generation."""
        # Test environment
        test_config = Neo4jContainerConfig(
            environment=Environment.TEST,
            password="test-password",
            test_id="test123"
        )
        assert test_config.volume_name == "blarify-neo4j-test-test123-data"
        
        # Development environment  
        dev_config = Neo4jContainerConfig(
            environment=Environment.DEVELOPMENT,
            password="dev-password"
        )
        assert dev_config.volume_name == "blarify-neo4j-dev-data"
    
    def test_to_dict_method(self):
        """Test conversion to dictionary."""
        config = Neo4jContainerConfig(
            environment=Environment.TEST,
            password="secret",
            username="admin",
            test_id="test123"
        )
        
        result = config.to_dict()
        
        # Password should be masked
        assert result["password"] == "***"
        assert result["username"] == "admin"
        assert result["environment"] == "test"
        assert result["test_id"] == "test123"
        assert result["container_name"] == "blarify-neo4j-test-test123"
        assert result["volume_name"] == "blarify-neo4j-test-test123-data"


class TestNeo4jContainerInstance:
    """Test Neo4jContainerInstance dataclass."""
    
    @pytest.fixture
    def sample_config(self):
        """Sample configuration for testing."""
        return Neo4jContainerConfig(
            environment=Environment.TEST,
            password="test-password",
            test_id="sample-test"
        )
    
    @pytest.fixture
    def sample_ports(self):
        """Sample port allocation."""
        return PortAllocation(
            bolt_port=7687,
            http_port=7474,
            https_port=7473
        )
    
    @pytest.fixture
    def sample_volume(self):
        """Sample volume info."""
        return VolumeInfo(
            name="test-volume",
            mount_path="/data"
        )
    
    def test_instance_creation(self, sample_config, sample_ports, sample_volume):
        """Test basic instance creation."""
        instance = Neo4jContainerInstance(
            config=sample_config,
            container_id="test-container",
            ports=sample_ports,
            volume=sample_volume
        )
        
        assert instance.config == sample_config
        assert instance.container_id == "test-container"
        assert instance.ports == sample_ports
        assert instance.volume == sample_volume
        assert instance.status == ContainerStatus.STARTING
        assert instance.started_at is not None
    
    def test_uri_properties(self, sample_config, sample_ports, sample_volume):
        """Test URI property generation."""
        instance = Neo4jContainerInstance(
            config=sample_config,
            container_id="test-container",
            ports=sample_ports,
            volume=sample_volume
        )
        
        assert instance.uri == "bolt://localhost:7687"
        assert instance.http_uri == "http://localhost:7474"
    
    def test_uptime_calculation(self, sample_config, sample_ports, sample_volume):
        """Test uptime calculation."""
        start_time = time.time()
        
        instance = Neo4jContainerInstance(
            config=sample_config,
            container_id="test-container",
            ports=sample_ports,
            volume=sample_volume,
            started_at=start_time
        )
        
        # Should be very small but positive
        uptime = instance.uptime_seconds
        assert uptime >= 0
        assert uptime < 1.0  # Should be less than 1 second
    
    def test_to_dict_method(self, sample_config, sample_ports, sample_volume):
        """Test conversion to dictionary."""
        instance = Neo4jContainerInstance(
            config=sample_config,
            container_id="test-container",
            ports=sample_ports,
            volume=sample_volume,
            status=ContainerStatus.RUNNING
        )
        
        result = instance.to_dict()
        
        assert result["container_id"] == "test-container"
        assert result["status"] == "running"
        assert result["uri"] == "bolt://localhost:7687"
        assert result["http_uri"] == "http://localhost:7474"
        assert "config" in result
        assert "ports" in result
        assert "volume" in result
        assert "uptime_seconds" in result


class TestTestDataSpec:
    """Test TestDataSpec dataclass."""
    
    def test_valid_cypher_spec(self, tmp_path):
        """Test creating spec for Cypher file."""
        cypher_file = tmp_path / "test.cypher"
        cypher_file.write_text("CREATE (n:Test)")
        
        spec = TestDataSpec(
            file_path=cypher_file,
            format=DataFormat.CYPHER
        )
        
        assert spec.file_path == cypher_file
        assert spec.format == DataFormat.CYPHER
        assert spec.clear_before_load is True
        assert spec.parameters == {}
    
    def test_spec_with_options(self, tmp_path):
        """Test spec with custom options."""
        json_file = tmp_path / "test.json"
        json_file.write_text('{"test": true}')
        
        spec = TestDataSpec(
            file_path=json_file,
            format=DataFormat.JSON,
            clear_before_load=False,
            parameters={"param1": "value1"}
        )
        
        assert spec.clear_before_load is False
        assert spec.parameters == {"param1": "value1"}
    
    def test_nonexistent_file_error(self, tmp_path):
        """Test error for nonexistent file."""
        nonexistent_file = tmp_path / "nonexistent.cypher"
        
        with pytest.raises(FileNotFoundError):
            TestDataSpec(
                file_path=nonexistent_file,
                format=DataFormat.CYPHER
            )
    
    def test_format_extension_mismatch(self, tmp_path):
        """Test error for format/extension mismatch."""
        # Create .txt file but specify JSON format
        text_file = tmp_path / "test.txt"
        text_file.write_text("test data")
        
        with pytest.raises(ValueError, match="File extension .txt doesn't match format json"):
            TestDataSpec(
                file_path=text_file,
                format=DataFormat.JSON
            )
    
    def test_valid_format_extensions(self, tmp_path):
        """Test valid format/extension combinations."""
        test_cases = [
            ("test.cypher", DataFormat.CYPHER),
            ("test.cql", DataFormat.CYPHER),
            ("test.json", DataFormat.JSON),
            ("test.csv", DataFormat.CSV),
        ]
        
        for filename, format_type in test_cases:
            test_file = tmp_path / filename
            test_file.write_text("test data")
            
            # Should not raise an error
            spec = TestDataSpec(
                file_path=test_file,
                format=format_type
            )
            assert spec.format == format_type


class TestExceptionTypes:
    """Test custom exception types."""
    
    def test_neo4j_container_error(self):
        """Test base exception."""
        error = Neo4jContainerError("Test error")
        assert str(error) == "Test error"
        assert isinstance(error, Exception)
    
    def test_container_startup_error(self):
        """Test container startup error."""
        error = ContainerStartupError("Startup failed")
        assert str(error) == "Startup failed"
        assert isinstance(error, Neo4jContainerError)
    
    def test_port_allocation_error(self):
        """Test port allocation error."""
        error = PortAllocationError("Port allocation failed")
        assert str(error) == "Port allocation failed"
        assert isinstance(error, Neo4jContainerError)
    
    def test_exception_inheritance(self):
        """Test exception inheritance hierarchy."""
        startup_error = ContainerStartupError("test")
        
        assert isinstance(startup_error, ContainerStartupError)
        assert isinstance(startup_error, Neo4jContainerError)
        assert isinstance(startup_error, Exception)