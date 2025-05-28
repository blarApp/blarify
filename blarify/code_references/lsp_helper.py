from typing import TYPE_CHECKING, Optional

import psutil

from blarify.vendor.multilspy import SyncLanguageServer

from blarify.utils.path_calculator import PathCalculator

from .types.Reference import Reference
from blarify.graph.node import DefinitionNode

from blarify.vendor.multilspy.multilspy_config import MultilspyConfig
from blarify.vendor.multilspy.multilspy_logger import MultilspyLogger
from blarify.vendor.multilspy.lsp_protocol_handler.server import Error

if TYPE_CHECKING:
    from blarify.graph.node import DefinitionNode
    from blarify.code_hierarchy.languages import (
        LanguageDefinitions,
    )


import asyncio

import logging
import threading

logger = logging.getLogger(__name__)


class FileExtensionNotSupported(Exception):
    pass


class LspQueryHelper:
    root_uri: str
    language_to_lsp_server: dict[str, SyncLanguageServer]

    LSP_USAGES = 0

    def __init__(self, root_uri: str, host: Optional[str] = None, port: Optional[int] = None):
        self.root_uri = root_uri
        self.entered_lsp_servers = {}
        self.language_to_lsp_server = {}

    @staticmethod
    def get_language_definition_for_extension(extension: str) -> "LanguageDefinitions":
        from blarify.code_hierarchy.languages import (
            PythonDefinitions,
            JavascriptDefinitions,
            RubyDefinitions,
            TypescriptDefinitions,
            CsharpDefinitions,
            GoDefinitions,
            PhpDefinitions,
        )

        if extension in PythonDefinitions.get_language_file_extensions():
            return PythonDefinitions
        elif extension in JavascriptDefinitions.get_language_file_extensions():
            return JavascriptDefinitions
        elif extension in TypescriptDefinitions.get_language_file_extensions():
            return TypescriptDefinitions
        elif extension in RubyDefinitions.get_language_file_extensions():
            return RubyDefinitions
        elif extension in CsharpDefinitions.get_language_file_extensions():
            return CsharpDefinitions
        elif extension in GoDefinitions.get_language_file_extensions():
            return GoDefinitions
        elif extension in PhpDefinitions.get_language_file_extensions():
            return PhpDefinitions
        else:
            raise FileExtensionNotSupported(f'File extension "{extension}" is not supported)')

    def _create_lsp_server(self, language_definitions: "LanguageDefinitions", timeout=15) -> SyncLanguageServer:
        language = language_definitions.get_language_name()

        config = MultilspyConfig.from_dict({"code_language": language})

        logger = MultilspyLogger()
        lsp = SyncLanguageServer.create(config, logger, PathCalculator.uri_to_path(self.root_uri), timeout=timeout)
        return lsp

    def start(self) -> None:
        """
        DEPRECATED, LSP servers are started on demand
        """

    def _get_or_create_lsp_server(self, extension, timeout=15) -> SyncLanguageServer:
        language_definitions = self.get_language_definition_for_extension(extension)
        language = language_definitions.get_language_name()

        if language in self.language_to_lsp_server:
            return self.language_to_lsp_server[language]
        else:
            new_lsp = self._create_lsp_server(language_definitions, timeout)
            self.language_to_lsp_server[language] = new_lsp
            self._initialize_lsp_server(language, new_lsp)
            return new_lsp

    def _initialize_lsp_server(self, language, lsp):
        context = lsp.start_server()
        context.__enter__()
        self.entered_lsp_servers[language] = context

    def initialize_directory(self, file) -> None:
        """
        DEPRECATED, LSP servers are started on demand
        """

    def get_paths_where_node_is_referenced(self, node: "DefinitionNode") -> list[Reference]:
        server = self._get_or_create_lsp_server(node.extension)
        references = self._request_references_with_exponential_backoff(node, server)

        return [Reference(reference) for reference in references]

    def _request_references_with_exponential_backoff(self, node, lsp):
        timeout = 10
        for _ in range(1, 3):
            try:
                references = lsp.request_references(
                    file_path=PathCalculator.get_relative_path_from_uri(root_uri=self.root_uri, uri=node.path),
                    line=node.definition_range.start_dict["line"],
                    column=node.definition_range.start_dict["character"],
                )

                return references

            except (TimeoutError, ConnectionResetError, Error):
                timeout = timeout * 2

                logger.warning(
                    f"Error requesting references for {self.root_uri}, {node.definition_range}, attempting to restart LSP server with timeout {timeout}"
                )
                self._restart_lsp_for_extension(extension=node.extension)
                lsp = self._get_or_create_lsp_server(extension=node.extension, timeout=timeout)

        logger.error("Failed to get references, returning empty list")
        return []

    def _restart_lsp_for_extension(self, extension):
        language_definitions = self.get_language_definition_for_extension(extension)
        language_name = language_definitions.get_language_name()

        self.exit_lsp_server(language_name)

        new_lsp = self._create_lsp_server(language_definitions)

        logger.warning("Restarting LSP server")
        try:
            self._initialize_lsp_server(language=language_name, lsp=new_lsp)
            self.language_to_lsp_server[language_name] = new_lsp
            logger.warning("LSP server restarted")
        except ConnectionResetError:
            logger.error("Connection reset error")

    def exit_lsp_server(self, language) -> None:
        # TODO: This should not be this hacky!!!

        # Since im using the sync language server, I need to manually kill the process
        # If I try to exit the context when the server has crahed, it will hang since it's waiting for the server response
        # A better way would be to use the async language server, but that would require a lot of changes
        # So for now, I'm just killing the process manually

        # Best line of code I've ever written:
        process = self.language_to_lsp_server[language].language_server.server.process

        # Kill running processes
        try:
            if psutil.pid_exists(process.pid):
                for child in psutil.Process(process.pid).children(recursive=True):
                    child.terminate()

                process.terminate()
        except Exception as e:
            logger.error(f"Error killing process: {e}")

        # Cancel all tasks in the loop
        loop = self.language_to_lsp_server[language].loop
        try:
            tasks = asyncio.all_tasks(loop=loop)
            for task in tasks:
                task.cancel()
            logger.info("Tasks cancelled")
        except Exception as e:
            logger.error(f"Error cancelling tasks: {e}")

        # Stop the loop

        # It is important to stop the loop before exiting the context otherwise there will be threads running in definitely
        if loop.is_running():
            loop.call_soon_threadsafe(loop.stop)

        del self.language_to_lsp_server[language]

    def get_definition_path_for_reference(self, reference: Reference, extension: str) -> str:
        lsp_caller = self._get_or_create_lsp_server(extension)
        definitions = self._request_definition_with_exponential_backoff(reference, lsp_caller, extension)

        if not definitions:
            return ""

        return definitions[0]["uri"]

    def _request_definition_with_exponential_backoff(self, reference: Reference, lsp, extension):
        timeout = 10
        for _ in range(1, 3):
            try:
                definitions = lsp.request_definition(
                    file_path=PathCalculator.get_relative_path_from_uri(root_uri=self.root_uri, uri=reference.uri),
                    line=reference.range.start.line,
                    column=reference.range.start.character,
                )

                return definitions

            except (TimeoutError, ConnectionResetError, Error):
                timeout = timeout * 2

                logger.warning(
                    f"Error requesting definitions for {self.root_uri}, {reference.start_dict}, attempting to restart LSP server with timeout {timeout}"
                )
                self._restart_lsp_for_extension(extension)
                lsp = self._get_or_create_lsp_server(extension=extension, timeout=timeout)

        logger.error("Failed to get references, returning empty list")
        return []

    def shutdown_exit_close(self) -> None:
        languages = list(self.language_to_lsp_server.keys())

        for language in languages:
            self.exit_lsp_server(language)

        self.entered_lsp_servers = {}
        self.language_to_lsp_server = {}
        logger.info("LSP servers have been shut down")
