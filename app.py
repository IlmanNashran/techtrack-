import streamlit as st
import pandas as pd
import gspread
import qrcode
import json
import io
import uuid
from datetime import datetime
from PIL import Image
from google.oauth2.service_account import Credentials

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="TechTrack",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;600;800&display=swap');
html, body, [class*="css"] { font-family: 'Syne', sans-serif; }
[data-testid="stSidebar"] { background: #0f0f0f; border-right: 2px solid #00ff88; }
[data-testid="stSidebar"] * { color: #e0e0e0 !important; }
[data-testid="stSidebar"] .stRadio label { color: #00ff88 !important; font-weight: 600; }
.main { background: #f5f5f0; }
.card { background: white; border: 2px solid #111; padding: 1.5rem; margin-bottom: 1rem; box-shadow: 5px 5px 0px #111; }
.card-green { background: #00ff88; border: 2px solid #111; padding: 1rem 1.5rem; box-shadow: 5px 5px 0px #111; margin-bottom: 1rem; }
.card-dark { background: #111; color: white; border: 2px solid #00ff88; padding: 1rem 1.5rem; box-shadow: 5px 5px 0px #00ff88; margin-bottom: 1rem; }
.badge-available { background: #00ff88; color: #111; padding: 3px 10px; font-weight: 700; font-size: 0.8rem; border: 1.5px solid #111; }
.badge-inuse { background: #ff4444; color: white; padding: 3px 10px; font-weight: 700; font-size: 0.8rem; border: 1.5px solid #111; }
.badge-maintenance { background: #ffcc00; color: #111; padding: 3px 10px; font-weight: 700; font-size: 0.8rem; border: 1.5px solid #111; }
h1 { font-family: 'Syne', sans-serif !important; font-weight: 800 !important; }
h2, h3 { font-family: 'Syne', sans-serif !important; font-weight: 600 !important; }
[data-testid="stMetric"] { background: white; border: 2px solid #111; padding: 1rem; box-shadow: 4px 4px 0 #111; }
.stButton > button { background: #111 !important; color: #00ff88 !important; border: 2px solid #00ff88 !important; border-radius: 0 !important; font-family: 'Syne', sans-serif !important; font-weight: 700 !important; }
.stButton > button:hover { background: #00ff88 !important; color: #111 !important; }
.header-strip { background: #111; color: #00ff88; padding: 1.2rem 2rem; font-family: 'Syne', sans-serif; font-size: 1.8rem; font-weight: 800; border-bottom: 3px solid #00ff88; margin-bottom: 2rem; }
.section-title { font-size: 1.1rem; font-weight: 800; letter-spacing: 0.1em; text-transform: uppercase; border-left: 5px solid #00ff88; padding-left: 0.7rem; margin: 1.5rem 0 1rem 0; color: #111; }
</style>
""", unsafe_allow_html=True)

# ── Google Sheets Connection ──────────────────────────────────────────────────
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

@st.cache_resource
def get_gsheet_client():
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return gspread.authorize(creds)

@st.cache_resource
def get_spreadsheet():
    client = get_gsheet_client()
    return client.open_by_key(st.secrets["sheet_id"])

def get_worksheet(sheet_name):
    return get_spreadsheet().worksheet(sheet_name)

# ── Read / Write Helpers ──────────────────────────────────────────────────────
def read_sheet(sheet_name) -> pd.DataFrame:
    try:
        ws = get_worksheet(sheet_name)
        data = ws.get_all_records()
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Error reading {sheet_name}: {e}")
        return pd.DataFrame()

def append_row(sheet_name, row: dict):
    ws = get_worksheet(sheet_name)
    # If sheet is empty, write headers first
    if not ws.get_all_values():
        ws.append_row(list(row.keys()))
    ws.append_row(list(row.values()))

def update_cell_by_id(sheet_name, id_col, id_val, update_dict: dict):
    ws = get_worksheet(sheet_name)
    records = ws.get_all_records()
    headers = ws.row_values(1)
    for i, record in enumerate(records):
        if str(record.get(id_col)) == str(id_val):
            row_num = i + 2  # +2 because row 1 is header
            for col_name, new_val in update_dict.items():
                if col_name in headers:
                    col_num = headers.index(col_name) + 1
                    ws.update_cell(row_num, col_num, new_val)
            return
    st.error(f"ID {id_val} not found in {sheet_name}")

def init_sheet_headers():
    """Write headers to empty sheets on first run"""
    sheets_headers = {
        "Items":     ["item_id","name","category","location","status","registered_by","registered_at","notes"],
        "Usage_Log": ["log_id","item_id","item_name","technician","action","timestamp","notes"],
        "Reports":   ["report_id","submitted_by","title","description","priority","status","assigned_to","created_at","updated_at","resolution"],
        "Users":     ["user_id","name","role","email"],
    }
    sp = get_spreadsheet()
    for sheet_name, headers in sheets_headers.items():
        try:
            ws = sp.worksheet(sheet_name)
            if not ws.get_all_values():
                ws.append_row(headers)
        except Exception as e:
            st.warning(f"Could not init {sheet_name}: {e}")

def seed_users():
    """Add demo users if Users sheet is empty"""
    df = read_sheet("Users")
    if df.empty:
        demo_users = [
            {"user_id":"U001","name":"Ahmad Technician","role":"technician","email":"ahmad@tech.com"},
            {"user_id":"U002","name":"Siti Technician","role":"technician","email":"siti@tech.com"},
            {"user_id":"U003","name":"Ali User","role":"user","email":"ali@user.com"},
            {"user_id":"U004","name":"Nurul User","role":"user","email":"nurul@user.com"},
        ]
        for user in demo_users:
            append_row("Users", user)

# ── QR Code Helpers ───────────────────────────────────────────────────────────
def generate_qr(data: dict) -> Image.Image:
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=8, border=3)
    qr.add_data(json.dumps(data))
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    return img._img if hasattr(img, '_img') else img

def qr_to_bytes(img) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def decode_qr_from_upload(uploaded_file):
    try:
        from pyzbar.pyzbar import decode
        import numpy as np
        img = Image.open(uploaded_file).convert("RGB")
        arr = np.array(img)
        decoded = decode(arr)
        if decoded:
            return json.loads(decoded[0].data.decode("utf-8"))
    except Exception as e:
        st.warning(f"QR decode error: {e}. Use Manual Entry tab instead.")
    return None

# ── Session State ─────────────────────────────────────────────────────────────
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user = None
if "initialized" not in st.session_state:
    st.session_state.initialized = False

# ── Initialize on first load ──────────────────────────────────────────────────
if not st.session_state.initialized:
    with st.spinner("Connecting to database..."):
        try:
            init_sheet_headers()
            seed_users()
            st.session_state.initialized = True
        except Exception as e:
            st.error(f"Connection failed: {e}")
            st.stop()

# ── Login Screen ──────────────────────────────────────────────────────────────
def login_screen():
    st.markdown('<div class="header-strip">🔧 TECHTRACK — ITEM & REPORT SYSTEM</div>', unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("### 🔐 Login")
        users = read_sheet("Users")
        if users.empty:
            st.error("Could not load users. Check your Google Sheet connection.")
            return
        names = users["name"].tolist()
        selected = st.selectbox("Select your account", names)
        if st.button("Login →", use_container_width=True):
            user_row = users[users["name"] == selected].iloc[0]
            st.session_state.logged_in = True
            st.session_state.user = user_row.to_dict()
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('<div class="card-dark"><b>Demo Accounts</b><br>👷 Ahmad Technician · Siti Technician<br>👤 Ali User · Nurul User</div>', unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
def sidebar_nav(role):
    st.sidebar.markdown("### 🔧 TECHTRACK")
    st.sidebar.markdown(f"**{st.session_state.user['name']}**")
    st.sidebar.markdown(f"`{role.upper()}`")
    st.sidebar.divider()
    if role == "technician":
        page = st.sidebar.radio("Navigation", [
            "📊 Dashboard",
            "📦 Register Item",
            "📷 Scan & Use Item",
            "✅ Item Availability",
            "📋 Manage Reports",
        ])
    else:
        page = st.sidebar.radio("Navigation", [
            "📊 My Dashboard",
            "📝 Submit Report",
            "🔍 Track My Reports",
        ])
    st.sidebar.divider()
    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.user = None
        st.rerun()
    return page

# ══════════════════════════════════════════════════════════════════════════════
# TECHNICIAN PAGES
# ══════════════════════════════════════════════════════════════════════════════

def page_dashboard_tech():
    st.markdown('<div class="header-strip">📊 DASHBOARD</div>', unsafe_allow_html=True)
    items   = read_sheet("Items")
    reports = read_sheet("Reports")
    usage   = read_sheet("Usage_Log")

    total     = len(items)
    available = len(items[items["status"] == "available"]) if not items.empty else 0
    in_use    = len(items[items["status"] == "in_use"])    if not items.empty else 0
    open_rpts = len(reports[reports["status"] == "open"])  if not reports.empty else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Items",    total)
    c2.metric("✅ Available",   available)
    c3.metric("🔴 In Use",      in_use)
    c4.metric("📋 Open Reports",open_rpts)

    st.markdown('<div class="section-title">Recent Usage Log</div>', unsafe_allow_html=True)
    if not usage.empty:
        st.dataframe(usage.tail(10).iloc[::-1], use_container_width=True)
    else:
        st.info("No usage logged yet.")

    st.markdown('<div class="section-title">Pending Reports</div>', unsafe_allow_html=True)
    if not reports.empty:
        pending = reports[reports["status"].isin(["open","in_progress"])]
        if not pending.empty:
            st.dataframe(pending[["report_id","title","submitted_by","priority","status","created_at"]], use_container_width=True)
        else:
            st.success("No pending reports! 🎉")
    else:
        st.info("No reports yet.")


def page_register_item():
    st.markdown('<div class="header-strip">📦 REGISTER ITEM</div>', unsafe_allow_html=True)
    col1, col2 = st.columns([1.5, 1])

    with col1:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("### Item Details")
        name     = st.text_input("Item Name *", placeholder="e.g. Multimeter Fluke 87V")
        category = st.selectbox("Category", ["Tools","Equipment","Consumable","Safety","Electrical","Mechanical","Other"])
        location = st.text_input("Location / Storage", placeholder="e.g. Rack A, Shelf 2")
        notes    = st.text_area("Notes", placeholder="Serial number, condition, etc.")
        tech     = st.session_state.user["name"]

        if st.button("🖨️ Register & Generate QR", use_container_width=True):
            if not name:
                st.error("Item name is required!")
            else:
                with st.spinner("Saving to Google Sheets..."):
                    item_id = f"ITM-{str(uuid.uuid4())[:8].upper()}"
                    qr_data = {"item_id": item_id, "name": name, "category": category}
                    qr_img  = generate_qr(qr_data)

                    new_row = {
                        "item_id":       item_id,
                        "name":          name,
                        "category":      category,
                        "location":      location,
                        "status":        "available",
                        "registered_by": tech,
                        "registered_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "notes":         notes,
                    }
                    append_row("Items", new_row)

                    st.session_state["last_qr_img"]  = qr_img
                    st.session_state["last_qr_data"] = qr_data
                    st.session_state["last_item_id"] = item_id
                    st.success(f"✅ Item saved to Google Sheets! ID: **{item_id}**")
        st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        if "last_qr_img" in st.session_state:
            st.markdown('<div class="section-title">Generated QR Code</div>', unsafe_allow_html=True)
            st.image(st.session_state["last_qr_img"], caption=f"ID: {st.session_state['last_item_id']}", width=220)
            qr_bytes = qr_to_bytes(st.session_state["last_qr_img"])
            st.download_button(
                "⬇️ Download QR Code",
                data=qr_bytes,
                file_name=f"{st.session_state['last_item_id']}.png",
                mime="image/png",
                use_container_width=True,
            )
            st.markdown('<div class="card-dark">', unsafe_allow_html=True)
            st.json(st.session_state["last_qr_data"])
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="card-green"><b>💡 Tip</b><br><br>Fill in item details and click Register.<br><br>A QR code will be generated automatically.<br><br>Download it, print it and attach to the physical item!</div>', unsafe_allow_html=True)


def page_scan_use():
    st.markdown('<div class="header-strip">📷 SCAN & USE ITEM</div>', unsafe_allow_html=True)
    items = read_sheet("Items")
    tech  = st.session_state.user["name"]

    def do_action(item_id, action, notes_val=""):
        if items.empty or item_id not in items["item_id"].values:
            st.error(f"Item {item_id} not found!")
            return
        row     = items[items["item_id"] == item_id].iloc[0]
        current = row["status"]
        item_name = row["name"]

        if action == "use" and current != "available":
            st.error(f"❌ Item is currently **{current}** — cannot check out!")
            return
        if action == "return" and current != "in_use":
            st.error(f"❌ Item is not checked out (status: **{current}**)")
            return

        with st.spinner("Updating Google Sheets..."):
            new_status = "in_use" if action == "use" else "available"
            update_cell_by_id("Items", "item_id", item_id, {"status": new_status})

            log_row = {
                "log_id":     str(uuid.uuid4())[:8].upper(),
                "item_id":    item_id,
                "item_name":  item_name,
                "technician": tech,
                "action":     "CHECK OUT" if action == "use" else "RETURN",
                "timestamp":  datetime.now().strftime("%Y-%m-%d %H:%M"),
                "notes":      notes_val,
            }
            append_row("Usage_Log", log_row)

        emoji = "🔴" if action == "use" else "✅"
        label = "Checked OUT" if action == "use" else "Returned"
        st.success(f"{emoji} **{item_name}** — {label} successfully!")
        st.balloons()

    tab1, tab2 = st.tabs(["📷 Scan QR Image", "⌨️ Manual Entry"])

    with tab1:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("#### Upload QR Code Image")
        st.caption("Take a photo of the item QR code and upload here")
        uploaded = st.file_uploader("Upload QR image", type=["png","jpg","jpeg"], label_visibility="collapsed")
        if uploaded:
            col_img, col_info = st.columns(2)
            with col_img:
                st.image(uploaded, width=200)
            with col_info:
                decoded = decode_qr_from_upload(uploaded)
                if decoded and "item_id" in decoded:
                    st.success("✅ QR Decoded!")
                    st.write(f"**Item:** {decoded.get('name','?')}")
                    st.write(f"**ID:** `{decoded['item_id']}`")
                    if not items.empty and decoded["item_id"] in items["item_id"].values:
                        row    = items[items["item_id"] == decoded["item_id"]].iloc[0]
                        status = row["status"]
                        badge  = "badge-available" if status=="available" else "badge-inuse"
                        st.markdown(f'<span class="{badge}">{status.upper()}</span>', unsafe_allow_html=True)
                        note = st.text_input("Notes (optional)", key="scan_notes")
                        c1, c2 = st.columns(2)
                        with c1:
                            if st.button("🔴 Check Out", use_container_width=True):
                                do_action(decoded["item_id"], "use", note)
                        with c2:
                            if st.button("✅ Return", use_container_width=True):
                                do_action(decoded["item_id"], "return", note)
                    else:
                        st.error("Item not found in database!")
                else:
                    st.warning("Could not decode QR. Try Manual Entry tab.")
        st.markdown('</div>', unsafe_allow_html=True)

    with tab2:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("#### Manual Item Lookup")
        if not items.empty:
            item_options = (items["item_id"] + " — " + items["name"]).tolist()
            selected = st.selectbox("Select Item", item_options)
            if selected:
                item_id = selected.split(" — ")[0]
                row     = items[items["item_id"] == item_id].iloc[0]
                status  = row["status"]
                c1, c2  = st.columns(2)
                c1.write(f"**Location:** {row['location']}")
                badge = "badge-available" if status=="available" else "badge-inuse"
                c2.markdown(f'Status: <span class="{badge}">{status.upper()}</span>', unsafe_allow_html=True)
                note = st.text_input("Notes", key="manual_notes")
                b1, b2 = st.columns(2)
                with b1:
                    if st.button("🔴 Check Out", key="m_use", use_container_width=True):
                        do_action(item_id, "use", note)
                        st.rerun()
                with b2:
                    if st.button("✅ Return", key="m_return", use_container_width=True):
                        do_action(item_id, "return", note)
                        st.rerun()
        else:
            st.info("No items registered yet.")
        st.markdown('</div>', unsafe_allow_html=True)


def page_availability():
    st.markdown('<div class="header-strip">✅ ITEM AVAILABILITY</div>', unsafe_allow_html=True)
    items = read_sheet("Items")

    if items.empty:
        st.info("No items registered yet.")
        return

    col1, col2, col3 = st.columns(3)
    f_status   = col1.selectbox("Filter by Status",   ["All","available","in_use","maintenance"])
    f_category = col2.selectbox("Filter by Category", ["All"] + sorted(items["category"].unique().tolist()))
    search     = col3.text_input("Search", placeholder="Name or ID...")

    df = items.copy()
    if f_status   != "All": df = df[df["status"]   == f_status]
    if f_category != "All": df = df[df["category"] == f_category]
    if search:
        df = df[df["name"].str.contains(search, case=False) | df["item_id"].str.contains(search, case=False)]

    st.markdown(f"**{len(df)} items found**")

    def color_status(val):
        if val == "available":  return "background-color:#d4fce8; font-weight:bold"
        if val == "in_use":     return "background-color:#ffe0e0; font-weight:bold"
        return "background-color:#fff3cd; font-weight:bold"

    styled = df.style.applymap(color_status, subset=["status"])
    st.dataframe(styled, use_container_width=True, height=420)


def page_manage_reports():
    st.markdown('<div class="header-strip">📋 MANAGE REPORTS</div>', unsafe_allow_html=True)
    reports = read_sheet("Reports")
    tech    = st.session_state.user["name"]

    if reports.empty:
        st.info("No reports submitted yet.")
        return

    tab1, tab2 = st.tabs(["📋 All Reports", "🔧 Execute Report"])

    with tab1:
        status_filter = st.selectbox("Filter", ["All","open","in_progress","resolved"])
        df = reports if status_filter == "All" else reports[reports["status"] == status_filter]

        def color_priority(val):
            if val == "high":   return "background-color:#ffe0e0; font-weight:bold"
            if val == "medium": return "background-color:#fff3cd"
            return "background-color:#d4fce8"

        styled = df.style.applymap(color_priority, subset=["priority"])
        st.dataframe(styled, use_container_width=True)

    with tab2:
        open_r = reports[reports["status"].isin(["open","in_progress"])]
        if open_r.empty:
            st.success("🎉 All reports resolved!")
            return

        opts   = (open_r["report_id"] + " | " + open_r["title"]).tolist()
        sel    = st.selectbox("Select report to action", opts)
        sel_id = sel.split(" | ")[0]
        row    = reports[reports["report_id"] == sel_id].iloc[0]

        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.write(f"**Title:** {row['title']}")
        st.write(f"**Submitted by:** {row['submitted_by']}")
        st.write(f"**Priority:** `{row['priority'].upper()}`")
        st.write(f"**Description:** {row['description']}")
        st.write(f"**Current Status:** `{row['status']}`")
        st.markdown('</div>', unsafe_allow_html=True)

        new_status = st.selectbox("Update Status", ["open","in_progress","resolved"])
        resolution = st.text_area("Resolution Notes")

        if st.button("💾 Update Report", use_container_width=True):
            with st.spinner("Updating Google Sheets..."):
                update_cell_by_id("Reports", "report_id", sel_id, {
                    "status":     new_status,
                    "assigned_to": tech,
                    "resolution": resolution,
                    "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                })
            st.success("✅ Report updated in Google Sheets!")
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# USER PAGES
# ══════════════════════════════════════════════════════════════════════════════

def page_dashboard_user():
    st.markdown('<div class="header-strip">📊 MY DASHBOARD</div>', unsafe_allow_html=True)
    name    = st.session_state.user["name"]
    reports = read_sheet("Reports")

    my = reports[reports["submitted_by"] == name] if not reports.empty else pd.DataFrame()
    c1, c2, c3 = st.columns(3)
    c1.metric("My Reports", len(my))
    c2.metric("Open",     len(my[my["status"] == "open"])     if not my.empty else 0)
    c3.metric("Resolved", len(my[my["status"] == "resolved"]) if not my.empty else 0)

    st.markdown('<div class="section-title">My Reports</div>', unsafe_allow_html=True)
    if not my.empty:
        st.dataframe(my[["report_id","title","priority","status","created_at","resolution"]], use_container_width=True)
    else:
        st.info("You haven't submitted any reports yet.")


def page_submit_report():
    st.markdown('<div class="header-strip">📝 SUBMIT REPORT</div>', unsafe_allow_html=True)
    name = st.session_state.user["name"]

    col1, col2 = st.columns([1.5, 1])
    with col1:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("### New Report")
        title       = st.text_input("Report Title *", placeholder="e.g. Equipment malfunction at Line 3")
        description = st.text_area("Description *",  placeholder="Describe the issue in detail...", height=120)
        priority    = st.select_slider("Priority", ["low","medium","high"], value="medium")

        if st.button("📤 Submit Report", use_container_width=True):
            if not title or not description:
                st.error("Title and description are required!")
            else:
                with st.spinner("Saving to Google Sheets..."):
                    rep_id  = f"RPT-{str(uuid.uuid4())[:8].upper()}"
                    new_row = {
                        "report_id":    rep_id,
                        "submitted_by": name,
                        "title":        title,
                        "description":  description,
                        "priority":     priority,
                        "status":       "open",
                        "assigned_to":  "",
                        "created_at":   datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "updated_at":   "",
                        "resolution":   "",
                    }
                    append_row("Reports", new_row)
                st.success(f"✅ Report submitted! ID: **{rep_id}**")
                st.balloons()
        st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="card-green"><b>📌 Tips for a good report</b><br><br>✔ Be specific about location<br>✔ Include equipment ID if known<br>✔ Describe when issue started<br>✔ Note any safety concerns<br>✔ Set correct priority level</div>', unsafe_allow_html=True)


def page_track_reports():
    st.markdown('<div class="header-strip">🔍 TRACK MY REPORTS</div>', unsafe_allow_html=True)
    name    = st.session_state.user["name"]
    reports = read_sheet("Reports")

    if reports.empty:
        st.info("No reports yet.")
        return

    my = reports[reports["submitted_by"] == name]
    if my.empty:
        st.info("You haven't submitted any reports.")
        return

    for _, row in my.iloc[::-1].iterrows():
        status = row["status"]
        color  = "#d4fce8" if status=="resolved" else ("#fff3cd" if status=="in_progress" else "white")
        resolution_html = f"<br>✅ <b>Resolution:</b> {row['resolution']}" if row.get('resolution') else ""
        assigned_html   = f"<br>👷 <b>Assigned to:</b> {row['assigned_to']}"  if row.get('assigned_to') else ""
        st.markdown(f"""
        <div class="card" style="background:{color}">
            <b>{row['title']}</b> &nbsp; <code>{row['report_id']}</code><br>
            Priority: <b>{str(row['priority']).upper()}</b> &nbsp;|&nbsp;
            Status: <b>{str(row['status']).upper()}</b> &nbsp;|&nbsp;
            Submitted: {row['created_at']}
            {assigned_html}
            {resolution_html}
        </div>
        """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
def main():
    if not st.session_state.logged_in:
        login_screen()
        return

    role = st.session_state.user["role"]
    page = sidebar_nav(role)

    if role == "technician":
        if   page == "📊 Dashboard":        page_dashboard_tech()
        elif page == "📦 Register Item":     page_register_item()
        elif page == "📷 Scan & Use Item":   page_scan_use()
        elif page == "✅ Item Availability": page_availability()
        elif page == "📋 Manage Reports":    page_manage_reports()
    else:
        if   page == "📊 My Dashboard":     page_dashboard_user()
        elif page == "📝 Submit Report":     page_submit_report()
        elif page == "🔍 Track My Reports":  page_track_reports()

main()
