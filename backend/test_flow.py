# -*- coding: utf-8 -*-
"""규칙 엔진(LLM 키 없음) 기준 대화 흐름 스모크 테스트.  실행: python3 test_flow.py"""
import asyncio
import sys

sys.path.insert(0, ".")
from app import chat_engine, describe, repository as repo  # noqa: E402


async def run(answers, label):
    print("=" * 78)
    print("시나리오:", label)
    print("=" * 78)
    s, msgs = chat_engine.start_session()
    for m in msgs:
        print("🤖", m["text"].replace("\n", " "))
    i = 0
    guard = 0
    while not s.finished and guard < 25:
        guard += 1
        ans = answers[i % len(answers)]
        i += 1
        print("🙋", ans)
        out = await chat_engine.process(s, ans)
        for m in out["messages"]:
            tag = ""
            if m.get("mode") == "clarify":
                tag = "  ⟲[되묻기]"
            print("🤖", m["text"].replace("\n", " "), tag)
            if m.get("embed"):
                e = m["embed"]
                print(f"   📎 EMBED → place_id={e['place_id']} 일치도={e['fit_score']}% cta={e['cta']}")
        if out["finished"]:
            break
    print("\n[슬롯]")
    for k, v in s.slots.items():
        print(f"   {k:14s} value={v['value']:>4}  conf={v['confidence']:>4}  {v['evidence'][:40]}")
    r = s.result
    print(f"\n[추천] {r['place']['place_name']}  일치도 {r['fit_score']}%")
    print("[상위 5]", ", ".join(f"{x['place_name']}({x['fit_score']})" for x in r["ranking"][:5]))
    d = await describe.regenerate(r["place"])
    print(f"\n[재생성 설명 / {d['generated_by']}]")
    print("  headline:", d["headline"])
    print("  intro   :", d["intro"][:120])
    for h in d["highlights"]:
        print(f"  · {h['title']}: {h['body'][:70]}")
    print("  good_for:", d["good_for"][:80])
    print("  keywords:", d["keywords"])
    print()
    return s


async def main():
    await run(
        [
            "차 가지고 갈 거예요",
            "직접 체험하는 게 좋아요",
            "먹는 거요! 대게 먹고 싶어요",
            "아이랑 같이 가요",
            "많이 걷는 건 힘들어요",
            "사람 많고 활기찬 데가 좋아요",
            "가볍게 즐기고 싶어요",
            "야외가 좋아요",
            "돈은 제대로 쓸 생각이에요",
            "두어 시간 정도요",
        ],
        "미식·가족·활기찬 핫플",
    )

    await run(
        [
            "음 잘 모르겠어요",          # 첫 지표에서 애매 → 되묻기 유발
            "전시 보는 거 좋아해요",
            "자연 경관이요",
            "혼자 갑니다",
            "등산도 괜찮아요",
            "한적한 곳이 좋아요",
            "역사 이야기를 깊게 보고 싶어요",
            "야외요",
            "무료면 좋겠어요",
            "반나절 정도 푹",
            "대중교통으로 다녀요",
        ],
        "혼자·역사 탐방·한적",
    )


if __name__ == "__main__":
    asyncio.run(main())
