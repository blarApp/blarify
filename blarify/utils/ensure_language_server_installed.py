import logging
import os
from pathlib import Path

from blarify.vendor.multilspy import SyncLanguageServer

from blarify.vendor.multilspy.multilspy_config import MultilspyConfig
from blarify.vendor.multilspy.multilspy_logger import MultilspyLogger


def ensure_language_server_installed(language: str):
    """
    Ensure that the language server for the given language is installed.
    """

    my_logger = logging.getLogger(__name__)

    config = MultilspyConfig.from_dict({"code_language": language})
    logger = MultilspyLogger()
    current_dir_path = os.path.join(str(Path(__file__).resolve().parent))

    if language == "csharp":
        print(f"Starting language server for {language}")
        from blarify.vendor.multilspy.language_servers.omnisharp.omnisharp import OmniSharp

        OmniSharp.setupRuntimeDependencies(None, logger, config)
        print(f"Started language server for {language}")
        return

    print(f"Starting language server for {language}, current_dir_path: {current_dir_path}")

    try:
        print(f"Starting language server for {language}")
        lsp = SyncLanguageServer.create(config=config, logger=logger, repository_root_path=current_dir_path, timeout=15)
        with lsp.start_server():
            my_logger.info(f"Started language server for {language}")
    except Exception as e:
        my_logger.exception(f"Failed to start language server for {language}: {e}")


if __name__ == "__main__":
    ensure_language_server_installed("csharp")
