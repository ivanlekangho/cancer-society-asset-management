"""
Hub Asset Manager — Streamlit app, no login required.
Deploy on Streamlit Community Cloud (free). Talks directly to Supabase.

Required secret (Settings > Secrets on Streamlit Cloud, or .streamlit/secrets.toml locally):
    SUPABASE_URL = "https://xxxx.supabase.co"
    SUPABASE_ANON_KEY = "sb_publishable_..."
"""

import streamlit as st
from supabase import create_client
from datetime import date, timedelta
import calendar as cal_module
import os

st.set_page_config(page_title="Hub Asset Manager", page_icon="🎗️", layout="wide")

TYPE_LABELS = {
    "vehicle": "Vehicle", "building": "Building", "fixture": "Fixture",
    "safety_equipment": "Safety equipment", "furniture": "Furniture",
    "appliance": "Appliance", "equipment": "Equipment", "other": "Other",
}
TASK_TYPE_LABELS = {
    "compliance_check": "Compliance check", "service": "Servicing",
    "inspection": "Inspection", "drill": "Drill", "repair": "Repair", "other": "Other",
}
FLAG_COLOR = {"Overdue": "red", "Due soon": "orange", "On track": "green", "Done": "gray", "No date": "gray"}
FLAG_ORDER = {"Overdue": 0, "Due soon": 1, "On track": 2, "Done": 3, "No date": 4}


@st.cache_resource
def get_client():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_ANON_KEY"])


supabase = get_client()


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------
def fmt_date(iso):
    return date.fromisoformat(iso).strftime("%d/%m/%Y") if iso else "—"


def flag_word(due_date, status):
    if status == "Done":
        return "Done"
    if not due_date:
        return "No date"
    today = date.today().isoformat()
    week_out = (date.today() + timedelta(days=7)).isoformat()
    if due_date < today:
        return "Overdue"
    if due_date <= week_out:
        return "Due soon"
    return "On track"


def colored(word):
    return f":{FLAG_COLOR.get(word, 'gray')}[{word}]"


def urgent_tag(priority):
    return " · :red[Urgent]" if priority == "Urgent" else ""


def due_phrase(due_date, status):
    """Granular relative wording for an individual task line, e.g. 'Due in 3 days'."""
    if status == "Done":
        return "Done", "gray"
    if not due_date:
        return "No date", "gray"
    delta = (date.fromisoformat(due_date) - date.today()).days
    if delta < 0:
        n = -delta
        return f"Overdue by {n} day{'s' if n != 1 else ''}", "red"
    if delta == 0:
        return "Due today", "orange"
    if delta <= 7:
        return f"Due in {delta} day{'s' if delta != 1 else ''}", "orange"
    if delta <= 60:
        weeks = max(1, round(delta / 7))
        return f"Due in {weeks} week{'s' if weeks != 1 else ''}", "green"
    months = max(1, round(delta / 30))
    return f"Due in {months} month{'s' if months != 1 else ''}", "green"


def contact_text(t, services_by_id):
    if t.get("service_id") and services_by_id.get(t["service_id"]):
        s = services_by_id[t["service_id"]]
        bits = [s["name"]] + ([s["phone"]] if s.get("phone") else [])
        return "Contact: " + " · ".join(bits)
    if t.get("custom_contact_name"):
        bits = [t["custom_contact_name"]] + ([t["custom_contact_phone"]] if t.get("custom_contact_phone") else [])
        return "Contact: " + " · ".join(bits)
    return None


def task_line_text(t, services_by_id):
    phrase, color = due_phrase(t["due_date"], t["status"])
    parts = [f":{color}[{phrase}]", f"**{t['title']}**"]
    if t["due_date"]:
        parts.append(fmt_date(t["due_date"]))
    if t["priority"] == "Urgent":
        parts.append(":red[Urgent]")
    if t.get("notes"):
        parts.append(f"Notes: {t['notes']}")
    c = contact_text(t, services_by_id)
    if c:
        parts.append(c)
    return " · ".join(parts)


def clear_and_rerun():
    st.cache_data.clear()
    st.rerun()


def close_dialog():
    st.session_state.dialog = None


def open_dialog(d):
    st.session_state.dialog = d


# ---------------------------------------------------------------------------
# DATA LOADERS
# ---------------------------------------------------------------------------
@st.cache_data(ttl=30)
def load_hubs():
    return supabase.table("hubs").select("*").order("name").execute().data


@st.cache_data(ttl=15)
def load_assets(hub_id):
    q = supabase.table("assets").select("*").order("name")
    if hub_id:
        q = q.eq("hub_id", hub_id)
    return q.execute().data


@st.cache_data(ttl=15)
def load_tasks(hub_id):
    q = supabase.table("tasks").select("*").order("due_date")
    if hub_id:
        q = q.eq("hub_id", hub_id)
    return q.execute().data


@st.cache_data(ttl=15)
def load_services(hub_id):
    if hub_id:
        rows = supabase.table("service_hubs").select("services(*)").eq("hub_id", hub_id).execute().data
        return [r["services"] for r in rows if r.get("services")]
    return supabase.table("services").select("*").order("name").execute().data


@st.cache_data(ttl=15)
def load_service_hub_map():
    rows = supabase.table("service_hubs").select("*").execute().data
    m = {}
    for r in rows:
        m.setdefault(r["service_id"], []).append(r["hub_id"])
    return m


@st.cache_data(ttl=15)
def load_open_task_counts():
    tasks = supabase.table("tasks").select("hub_id,due_date,status").neq("status", "Done").execute().data
    counts = {}
    for t in tasks:
        word = flag_word(t["due_date"], t["status"])
        d = counts.setdefault(t["hub_id"], {})
        d[word] = d.get(word, 0) + 1
    return counts


def get_asset(asset_id):
    r = supabase.table("assets").select("*").eq("id", asset_id).execute().data
    return r[0] if r else None


def get_task(task_id):
    r = supabase.table("tasks").select("*").eq("id", task_id).execute().data
    return r[0] if r else None


def get_service(service_id):
    r = supabase.table("services").select("*").eq("id", service_id).execute().data
    return r[0] if r else None


def asset_summary_line(asset_tasks):
    open_t = [t for t in asset_tasks if t["status"] != "Done"]
    if not open_t:
        return "No open tasks"
    words = [flag_word(t["due_date"], t["status"]) for t in open_t]
    worst = min(words, key=lambda w: FLAG_ORDER[w])
    urgent_n = sum(1 for t in open_t if t["priority"] == "Urgent")
    routine_n = len(open_t) - urgent_n
    bits = [b for b in [f"{urgent_n} Urgent" if urgent_n else "", f"{routine_n} Routine" if routine_n else ""] if b]
    return f"{colored(worst)}" + (" · " + ", ".join(bits) if bits else "")


# ---------------------------------------------------------------------------
# SHARED WIDGET: contact/service picker — lives outside any st.form
# ---------------------------------------------------------------------------
def contact_picker(key_prefix, hub_id, current_service_id=None, current_custom_name=None):
    services = load_services(hub_id) if hub_id else load_services(None)
    NONE, NEW = "__none__", "__new__"
    options = [NONE] + [s["id"] for s in services] + [NEW]

    def label(sid):
        if sid == NONE:
            return "No contact"
        if sid == NEW:
            return "+ Add a new contact"
        s = next((x for x in services if x["id"] == sid), None)
        if not s:
            return "—"
        return f"{s['name']} ({s['category']})" if s.get("category") else s["name"]

    default_value = current_service_id if current_service_id in [s["id"] for s in services] else NONE
    choice = st.selectbox("Contact / service", options, format_func=label,
                           index=options.index(default_value), key=f"{key_prefix}_choice")

    result = {"mode": "none"}
    if choice == NEW:
        name = st.text_input("Name", key=f"{key_prefix}_new_name")
        category = st.text_input("Category (e.g. Plumber, Electrician)", key=f"{key_prefix}_new_category")
        phone = st.text_input("Phone", key=f"{key_prefix}_new_phone")
        email = st.text_input("Email", key=f"{key_prefix}_new_email")
        website = st.text_input("Website", key=f"{key_prefix}_new_website")
        notes = st.text_area("Contact notes", key=f"{key_prefix}_new_notes")
        save_reusable = st.checkbox("Save as a reusable contact for this hub", value=False, key=f"{key_prefix}_new_save")
        result = {
            "mode": "new", "name": name, "category": category, "phone": phone,
            "email": email, "website": website, "notes": notes,
            "save_reusable": save_reusable, "hub_id": hub_id,
        }
    elif choice != NONE:
        result = {"mode": "existing", "service_id": choice}
    elif current_custom_name:
        st.caption(f"Currently: {current_custom_name} (one-off, not saved as reusable)")

    return result


def resolve_contact(picked):
    if picked["mode"] == "existing":
        return {"service_id": picked["service_id"], "custom_contact_name": None,
                "custom_contact_phone": None, "custom_contact_email": None, "custom_contact_website": None}
    if picked["mode"] == "new" and picked.get("name"):
        if picked["save_reusable"]:
            new_service = supabase.table("services").insert({
                "name": picked["name"], "category": picked["category"] or None,
                "phone": picked["phone"] or None, "email": picked["email"] or None,
                "website": picked["website"] or None, "notes": picked["notes"] or None,
            }).execute().data[0]
            if picked.get("hub_id"):
                supabase.table("service_hubs").insert({"service_id": new_service["id"], "hub_id": picked["hub_id"]}).execute()
            return {"service_id": new_service["id"], "custom_contact_name": None,
                    "custom_contact_phone": None, "custom_contact_email": None, "custom_contact_website": None}
        return {"service_id": None, "custom_contact_name": picked["name"],
                "custom_contact_phone": picked["phone"] or None, "custom_contact_email": picked["email"] or None,
                "custom_contact_website": picked["website"] or None}
    return {"service_id": None, "custom_contact_name": None, "custom_contact_phone": None,
            "custom_contact_email": None, "custom_contact_website": None}


def render_task_row(t, services_by_id, key_prefix):
    c1, c2, c3 = st.columns([0.6, 8.4, 1], vertical_alignment="center")
    with c1:
        checked = st.checkbox("Done", value=(t["status"] == "Done"), key=f"{key_prefix}_chk_{t['id']}", label_visibility="collapsed")
    with c2:
        st.markdown(task_line_text(t, services_by_id))
    with c3:
        if st.button("Edit", key=f"{key_prefix}_edit_{t['id']}"):
            open_dialog({"type": "task", "id": t["id"], "mode": "edit"})
            st.rerun()
    if checked != (t["status"] == "Done"):
        supabase.table("tasks").update({
            "status": "Done" if checked else "Scheduled",
            "completed_date": date.today().isoformat() if checked else None,
        }).eq("id", t["id"]).execute()
        clear_and_rerun()


# ---------------------------------------------------------------------------
# DIALOG CONTENT RENDERERS
# ---------------------------------------------------------------------------
def dlg_asset_view(asset_id):
    asset = get_asset(asset_id)
    if not asset:
        st.error("This asset no longer exists.")
        if st.button("Close"):
            close_dialog(); st.rerun()
        return

    st.subheader(asset["name"])
    c1, c2, c3, c4 = st.columns(4)
    if c1.button("Edit", use_container_width=True):
        open_dialog({"type": "asset", "id": asset_id, "mode": "edit"}); st.rerun()
    if c2.button("Add task", use_container_width=True):
        open_dialog({"type": "add_task", "asset_id": asset_id, "hub_id": asset["hub_id"]}); st.rerun()
    archive_label = "Restore" if asset["status"] == "Archived" else "Archive"
    if c3.button(archive_label, use_container_width=True):
        new_status = "Active" if asset["status"] == "Archived" else "Archived"
        supabase.table("assets").update({"status": new_status}).eq("id", asset_id).execute()
        clear_and_rerun()
    if c4.button("Close", use_container_width=True):
        close_dialog(); st.rerun()

    info_bits = [b for b in [asset.get("identifier"), asset.get("details")] if b]
    if info_bits:
        st.write(" · ".join(info_bits))
    if asset["status"] != "Active":
        st.caption(asset["status"])

    st.divider()
    st.write("**Tasks**")
    services_by_id = {s["id"]: s for s in load_services(None)}
    asset_tasks = supabase.table("tasks").select("*").eq("asset_id", asset_id).order("due_date").execute().data
    if not asset_tasks:
        st.caption("None yet.")
    for t in asset_tasks:
        render_task_row(t, services_by_id, key_prefix="dlgasset")


def dlg_asset_edit(asset_id):
    asset = get_asset(asset_id)
    if not asset:
        st.error("This asset no longer exists.")
        if st.button("Close"):
            close_dialog(); st.rerun()
        return

    st.subheader(f"Edit {asset['name']}")
    with st.form("edit_asset_form"):
        new_name = st.text_input("Item name", value=asset["name"])
        type_keys = list(TYPE_LABELS.keys())
        new_type = st.selectbox("Type", type_keys, format_func=lambda k: TYPE_LABELS[k], index=type_keys.index(asset["type"]))
        new_identifier = st.text_input("Identifier (rego / address / serial)", value=asset.get("identifier") or "")
        new_details = st.text_area("Details", value=asset.get("details") or "")
        new_status = st.selectbox("Status", ["Active", "Archived"], index=["Active", "Archived"].index(asset["status"]))
        c1, c2 = st.columns(2)
        cancel = c1.form_submit_button("Cancel", use_container_width=True)
        save = c2.form_submit_button("Save", use_container_width=True)

    if save:
        supabase.table("assets").update({
            "name": new_name, "type": new_type, "identifier": new_identifier,
            "details": new_details, "status": new_status,
        }).eq("id", asset_id).execute()
        st.session_state.pop(f"confirm_del_asset_{asset_id}", None)
        close_dialog(); clear_and_rerun()
    if cancel:
        st.session_state.pop(f"confirm_del_asset_{asset_id}", None)
        close_dialog(); st.rerun()

    st.divider()
    dkey = f"confirm_del_asset_{asset_id}"
    if st.session_state.get(dkey):
        st.warning("Delete this asset and all its tasks? This can't be undone.")
        d1, d2 = st.columns(2)
        if d1.button("Keep asset", use_container_width=True, key="cancel_del_asset"):
            st.session_state.pop(dkey, None); st.rerun()
        if d2.button("Yes, delete", use_container_width=True):
            supabase.table("assets").delete().eq("id", asset_id).execute()
            st.session_state.pop(dkey, None)
            close_dialog(); clear_and_rerun()
    else:
        if st.button("Delete asset"):
            st.session_state[dkey] = True; st.rerun()


def dlg_add_task(asset_id, hub_id):
    asset = get_asset(asset_id)
    st.subheader(f"Add task — {asset['name'] if asset else ''}")
    picked = contact_picker("newtask", hub_id)
    with st.form("add_task_form", clear_on_submit=True):
        title = st.text_input("Task name")
        type_keys = list(TASK_TYPE_LABELS.keys())
        ttype = st.selectbox("Type", type_keys, format_func=lambda k: TASK_TYPE_LABELS[k])
        due = st.date_input("Due date", format="DD/MM/YYYY")
        priority = st.selectbox("Priority", ["Routine", "Urgent"])
        notes = st.text_area("Notes")
        c1, c2 = st.columns(2)
        cancel = c1.form_submit_button("Cancel", use_container_width=True)
        save = c2.form_submit_button("Add task", use_container_width=True)

    if save and title:
        contact_fields = resolve_contact(picked)
        supabase.table("tasks").insert({
            "title": title, "asset_id": asset_id, "hub_id": hub_id,
            "task_type": ttype, "due_date": due.isoformat(),
            "priority": priority, "status": "Scheduled", "notes": notes,
            **contact_fields,
        }).execute()
        close_dialog(); clear_and_rerun()
    if cancel:
        close_dialog(); st.rerun()


def dlg_add_asset(hubs, default_hub_id):
    st.subheader("Add a new asset")
    with st.form("add_asset_form", clear_on_submit=True):
        name = st.text_input("Item name")
        type_keys = list(TYPE_LABELS.keys())
        type_ = st.selectbox("Type", type_keys, format_func=lambda k: TYPE_LABELS[k])
        identifier = st.text_input("Identifier (rego / address / serial)")
        details = st.text_area("Details")
        hub_names = [h["name"] for h in hubs]
        default_idx = next((i for i, h in enumerate(hubs) if h["id"] == default_hub_id), 0) if default_hub_id else 0
        hub_choice = st.selectbox("Hub", hub_names, index=default_idx)
        c1, c2 = st.columns(2)
        cancel = c1.form_submit_button("Cancel", use_container_width=True)
        save = c2.form_submit_button("Add asset", use_container_width=True)

    if save and name:
        asset_hub_id = next(h["id"] for h in hubs if h["name"] == hub_choice)
        supabase.table("assets").insert({
            "name": name, "type": type_, "hub_id": asset_hub_id,
            "identifier": identifier, "details": details,
        }).execute()
        close_dialog(); clear_and_rerun()
    if cancel:
        close_dialog(); st.rerun()


def dlg_task_edit(task_id):
    t = get_task(task_id)
    if not t:
        st.error("This task no longer exists.")
        if st.button("Close"):
            close_dialog(); st.rerun()
        return

    st.subheader(f"Edit — {t['title']}")
    all_assets = load_assets(None)
    hubs_by_id = {h["id"]: h for h in load_hubs()}
    picked = contact_picker("edittask", t["hub_id"], current_service_id=t.get("service_id"),
                             current_custom_name=t.get("custom_contact_name"))

    def asset_label(aid):
        a = next((x for x in all_assets if x["id"] == aid), None)
        if not a:
            return "—"
        hub_name = hubs_by_id.get(a["hub_id"], {}).get("name", "")
        ident = f" ({a['identifier']})" if a.get("identifier") else ""
        return f"{a['name']}{ident} — {hub_name}" if hub_name else f"{a['name']}{ident}"

    with st.form("edit_task_form"):
        new_title = st.text_input("Task name", value=t["title"])
        asset_ids = [a["id"] for a in all_assets] or [None]
        current_index = asset_ids.index(t["asset_id"]) if t["asset_id"] in asset_ids else 0
        chosen_asset_id = st.selectbox("Asset", asset_ids, format_func=asset_label, index=current_index)
        type_keys = list(TASK_TYPE_LABELS.keys())
        new_type = st.selectbox("Type", type_keys, format_func=lambda k: TASK_TYPE_LABELS[k], index=type_keys.index(t["task_type"]))
        new_due = st.date_input("Due date", value=date.fromisoformat(t["due_date"]) if t["due_date"] else None, format="DD/MM/YYYY")
        new_priority = st.selectbox("Priority", ["Routine", "Urgent"], index=["Routine", "Urgent"].index(t["priority"]))
        new_status = st.selectbox("Status", ["Scheduled", "Done"], index=["Scheduled", "Done"].index(t["status"]))
        new_notes = st.text_area("Notes", value=t.get("notes") or "")
        c1, c2 = st.columns(2)
        cancel = c1.form_submit_button("Cancel", use_container_width=True)
        save = c2.form_submit_button("Save", use_container_width=True)

    if save:
        chosen = next((a for a in all_assets if a["id"] == chosen_asset_id), None)
        contact_fields = resolve_contact(picked)
        updates = {
            "title": new_title,
            "asset_id": chosen["id"] if chosen else t["asset_id"],
            "hub_id": chosen["hub_id"] if chosen else t["hub_id"],
            "task_type": new_type,
            "due_date": new_due.isoformat() if new_due else None,
            "priority": new_priority,
            "status": new_status,
            "completed_date": date.today().isoformat() if new_status == "Done" and t["status"] != "Done" else (None if new_status == "Scheduled" else t.get("completed_date")),
            "notes": new_notes,
            **contact_fields,
        }
        supabase.table("tasks").update(updates).eq("id", task_id).execute()
        st.session_state.pop(f"confirm_del_task_{task_id}", None)
        close_dialog(); clear_and_rerun()
    if cancel:
        st.session_state.pop(f"confirm_del_task_{task_id}", None)
        close_dialog(); st.rerun()

    st.divider()
    dkey = f"confirm_del_task_{task_id}"
    if st.session_state.get(dkey):
        st.warning("Delete this task? This can't be undone.")
        d1, d2 = st.columns(2)
        if d1.button("Keep task", use_container_width=True, key="cancel_del_task"):
            st.session_state.pop(dkey, None); st.rerun()
        if d2.button("Yes, delete", use_container_width=True):
            supabase.table("tasks").delete().eq("id", task_id).execute()
            st.session_state.pop(dkey, None)
            close_dialog(); clear_and_rerun()
    else:
        if st.button("Delete task"):
            st.session_state[dkey] = True; st.rerun()


def dlg_service_edit(service_id, hubs, hub_map):
    s = get_service(service_id)
    if not s:
        st.error("This contact no longer exists.")
        if st.button("Close"):
            close_dialog(); st.rerun()
        return
    st.subheader(f"Edit — {s['name']}")
    with st.form("edit_service_form"):
        new_name = st.text_input("Name", value=s["name"])
        new_category = st.text_input("Category", value=s.get("category") or "")
        new_phone = st.text_input("Phone", value=s.get("phone") or "")
        new_email = st.text_input("Email", value=s.get("email") or "")
        new_website = st.text_input("Website", value=s.get("website") or "")
        new_notes = st.text_area("Notes", value=s.get("notes") or "")
        all_hub_names = [h["name"] for h in hubs]
        current_hub_names = [h["name"] for h in hubs if h["id"] in hub_map.get(service_id, [])]
        new_hub_names = st.multiselect("Assigned hubs", all_hub_names, default=current_hub_names)
        c1, c2 = st.columns(2)
        cancel = c1.form_submit_button("Cancel", use_container_width=True)
        save = c2.form_submit_button("Save", use_container_width=True)

    if save:
        supabase.table("services").update({
            "name": new_name, "category": new_category or None, "phone": new_phone or None,
            "email": new_email or None, "website": new_website or None, "notes": new_notes or None,
        }).eq("id", service_id).execute()
        supabase.table("service_hubs").delete().eq("service_id", service_id).execute()
        new_hub_ids = [h["id"] for h in hubs if h["name"] in new_hub_names]
        if new_hub_ids:
            supabase.table("service_hubs").insert([{"service_id": service_id, "hub_id": hid} for hid in new_hub_ids]).execute()
        st.session_state.pop(f"confirm_del_service_{service_id}", None)
        close_dialog(); clear_and_rerun()
    if cancel:
        st.session_state.pop(f"confirm_del_service_{service_id}", None)
        close_dialog(); st.rerun()

    st.divider()
    dkey = f"confirm_del_service_{service_id}"
    if st.session_state.get(dkey):
        st.warning("Delete this contact? Tasks using it will show no contact. This can't be undone.")
        d1, d2 = st.columns(2)
        if d1.button("Keep contact", use_container_width=True, key="cancel_del_service"):
            st.session_state.pop(dkey, None); st.rerun()
        if d2.button("Yes, delete", use_container_width=True):
            supabase.table("services").delete().eq("id", service_id).execute()
            st.session_state.pop(dkey, None)
            close_dialog(); clear_and_rerun()
    else:
        if st.button("Delete contact"):
            st.session_state[dkey] = True; st.rerun()


def dlg_add_service(hubs, default_hub_id):
    st.subheader("Add a new contact")
    with st.form("add_service_form", clear_on_submit=True):
        name = st.text_input("Name")
        category = st.text_input("Category (e.g. Plumber, Electrician)")
        phone = st.text_input("Phone")
        email = st.text_input("Email")
        website = st.text_input("Website")
        notes = st.text_area("Notes")
        default_names = [h["name"] for h in hubs if h["id"] == default_hub_id]
        hub_names = st.multiselect("Assigned hubs", [h["name"] for h in hubs], default=default_names)
        c1, c2 = st.columns(2)
        cancel = c1.form_submit_button("Cancel", use_container_width=True)
        save = c2.form_submit_button("Add contact", use_container_width=True)

    if save and name:
        new_service = supabase.table("services").insert({
            "name": name, "category": category or None, "phone": phone or None,
            "email": email or None, "website": website or None, "notes": notes or None,
        }).execute().data[0]
        hub_ids = [h["id"] for h in hubs if h["name"] in hub_names]
        if hub_ids:
            supabase.table("service_hubs").insert([{"service_id": new_service["id"], "hub_id": hid} for hid in hub_ids]).execute()
        close_dialog(); clear_and_rerun()
    if cancel:
        close_dialog(); st.rerun()


def dlg_day_view(year, month, day, hub_id):
    d = date(year, month, day)
    st.subheader(d.strftime("%A, %d %B %Y"))
    services_by_id = {s["id"]: s for s in load_services(None)}
    query = supabase.table("tasks").select("*").eq("due_date", d.isoformat())
    if hub_id:
        query = query.eq("hub_id", hub_id)
    tasks = query.order("title").execute().data
    if not tasks:
        st.caption("No tasks due this day.")
    for t in tasks:
        render_task_row(t, services_by_id, key_prefix="dlgday")
    if st.button("Close"):
        close_dialog(); st.rerun()


# ---------------------------------------------------------------------------
# DIALOG DISPATCHER — one modal, content swaps based on session_state.dialog
# ---------------------------------------------------------------------------
@st.dialog("Hub Asset Manager", width="large")
def show_dialog():
    d = st.session_state.dialog
    hubs = load_hubs()
    hub_map = load_service_hub_map()
    if d["type"] == "asset" and d["mode"] == "view":
        dlg_asset_view(d["id"])
    elif d["type"] == "asset" and d["mode"] == "edit":
        dlg_asset_edit(d["id"])
    elif d["type"] == "add_task":
        dlg_add_task(d["asset_id"], d["hub_id"])
    elif d["type"] == "add_asset":
        dlg_add_asset(hubs, d.get("hub_id"))
    elif d["type"] == "task":
        dlg_task_edit(d["id"])
    elif d["type"] == "service":
        dlg_service_edit(d["id"], hubs, hub_map)
    elif d["type"] == "add_service":
        dlg_add_service(hubs, d.get("hub_id"))
    elif d["type"] == "day":
        dlg_day_view(d["year"], d["month"], d["day"], d.get("hub_id"))


# ---------------------------------------------------------------------------
# TOP BAR
# ---------------------------------------------------------------------------
def top_bar(hubs, task_counts_by_hub):
    if os.path.exists("logo.png"):
        st.image("logo.png", width=400)
    st.title("Greater Wellington Hub Asset Manager")

    col1, col2 = st.columns([2, 5])
    with col1:
        options = ["All hubs"] + [h["name"] for h in hubs]
        current = st.session_state.get("hub_name", "All hubs")
        choice = st.selectbox("Hub", options, index=options.index(current) if current in options else 0, label_visibility="collapsed")
    if choice != st.session_state.get("hub_name", "All hubs"):
        st.session_state.hub_name = choice
        st.session_state.hub_id = None if choice == "All hubs" else next(h["id"] for h in hubs if h["name"] == choice)
        st.rerun()

    hub_id = st.session_state.get("hub_id")
    if hub_id:
        counts = task_counts_by_hub.get(hub_id) or {}
    else:
        counts = {}
        for v in task_counts_by_hub.values():
            for k, n in v.items():
                counts[k] = counts.get(k, 0) + n
    parts = [colored(f"{word} {counts.get(word, 0)}") for word in ["Overdue", "Due soon", "On track"] if counts.get(word)]
    st.markdown(" · ".join(parts) if parts else "No open tasks")
    st.divider()


# ---------------------------------------------------------------------------
# ASSETS TAB — grouped by type, compact flashcards
# ---------------------------------------------------------------------------
def render_assets_tab(hub_id, hubs, all_assets, all_tasks):
    hubs_by_id = {h["id"]: h for h in hubs}
    top_c1, top_c2 = st.columns([5, 2])
    with top_c1:
        show_archived = st.checkbox("Show archived assets", value=False)
    with top_c2:
        if st.button("Add asset", use_container_width=True):
            open_dialog({"type": "add_asset", "hub_id": hub_id}); st.rerun()

    visible_assets = [a for a in all_assets if show_archived or a["status"] == "Active"]
    if not visible_assets:
        st.info("No assets yet — add one above.")
        return

    tasks_by_asset = {}
    for t in all_tasks:
        tasks_by_asset.setdefault(t["asset_id"], []).append(t)

    def render_card(a, show_type):
        with st.container(border=True):
            st.markdown(f"**{a['name']}**")
            if show_type:
                st.caption(TYPE_LABELS.get(a["type"], "Other"))
            if a.get("identifier"):
                st.caption(a["identifier"])
            st.markdown(asset_summary_line(tasks_by_asset.get(a["id"], [])))
            if st.button("View", key=f"view_{a['id']}", use_container_width=True):
                open_dialog({"type": "asset", "id": a["id"], "mode": "view"}); st.rerun()

    if hub_id is None:
        # All-hubs view: hub is the ambiguity here, so group by hub (full names,
        # no abbreviation) instead of by type. Type moves onto each card instead,
        # since it's no longer implied by the section header.
        for h in hubs:
            group = [a for a in visible_assets if a["hub_id"] == h["id"]]
            if not group:
                continue
            st.subheader(h["name"])
            cols = st.columns(3)
            for i, a in enumerate(group):
                with cols[i % 3]:
                    render_card(a, show_type=True)
    else:
        # Single-hub view: hub is already fixed and shown in the top bar, so
        # group by type instead — type is the useful axis here.
        for type_key, type_label in TYPE_LABELS.items():
            group = [a for a in visible_assets if a["type"] == type_key]
            if not group:
                continue
            st.subheader(type_label)
            cols = st.columns(3)
            for i, a in enumerate(group):
                with cols[i % 3]:
                    render_card(a, show_type=False)


# ---------------------------------------------------------------------------
# TASKS TAB
# ---------------------------------------------------------------------------
def render_tasks_tab(hub_id, hubs_by_id, all_tasks):
    services_by_id = {s["id"]: s for s in load_services(None)}
    open_tasks = [t for t in all_tasks if t["status"] != "Done"]
    done_tasks = [t for t in all_tasks if t["status"] == "Done"]

    groups = {"Overdue": [], "Due soon": [], "On track": [], "No date": []}
    for t in open_tasks:
        groups[flag_word(t["due_date"], t["status"])].append(t)

    for group_name, group_tasks in groups.items():
        if not group_tasks:
            continue
        st.markdown(f"### {colored(group_name)}")
        for t in group_tasks:
            render_task_row(t, services_by_id, key_prefix="tabtask")

    if done_tasks:
        with st.expander(f"Done ({len(done_tasks)})"):
            for t in done_tasks:
                render_task_row(t, services_by_id, key_prefix="tabtask")

    if not open_tasks and not done_tasks:
        st.info("No tasks yet — add one from the Assets tab.")


# ---------------------------------------------------------------------------
# CALENDAR TAB
# ---------------------------------------------------------------------------
def render_calendar_tab(hub_id, all_tasks):
    st.session_state.setdefault("cal_year", date.today().year)
    st.session_state.setdefault("cal_month", date.today().month)

    nav1, nav2, nav3 = st.columns([1, 3, 1])
    with nav1:
        if st.button("← Prev", use_container_width=True):
            m, y = st.session_state.cal_month - 1, st.session_state.cal_year
            if m < 1:
                m, y = 12, y - 1
            st.session_state.cal_month, st.session_state.cal_year = m, y
            st.rerun()
    with nav2:
        st.markdown(f"<h3 style='text-align:center'>{cal_module.month_name[st.session_state.cal_month]} {st.session_state.cal_year}</h3>", unsafe_allow_html=True)
    with nav3:
        if st.button("Next →", use_container_width=True):
            m, y = st.session_state.cal_month + 1, st.session_state.cal_year
            if m > 12:
                m, y = 1, y + 1
            st.session_state.cal_month, st.session_state.cal_year = m, y
            st.rerun()
    if st.button("Today", key="cal_today"):
        st.session_state.cal_year = date.today().year
        st.session_state.cal_month = date.today().month
        st.rerun()

    open_tasks = [t for t in all_tasks if t["status"] != "Done" and t["due_date"]]
    tasks_by_day = {}
    for t in open_tasks:
        d = date.fromisoformat(t["due_date"])
        if d.year == st.session_state.cal_year and d.month == st.session_state.cal_month:
            tasks_by_day.setdefault(d.day, []).append(t)

    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    header_cols = st.columns(7)
    for i, dn in enumerate(day_names):
        header_cols[i].markdown(f"**{dn}**")

    weeks = cal_module.Calendar(firstweekday=0).monthdayscalendar(st.session_state.cal_year, st.session_state.cal_month)
    today_ = date.today()
    for week in weeks:
        row_cols = st.columns(7)
        for i, day_num in enumerate(week):
            with row_cols[i]:
                if day_num == 0:
                    continue
                is_today = (day_num == today_.day and st.session_state.cal_month == today_.month
                            and st.session_state.cal_year == today_.year)
                with st.container(border=True):
                    st.markdown(f"**{day_num}**" + (" (today)" if is_today else ""))
                    day_tasks = tasks_by_day.get(day_num, [])
                    if day_tasks:
                        worst = min((flag_word(t["due_date"], t["status"]) for t in day_tasks), key=lambda w: FLAG_ORDER[w])
                        st.markdown(f"{colored(worst)}")
                        st.caption(f"{len(day_tasks)} task{'s' if len(day_tasks) != 1 else ''}")
                        if st.button("View", key=f"cal_{st.session_state.cal_year}_{st.session_state.cal_month}_{day_num}", use_container_width=True):
                            open_dialog({
                                "type": "day", "year": st.session_state.cal_year,
                                "month": st.session_state.cal_month, "day": day_num, "hub_id": hub_id,
                            })
                            st.rerun()

    st.caption("Note: on a narrow screen this grid will stack into a single column rather than staying calendar-shaped — it becomes a plain day-by-day list instead.")


# ---------------------------------------------------------------------------
# CONTACTS TAB
# ---------------------------------------------------------------------------
def render_contacts_tab(hub_id, hubs):
    top_c1, top_c2 = st.columns([5, 2])
    with top_c2:
        if st.button("Add contact", use_container_width=True):
            open_dialog({"type": "add_service", "hub_id": hub_id}); st.rerun()

    services = load_services(hub_id)
    hub_map = load_service_hub_map()
    if not services:
        st.info("No contacts yet — add one above.")
        return

    for s in services:
        c1, c2 = st.columns([6, 1])
        with c1:
            assigned = [h["name"] for h in hubs if h["id"] in hub_map.get(s["id"], [])]
            st.markdown(f"**{s['name']}**" + (f" · {s['category']}" if s.get("category") else ""))
            bits = [b for b in [s.get("phone"), s.get("email"), s.get("website")] if b]
            st.caption(" · ".join(bits) if bits else "No contact details")
            st.caption("Hubs: " + (", ".join(assigned) if assigned else "none"))
        with c2:
            if st.button("Edit", key=f"editS_{s['id']}", use_container_width=True):
                open_dialog({"type": "service", "id": s["id"]}); st.rerun()
        st.divider()


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    st.markdown("""
    <style>
    .stTabs [data-baseweb="tab-list"] { width: 100%; }
    .stTabs [data-baseweb="tab"] { flex: 1; justify-content: center; }
    </style>
    """, unsafe_allow_html=True)

    hubs = load_hubs()
    hubs_by_id = {h["id"]: h for h in hubs}
    if "hub_id" not in st.session_state:
        st.session_state.hub_id = None
        st.session_state.hub_name = "All hubs"
    st.session_state.setdefault("dialog", None)

    top_bar(hubs, load_open_task_counts())

    hub_id = st.session_state.hub_id
    all_assets = load_assets(hub_id)
    all_tasks = load_tasks(hub_id)

    tab_assets, tab_tasks, tab_calendar, tab_contacts = st.tabs(["Assets", "Tasks", "Calendar", "Contacts"])
    with tab_assets:
        render_assets_tab(hub_id, hubs, all_assets, all_tasks)
    with tab_tasks:
        render_tasks_tab(hub_id, hubs_by_id, all_tasks)
    with tab_calendar:
        render_calendar_tab(hub_id, all_tasks)
    with tab_contacts:
        render_contacts_tab(hub_id, hubs)

    if st.session_state.get("dialog"):
        show_dialog()


main()
