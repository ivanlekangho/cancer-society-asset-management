# Hub Asset Manager

A simple asset, task, and contact tracker for the Cancer Society's hubs. No login, no email, no server to run — just a Streamlit app talking to a free Supabase database.

## How it works
- Pick your hub from the dropdown at the top — no password. "All hubs" shows everything.
- **Assets** — shown as compact cards grouped by type (Vehicle/Building/Fixture/Safety equipment/Furniture/Appliance/Equipment/Other). Each card shows a quick summary (worst urgency + task counts by priority). Click **View** to open the full asset — its details, its task list, and **Edit** / **Add task** buttons.
- **Tasks** — grouped by urgency. Tick the checkbox to mark done/not done directly; click **Edit** to open the full editor.
- **Calendar** — a month grid of due dates; click a day to see and act on everything due that day. Navigate months with the arrows, or jump back with **Today**.
- **Contacts** — your repair people (plumber, electrician, etc.), each assignable to one or more hubs.
- Adding or editing anything opens as a popup with Cancel and Save — nothing saves until you click Save, and Cancel discards changes. The popup just closes on save, with no extra confirmation message.
- Each open task shows a relative due phrase ("Due in 3 days", "Overdue by 2 days") rather than a repeated static label.
- Dates display as dd/mm/yyyy throughout.
- Archive an asset with the one-click **Archive** button on its popup (next to Edit/Add task/Close) — no need to go into Edit to find it.

## A Streamlit limitation worth knowing
Streamlit only supports one popup open at a time — there's no true "popup on top of a popup." Clicking Edit or Add task from within an asset's popup swaps that popup's content rather than opening a second layer on top. It reads as forward navigation rather than stacked windows; Cancel always returns you to the main page rather than back one step, to keep the logic simple and predictable.

## Setup

### 1. Create or reset your Supabase project
Run all of `schema.sql` in the SQL Editor. It starts with `drop table if exists ... cascade` — safe to re-run, but it erases existing data in those tables first.

### 2. Get your API keys
**Settings > API** — copy the **Project URL** and the **Publishable key**.

### 3. Deploy to Streamlit Community Cloud
Push this whole folder (including `logo.png` and `.streamlit/config.toml`) to GitHub, connect it at [share.streamlit.io](https://share.streamlit.io), point at `app.py`, and add your secrets:
```
SUPABASE_URL = "https://xxxx.supabase.co"
SUPABASE_ANON_KEY = "sb_publishable_..."
```

### 4. Share the link

## Important trade-off: there's no login
Anyone with the link can view, edit, or delete anything. Deletes require a confirmation click but there's no undo after that. Don't post the link anywhere public.

## Keeping it alive
Supabase free projects pause after about a week of inactivity, and wake up automatically on the next visit with a short delay.

## If you've already got real data in Supabase
`schema.sql` drops and recreates everything, which is fine while testing but will erase real data. If you've moved past testing and want to add the new asset categories without losing anything, run this instead:
```sql
alter table assets drop constraint assets_type_check;
alter table assets add constraint assets_type_check
  check (type in ('vehicle','building','fixture','safety_equipment','furniture','appliance','equipment','other'));
```

## Testing
This app has an automated test suite (built with Streamlit's own `AppTest` framework and a mock Supabase backend) that exercises the full click-through flow — adding/editing/deleting assets, tasks, and contacts, the calendar, cascades, and archive/restore — without needing a real database. It isn't included in this delivery bundle, but ask if you'd like it as a standalone tool to re-run after future changes.

