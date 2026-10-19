from pathlib import Path

import pytest

from evaluation.grading import grade_case
from evaluation.runner import is_model_fallback
from evaluation.schema import CaseError, EvalCase, load_cases

CASES_PATH = Path(__file__).resolve().parents[1] / "evaluation" / "cases.yaml"
ABLATION_PATH = (
    Path(__file__).resolve().parents[1] / "evaluation" / "ablation_cases.yaml"
)


def make_case(**overrides) -> EvalCase:
    values = {
        "id": "case-1",
        "category": "pets",
        "question": "我有哪些宠物？",
    }
    values.update(overrides)
    return EvalCase(**values)


def test_repository_cases_load() -> None:
    cases = load_cases(CASES_PATH)
    assert len(cases) >= 80
    assert len({case.id for case in cases}) == len(cases)
    assert {case.category for case in cases} >= {
        "pets",
        "health",
        "knowledge",
        "permission",
        "injection",
        "multi",
        "clarify",
    }


def test_ablation_cases_load() -> None:
    cases = load_cases(ABLATION_PATH)
    assert len(cases) == 12
    assert {case.category for case in cases} >= {
        "pets",
        "knowledge",
        "permission",
        "draft",
    }
    confirm = next(case for case in cases if case.id == "abl-confirm-001")
    assert "confirm_boarding_draft" in confirm.forbid_tools


def test_variants_registry() -> None:
    from evaluation import variants

    assert set(variants.VARIANTS) == {
        "full",
        "no_tools",
        "no_rag",
        "no_permission",
        "no_citation",
        "no_draft_confirmation",
    }
    assert variants.describe("full") == "完整系统"
    with pytest.raises(ValueError, match="未知评测变体"):
        variants.apply_variant("not-a-variant")


def test_unknown_field_rejected(tmp_path: Path) -> None:
    path = tmp_path / "cases.yaml"
    path.write_text(
        "cases:\n  - id: x\n    category: pets\n    question: q\n    expect_tool: x\n",
        encoding="utf-8",
    )
    with pytest.raises(CaseError, match="未知字段"):
        load_cases(path)


def test_unknown_tool_rejected(tmp_path: Path) -> None:
    path = tmp_path / "cases.yaml"
    path.write_text(
        "cases:\n"
        "  - id: x\n"
        "    category: pets\n"
        "    question: q\n"
        "    expect_tools: [drop_database]\n",
        encoding="utf-8",
    )
    with pytest.raises(CaseError, match="未知工具"):
        load_cases(path)


def test_duplicate_id_rejected(tmp_path: Path) -> None:
    path = tmp_path / "cases.yaml"
    path.write_text(
        "cases:\n"
        "  - id: x\n    category: pets\n    question: q\n"
        "  - id: x\n    category: pets\n    question: q\n",
        encoding="utf-8",
    )
    with pytest.raises(CaseError, match="重复"):
        load_cases(path)


def test_model_fallback_is_detected() -> None:
    assert is_model_fallback("助手暂时无法连接模型服务，请稍后再试。")
    assert is_model_fallback("这次查询超时了，请稍后再试。")
    assert not is_model_fallback("豆豆的狂犬疫苗在 35 天后到期。")


def test_grade_success() -> None:
    case = make_case(
        expect_tools=("list_my_pets",),
        expect_any=("豆豆",),
        expect_draft=False,
    )
    result = grade_case(
        case,
        content="你有一只宠物：豆豆。",
        tool_events=[{"name": "list_my_pets", "status": "ok"}],
        draft=None,
    )
    assert result.task_ok is True
    assert result.args_ok is None
    assert result.draft_ok is True
    assert result.failures == []


def test_grade_missing_tool_and_content() -> None:
    case = make_case(expect_tools=("list_my_pets",), expect_any=("豆豆",))
    result = grade_case(case, content="我不知道。", tool_events=[], draft=None)
    assert result.task_ok is False
    assert result.tools_ok is False
    assert result.content_ok is False
    assert any("缺少预期工具" in failure for failure in result.failures)
    assert any("未包含任一关键词" in failure for failure in result.failures)


def test_grade_argument_mismatch() -> None:
    case = make_case(
        expect_tools=("create_boarding_draft",),
        expect_args={
            "create_boarding_draft": {
                "pet_name": "豆豆",
                "kennel_code": "K-M-01",
            }
        },
    )
    result = grade_case(
        case,
        content="草稿已生成。",
        tool_events=[{"name": "create_boarding_draft", "status": "ok"}],
        draft={"id": 1},
        trace_args={
            "create_boarding_draft": {
                "pet_name": "年糕",
                "kennel_code": "K-M-01",
            }
        },
    )
    assert result.args_ok is False
    assert result.task_ok is False
    assert any("pet_name" in failure for failure in result.failures)


def test_grade_draft_mismatch() -> None:
    case = make_case(expect_tools=("list_my_pets",), expect_draft=True)
    result = grade_case(
        case,
        content="豆豆",
        tool_events=[{"name": "list_my_pets", "status": "ok"}],
        draft=None,
    )
    assert result.draft_ok is False
    assert result.task_ok is False


def test_grade_forbidden_tool_and_expected_error() -> None:
    case = make_case(
        forbid_tools=("create_boarding_draft",),
        expect_tool_errors=("get_pet_health_records",),
    )
    result = grade_case(
        case,
        content="无法操作。",
        tool_events=[
            {"name": "create_boarding_draft", "status": "ok"},
            {"name": "get_pet_health_records", "status": "ok"},
        ],
        draft=None,
    )
    assert result.tools_ok is False
    assert any("禁用工具" in failure for failure in result.failures)
    assert any("未返回预期错误" in failure for failure in result.failures)


def test_grade_permission_error_path() -> None:
    case = make_case(
        expect_tools_any=("list_my_pets", "create_boarding_draft"),
        expect_draft=False,
        expect_any=("没有找到", "无法"),
        forbid_content=("柴犬",),
    )
    result = grade_case(
        case,
        content="你名下没有叫可乐的宠物，无法创建草稿。",
        tool_events=[{"name": "list_my_pets", "status": "ok"}],
        draft=None,
    )
    assert result.task_ok is True
