import json
import logging
from typing import Optional

from langchain_core.callbacks import CallbackManagerForToolRun
from langchain_core.tools import BaseTool
from openai import OpenAI

logger = logging.getLogger(__name__)


class GetPRIssueHistory(BaseTool):
    name: str = "get_pr_issue_history"
    description: str = "Retrieves the history of a pull request issue based on openai thread history"
    pr_issue_thread_id: str = "The id of the thread to retrieve history for"

    def __init__(self, pr_issue_thread_id: str):
        logger.info(f"Initializing GetPRIssueHistory with pr issue thread id: {pr_issue_thread_id}")
        super().__init__(pr_issue_thread_id=pr_issue_thread_id)

    def _run(
        self,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Retrieves all messages from the thread."""
        openai_client = OpenAI()
        try:
            messages = openai_client.beta.threads.messages.list(self.pr_issue_thread_id)
            # Convert messages to a serializable format
            message_list = [
                {
                    "content": [content.text.value for content in msg.content],
                }
                for msg in messages.data
            ]
            message_list.reverse()
            return json.dumps({"messages": message_list})
        except Exception as e:
            logger.warning(f"Error retrieving messages for PR issue {self.pr_issue_thread_id}: {e}")
            return json.dumps({"error": f"No messages found for the given PR issue id: {self.pr_issue_thread_id}"})
