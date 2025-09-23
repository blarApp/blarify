#!/usr/bin/env python3
"""
Script to initialize SCIP for a project.

This script:
1. Checks if scip-python is installed
2. Downloads the latest scip.proto file if needed
3. Generates Python protobuf bindings
4. Creates a SCIP index for the project
"""

import os
import sys
import subprocess
import urllib.request
import logging
from typing import Optional

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def check_scip_python_installed():
    """Check if scip-python is installed and available"""
    try:
        result = subprocess.run(["scip-python", "--version"], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            logger.info(f"✅ scip-python is installed: {result.stdout.strip()}")
            return True
        else:
            logger.error("❌ scip-python is installed but not working properly")
            return False
    except FileNotFoundError:
        logger.error("❌ scip-python not found. Install with: npm install -g @sourcegraph/scip-python")
        return False
    except subprocess.TimeoutExpired:
        logger.error("❌ scip-python command timed out")
        return False


def check_scip_typescript_installed():
    """Check if scip-typescript is installed and available"""
    try:
        result = subprocess.run(["scip-typescript", "--version"], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            logger.info(f"✅ scip-typescript is installed: {result.stdout.strip()}")
            return True
        else:
            logger.error("❌ scip-typescript is installed but not working properly")
            return False
    except FileNotFoundError:
        logger.error("❌ scip-typescript not found. Install with: npm install -g @sourcegraph/scip-typescript")
        return False
    except subprocess.TimeoutExpired:
        logger.error("❌ scip-typescript command timed out")
        return False


def check_scip_indexer_installed(language: str):
    """Check if the appropriate SCIP indexer is installed for the given language"""
    if language.lower() == "python":
        return check_scip_python_installed()
    elif language.lower() in ["typescript", "javascript"]:
        return check_scip_typescript_installed()
    else:
        logger.error(f"❌ Unsupported language: {language}")
        return False


def check_protoc_installed():
    """Check if protoc (Protocol Buffer compiler) is installed"""
    try:
        result = subprocess.run(["protoc", "--version"], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            logger.info(f"✅ protoc is installed: {result.stdout.strip()}")
            return True
        else:
            logger.error("❌ protoc is installed but not working properly")
            return False
    except FileNotFoundError:
        logger.error(
            "❌ protoc not found. Install with: brew install protobuf (macOS) or apt-get install protobuf-compiler (Ubuntu)"
        )
        return False
    except subprocess.TimeoutExpired:
        logger.error("❌ protoc command timed out")
        return False


def download_scip_proto(project_root: str):
    """Download the latest scip.proto file from the SCIP repository"""
    proto_url = "https://raw.githubusercontent.com/sourcegraph/scip/main/scip.proto"
    proto_path = os.path.join(project_root, "scip.proto")

    if os.path.exists(proto_path):
        logger.info(f"📄 scip.proto already exists at {proto_path}")
        return proto_path

    try:
        logger.info(f"📥 Downloading scip.proto from {proto_url}")
        urllib.request.urlretrieve(proto_url, proto_path)
        logger.info(f"✅ Downloaded scip.proto to {proto_path}")
        return proto_path
    except Exception as e:
        logger.error(f"❌ Failed to download scip.proto: {e}")
        return None


def generate_protobuf_bindings(project_root: str, proto_path: str):
    """Generate Python protobuf bindings from scip.proto"""
    if not check_protoc_installed():
        logger.error("❌ Cannot generate protobuf bindings without protoc")
        return False

    try:
        logger.info("🔧 Generating Python protobuf bindings...")
        cmd = [
            "protoc",
            "--python_out=.",
            "--proto_path=.",
            os.path.basename(proto_path),  # Use just the filename since we're in the right directory
        ]

        result = subprocess.run(cmd, cwd=project_root, capture_output=True, text=True)

        if result.returncode == 0:
            pb2_path = os.path.join(project_root, "scip_pb2.py")
            if os.path.exists(pb2_path):
                logger.info(f"✅ Generated scip_pb2.py at {pb2_path}")
                return True
            else:
                logger.error("❌ scip_pb2.py was not generated")
                return False
        else:
            logger.error(f"❌ Failed to generate protobuf bindings: {result.stderr}")
            return False

    except Exception as e:
        logger.error(f"❌ Error generating protobuf bindings: {e}")
        return False


def create_scip_index(project_root: str, project_name: str = "project", language: str = "python"):
    """Create a SCIP index for the project using the appropriate language indexer"""
    if not check_scip_indexer_installed(language):
        logger.error(f"❌ Cannot create SCIP index without scip-{language}")
        return False

    try:
        logger.info(f"📚 Creating SCIP index for {language} project '{project_name}'...")

        # Choose the appropriate indexer command
        if language.lower() == "python":
            cmd = [
                "scip-python",
                "index",
                "--project-name",
                project_name,
                "--output",
                os.path.join(project_root, "index.scip"),
            ]
        elif language.lower() in ["typescript", "javascript"]:
            # scip-typescript has simpler command structure - no --project-name support
            cmd = [
                "scip-typescript",
                "index",
                "--output",
                "index.scip",  # Must be just filename, not full path
            ]
        else:
            logger.error(f"❌ Unsupported language: {language}")
            return False

        result = subprocess.run(cmd, cwd=project_root, capture_output=True, text=True)

        if result.returncode == 0:
            index_path = os.path.join(project_root, "index.scip")
            if os.path.exists(index_path):
                size_mb = os.path.getsize(index_path) / (1024 * 1024)
                logger.info(f"✅ Created {language} SCIP index at {index_path} ({size_mb:.1f} MB)")
                return True
            else:
                logger.error("❌ SCIP index was not created")
                return False
        else:
            logger.error(f"❌ Failed to create SCIP index: {result.stderr}")
            return False

    except Exception as e:
        logger.error(f"❌ Error creating SCIP index: {e}")
        return False


def test_scip_bindings(project_root: str):
    """Test that the SCIP protobuf bindings work correctly"""
    try:
        # Add project root to Python path for import
        sys.path.insert(0, project_root)

        import scip_pb2 as scip

        # Try to create a simple SCIP object
        index = scip.Index()
        logger.info("✅ SCIP protobuf bindings are working correctly")
        return True

    except ImportError as e:
        logger.error(f"❌ Cannot import scip_pb2: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Error testing SCIP bindings: {e}")
        return False


def initialize_scip(project_root: str, project_name: Optional[str] = None, language: Optional[str] = None):
    """Main function to initialize SCIP for a project"""
    project_root = os.path.abspath(project_root)

    if not project_name:
        project_name = os.path.basename(project_root)

    # Auto-detect language if not specified
    if not language:
        # Add project root to Python path for import
        sys.path.insert(0, os.path.dirname(os.path.dirname(project_root)))
        try:
            from blarify.utils.project_detector import ProjectDetector

            if ProjectDetector.is_python_project(project_root):
                language = "python"
            elif ProjectDetector.is_typescript_project(project_root):
                language = "typescript"
            else:
                logger.error("❌ Could not detect project language. Please specify --language")
                return False
        except ImportError:
            logger.warning("⚠️ Could not import ProjectDetector, defaulting to Python")
            language = "python"

    logger.info(f"🚀 Initializing SCIP for {language} project '{project_name}' at {project_root}")

    # Step 1: Check prerequisites
    logger.info("1️⃣ Checking prerequisites...")
    if not check_scip_indexer_installed(language):
        logger.error(f"❌ SCIP initialization failed: scip-{language} not available")
        return False

    # Step 2: Download scip.proto if needed
    logger.info("2️⃣ Setting up scip.proto...")
    proto_path = download_scip_proto(project_root)
    if not proto_path:
        logger.error("❌ SCIP initialization failed: could not get scip.proto")
        return False

    # Step 3: Generate protobuf bindings
    logger.info("3️⃣ Generating protobuf bindings...")
    if not generate_protobuf_bindings(project_root, proto_path):
        logger.warning("⚠️ Could not generate fresh protobuf bindings (protoc not available)")
        logger.info("   Using existing scip_pb2.py file if available...")

    # Step 4: Test bindings
    logger.info("4️⃣ Testing protobuf bindings...")
    if not test_scip_bindings(project_root):
        logger.error("❌ SCIP initialization failed: protobuf bindings not working")
        return False

    # Step 5: Create SCIP index
    logger.info("5️⃣ Creating SCIP index...")
    if not create_scip_index(project_root, project_name, language):
        logger.error("❌ SCIP initialization failed: could not create index")
        return False

    logger.info("🎉 SCIP initialization completed successfully!")
    logger.info("\n📋 Next steps:")
    logger.info(f"   - Use ScipReferenceResolver with {language} projects")
    logger.info("   - The SCIP index will be automatically regenerated when source files change")
    logger.info("   - Enjoy 330x faster reference resolution compared to LSP!")

    return True


def main():
    """CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Initialize SCIP for a project")
    parser.add_argument(
        "project_root", nargs="?", default=".", help="Project root directory (default: current directory)"
    )
    parser.add_argument("--project-name", help="Project name for SCIP index (default: directory name)")
    parser.add_argument(
        "--language", choices=["python", "typescript", "javascript"], help="Project language (default: auto-detect)"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    success = initialize_scip(args.project_root, args.project_name, args.language)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
