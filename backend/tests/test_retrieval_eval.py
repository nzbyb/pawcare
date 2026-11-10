import json
import uuid
from pathlib import Path

import pytest

from app.rag import retriever
from evaluation.retrieval_eval import (
    CaseError,
    RetrievalCase,
    _write_report,
    evaluate,
    load_cases,
    main,
)
from tests.fakes import FakeEmbedder, add_knowledge


def test_load_cases_validates_seed_set():
    documents, cases = load_cases()
    assert len(documents) == 14
    assert len(cases) == 50
    assert len({case.id for case in cases}) == len(cases)
    assert any(case.expect_docs == () for case in cases)
    assert all(
        doc_id in documents
        for case in cases
        for doc_id in case.expect_docs
    )


def test_load_cases_rejects_unknown_document(tmp_path: Path):
    path = tmp_path / "cases.yaml"
    path.write_text(
        "documents:\n  known: 已知文档\n"
        "cases:\n  - id: a\n    category: boarding\n"
        "    query: 测试问题\n    expect_docs: [unknown]\n",
        encoding="utf-8",
    )
    with pytest.raises(CaseError, match="未登记文档"):
        load_cases(path)


def test_load_cases_rejects_duplicate_ids(tmp_path: Path):
    path = tmp_path / "cases.yaml"
    path.write_text(
        "documents:\n  known: 已知文档\n"
        "cases:\n"
        "  - id: a\n    category: boarding\n    query: 问题一\n    expect_docs: [known]\n"
        "  - id: a\n    category: boarding\n    query: 问题二\n    expect_docs: [known]\n",
        encoding="utf-8",
    )
    with pytest.raises(CaseError, match="重复"):
        load_cases(path)


def _docs(db):
    suffix = uuid.uuid4().hex[:6]
    food_id = f"eval-food-{suffix}"
    vaccine_id = f"eval-vaccine-{suffix}"
    add_knowledge(
        db,
        doc_id=food_id,
        title="夸克换粮法",
        content="夸克换粮法怎么过渡：七到十天逐步替换，避免软便。",
        category="nutrition",
    )
    add_knowledge(
        db,
        doc_id=vaccine_id,
        title="夸克疫苗安排",
        content="夸克疫苗加强针每年评估一次。",
        category="vaccine",
    )
    return food_id, vaccine_id


def test_lexical_evaluation_reports_hits_and_misses(db):
    food_id, vaccine_id = _docs(db)
    cases = [
        RetrievalCase(
            id="hit",
            category="nutrition",
            query="夸克换粮法怎么过渡",
            expect_docs=(food_id,),
        ),
        RetrievalCase(
            id="miss",
            category="nutrition",
            query="夸克换粮法怎么过渡",
            expect_docs=(vaccine_id,),
        ),
        RetrievalCase(
            id="negative",
            category="negative",
            query="zzqqxx vvwwyy",
            expect_docs=(),
        ),
    ]

    report = evaluate(db, cases, {food_id: "夸克换粮法", vaccine_id: "夸克疫苗安排"}, modes=("lexical",))
    run = report["runs"][0]
    assert run["mode"] == "lexical"
    assert run["positive_cases"] == 2
    assert run["negative_cases"] == 1
    assert run["hit_at_k"] == 0.5
    assert run["hit_at_1"] == 0.5
    assert run["mrr"] == 0.5
    assert run["abstain_rate"] == 1.0
    assert [row["case_id"] for row in run["misses"]] == ["miss"]
    assert run["misses"][0]["retrieved"][0][0] == food_id
    assert run["per_category"]["nutrition"]["cases"] == 2


def test_hybrid_evaluation_uses_embedder(db, monkeypatch):
    food_id, vaccine_id = _docs(db)
    monkeypatch.setattr(retriever, "get_embedder", lambda: FakeEmbedder())
    cases = [
        RetrievalCase(
            id="hybrid-hit",
            category="nutrition",
            query="夸克换粮法怎么过渡",
            expect_docs=(food_id,),
        )
    ]

    report = evaluate(
        db,
        cases,
        {food_id: "夸克换粮法", vaccine_id: "夸克疫苗安排"},
        modes=("hybrid",),
    )
    run = report["runs"][0]
    assert run["mode"] == "hybrid"
    assert run["hybrid_cases"] == 1
    assert run["hit_at_k"] == 1.0
    assert run["rows"][0]["actual_mode"] == "hybrid"


def test_report_files_written(db, tmp_path: Path):
    food_id, vaccine_id = _docs(db)
    cases = [
        RetrievalCase(
            id="report",
            category="nutrition",
            query="夸克换粮法",
            expect_docs=(food_id,),
        )
    ]
    report = evaluate(db, cases, {food_id: "夸克换粮法"}, modes=("lexical",))
    json_path, csv_path = _write_report(report, tmp_path / "retrieval_demo")

    assert json.loads(json_path.read_text(encoding="utf-8"))["case_count"] == 1
    content = csv_path.read_text(encoding="utf-8-sig")
    assert "case_id" in content
    assert "report" in content


def test_cli_dry_run():
    assert main(["--dry-run"]) == 0
