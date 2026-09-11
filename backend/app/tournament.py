# -*- coding: utf-8 -*-
"""
2택 월드컵(이상형 월드컵) 추천 엔진 — 채팅 엔진을 대체한다.

두 여행지 중 하나를 고르는 대결을 TOTAL_ROUNDS 만큼 반복한다.
  1) 선택 + 반응시간으로 Elo 레이팅을 갱신한다.
     빠르게 고를수록(= 더 끌릴수록) 갱신 폭 K 가 커진다.
  2) 끝나면 레이팅 순으로 전체 순위가 나오고, 1위를 결과로 띄운다.
  3) 고른 곳들의 10축 점수를 반응시간 가중 평균해 '사용자 취향 벡터'를 역산한다.
     (결과 화면의 fit_score / matched_axes / '내 응답의 취향 점수'에 사용)

결과 설명은 describe.regenerate 가 CSV 근거로 재생성한다(엔진과 무관).
"""
from __future__ import annotations

import logging
import random
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

from . import describe, recommender, repository as repo
from . import supabase as sb

log = logging.getLogger("pohang.match")

TOTAL_ROUNDS = 12
START_RATING = 1000.0
K_BASE = 48.0

# 반응시간(초) → 선호도(appeal, 0~10). 빠를수록 강하게 끌린 것으로 본다.
#   카드 2장을 읽고 고민하는 바닥 시간(~5초)까지는 9~10점,
#   그 뒤로는 SEC_PER_POINT 초마다 1점씩 하락한다.
# ponytail: 첫 라운드는 UI를 처음 읽느라 느리게 찍힐 수 있음 — 필요하면 첫 라운드만 바닥 보정.
READ_FLOOR_S = 5.0      # 이 안에 고르면 최고 선호대(9~10점)
FULL_APPEAL = 10.0      # 즉답(0초)
FLOOR_APPEAL = 9.0      # 5초 지점의 선호도
SEC_PER_POINT = 1.5     # 5초 이후 이 초만큼 지날 때마다 1점 하락 (1~2초 사이 취향껏)
MIN_APPEAL = 2.0        # 아무리 오래 걸려도 이 밑으로는 안 내려감

_SESSIONS: Dict[str, "Match"] = {}


def _appeal(elapsed_ms: Optional[float]) -> float:
    """반응시간 → 0~10 선호도."""
    if elapsed_ms is None:
        return MIN_APPEAL
    t = max(0.0, float(elapsed_ms)) / 1000.0
    if t <= READ_FLOOR_S:
        a = FULL_APPEAL - (FULL_APPEAL - FLOOR_APPEAL) * (t / READ_FLOOR_S)   # 10→9
    else:
        a = FLOOR_APPEAL - (t - READ_FLOOR_S) / SEC_PER_POINT                 # 9에서 하락
    return max(MIN_APPEAL, min(FULL_APPEAL, a))


def _confidence(elapsed_ms: Optional[float]) -> float:
    """Elo K·취향 가중치로 쓰는 0~1 신뢰도 (= 선호도/10)."""
    return _appeal(elapsed_ms) / 10.0


# evidence 문장에서 '무엇을 할 수 있는지 / 누구에게 맞는지'를 뽑아
# 카드에서 "이 곳에 가고 싶은지"가 느껴지게 한다.
_ACT_PAT = re.compile(r"(.+?)(?:하기|하는\s*데|에)\s*(?:좋|적합|안성맞춤|추천)")


def _activities(p: Dict[str, Any]) -> List[str]:
    """'일출 감상, 해안 산책 …에 좋습니다' → ['일출 감상','해안 산책', …]"""
    for e in p.get("evidence_texts") or []:
        m = _ACT_PAT.search(e)
        if m:
            parts = [x.strip() for x in re.split(r"[,·]", m.group(1)) if x.strip()]
            if parts:
                return parts[:3]
    return describe._keywords(p)[:3]


def _good_for(p: Dict[str, Any]) -> str:
    """'…여행객에게 특히 맞습니다' → '…여행객' 한 줄."""
    for e in reversed(p.get("evidence_texts") or []):
        if "맞습니다" in e or "추천" in e:
            head = e.split("에게")[0].strip()
            if "," in head:                    # 앞 수식절(축제·날짜 등) 제거
                head = head.split(",")[-1].strip()
            if head:
                return head[:36]
    return ""


def _card(p: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "place_id": p["place_id"],
        "place_name": p["place_name"],
        "image_url": p.get("image_url"),
        "summary": p.get("summary", ""),
        "activities": _activities(p),
        "good_for": _good_for(p),
    }


class Match:
    def __init__(self):
        self.id = str(uuid.uuid4())
        self.ids = [p["place_id"] for p in repo.places()]
        self.rating: Dict[str, float] = {pid: START_RATING for pid in self.ids}
        self.faced: set = set()                 # frozenset({a,b})
        self.taste_num: Dict[str, float] = {}
        self.taste_den = 0.0
        self.round = 0                          # 완료한 라운드 수
        self.pair: Optional[Tuple[str, str]] = None
        self.queue: List[Tuple[str, str]] = self._seed()
        self.finished = False
        self.result: Optional[Dict[str, Any]] = None

    # --- 짝짓기 ----------------------------------------------------------
    def _seed(self) -> List[Tuple[str, str]]:
        """1페이즈: 셔플해 모든 곳을 한 번씩 붙인다(20곳 → 10쌍)."""
        pool = self.ids[:]
        random.shuffle(pool)
        return [(pool[i], pool[i + 1]) for i in range(0, len(pool) - 1, 2)]

    def _next_pair(self) -> Tuple[str, str]:
        while self.queue:
            a, b = self.queue.pop(0)
            if frozenset((a, b)) not in self.faced:
                return a, b
        # 2페이즈: 상위 레이팅끼리 붙여 1위를 가린다.
        order = sorted(self.ids, key=lambda p: -self.rating[p])
        top = order[0]
        for b in order[1:]:
            if frozenset((top, b)) not in self.faced:
                return top, b
        return tuple(random.sample(order[:6], 2))  # 전부 붙어봤으면 상위권 무작위

    # --- 진행 ------------------------------------------------------------
    def start(self) -> Dict[str, Any]:
        self.pair = self._next_pair()
        return self._pair_payload()

    def current(self) -> Dict[str, Any]:
        """진행 중이면 지금 대결을, 끝났으면 finished 를 돌려준다(새로고침 복원용)."""
        if self.finished or self.pair is None:
            return {"finished": True, "session_id": self.id}
        return self._pair_payload()

    def _pair_payload(self) -> Dict[str, Any]:
        a, b = self.pair
        return {
            "session_id": self.id,
            "round": self.round + 1,
            "total": TOTAL_ROUNDS,
            "pair": [_card(repo.get_place(a)), _card(repo.get_place(b))],
            "finished": False,
        }

    def choose(self, winner_id: str, loser_id: str,
               elapsed_ms: Optional[float]) -> Dict[str, Any]:
        if self.finished:
            return {"finished": True, "session_id": self.id}
        if winner_id not in self.rating or loser_id not in self.rating:
            raise ValueError("알 수 없는 여행지입니다")

        conf = _confidence(elapsed_ms)
        self._update_elo(winner_id, loser_id, conf)
        self._update_taste(winner_id, conf)
        self.faced.add(frozenset((winner_id, loser_id)))
        self.round += 1

        if self.round >= TOTAL_ROUNDS:
            self._finalize()
            return {"finished": True, "session_id": self.id}

        self.pair = self._next_pair()
        return self._pair_payload()

    def _update_elo(self, win: str, lose: str, conf: float):
        rw, rl = self.rating[win], self.rating[lose]
        expected = 1.0 / (1.0 + 10 ** ((rl - rw) / 400.0))
        k = K_BASE * conf
        self.rating[win] = rw + k * (1 - expected)
        self.rating[lose] = rl - k * (1 - expected)

    def _update_taste(self, win: str, conf: float):
        for key, val in repo.get_place(win)["scores"].items():
            self.taste_num[key] = self.taste_num.get(key, 0.0) + float(val) * conf
        self.taste_den += conf

    def _slots(self) -> Dict[str, Dict[str, Any]]:
        if self.taste_den <= 0:
            return {}
        return {
            key: {
                "value": round(num / self.taste_den, 1),
                "confidence": 0.7,
                "evidence": "월드컵에서 고른 곳들의 공통 취향",
            }
            for key, num in self.taste_num.items()
        }

    def _finalize(self):
        self.finished = True
        order = sorted(self.ids, key=lambda p: -self.rating[p])
        slots = self._slots()
        axmap = repo.axis_map()
        winner = repo.get_place(order[0])
        top = recommender.score_place(winner, slots, axmap)
        matched = [c for c in top["contributions"] if c["gap"] <= 2.5][:4]
        tradeoff = [c for c in top["contributions"] if c["gap"] > 4.0][:2]

        ranking = [
            {
                "place_id": pid,
                "place_name": repo.get_place(pid)["place_name"],
                "fit_score": recommender.score_place(repo.get_place(pid), slots, axmap)["fit_score"],
                "rating": round(self.rating[pid], 1),
            }
            for pid in order
        ]
        self.result = {
            "place": winner,
            "fit_score": top["fit_score"],
            "matched_axes": matched,
            "tradeoff_axes": tradeoff,
            "contributions": top["contributions"],
            "ranking": ranking,
            "runner_ups": ranking[1:4],
            "slots": slots,
        }
        sb.log_recommendation(self.id, winner["place_id"], top["fit_score"],
                              slots, ranking[:5])


def get_session(sid: str) -> Optional[Match]:
    return _SESSIONS.get(sid)


def start_session() -> Match:
    m = Match()
    _SESSIONS[m.id] = m
    return m


if __name__ == "__main__":  # 스모크 자체검사: 항상 12라운드 뒤 1위+순위가 나온다
    repo.load(force=True)
    m = start_session()
    p = m.start()
    seen = 0
    while not p.get("finished"):
        a, b = p["pair"][0]["place_id"], p["pair"][1]["place_id"]
        p = m.choose(a, b, elapsed_ms=800)   # 항상 첫 카드를 빠르게 선택
        seen += 1
    assert m.result and m.round == TOTAL_ROUNDS, (m.round, seen)
    assert len(m.result["ranking"]) == len(m.ids)
    assert m.result["ranking"][0]["rating"] >= m.result["ranking"][-1]["rating"]
    print("ok:", m.result["place"]["place_name"], "| rounds:", m.round,
          "| top fit:", m.result["fit_score"])
