"""Extract documentation from various sources in the codebase."""

from typing import List, Dict, Any
from pathlib import Path
import re
import ast


class DocumentationExtractor:
    """Extracts raw documentation from different sources in the codebase."""

    def __init__(self):
        self.docstring_patterns = {
            "python": self._extract_python_docstrings,
            "javascript": self._extract_js_comments,
            "typescript": self._extract_js_comments,
        }

    def extract_from_node(self, node: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract documentation from a code node.

        Args:
            node: A node dictionary from the graph

        Returns:
            List of extracted documentation pieces
        """
        docs = []

        # Extract based on node type
        if node.get("label") in ["FUNCTION", "CLASS", "METHOD"]:
            if "text" in node.get("attributes", {}):
                code_text = node["attributes"]["text"]
                extension = self._get_extension(node.get("path", ""))

                if extension in self.docstring_patterns:
                    extracted = self.docstring_patterns[extension](code_text)
                    for doc in extracted:
                        doc["source_node_id"] = node["id"]
                        doc["source_path"] = node.get("path", "")
                        docs.append(doc)

        return docs

    def extract_from_file(self, file_path: str, content: str) -> List[Dict[str, Any]]:
        """Extract documentation from a file.

        Args:
            file_path: Path to the file
            content: File content

        Returns:
            List of extracted documentation pieces
        """
        docs = []
        extension = self._get_extension(file_path)

        # Extract README files
        if Path(file_path).name.lower() in ["readme.md", "readme.rst", "readme.txt"]:
            docs.append(
                {"content": content, "source_type": "readme", "source_path": file_path, "info_type": "overview"}
            )

        # Extract markdown documentation
        elif extension in [".md", ".markdown"]:
            sections = self._extract_markdown_sections(content)
            for section in sections:
                section["source_path"] = file_path
                docs.append(section)

        # Extract inline comments and docstrings
        elif extension in self.docstring_patterns:
            extracted = self.docstring_patterns[extension](content)
            for doc in extracted:
                doc["source_path"] = file_path
                docs.append(doc)

        return docs

    def _extract_python_docstrings(self, code: str) -> List[Dict[str, Any]]:
        """Extract docstrings from Python code."""
        docs = []

        try:
            tree = ast.parse(code)

            for node in ast.walk(tree):
                docstring = ast.get_docstring(node)
                if docstring:
                    doc_info = {
                        "content": docstring,
                        "source_type": "docstring",
                    }

                    if isinstance(node, ast.FunctionDef):
                        doc_info["info_type"] = "function"
                        doc_info["title"] = f"Function: {node.name}"
                    elif isinstance(node, ast.ClassDef):
                        doc_info["info_type"] = "class"
                        doc_info["title"] = f"Class: {node.name}"
                    elif isinstance(node, ast.Module):
                        doc_info["info_type"] = "module"
                        doc_info["title"] = "Module Documentation"

                    docs.append(doc_info)
        except:
            # If parsing fails, try regex-based extraction
            docstring_pattern = r'"""(.*?)"""'
            matches = re.findall(docstring_pattern, code, re.DOTALL)
            for match in matches:
                docs.append({"content": match.strip(), "source_type": "docstring", "info_type": "unknown"})

        return docs

    def _extract_js_comments(self, code: str) -> List[Dict[str, Any]]:
        """Extract JSDoc and multi-line comments from JavaScript/TypeScript."""
        docs = []

        # Extract JSDoc comments
        jsdoc_pattern = r"/\*\*(.*?)\*/"
        matches = re.findall(jsdoc_pattern, code, re.DOTALL)

        for match in matches:
            # Clean up the comment
            lines = match.split("\n")
            cleaned_lines = []
            for line in lines:
                line = line.strip()
                if line.startswith("*"):
                    line = line[1:].strip()
                cleaned_lines.append(line)

            content = "\n".join(cleaned_lines).strip()
            if content:
                docs.append(
                    {
                        "content": content,
                        "source_type": "jsdoc",
                        "info_type": "function",  # Could be refined based on content
                    }
                )

        return docs

    def _extract_markdown_sections(self, content: str) -> List[Dict[str, Any]]:
        """Extract sections from markdown files."""
        sections = []

        # Split by headers
        header_pattern = r"^(#{1,6})\s+(.+)$"
        lines = content.split("\n")

        current_section = None
        current_content = []

        for line in lines:
            header_match = re.match(header_pattern, line)

            if header_match:
                # Save previous section
                if current_section:
                    sections.append(
                        {
                            "title": current_section["title"],
                            "content": "\n".join(current_content).strip(),
                            "source_type": "markdown",
                            "info_type": "documentation",
                            "level": current_section["level"],
                        }
                    )

                # Start new section
                level = len(header_match.group(1))
                title = header_match.group(2)
                current_section = {"title": title, "level": level}
                current_content = []
            else:
                current_content.append(line)

        # Save last section
        if current_section:
            sections.append(
                {
                    "title": current_section["title"],
                    "content": "\n".join(current_content).strip(),
                    "source_type": "markdown",
                    "info_type": "documentation",
                    "level": current_section["level"],
                }
            )

        return sections

    def _get_extension(self, file_path: str) -> str:
        """Get file extension, handling language mappings."""
        path = Path(file_path)
        ext = path.suffix.lower()

        # Map extensions to language keys
        if ext in [".py"]:
            return "python"
        elif ext in [".js", ".jsx"]:
            return "javascript"
        elif ext in [".ts", ".tsx"]:
            return "typescript"
        else:
            return ext
