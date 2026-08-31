# 여행지 이미지

`pohang_001.jpg` ~ `pohang_020.jpg` 이름으로 각 여행지 사진을 넣어 주세요.
(place_id 를 소문자로 바꾼 이름 = data/places.json 의 image_path)

넣은 뒤:
    python3 supabase/seed.py --images
로 Supabase Storage `place-images` 버킷에 업로드됩니다.
