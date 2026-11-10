"""知识库召回评测。

用法（在 backend 目录）：
    .venv\\Scripts\\python.exe evaluation\\retrieval_eval.py --dry-run
    .venv\\Scripts\\python.exe evaluation\\retrieval_eval.py
    .venv\\Scripts\\python.exe evaluation\\retrieval_eval.py --mode lexical
    .venv\\Scripts\\python.exe evaluation\\retrieval_eval.py --category boarding

设计：
- 用例写 YAML：一句真实问法 + 可接受的文档 ID（`expect_docs` 为空表示应拒答）。
- 直接调用生产检索器 `app.rag.retriever.search`，不经过 Agent 和模型，
  只衡量“召回”本身；混合模式和纯词法模式各跑一遍，作为 RAG 消融对照。
- 只读数据库，不建表、不清库；首次运行若切片没有向量，检索器会按需补写
  embedding（幂等），因此建议先跑过一次 RAG 检索或知识库重建。
- 输出控制台摘要 + JSON / CSV 报告，便于论文实验章节引用。
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

CASES_PATH = Path(__file__).with_name("retrieval_cases.yaml")
REPORT_DIR = Path(__file__).with_name("reports")
MODES = ("hybrid", "lexical")
MAX_TOP_K = 5


class CaseError(ValueError):
    """评测用例格式错误。"""


@dataclass(frozen=True)
class RetrievalCase:
    id: str
    category: str
    query: str
    expect_docs: tuple[str, ...]
    top_k: int | None = None
    notes: str | None = None


def _as_docs(value: Any, documents: dict[str, str], case_id: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise CaseError(f"{case_id}: expect_docs 必须是字符串列表")
    unknown = [item for item in value if item not in documents]
    if unknown:
        raise CaseError(f"{case_id}: expect_docs 中出现未登记文档：{unknown}")
    return tuple(value)


def load_cases(
    path: Path = CASES_PATH,
) -> tuple[dict[str, str], list[RetrievalCase]]:
    if not path.exists():
        raise CaseError(f"用例文件不存在：{path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise CaseError("用例文件顶层必须是对象")

    documents = raw.get("documents") or {}
    if not isinstance(documents, dict) or not documents:
        raise CaseError("documents 必须是非空对象（doc_id → 标题）")
    if not all(isinstance(key, str) and isinstance(value, str) for key, value in documents.items()):
        raise CaseError("documents 的键和值都必须是字符串")

    defaults = raw.get("defaults") or {}
    if not isinstance(defaults, dict):
        raise CaseError("defaults 必须是对象")
    default_top_k = int(defaults.get("top_k") or 3)
    if not 1 <= default_top_k <= MAX_TOP_K:
        raise CaseError(f"defaults.top_k 必须在 1–{MAX_TOP_K} 之间")

    raw_cases = raw.get("cases") or []
    if not isinstance(raw_cases, list) or not raw_cases:
        raise CaseError("cases 必须是非空列表")

    cases: list[RetrievalCase] = []
    seen: set[str] = set()
    for index, item in enumerate(raw_cases, start=1):
        if not isinstance(item, dict):
            raise CaseError(f"第 {index} 个用例必须是对象")
        case_id = item.get("id")
        if not isinstance(case_id, str) or not case_id.strip():
            raise CaseError(f"第 {index} 个用例缺少 id")
        if case_id in seen:
            raise CaseError(f"用例 id 重复：{case_id}")
        seen.add(case_id)
        query = item.get("query")
        if not isinstance(query, str) or not query.strip():
            raise CaseError(f"{case_id}: query 不能为空")
        category = item.get("category")
        if not isinstance(category, str) or not category.strip():
            raise CaseError(f"{case_id}: category 不能为空")
        top_k = item.get("top_k")
        if top_k is not None:
            top_k = int(top_k)
            if not 1 <= top_k <= MAX_TOP_K:
                raise CaseError(f"{case_id}: top_k 必须在 1–{MAX_TOP_K} 之间")
        cases.append(
            RetrievalCase(
                id=case_id,
                category=category,
                query=query.strip(),
                expect_docs=_as_docs(item.get("expect_docs"), documents, case_id),
                top_k=top_k,
                notes=item.get("notes"),
            )
        )
    return documents, cases


@contextmanager
def _lexical_only():
    """临时关闭向量检索，让同一套用例走纯词法打分。"""
    from app.config import settings

    previous = settings.RAG_ENABLED
    settings.RAG_ENABLED = False
    try:
        yield
    finally:
        settings.RAG_ENABLED = previous


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def _case_row(case: RetrievalCase, result, requested_mode: str) -> dict:
    retrieved = [(chunk.doc_id, round(chunk.score, 4)) for chunk in result.chunks]
    acceptable = set(case.expect_docs)
    if acceptable:
        ranks = [
            rank
            for rank, (doc_id, _) in enumerate(retrieved, start=1)
            if doc_id in acceptable
        ]
        first_rank = ranks[0] if ranks else None
        hit_score = next(
            (score for doc_id, score in retrieved if doc_id in acceptable), None
        )
        hit = bool(ranks)
        hit_at_1 = first_rank == 1
    else:
        # 拒答用例：没有召回任何切片才算通过。
        first_rank = None
        hit_score = None
        hit = not retrieved
        hit_at_1 = hit
    return {
        "case_id": case.id,
        "category": case.category,
        "query": case.query,
        "requested_mode": requested_mode,
        "actual_mode": result.mode,
        "expected": list(case.expect_docs),
        "retrieved": retrieved,
        "top_doc": retrieved[0][0] if retrieved else None,
        "top_score": retrieved[0][1] if retrieved else 0.0,
        "hit": hit,
        "hit_at_1": hit_at_1,
        "first_rank": first_rank,
        "hit_score": hit_score,
    }


def _summarize(rows: list[dict], documents: dict[str, str], mode: str, top_k: int) -> dict:
    positive = [row for row in rows if row["expected"]]
    negative = [row for row in rows if not row["expected"]]

    per_category: dict[str, dict] = {}
    for row in positive:
        bucket = per_category.setdefault(
            row["category"],
            {"cases": 0, "hits": 0, "top1": 0, "reciprocal_rank": 0.0},
        )
        bucket["cases"] += 1
        bucket["hits"] += int(row["hit"])
        bucket["top1"] += int(row["hit_at_1"])
        bucket["reciprocal_rank"] += 1 / row["first_rank"] if row["first_rank"] else 0.0
    categories = {
        name: {
            "cases": bucket["cases"],
            "hit_at_k": round(bucket["hits"] / bucket["cases"], 4),
            "hit_at_1": round(bucket["top1"] / bucket["cases"], 4),
            "mrr": round(bucket["reciprocal_rank"] / bucket["cases"], 4),
        }
        for name, bucket in sorted(per_category.items())
    }

    # 目标文档级召回：只统计只有一个可接受文档的用例，避免“一题多解”重复计数。
    per_document: dict[str, dict] = {}
    for row in positive:
        if len(row["expected"]) != 1:
            continue
        doc_id = row["expected"][0]
        bucket = per_document.setdefault(
            doc_id, {"cases": 0, "hits": 0, "top1": 0, "scores": []}
        )
        bucket["cases"] += 1
        bucket["hits"] += int(row["hit"])
        bucket["top1"] += int(row["hit_at_1"])
        if row["hit_score"] is not None:
            bucket["scores"].append(row["hit_score"])
    document_rows = [
        {
            "doc_id": doc_id,
            "title": documents.get(doc_id, doc_id),
            "cases": bucket["cases"],
            "hit_at_k": round(bucket["hits"] / bucket["cases"], 4),
            "hit_at_1": round(bucket["top1"] / bucket["cases"], 4),
            "avg_hit_score": _mean(bucket["scores"]),
        }
        for doc_id, bucket in sorted(per_document.items())
    ]

    hits = [row for row in positive if row["hit"]]
    misses = [
        {
            "case_id": row["case_id"],
            "category": row["category"],
            "query": row["query"],
            "expected": row["expected"],
            "retrieved": row["retrieved"],
        }
        for row in positive
        if not row["hit"]
    ]
    false_retrievals = [
        {
            "case_id": row["case_id"],
            "query": row["query"],
            "retrieved": row["retrieved"],
        }
        for row in negative
        if not row["hit"]
    ]

    return {
        "mode": mode,
        "top_k": top_k,
        "cases": len(rows),
        "positive_cases": len(positive),
        "negative_cases": len(negative),
        "hit_at_k": _mean([float(row["hit"]) for row in positive]),
        "hit_at_1": _mean([float(row["hit_at_1"]) for row in positive]),
        "mrr": _mean(
            [1 / row["first_rank"] if row["first_rank"] else 0.0 for row in positive]
        ),
        "avg_top_score": _mean([row["top_score"] for row in positive]),
        "avg_hit_score": _mean([row["hit_score"] for row in hits if row["hit_score"] is not None]),
        "abstain_rate": _mean([float(row["hit"]) for row in negative]),
        "hybrid_cases": sum(1 for row in rows if row["actual_mode"] == "hybrid"),
        "lexical_fallback_cases": sum(1 for row in rows if row["actual_mode"] != "hybrid"),
        "per_category": categories,
        "per_document": document_rows,
        "misses": misses,
        "false_retrievals": false_retrievals,
        "rows": rows,
    }


def evaluate(
    db,
    cases: list[RetrievalCase],
    documents: dict[str, str],
    modes: tuple[str, ...] = MODES,
    top_k: int = 3,
) -> dict:
    """对每个模式跑一遍用例，返回可直接 JSON 序列化的报告。"""
    from app.rag import retriever

    runs = []
    for mode in modes:
        rows = []
        context = _lexical_only() if mode == "lexical" else nullcontext()
        with context:
            for case in cases:
                result = retriever.search(
                    db,
                    case.query,
                    top_k=case.top_k or top_k,
                )
                rows.append(_case_row(case, result, mode))
        runs.append(_summarize(rows, documents, mode, top_k))

    comparison = {}
    if len(runs) == 2:
        left, right = runs[0], runs[1]
        comparison = {
            "hit_at_k_delta": round((left["hit_at_k"] or 0) - (right["hit_at_k"] or 0), 4),
            "mrr_delta": round((left["mrr"] or 0) - (right["mrr"] or 0), 4),
            "note": f"{left['mode']} 相对 {right['mode']}（正数表示前者更好）",
        }
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "cases_path": str(CASES_PATH),
        "top_k": top_k,
        "case_count": len(cases),
        "runs": runs,
        "comparison": comparison,
    }


def _missing_documents(db, documents: dict[str, str]) -> list[str]:
    from app.models.knowledge import KnowledgeDocument

    existing = {
        doc_id
        for (doc_id,) in db.query(KnowledgeDocument.doc_id)
        .filter(KnowledgeDocument.doc_id.in_(list(documents)))
        .all()
    }
    return sorted(set(documents) - existing)


def _print_summary(report: dict) -> None:
    print(f"用例 {report['case_count']} 条，top_k={report['top_k']}")
    for run in report["runs"]:
        print(
            f"\n[{run['mode']}] 命中@1 {_pct(run['hit_at_1'])} · "
            f"命中@k {_pct(run['hit_at_k'])} · MRR {_num(run['mrr'])} · "
            f"拒答率 {_pct(run['abstain_rate'])} · 平均首条得分 {_num(run['avg_top_score'])}"
        )
        for category, stats in run["per_category"].items():
            print(
                f"  {category:<12} 命中@k {_pct(stats['hit_at_k'])} "
                f"@1 {_pct(stats['hit_at_1'])} MRR {_num(stats['mrr'])}"
            )
        if run["misses"]:
            print(f"  未命中 {len(run['misses'])} 条：")
            for miss in run["misses"]:
                got = "、".join(doc for doc, _ in miss["retrieved"]) or "（空）"
                print(f"    - {miss['case_id']}: {miss['query']} → 期望 {miss['expected']}，实际 {got}")
        if run["false_retrievals"]:
            print(f"  拒答失败 {len(run['false_retrievals'])} 条：")
            for row in run["false_retrievals"]:
                got = "、".join(doc for doc, _ in row["retrieved"])
                print(f"    - {row['case_id']}: {row['query']} → 实际 {got}")
    if report.get("comparison"):
        print(f"\n对照：{report['comparison']['note']}")


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.1f}%"


def _num(value: float | None) -> str:
    return "—" if value is None else f"{value:.4f}"


def _write_report(report: dict, path: Path) -> tuple[Path, Path]:
    path.parent.mkdir(parents=True, exist_ok=True)
    json_path = path.with_suffix(".json")
    csv_path = path.with_suffix(".csv")
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    fields = [
        "mode",
        "case_id",
        "category",
        "query",
        "expected",
        "retrieved",
        "top_doc",
        "top_score",
        "hit",
        "hit_at_1",
        "first_rank",
        "hit_score",
    ]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for run in report["runs"]:
            for row in run["rows"]:
                writer.writerow(
                    {
                        "mode": run["mode"],
                        "case_id": row["case_id"],
                        "category": row["category"],
                        "query": row["query"],
                        "expected": ";".join(row["expected"]),
                        "retrieved": ";".join(
                            f"{doc}:{score}" for doc, score in row["retrieved"]
                        ),
                        "top_doc": row["top_doc"] or "",
                        "top_score": row["top_score"],
                        "hit": int(row["hit"]),
                        "hit_at_1": int(row["hit_at_1"]),
                        "first_rank": row["first_rank"] or "",
                        "hit_score": row["hit_score"] if row["hit_score"] is not None else "",
                    }
                )
    return json_path, csv_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PawCare 知识库召回评测")
    parser.add_argument("--cases", type=Path, default=CASES_PATH, help="用例 YAML 路径")
    parser.add_argument("--top-k", type=int, default=3, help="召回条数（1–5）")
    parser.add_argument(
        "--mode",
        choices=("all", *MODES),
        default="all",
        help="all 同时跑混合与纯词法，用于对照",
    )
    parser.add_argument("--category", help="只跑指定分类")
    parser.add_argument("--database-url", help="默认读取 .env 的 DATABASE_URL")
    parser.add_argument("--report", type=Path, help="报告输出前缀（不含扩展名）")
    parser.add_argument("--no-report", action="store_true", help="只打印，不写文件")
    parser.add_argument("--dry-run", action="store_true", help="只校验用例，不连数据库")
    args = parser.parse_args(argv)

    try:
        documents, cases = load_cases(args.cases)
    except CaseError as exc:
        print(f"用例错误：{exc}", file=sys.stderr)
        return 2

    if args.category:
        cases = [case for case in cases if case.category == args.category]
        if not cases:
            print(f"没有分类为 {args.category} 的用例", file=sys.stderr)
            return 2

    if not 1 <= args.top_k <= MAX_TOP_K:
        print(f"top_k 必须在 1–{MAX_TOP_K} 之间", file=sys.stderr)
        return 2

    if args.dry_run:
        print(f"用例校验通过：{len(cases)} 条，文档 {len(documents)} 篇")
        counts: dict[str, int] = {}
        for case in cases:
            counts[case.category] = counts.get(case.category, 0) + 1
        for category, count in sorted(counts.items()):
            print(f"  {category:<12} {count} 条")
        return 0

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.config import settings

    url = args.database_url or settings.DATABASE_URL
    engine = create_engine(url, pool_pre_ping=True)
    session = sessionmaker(bind=engine)()
    try:
        from app.models.knowledge import KnowledgeDocument

        total_docs = session.query(KnowledgeDocument).count()
        if total_docs == 0:
            print(
                "数据库里没有知识库文档，请先运行 scripts/seed.py 或导入知识库。",
                file=sys.stderr,
            )
            return 2
        missing = _missing_documents(session, documents)
        if missing:
            print(
                f"警告：用例引用的文档在库中不存在：{missing}；这些用例会被记为未命中。",
                file=sys.stderr,
            )
        modes = MODES if args.mode == "all" else (args.mode,)
        report = evaluate(
            session,
            cases,
            documents,
            modes=modes,
            top_k=args.top_k,
        )
    finally:
        session.close()
        engine.dispose()

    _print_summary(report)
    if not args.no_report:
        prefix = args.report or (
            REPORT_DIR / f"retrieval_{datetime.now():%Y%m%d_%H%M%S}"
        )
        json_path, csv_path = _write_report(report, prefix)
        print(f"\n报告：{json_path}")
        print(f"      {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
