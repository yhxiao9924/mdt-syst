"""命令行入口：跑一份病例并打印会诊报告。

用法：
    python main.py
    python main.py data/cases/case_001.json
"""

import json
import sys
from pathlib import Path

from config import CASE_DIR
from src.graph import build_graph
from src.schemas import Case


def load_case(path: Path) -> dict:
    return Case.model_validate_json(path.read_text(encoding="utf-8")).model_dump()


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else CASE_DIR / "case_001.json"
    case = load_case(path)

    print(f"=== 病例 {case['case_id']}：{case['cancer_type']} ===\n")

    app = build_graph()
    report = None
    # stream_mode="updates"：每完成一个节点就吐一次结果，便于观察执行顺序
    for chunk in app.stream({"case": case, "trace": []}, stream_mode="updates"):
        for node, update in chunk.items():
            print(f"[完成] {node}")
            for item in update.get("trace", []):
                print(f"  └─ {item['agent']}")
            if node == "decision":
                report = update.get("report")

    print("\n===== 最终会诊报告 =====")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
