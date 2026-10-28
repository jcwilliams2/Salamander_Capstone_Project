-- Study support schema (Salamander capstone)

-- Anonymous participants have no username; give them a pseudonymous default
create or replace function public.handle_new_user()
 returns trigger language plpgsql security definer set search_path to 'public'
as $function$
begin
  insert into public.profiles (id, username)
  values (new.id, coalesce(new.raw_user_meta_data ->> 'username', 'participant-' || left(new.id::text, 8)));
  return new;
end;
$function$;

alter table profiles add column if not exists onboarding_genres text[];

create table if not exists study_consent (
    user_id uuid primary key references auth.users(id) on delete cascade,
    consent_version text not null,
    consented_at timestamptz not null default now()
);
alter table study_consent enable row level security;
drop policy if exists "participants record their own consent" on study_consent;
create policy "participants record their own consent"
    on study_consent for insert to authenticated
    with check (auth.uid() = user_id);

create table if not exists participant_assignments (
    user_id uuid primary key references auth.users(id) on delete cascade,
    arm text not null check (arm in ('A', 'B')),
    assigned_at timestamptz not null default now()
);
alter table participant_assignments enable row level security;

create table if not exists survey_responses (
    user_id uuid primary key references auth.users(id) on delete cascade,
    answers jsonb not null,
    attention_passed boolean not null,
    rated_count integer not null,
    session_seconds integer,
    submitted_at timestamptz not null default now()
);
alter table survey_responses enable row level security;

grant usage on schema public to anon, authenticated, service_role;
grant insert on table public.study_consent to authenticated;
grant all on table public.study_consent to service_role;
grant all on table public.participant_assignments to service_role;
grant all on table public.survey_responses to service_role;

create or replace view survey_scores as
select
    a.user_id, a.arm, s.attention_passed, s.rated_count, s.session_seconds,
    ((s.answers->>'r1')::int + (s.answers->>'r2')::int + (s.answers->>'r3')::int) / 3.0 as relevance,
    ((s.answers->>'n1')::int + (s.answers->>'n2')::int + (s.answers->>'n3')::int) / 3.0 as novelty,
    ((s.answers->>'d1')::int + (s.answers->>'d2')::int + (6 - (s.answers->>'d3')::int) + (s.answers->>'d4')::int) / 4.0 as diversity,
    ((s.answers->>'s1')::int + (s.answers->>'s2')::int + (s.answers->>'s3')::int) / 3.0 as satisfaction
from participant_assignments a
join survey_responses s using (user_id);