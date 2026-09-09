-- Hub Asset Manager — Supabase schema (v3: contacts/services, capitalised enums)
-- This DROPS and recreates everything — safe to run repeatedly during setup,
-- but it will erase any real data you've already entered. Run this whole
-- file in the Supabase SQL editor.

drop table if exists tasks cascade;
drop table if exists service_hubs cascade;
drop table if exists services cascade;
drop table if exists assets cascade;
drop table if exists hubs cascade;

create extension if not exists "pgcrypto";

-- ---------------------------------------------------------------------------
-- HUBS — identity is plain text (initials), not colour. Colour is reserved
-- entirely for urgency, so the two systems can never collide.
-- ---------------------------------------------------------------------------
create table hubs (
  id uuid primary key default gen_random_uuid(),
  name text not null unique,
  initials text not null,
  address text,
  created_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- ASSETS
-- ---------------------------------------------------------------------------
create table assets (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  type text not null default 'other' check (type in ('vehicle','building','fixture','safety_equipment','furniture','appliance','equipment','other')),
  hub_id uuid references hubs(id) on delete set null,
  identifier text,
  details text,
  status text not null default 'Active' check (status in ('Active','Archived')),
  created_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- SERVICES — reusable repair/maintenance contacts (plumber, electrician, etc.)
-- ---------------------------------------------------------------------------
create table services (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  category text,
  phone text,
  email text,
  website text,
  notes text,
  created_at timestamptz not null default now()
);

-- A service can be assigned to one or several hubs
create table service_hubs (
  service_id uuid references services(id) on delete cascade,
  hub_id uuid references hubs(id) on delete cascade,
  primary key (service_id, hub_id)
);

-- ---------------------------------------------------------------------------
-- TASKS
-- A task's contact is EITHER a saved service (service_id) OR a one-off
-- contact entered just for this task (the custom_* columns), never both.
-- ---------------------------------------------------------------------------
create table tasks (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  asset_id uuid references assets(id) on delete cascade,
  hub_id uuid references hubs(id) on delete set null,
  task_type text not null default 'other' check (task_type in ('compliance_check','service','inspection','drill','repair','other')),
  due_date date,
  status text not null default 'Scheduled' check (status in ('Scheduled','Done')),
  priority text not null default 'Routine' check (priority in ('Routine','Urgent')),
  completed_date date,
  notes text,
  service_id uuid references services(id) on delete set null,
  custom_contact_name text,
  custom_contact_phone text,
  custom_contact_email text,
  custom_contact_website text,
  created_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- ROW LEVEL SECURITY — no login, anon key gets full access, delete included.
-- ---------------------------------------------------------------------------
alter table hubs enable row level security;
alter table assets enable row level security;
alter table services enable row level security;
alter table service_hubs enable row level security;
alter table tasks enable row level security;

create policy "hubs_all_anon" on hubs for all to anon using (true) with check (true);
create policy "assets_all_anon" on assets for all to anon using (true) with check (true);
create policy "services_all_anon" on services for all to anon using (true) with check (true);
create policy "service_hubs_all_anon" on service_hubs for all to anon using (true) with check (true);
create policy "tasks_all_anon" on tasks for all to anon using (true) with check (true);

-- ---------------------------------------------------------------------------
-- SEED DATA
-- ---------------------------------------------------------------------------
insert into hubs (name, initials, address) values
  ('Richard Evans House', 'RE', '52 Riddiford Street, Newtown, Wellington 6021'),
  ('Margaret Stewart House', 'MS', '16 Hospital Road, Newtown, Wellington 6021'),
  ('Lower Hutt', 'LH', 'Level 2 / 20 Pretoria Street, Lower Hutt, 5010'),
  ('Porirua', 'PO', 'Level 4, Suite 403 North City Plaza, 2 Titahi Bay Road, Porirua 502'),
  ('Kāpiti', 'KP', '27 Kāpiti Road, Paraparaumu, 5032');
