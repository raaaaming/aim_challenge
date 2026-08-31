# -*- coding: utf-8 -*-
"""
Supabase 시딩 스크립트.

  1) supabase/schema.sql 을 대시보드 SQL Editor 에서 먼저 실행
  2) backend/.env 에 SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY 설정
  3) python3 supabase/seed.py            → places / preference_axes 적재
     python3 supabase/seed.py --images   → assets/images/*.jpg 도 Storage 업로드

실행:  프로젝트 루트에서
"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app import supabase as sb            # noqa: E402
from app.config import settings           # noqa: E402


def load_axes():
    data = json.loads((ROOT / "data" / "places.json").read_text(encoding="utf-8"))
    return [
        {
            "key": a["key"],
            "label": a["label"],
            "priority": a["priority"],
            "low_label": a["low"],
            "high_label": a["high"],
            "question": a["question"],
            "sort_order": i,
        }
        for i, a in enumerate(data["axes"])
    ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", action="store_true", help="assets/images 도 Storage 에 업로드")
    args = ap.parse_args()

    if not sb.available():
        print("✖ Supabase 에 연결할 수 없습니다. backend/.env 의 SUPABASE_URL / "
              "SUPABASE_SERVICE_ROLE_KEY 를 확인하세요.")
        print("  현재 상태:", sb.status())
        sys.exit(1)

    axes = load_axes()
    sb.seed_axes(axes)
    print(f"✔ preference_axes {len(axes)}행 적재")

    records = json.loads((ROOT / "supabase" / "seed_data.json").read_text(encoding="utf-8"))
    sb.seed_places(records)
    print(f"✔ places {len(records)}행 적재 (점수 {len(records) * 10}개 포함)")

    if args.images:
        img_dir = ROOT / "assets" / "images"
        if not img_dir.exists():
            print(f"✖ 이미지 폴더가 없습니다: {img_dir}")
            print("  각 여행지 이미지를 pohang_001.jpg ~ pohang_020.jpg 이름으로 넣어 주세요.")
            sys.exit(1)
        n = 0
        for rec in records:
            p = img_dir / rec["image_path"]
            if not p.exists():
                print(f"  · 건너뜀 (파일 없음): {rec['image_path']}")
                continue
            ct = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
            if sb.upload_image(rec["image_path"], p.read_bytes(), ct):
                n += 1
                print(f"  · 업로드 {rec['image_path']}  ({rec['place_name']})")
        print(f"✔ Storage '{settings.SUPABASE_BUCKET}' 에 이미지 {n}개 업로드")

    print("\n완료. 백엔드를 재시작하면 데이터 소스가 supabase 로 바뀝니다.")


if __name__ == "__main__":
    main()
