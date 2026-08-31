# -*- coding: utf-8 -*-
"""
여행지_20_포항.csv (CP949) + tools/scores_data.py 를 합쳐
  - data/places.json        : 앱/백엔드가 그대로 읽는 마스터 데이터
  - data/place_scores.csv   : 점수만 뽑은 표 (UTF-8-SIG, 엑셀에서 바로 열림)
  - data/places_utf8.csv    : 원본 CSV 의 UTF-8 변환본
  - docs/평가근거.md         : 200개 점수 각각의 산정 근거 문서
  - supabase/seed_data.json : Supabase 시드용 payload
를 생성한다.

실행:  python3 tools/build_scores.py
"""
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scores_data import AXES, AXIS_KEYS, PRIORITY_WEIGHT, SCORES  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_CSV = os.path.join(ROOT, "여행지_20_포항.csv")

TEXT_FIELDS = [
    "summary",
    "embedding_text",
    "evidence_text_1",
    "evidence_text_2",
    "evidence_text_3",
    "evidence_text_4",
    "evidence_text_5",
]


def read_source():
    with open(SRC_CSV, "r", encoding="cp949", newline="") as f:
        return list(csv.DictReader(f))


def slugify(place_id):
    return place_id.lower()


def build():
    rows = read_source()
    assert len(rows) == 20, f"여행지가 20개가 아닙니다: {len(rows)}"

    places = []
    for r in rows:
        pid = r["place_id"].strip()
        if pid not in SCORES:
            raise KeyError(f"{pid} 의 점수가 scores_data.py 에 없습니다")
        sc = SCORES[pid]
        missing = [k for k in AXIS_KEYS if k not in sc]
        if missing:
            raise KeyError(f"{pid} 누락 축: {missing}")

        for k in AXIS_KEYS:
            v = sc[k][0]
            if not (0.0 <= v <= 10.0):
                raise ValueError(f"{pid}.{k} 점수 범위 오류: {v}")

        places.append(
            {
                "place_id": pid,
                "place_name": r["place_name"].strip(),
                "slug": slugify(pid),
                "summary": r["summary"].strip(),
                "embedding_text": r["embedding_text"].strip(),
                "evidence_texts": [r[f"evidence_text_{i}"].strip() for i in range(1, 6)],
                "scores": {k: round(float(sc[k][0]), 1) for k in AXIS_KEYS},
                "score_reasons": {k: sc[k][1] for k in AXIS_KEYS},
                "image_path": f"{slugify(pid)}.jpg",
            }
        )

    os.makedirs(os.path.join(ROOT, "data"), exist_ok=True)
    os.makedirs(os.path.join(ROOT, "docs"), exist_ok=True)
    os.makedirs(os.path.join(ROOT, "supabase"), exist_ok=True)

    # ---- data/places.json -------------------------------------------------
    master = {
        "axes": AXES,
        "priority_weight": PRIORITY_WEIGHT,
        "places": places,
    }
    with open(os.path.join(ROOT, "data", "places.json"), "w", encoding="utf-8") as f:
        json.dump(master, f, ensure_ascii=False, indent=2)

    # ---- data/place_scores.csv -------------------------------------------
    with open(os.path.join(ROOT, "data", "place_scores.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["place_id", "place_name"] + AXIS_KEYS)
        for p in places:
            w.writerow([p["place_id"], p["place_name"]] + [p["scores"][k] for k in AXIS_KEYS])

    # ---- data/places_utf8.csv --------------------------------------------
    with open(os.path.join(ROOT, "data", "places_utf8.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow(r)

    # ---- supabase/seed_data.json -----------------------------------------
    seed = []
    for p in places:
        rec = {
            "place_id": p["place_id"],
            "place_name": p["place_name"],
            "slug": p["slug"],
            "summary": p["summary"],
            "embedding_text": p["embedding_text"],
            "evidence_text_1": p["evidence_texts"][0],
            "evidence_text_2": p["evidence_texts"][1],
            "evidence_text_3": p["evidence_texts"][2],
            "evidence_text_4": p["evidence_texts"][3],
            "evidence_text_5": p["evidence_texts"][4],
            "image_path": p["image_path"],
        }
        for k in AXIS_KEYS:
            rec[f"score_{k}"] = p["scores"][k]
            rec[f"reason_{k}"] = p["score_reasons"][k]
        seed.append(rec)
    with open(os.path.join(ROOT, "supabase", "seed_data.json"), "w", encoding="utf-8") as f:
        json.dump(seed, f, ensure_ascii=False, indent=2)

    # ---- docs/평가근거.md --------------------------------------------------
    write_evidence_doc(places)

    print(f"OK  places={len(places)}  scores={len(places) * len(AXIS_KEYS)}")
    for path in [
        "data/places.json",
        "data/place_scores.csv",
        "data/places_utf8.csv",
        "supabase/seed_data.json",
        "docs/평가근거.md",
    ]:
        full = os.path.join(ROOT, path)
        print(f"    - {path} ({os.path.getsize(full):,} bytes)")


def write_evidence_doc(places):
    L = []
    L.append("# 포항항 — 여행지 20곳 취향 점수 산정 근거\n")
    L.append("`여행지_20_포항.csv` 의 20개 여행지를 `평가 기준.txt` 의 취향 지표 10개에 대해 ")
    L.append("각각 **0.0 ~ 10.0** 으로 채점한 결과와 그 근거를 정리한 문서입니다. ")
    L.append("총 **20 × 10 = 200개** 점수 전부에 근거를 남겼습니다.\n")

    L.append("\n## 0. 채점 방법\n")
    L.append("각 취향 지표는 서로 반대되는 두 극(極)을 가진 **하나의 연속 축**으로 정의했습니다. ")
    L.append("예를 들어 `전시·관람형 / 참여형` 지표는 0.0 에 가까울수록 관람형, 10.0 에 가까울수록 참여형입니다. ")
    L.append("이렇게 하면 사용자의 대답도 같은 축 위의 한 점으로 환산할 수 있어, ")
    L.append("여행지 점수와 사용자 취향 점수 사이의 **가중 거리**로 추천을 계산할 수 있습니다.\n")
    L.append("\n근거 표기 규칙:\n\n")
    L.append("| 표기 | 의미 |\n|---|---|\n")
    L.append("| `[summary]` `[embedding]` `[ev1]`~`[ev5]` | CSV 원문 필드에 직접 명시된 내용을 근거로 삼은 부분 |\n")
    L.append("| `[보정]` | CSV 에 정보가 없어 포항 현지의 위치·요금·접근성 상식으로 보정한 부분 |\n")

    L.append("\n## 1. 평가 축 정의\n\n")
    L.append("| # | 취향 지표 | 우선순위 | 0.0 쪽 | 10.0 쪽 |\n|---|---|---|---|---|\n")
    for i, a in enumerate(AXES, 1):
        L.append(f"| {i} | {a['label']} | **{a['priority']}** | {a['low']} | {a['high']} |\n")

    L.append("\n> 우선순위 가중치: **P0 = 1.0**, **P1 = 0.6**. ")
    L.append("챗봇은 P0 지표를 먼저 질문하고, P0 를 모두 확보한 뒤 P1 을 묻습니다.\n")

    L.append("\n## 2. 점수 종합표\n\n")
    header = "| 여행지 | " + " | ".join(a["label"].split(" / ")[0][:6] for a in AXES) + " |\n"
    L.append(header)
    L.append("|" + "---|" * (len(AXES) + 1) + "\n")
    for p in places:
        L.append(
            f"| {p['place_name']} | "
            + " | ".join(f"{p['scores'][k]:.1f}" for k in AXIS_KEYS)
            + " |\n"
        )
    L.append("\n(열 순서는 위 '평가 축 정의' 표와 동일합니다.)\n")

    L.append("\n## 3. 여행지별 상세 근거\n")
    for idx, p in enumerate(places, 1):
        L.append(f"\n### {idx}. {p['place_name']} (`{p['place_id']}`)\n\n")
        L.append(f"> {p['summary']}\n\n")
        L.append("<details><summary>채점에 사용한 CSV 원문</summary>\n\n")
        L.append(f"- **embedding_text**: {p['embedding_text']}\n")
        for i, ev in enumerate(p["evidence_texts"], 1):
            L.append(f"- **evidence_text_{i}**: {ev}\n")
        L.append("\n</details>\n\n")
        L.append("| 취향 지표 | 우선순위 | 점수 | 근거 |\n|---|:--:|:--:|---|\n")
        for a in AXES:
            k = a["key"]
            reason = p["score_reasons"][k].replace("|", "\\|")
            L.append(f"| {a['label']} | {a['priority']} | **{p['scores'][k]:.1f}** | {reason} |\n")

    L.append("\n---\n\n")
    L.append("## 4. 이 점수가 추천에 쓰이는 방식\n\n")
    L.append("사용자의 대화 응답에서 각 축의 목표값 `u_k` 와 확신도 `c_k` (0~1) 를 뽑아낸 뒤, ")
    L.append("여행지 `p` 의 적합도를 다음과 같이 계산합니다.\n\n")
    L.append("```\n")
    L.append("w_k        = priority_weight(k) × c_k        # P0=1.0, P1=0.6\n")
    L.append("distance   = Σ_k w_k × |score_p,k − u_k|  /  Σ_k w_k\n")
    L.append("fit_score  = (1 − distance / 10) × 100      # 0~100 점\n")
    L.append("```\n\n")
    L.append("즉 **사용자가 확실하게 답한 축일수록**, 그리고 **P0 축일수록** 추천 결과에 강하게 반영됩니다. ")
    L.append("사용자가 판단을 유보한 축은 `c_k = 0` 이 되어 계산에서 자연히 빠집니다.\n")

    with open(os.path.join(ROOT, "docs", "평가근거.md"), "w", encoding="utf-8") as f:
        f.write("".join(L))


if __name__ == "__main__":
    build()
