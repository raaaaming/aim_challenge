-- ============================================================================
--  포항항(Pohang-Hang) — Supabase 스키마
--  Supabase 대시보드 > SQL Editor 에 그대로 붙여넣고 실행하세요.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 1. 여행지 마스터 + 취향 점수 (여행지_20_포항.csv 20행)
--    평가 기준.txt 의 취향 지표 10개를 score_* 컬럼으로, 산정 근거를 reason_* 로 보관
-- ---------------------------------------------------------------------------
create table if not exists public.places (
    place_id            text primary key,
    place_name          text not null,
    slug                text not null unique,

    -- CSV 원문 (최종 결과 화면의 설명은 오직 이 필드들만으로 재생성한다)
    summary             text not null,
    embedding_text      text not null,
    evidence_text_1     text,
    evidence_text_2     text,
    evidence_text_3     text,
    evidence_text_4     text,
    evidence_text_5     text,

    -- Supabase Storage 내 이미지 경로 (bucket: place-images)
    image_path          text,

    -- 취향 점수 0.0 ~ 10.0
    score_transit       numeric(3,1) not null check (score_transit       between 0 and 10),
    score_participation numeric(3,1) not null check (score_participation between 0 and 10),
    score_nature_food   numeric(3,1) not null check (score_nature_food   between 0 and 10),
    score_companion     numeric(3,1) not null check (score_companion     between 0 and 10),
    score_barrier_free  numeric(3,1) not null check (score_barrier_free  between 0 and 10),
    score_liveliness    numeric(3,1) not null check (score_liveliness    between 0 and 10),
    score_depth         numeric(3,1) not null check (score_depth         between 0 and 10),
    score_indoor        numeric(3,1) not null check (score_indoor        between 0 and 10),
    score_budget        numeric(3,1) not null check (score_budget        between 0 and 10),
    score_duration      numeric(3,1) not null check (score_duration      between 0 and 10),

    -- 각 점수의 산정 근거
    reason_transit       text,
    reason_participation text,
    reason_nature_food   text,
    reason_companion     text,
    reason_barrier_free  text,
    reason_liveliness    text,
    reason_depth         text,
    reason_indoor        text,
    reason_budget        text,
    reason_duration      text,

    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

comment on table public.places is '포항 여행지 20곳 + 취향 지표 10축 점수(0.0~10.0)';

-- ---------------------------------------------------------------------------
-- 2. 평가 축 메타 (프론트 레이더 차트 라벨 / 챗봇 질문 순서에 사용)
-- ---------------------------------------------------------------------------
create table if not exists public.preference_axes (
    key         text primary key,
    label       text not null,
    priority    text not null check (priority in ('P0', 'P1')),
    low_label   text not null,   -- 0.0 쪽 의미
    high_label  text not null,   -- 10.0 쪽 의미
    question    text not null,   -- 챗봇 기본 질문
    sort_order  int  not null
);

-- ---------------------------------------------------------------------------
-- 3. 대화 세션 (챗봇이 채워 나가는 취향 슬롯)
-- ---------------------------------------------------------------------------
create table if not exists public.chat_sessions (
    id          uuid primary key default gen_random_uuid(),
    slots       jsonb not null default '{}'::jsonb,  -- {axis: {value, confidence, evidence}}
    messages    jsonb not null default '[]'::jsonb,
    finished    boolean not null default false,
    result_place_id text references public.places(place_id),
    created_at  timestamptz not null default now(),
    updated_at  timestamptz not null default now()
);

create index if not exists chat_sessions_created_at_idx on public.chat_sessions (created_at desc);

-- ---------------------------------------------------------------------------
-- 4. 추천 로그 (어떤 취향에 무엇을 추천했는지 기록)
-- ---------------------------------------------------------------------------
create table if not exists public.recommendations (
    id          bigserial primary key,
    session_id  uuid references public.chat_sessions(id) on delete cascade,
    place_id    text not null references public.places(place_id),
    fit_score   numeric(5,2) not null,
    user_vector jsonb not null,
    ranking     jsonb not null,
    created_at  timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- 5. RLS — 익명 키로 읽기만 허용, 쓰기는 서버(service_role)만
-- ---------------------------------------------------------------------------
alter table public.places          enable row level security;
alter table public.preference_axes enable row level security;
alter table public.chat_sessions   enable row level security;
alter table public.recommendations enable row level security;

drop policy if exists "places are public" on public.places;
create policy "places are public"
    on public.places for select using (true);

drop policy if exists "axes are public" on public.preference_axes;
create policy "axes are public"
    on public.preference_axes for select using (true);

-- chat_sessions / recommendations 는 정책을 만들지 않아 service_role 만 접근 가능

-- ---------------------------------------------------------------------------
-- 6. Storage 버킷 — 여행지 이미지
-- ---------------------------------------------------------------------------
insert into storage.buckets (id, name, public)
values ('place-images', 'place-images', true)
on conflict (id) do update set public = true;

drop policy if exists "place images are public" on storage.objects;
create policy "place images are public"
    on storage.objects for select
    using (bucket_id = 'place-images');
