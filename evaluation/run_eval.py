"""评测脚本：三种配置对比，产出可直接写进报告的指标表。

对比的三种配置：
    full      —— 完整多 Agent（协调 + 基因组 + 病理 + 药物 + 文献 + 决策）
    baseline  —— 单 Agent 基线：一个大 prompt 直接让模型看病例给结论，不用工具
    no_lit    —— 消融：多 Agent 但去掉文献 Agent

用法：
    python evaluation/run_eval.py                      # 跑全部病例，对比 full 和 baseline
    python evaluation/run_eval.py --groups full,baseline,no_lit
    python evaluation/run_eval.py --case case_001      # 只跑一份，快速验证

结果保存在 outputs/ 下（json 明细 + csv 汇总），控制台打印对比表。
"""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import re
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import CASE_DIR, KB_FILE  # noqa: E402
from src.graph import build_graph  # noqa: E402
from src.llm import chat_json  # noqa: E402
from src.schemas import Case, FinalReport  # noqa: E402

OUTPUT_DIR = ROOT / "outputs"

BASELINE_PROMPT = """你是肿瘤科医生。请根据给出的病例信息，直接给出诊断与用药建议。

要求：
- 只能使用病例中提供的信息，不要引用病例之外的具体文献或数据
- 每个建议的 mechanism 写成"变异 → 通路/机制 → 药物作用"的链条
- 无法判断的内容写入 uncertainties
"""

GROUP_NAMES = {
    "full": "完整多 Agent",
    "baseline": "单 Agent 基线",
    "no_lit": "去掉文献 Agent",
}


# ---------------------------------------------------------------- 数据加载

def strip_answer(raw: dict) -> dict:
    """去掉 ground_truth_drugs 再喂给模型，否则等于把答案直接给它。"""
    case = dict(raw)
    case.pop("ground_truth_drugs", None)
    return case


def load_cases(case_filter: str | None) -> list[dict]:
    files = sorted(CASE_DIR.glob("*.json"))
    if case_filter:
        files = [p for p in files if case_filter in p.stem]
    if not files:
        raise SystemExit(f"在 {CASE_DIR} 下没有找到病例文件")
    cases = []
    for path in files:
        cases.append(Case.model_validate_json(path.read_text(encoding="utf-8")).model_dump())
    return cases


# ---------------------------------------------------------------- 三种运行器

def run_full(case: dict) -> dict:
    """完整多 Agent：走 LangGraph 图。"""
    app = build_graph(enable_literature=True)
    report = _stream_to_report(app, case)
    return report


def run_no_lit(case: dict) -> dict:
    """消融实验：多 Agent 但去掉文献。"""
    app = build_graph(enable_literature=False)
    report = _stream_to_report(app, case)
    return report


def run_baseline(case: dict) -> dict:
    """单 Agent 基线：一次性把病例丢给模型，不挂任何工具。"""
    payload = json.dumps(strip_answer(case), ensure_ascii=False, indent=2)
    result = chat_json(
        [
            {"role": "system", "content": BASELINE_PROMPT},
            {"role": "user", "content": f"病例：\n{payload}\n\n请给出结构化会诊结论。"},
        ],
        FinalReport,
    )
    return result.model_dump()


def _stream_to_report(app, case: dict) -> dict:
    """跑一次图，取决策节点的输出。"""
    report = None
    for chunk in app.stream({"case": strip_answer(case), "trace": []}, stream_mode="updates"):
        for node, update in chunk.items():
            if node == "decision":
                report = update.get("report")
    if report is None:
        raise RuntimeError("决策节点没有产出报告")
    return report


RUNNERS = {"full": run_full, "baseline": run_baseline, "no_lit": run_no_lit}


# ---------------------------------------------------------------- 指标计算

# 中英文药名对照。模型可能输出中文名（甚至带括号说明），
# 不做归一化会把"答对了"误判成"没答对"，导致指标失真。
DRUG_ALIASES = {
    "奥希替尼": "osimertinib",
    "奥西替尼": "osimertinib",
    "泰瑞沙": "osimertinib",
    "厄洛替尼": "erlotinib",
    "特罗凯": "erlotinib",
    "吉非替尼": "gefitinib",
    "易瑞沙": "gefitinib",
    "阿法替尼": "afatinib",
    "阿来替尼": "alectinib",
    "阿雷替尼": "alectinib",
    "克唑替尼": "crizotinib",
    "劳拉替尼": "lorlatinib",
    "洛拉替尼": "lorlatinib",
    "恩曲替尼": "entrectinib",
    "索托拉西布": "sotorasib",
    "索托雷塞": "sotorasib",
    "阿达格拉西布": "adagrasib",
    "达拉非尼": "dabrafenib",
    "曲美替尼": "trametinib",
    "卡马替尼": "capmatinib",
    "特泊替尼": "tepotinib",
    "塞尔帕替尼": "selpercatinib",
    "普拉替尼": "pralsetinib",
    "拉罗替尼": "larotrectinib",
    "埃万妥单抗": "amivantamab",
    "德曲妥珠单抗": "trastuzumabderuxtecan",
    "恩美曲妥珠单抗": "trastuzumabemtansine",
    "曲妥珠单抗": "trastuzumab",
    "帕妥珠单抗": "pertuzumab",
    "帕博利珠单抗": "pembrolizumab",
    "阿培利司": "alpelisib",
    "奥拉帕利": "olaparib",
    "他拉唑帕利": "talazoparib",
    "艾拉司群": "elacestrant",
    "卡匹色替": "capivasertib",
    "恩考芬尼": "encorafenib",
    "西妥昔单抗": "cetuximab",
    "维莫非尼": "vemurafenib",
    "考比替尼": "cobimetinib",
    "伊马替尼": "imatinib",
    "舒尼替尼": "sunitinib",
    "瑞戈非尼": "regorafenib",
    "阿伐替尼": "avapritinib",
    "佐妥昔单抗": "zolbetuximab",
    "培米替尼": "pemigatinib",
    "福巴替尼": "futibatinib",
    "艾伏尼布": "ivosidenib",
    "尼拉帕利": "niraparib",
}


def drug_tokens(name: str) -> set[str]:
    """把药名拆成可比较的原子并归一化。

    处理四种情况：
    - 组合药：'Dabrafenib + Trametinib' → {dabrafenib, trametinib}
    - 括号说明：'奥希替尼（第三代EGFR-TKI）' → {osimertinib}
    - 中英对照：'奥希替尼' → {osimertinib}
    - 中英双写：'奥希替尼 (Osimertinib)' → {osimertinib}（括号内英文优先）
    """
    tokens: set[str] = set()
    # 括号里如果是英文通用名，直接拿来用，不再依赖别名表
    for inner in re.findall(r"[（(]([^）)]*)[）)]", name):
        if re.search(r"[a-z]", inner.lower()):
            for part in re.split(r"[+,/、，]| and ", inner.lower()):
                token = part.strip().replace(" ", "").replace("-", "")
                if token:
                    tokens.add(DRUG_ALIASES.get(token, token))

    cleaned = re.sub(r"[（(][^）)]*[）)]", "", name.lower())
    for part in re.split(r"[+,/、，]| and ", cleaned):
        token = part.strip().replace(" ", "").replace("-", "")
        if token:
            tokens.add(DRUG_ALIASES.get(token, token))
    return tokens


def predicted_drugs(report: dict) -> list[str]:
    return [rec.get("drug", "") for rec in report.get("recommendations", []) if rec.get("drug")]


def hit_at_k(pred: list[str], gold: set[str], k: int) -> float:
    """Top-k 里是否命中了任意一个标准答案药物。

    负样本（标准答案为空）考察的是"该不该推荐"：
    给出任何靶向药都算错，正确做法是不推荐。
    """
    if not gold:
        return 1.0 if not pred else 0.0
    for name in pred[:k]:
        if drug_tokens(name) & gold:
            return 1.0
    return 0.0


def recall(pred: list[str], gold: set[str]) -> float:
    """标准答案里的药物被覆盖了多少比例。"""
    if not gold:
        return 1.0 if not pred else 0.0
    covered = set()
    for name in pred:
        covered |= drug_tokens(name) & gold
    return len(covered) / len(gold)


def structure_score(report: dict) -> float:
    """结构完整率：关键字段是否都有内容。"""
    checks = [
        bool(report.get("case_summary")),
        len(report.get("key_findings") or []) > 0,
        len(report.get("recommendations") or []) > 0,
        len(report.get("uncertainties") or []) > 0,
        all(rec.get("mechanism") for rec in report.get("recommendations") or []),
    ]
    return sum(checks) / len(checks)


def count_pmids(report: dict) -> int:
    n = 0
    for rec in report.get("recommendations") or []:
        for ref in rec.get("references") or []:
            if "PMID" in ref.upper():
                n += 1
    return n


def precision(pred: list[str], gold: set[str]) -> float:
    """精确率：推荐出来的药里，有多少是标准答案里的。

    和召回率互补：召回率罚"漏"，精确率罚"多"。
    """
    if not pred or not gold:
        return 0.0
    correct = sum(1 for name in pred if drug_tokens(name) & gold)
    return correct / len(pred)


def citation_coverage(report: dict) -> float:
    """引用覆盖率：有 PMID 引用的推荐占比（不是每条都有文献，但要能查到）。"""
    recs = report.get("recommendations") or []
    if not recs:
        return 0.0
    with_ref = sum(
        1
        for rec in recs
        if any("PMID" in (ref or "").upper() for ref in (rec.get("references") or []))
    )
    return with_ref / len(recs)


def _load_kb_drugs() -> set[str]:
    """知识库里出现过的药名集合，用来判断某条推荐"是不是靶向药"。"""
    drugs: set[str] = set()
    with KB_FILE.open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if (row.get("drug") or "").strip():
                drugs |= drug_tokens(row["drug"])
    return drugs


KB_DRUGS = _load_kb_drugs()


def targeted_predictions(report: dict) -> list[str]:
    """只保留"靶向药"性质的推荐：target 字段非空，或药名在知识库里。

    负样本（无靶向药可用）的正确行为是这里返回空列表：
    可以建议化疗，但不能声称有靶向药。
    """
    out = []
    for rec in report.get("recommendations") or []:
        name = rec.get("drug") or ""
        if not name:
            continue
        if (rec.get("target") or "").strip() or (drug_tokens(name) & KB_DRUGS):
            out.append(name)
    return out


# ---------------------------------------------------------------- 主流程

def evaluate(groups: list[str], cases: list[dict], repeat: int = 1) -> dict:
    results: dict[str, list[dict]] = {g: [] for g in groups}
    total = len(cases) * repeat * len(groups)
    done = 0

    for group in groups:
        runner = RUNNERS[group]
        print(f"\n=== 配置：{GROUP_NAMES[group]} ===")
        for case in cases:
            gold = {t for drug in case.get("ground_truth_drugs", []) for t in drug_tokens(drug)}
            for run_idx in range(1, repeat + 1):
                done += 1
                started = time.time()
                record = {
                    "case_id": case["case_id"],
                    "group": group,
                    "run": run_idx,
                    "negative": not gold,
                }

                try:
                    report = runner(case)
                    pred = predicted_drugs(report)
                    targeted = targeted_predictions(report)
                    # 负样本只考核"有没有声称靶向药"，避免把合理的化疗建议判成错
                    scored = targeted if record["negative"] else pred
                    record.update(
                        {
                            "status": "ok",
                            "seconds": round(time.time() - started, 1),
                            "predictions": pred,
                            "pred_set": sorted({t for name in pred[:3] for t in drug_tokens(name)}),
                            "hit@1": hit_at_k(scored, gold, 1),
                            "hit@3": hit_at_k(scored, gold, 3),
                            "recall": round(recall(scored, gold), 3),
                            "precision": round(precision(pred, gold), 3),
                            "structure": round(structure_score(report), 3),
                            "pmid_count": count_pmids(report),
                            "citation_coverage": round(citation_coverage(report), 3),
                            "drug_count": len(pred),
                            "abstain": 1.0 if (record["negative"] and not targeted) else 0.0,
                            "report": report,
                        }
                    )
                    print(
                        f"  [{done}/{total}] {case['case_id']}#{run_idx}  "
                        f"hit@1={record['hit@1']:.0f}  recall={record['recall']:.2f}  "
                        f"precision={record['precision']:.2f}  ref={record['citation_coverage']:.2f}  "
                        f"{record['seconds']}s"
                    )
                except Exception as exc:
                    record.update(
                        {
                            "status": "failed",
                            "seconds": round(time.time() - started, 1),
                            "error": f"{type(exc).__name__}: {exc}",
                            "traceback": traceback.format_exc(limit=3),
                        }
                    )
                    print(f"  [{done}/{total}] {case['case_id']}#{run_idx}  失败：{record['error']}")

                results[group].append(record)

    return results


def stability(records: list[dict]) -> tuple[float, float]:
    """稳定性：同一份病例多次运行之间结论的一致程度。

    返回（平均 Jaccard 相似度, 完全一致率）：
    - Jaccard = 两次 Top-3 药名集合的交集 / 并集
    - 完全一致率 = 两次结论完全相同的比例
    """
    by_case: dict[str, list[set[str]]] = {}
    for r in records:
        if r["status"] != "ok":
            continue
        by_case.setdefault(r["case_id"], []).append(set(r["pred_set"]))

    scores, same, pairs = [], 0, 0
    for sets in by_case.values():
        for a, b in itertools.combinations(sets, 2):
            union = a | b
            scores.append(len(a & b) / len(union) if union else 1.0)
            same += int(a == b)
            pairs += 1

    if not pairs:
        return (1.0, 1.0)
    return (sum(scores) / pairs, same / pairs)


def summarize(results: dict[str, list[dict]]) -> None:
    """打印两张表：主指标表 + 稳定性/覆盖表。"""
    header = (
        f"{'配置':<16}{'成功':<7}{'Hit@1':<7}{'Hit@3':<7}{'召回':<7}"
        f"{'精确':<7}{'结构':<7}{'引用覆盖':<10}{'耗时':<8}{'PMID':<6}"
    )
    print("\n" + "=" * len(header))
    print("主指标（正样本算命中/召回/精确，负样本算弃权）")
    print("-" * len(header))
    print(header)
    print("-" * len(header))

    stats: dict[str, dict] = {}
    for group, records in results.items():
        ok = [r for r in records if r["status"] == "ok"]
        if not ok:
            print(f"{GROUP_NAMES[group]:<16}{'0/' + str(len(records)):<7}全部失败")
            continue

        positive = [r for r in ok if not r["negative"]]
        negative = [r for r in ok if r["negative"]]

        def avg(rows: list[dict], key: str) -> float:
            return sum(r[key] for r in rows) / len(rows) if rows else 0.0

        jaccard, identical = stability(ok)
        stats[group] = {
            "success": f"{len(ok)}/{len(records)}",
            "abstain": avg(negative, "abstain"),
            "drug_count": avg(positive, "drug_count"),
            "jaccard": jaccard,
            "identical": identical,
            "citation_coverage": avg(positive, "citation_coverage"),
        }

        print(
            f"{GROUP_NAMES[group]:<16}"
            f"{f'{len(ok)}/{len(records)}':<7}"
            f"{avg(positive, 'hit@1'):<7.2f}"
            f"{avg(positive, 'hit@3'):<7.2f}"
            f"{avg(positive, 'recall'):<7.2f}"
            f"{avg(positive, 'precision'):<7.2f}"
            f"{avg(ok, 'structure'):<7.2f}"
            f"{avg(positive, 'citation_coverage'):<10.2f}"
            f"{avg(ok, 'seconds'):<8.1f}"
            f"{avg(positive, 'pmid_count'):<6.1f}"
        )

    print("-" * len(header))
    header2 = f"\n{'配置':<16}{'负样本弃权':<12}{'平均推荐药数':<14}{'稳定性(Jaccard)':<17}{'完全一致率':<12}"
    print(header2)
    print("-" * len(header2))
    for group, s in stats.items():
        print(
            f"{GROUP_NAMES[group]:<16}"
            f"{s['abstain']:<12.2f}"
            f"{s['drug_count']:<14.1f}"
            f"{s['jaccard']:<17.2f}"
            f"{s['identical']:<12.2f}"
        )
    print("=" * len(header2))


def save(results: dict, cases: list[dict]) -> Path:
    OUTPUT_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    out = OUTPUT_DIR / f"eval_{stamp}.json"
    payload = {
        "timestamp": stamp,
        "case_count": len(cases),
        "groups": results,
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # 同时导一份 csv，方便直接贴进报告
    csv_path = OUTPUT_DIR / f"eval_{stamp}.csv"
    lines = [
        "group,case_id,run,status,hit@1,hit@3,recall,precision,structure,"
        "citation_coverage,drug_count,abstain,pmid,seconds"
    ]
    for group, records in results.items():
        for r in records:
            lines.append(
                ",".join(
                    [
                        group,
                        r["case_id"],
                        str(r.get("run", "")),
                        r["status"],
                        str(r.get("hit@1", "")),
                        str(r.get("hit@3", "")),
                        str(r.get("recall", "")),
                        str(r.get("precision", "")),
                        str(r.get("structure", "")),
                        str(r.get("citation_coverage", "")),
                        str(r.get("drug_count", "")),
                        str(r.get("abstain", "")),
                        str(r.get("pmid_count", "")),
                        str(r.get("seconds", "")),
                    ]
                )
            )
    csv_path.write_text("\n".join(lines), encoding="utf-8-sig")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="MDT 多智能体会诊系统评测")
    parser.add_argument(
        "--groups",
        default="full,baseline",
        help="要跑的配置，逗号分隔：full / baseline / no_lit",
    )
    parser.add_argument("--case", default=None, help="只跑文件名包含该关键字的病例")
    parser.add_argument(
        "--repeat",
        type=int,
        default=1,
        help="每份病例重复运行次数，>1 时统计稳定性（会成倍消耗 token）",
    )
    args = parser.parse_args()

    groups = [g.strip() for g in args.groups.split(",") if g.strip()]
    unknown = [g for g in groups if g not in RUNNERS]
    if unknown:
        raise SystemExit(f"未知配置：{unknown}，可选 {list(RUNNERS)}")

    cases = load_cases(args.case)
    print(f"共 {len(cases)} 份病例，配置：{groups}，重复 {args.repeat} 次")

    results = evaluate(groups, cases, args.repeat)
    summarize(results)
    out = save(results, cases)
    print(f"\n明细已保存：{out}")


if __name__ == "__main__":
    main()
