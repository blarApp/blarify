# pyright: reportPrivateUsage=false
from typing import List, Optional
from unittest.mock import Mock, MagicMock

from blarify.agents.llm_provider import LLMProvider
from blarify.agents.prompt_templates import (
    FRONTEND_FUNCTION_WITH_CALLS_ANALYSIS_TEMPLATE,
    FRONTEND_LEAF_NODE_ANALYSIS_TEMPLATE,
    FRONTEND_PARENT_NODE_ANALYSIS_TEMPLATE,
    FUNCTION_WITH_CALLS_ANALYSIS_TEMPLATE,
    LEAF_NODE_ANALYSIS_TEMPLATE,
    PARENT_NODE_ANALYSIS_TEMPLATE,
)
from blarify.documentation.utils.bottom_up_batch_processor import (
    FRONTEND_EXTENSIONS,
    FRONTEND_MODEL,
    BottomUpBatchProcessor,
)
from blarify.graph.graph_environment import GraphEnvironment
from blarify.graph.node.documentation_node import DocumentationNode
from blarify.repositories.graph_db_manager.dtos.node_with_content_dto import NodeWithContentDto


def _make_llm_mock() -> Mock:
    m = Mock(spec=LLMProvider)
    m.call_dumb_agent.return_value = "mock description"
    return m


def _make_processor(llm_mock: Mock) -> BottomUpBatchProcessor:
    db_mock = MagicMock()
    env = GraphEnvironment(environment="test", diff_identifier="abc123", root_path="/tmp")
    return BottomUpBatchProcessor(
        db_manager=db_mock,
        agent_caller=llm_mock,
        graph_environment=env,
    )


def _make_node(path: str, labels: Optional[List[str]] = None) -> NodeWithContentDto:
    return NodeWithContentDto(
        id="node-1",
        name=path.split("/")[-1],
        labels=labels or ["FUNCTION"],
        path=path,
        start_line=1,
        end_line=10,
        content="function App() { return <div>Hello</div>; }",
    )


def _make_child_description(processor: BottomUpBatchProcessor) -> DocumentationNode:
    return DocumentationNode(
        content="Renders a button",
        info_type="child_description",
        source_path="file:///tmp/src/Button.tsx",
        source_name="Button",
        source_id="child-1",
        source_labels=["FUNCTION"],
        source_type="child",
        graph_environment=processor.graph_environment,
    )


class TestIsFrontendFile:
    def test_tsx_is_frontend(self) -> None:
        assert BottomUpBatchProcessor._is_frontend_file("file:///project/src/App.tsx") is True

    def test_jsx_is_frontend(self) -> None:
        assert BottomUpBatchProcessor._is_frontend_file("file:///project/components/Card.jsx") is True

    def test_vue_is_frontend(self) -> None:
        assert BottomUpBatchProcessor._is_frontend_file("file:///project/views/Home.vue") is True

    def test_svelte_is_frontend(self) -> None:
        assert BottomUpBatchProcessor._is_frontend_file("file:///project/routes/Page.svelte") is True

    def test_py_is_not_frontend(self) -> None:
        assert BottomUpBatchProcessor._is_frontend_file("file:///project/app/views.py") is False

    def test_ts_is_not_frontend(self) -> None:
        assert BottomUpBatchProcessor._is_frontend_file("file:///project/utils/helper.ts") is False

    def test_js_is_not_frontend(self) -> None:
        assert BottomUpBatchProcessor._is_frontend_file("file:///project/server/index.js") is False

    def test_extensions_constant_matches(self) -> None:
        assert FRONTEND_EXTENSIONS == {".tsx", ".jsx", ".vue", ".svelte"}


class TestLeafNodeTemplateSelection:
    def test_frontend_leaf_uses_frontend_template_and_model(self) -> None:
        llm_mock = _make_llm_mock()
        processor = _make_processor(llm_mock)
        node = _make_node("file:///project/src/components/Header.tsx")

        processor._process_leaf_node(node)

        call_kwargs = llm_mock.call_dumb_agent.call_args
        expected_system, _ = FRONTEND_LEAF_NODE_ANALYSIS_TEMPLATE.get_prompts()
        assert call_kwargs.kwargs["system_prompt"] == expected_system
        assert call_kwargs.kwargs["ai_model"] == FRONTEND_MODEL

    def test_backend_leaf_uses_standard_template_and_no_model_override(self) -> None:
        llm_mock = _make_llm_mock()
        processor = _make_processor(llm_mock)
        node = _make_node("file:///project/app/services/auth.py")

        processor._process_leaf_node(node)

        call_kwargs = llm_mock.call_dumb_agent.call_args
        expected_system, _ = LEAF_NODE_ANALYSIS_TEMPLATE.get_prompts()
        assert call_kwargs.kwargs["system_prompt"] == expected_system
        assert call_kwargs.kwargs["ai_model"] is None


class TestParentNodeTemplateSelection:
    def test_frontend_function_with_calls_uses_frontend_template(self) -> None:
        llm_mock = _make_llm_mock()
        processor = _make_processor(llm_mock)
        node = _make_node("file:///project/src/pages/Dashboard.tsx", labels=["FUNCTION"])
        child = _make_child_description(processor)

        processor._process_parent_node(node, [child])

        call_kwargs = llm_mock.call_dumb_agent.call_args
        expected_system, _ = FRONTEND_FUNCTION_WITH_CALLS_ANALYSIS_TEMPLATE.get_prompts()
        assert call_kwargs.kwargs["system_prompt"] == expected_system
        assert call_kwargs.kwargs["ai_model"] == FRONTEND_MODEL

    def test_backend_function_with_calls_uses_standard_template(self) -> None:
        llm_mock = _make_llm_mock()
        processor = _make_processor(llm_mock)
        node = _make_node("file:///project/app/views.py", labels=["FUNCTION"])
        child = _make_child_description(processor)

        processor._process_parent_node(node, [child])

        call_kwargs = llm_mock.call_dumb_agent.call_args
        expected_system, _ = FUNCTION_WITH_CALLS_ANALYSIS_TEMPLATE.get_prompts()
        assert call_kwargs.kwargs["system_prompt"] == expected_system
        assert call_kwargs.kwargs["ai_model"] is None

    def test_frontend_parent_file_uses_frontend_template(self) -> None:
        llm_mock = _make_llm_mock()
        processor = _make_processor(llm_mock)
        node = _make_node("file:///project/src/pages/Settings.tsx", labels=["FILE"])
        child = _make_child_description(processor)

        processor._process_parent_node(node, [child])

        call_kwargs = llm_mock.call_dumb_agent.call_args
        expected_system, _ = FRONTEND_PARENT_NODE_ANALYSIS_TEMPLATE.get_prompts()
        assert call_kwargs.kwargs["system_prompt"] == expected_system
        assert call_kwargs.kwargs["ai_model"] == FRONTEND_MODEL

    def test_backend_parent_file_uses_standard_template(self) -> None:
        llm_mock = _make_llm_mock()
        processor = _make_processor(llm_mock)
        node = _make_node("file:///project/app/models.py", labels=["FILE"])
        child = _make_child_description(processor)

        processor._process_parent_node(node, [child])

        call_kwargs = llm_mock.call_dumb_agent.call_args
        expected_system, _ = PARENT_NODE_ANALYSIS_TEMPLATE.get_prompts()
        assert call_kwargs.kwargs["system_prompt"] == expected_system
        assert call_kwargs.kwargs["ai_model"] is None


class TestFrontendModelConstant:
    def test_frontend_model_is_gemini_3_flash(self) -> None:
        assert FRONTEND_MODEL == "gemini-3-flash-preview"
