import logging

logger = logging.getLogger(__name__)


class Logger:
    @staticmethod
    def log(message: str) -> None:
        # if os.getenv("DEBUG"):
        logger.info(message)
