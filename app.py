
import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
from datetime import datetime
import re
import io

st.set_page_config(page_title="BuyIT Hub Demo", layout="wide")

DB_URL = "sqlite:///buyit_hub.db"
engine = create_engine(DB_URL, future=True)

# ---------- DB Setup ----------
DDL = """
CREATE TABLE IF NOT EXISTS users (
  user_id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  role TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS vendors (
  vendor_id INTEGER PRIMARY KEY AUTOINCREMENT,
  vendor_name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS requests (
  request_id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT NOT NULL,
  requester_name TEXT NOT NULL,
  department TEXT NOT NULL,
  item_desc TEXT NOT NULL,
  quantity INTEGER NOT NULL,
  est_cost REAL NOT NULL,
  justification TEXT NOT NULL,
  vendor_name TEXT,
  status TEXT NOT NULL DEFAULT 'Submitted'
);

CREATE TABLE IF NOT EXISTS approvals (
  approval_id INTEGER PRIMARY KEY AUTOINCREMENT,
  request_id INTEGER NOT NULL,
  approver_name TEXT NOT NULL,
  decision TEXT NOT NULL,
  comments TEXT,
  decided_at TEXT NOT NULL,
  FOREIGN KEY(request_id) REFERENCES requests(request_id)
);

CREATE TABLE IF NOT EXISTS purchase_orders (
  po_id INTEGER PRIMARY KEY AUTOINCREMENT,
  request_id INTEGER NOT NULL UNIQUE,
  po_number TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL,
  created_by TEXT NOT NULL,
  vendor_name TEXT NOT NULL,
  total_amount REAL NOT NULL,
  status TEXT NOT NULL DEFAULT 'Created',
  FOREIGN KEY(request_id) REFERENCES requests(request_id)
);

CREATE TABLE IF NOT EXISTS invoices (
  invoice_id INTEGER PRIMARY KEY AUTOINCREMENT,
  po_number TEXT NOT NULL,
  vendor_name TEXT NOT NULL,
  invoice_number TEXT NOT NULL,
  invoice_amount REAL NOT NULL,
  invoice_date TEXT NOT NULL,
  status TEXT NOT NULL,
  exception_reason TEXT,
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_requests_status ON requests(status);
CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices(status);
"""

def init_db():
    with engine.begin() as conn:
        for stmt in DDL.strip().split(";"):
            s = stmt.strip()
            if s:
                conn.execute(text(s))

def seed_data():
    with engine.begin() as conn:
        conn.execute(text("INSERT OR IGNORE INTO vendors(vendor_name) VALUES (:v)"),
                     [{"v":"Figma"}, {"v":"Microsoft"}, {"v":"Amazon Business"}, {"v":"Dell"}, {"v": "T"}])
        conn.execute(text("INSERT INTO users(name, role) VALUES (:n, :r)"), [
            {"n":"Rohan", "r":"Employee/Requester"},
            {"n":"Isha", "r":"Approver"},
            {"n":"Shalini", "r":"Procurement Specialist"},
            {"n":"Asha", "r":"AP Analyst"},
            {"n":"Neel", "r":"Compliance Auditor"},
        ])

init_db()

# ---------- Helpers ----------
def df(query, params=None):
    with engine.begin() as conn:
        return pd.read_sql(text(query), conn, params=params or {})

def exec_sql(query, params=None):
    with engine.begin() as conn:
        conn.execute(text(query), params or {})

def now_iso():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def extract_fields(free_text: str):
    t = free_text.strip()
    qty = None
    m = re.search(r"\b(\d+)\s*(licenses|license|units|laptops|seats|subscriptions)?\b", t, flags=re.I)
    if m:
        qty = int(m.group(1))

    cost = None
    m = re.search(r"(\$|usd)\s*([\d,]+(\.\d+)?)", t, flags=re.I)
    if m:
        cost = float(m.group(2).replace(",", ""))
    else:
        m = re.search(r"\b([\d,]+(\.\d+)?)\s*(usd|dollars)\b", t, flags=re.I)
        if m:
            cost = float(m.group(1).replace(",", ""))

    vendor = ""
    for v in ["Figma", "Microsoft", "Amazon", "Dell", "Adobe", "Google"]:
        if re.search(rf"\b{re.escape(v)}\b", t, flags=re.I):
            vendor = "Amazon Business" if v.lower()=="amazon" else v
            break

    item_desc = t.split(".")[0][:180] if t else "Software/Hardware purchase"
    return {"item_desc": item_desc, "quantity": qty or 1, "est_cost": cost or 0.0, "vendor_name": vendor}

def status_badge(s):
    color = {
        "Submitted":"🟦",
        "Pending Approval":"🟨",
        "Approved":"🟩",
        "Rejected":"🟥",
        "PO Created":"🟪",
        "PO Sent":"🟪",
        "Closed":"⬛"
    }.get(s, "⬜")
    return f"{color} {s}"

# ---------- Sidebar ----------
st.sidebar.title("BuyIT Hub Demo")
with st.sidebar.expander("Demo Setup", expanded=False):
    if st.button("Seed sample users & vendors"):
        seed_data()
        st.success("Seeded sample data.")
    if st.button("Reset demo database (danger)"):
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE IF EXISTS invoices"))
            conn.execute(text("DROP TABLE IF EXISTS purchase_orders"))
            conn.execute(text("DROP TABLE IF EXISTS approvals"))
            conn.execute(text("DROP TABLE IF EXISTS requests"))
            conn.execute(text("DROP TABLE IF EXISTS vendors"))
            conn.execute(text("DROP TABLE IF EXISTS users"))
        init_db()
        st.warning("Database reset complete.")

page = st.sidebar.radio("Navigate", [
    "1) Create Request (AI Intake)",
    "2) Approvals",
    "3) Purchase Orders",
    "4) Invoice Processing (Match PO)",
    "5) Analytics & Audit"
])

st.sidebar.markdown("---")
st.sidebar.caption("UML mapping: Request → Approval → PO → Invoice Match («include») → Reports")

# ---------- Page 1 ----------
if page.startswith("1)"):
    st.header("1) AI Intake: Create Procurement Request")

    col1, col2 = st.columns([1.2, 1])
    with col1:
        st.subheader("Free-text intake (demo AI)")
        free_text = st.text_area(
            "Describe your procurement need",
            height=140,
            placeholder="Example: Need 20 Figma licenses for Design team, annual plan, budget $8,000."
        )

        if st.button("Extract fields (AI Intake)"):
            st.session_state["extracted"] = extract_fields(free_text)
            st.success("Fields extracted. Review and submit below.")

        extracted = st.session_state.get("extracted", {"item_desc":"", "quantity":1, "est_cost":0.0, "vendor_name":""})

        st.subheader("Structured request form")
        requester = st.text_input("Requester name", value="Rohan")
        dept = st.text_input("Department", value="Design")
        item_desc = st.text_input("Item / Service description", value=extracted.get("item_desc",""))
        qty = st.number_input("Quantity", min_value=1, step=1, value=int(extracted.get("quantity", 1)))
        est_cost = st.number_input("Estimated total cost (USD)", min_value=0.0, step=100.0, value=float(extracted.get("est_cost", 0.0)))
        vendor_name = st.text_input("Preferred vendor (optional)", value=extracted.get("vendor_name",""))
        justification = st.text_area("Business justification", height=100, value="Enable team productivity / required tools for delivery.")

        if st.button("Submit Request"):
            exec_sql("""
                INSERT INTO requests(created_at, requester_name, department, item_desc, quantity, est_cost, justification, vendor_name, status)
                VALUES (:created_at, :requester_name, :department, :item_desc, :quantity, :est_cost, :justification, :vendor_name, 'Submitted')
            """, {
                "created_at": now_iso(),
                "requester_name": requester,
                "department": dept,
                "item_desc": item_desc,
                "quantity": int(qty),
                "est_cost": float(est_cost),
                "justification": justification,
                "vendor_name": vendor_name.strip() or None
            })
            st.success("Request submitted ✅")

    with col2:
        st.subheader("Recent requests")
        r = df("SELECT request_id, created_at, requester_name, department, item_desc, quantity, est_cost, vendor_name, status FROM requests ORDER BY request_id DESC LIMIT 20")
        if r.empty:
            st.info("No requests yet.")
        else:
            r2 = r.copy()
            r2["status"] = r2["status"].apply(status_badge)
            st.dataframe(r2, use_container_width=True)

# ---------- Page 2 ----------
elif page.startswith("2)"):
    st.header("2) Execute Approval Workflow")

    left, right = st.columns([1.2, 1])
    with left:
        pending = df("""
            SELECT request_id, created_at, requester_name, department, item_desc, quantity, est_cost, vendor_name, status
            FROM requests
            WHERE status IN ('Submitted','Pending Approval')
            ORDER BY request_id DESC
        """)
        st.subheader("Requests awaiting decision")
        if pending.empty:
            st.success("No pending requests.")
        else:
            p2 = pending.copy()
            p2["status"] = p2["status"].apply(status_badge)
            st.dataframe(p2, use_container_width=True)

    with right:
        st.subheader("Take action")
        req_ids = df("SELECT request_id FROM requests WHERE status IN ('Submitted','Pending Approval') ORDER BY request_id DESC")["request_id"].tolist()
        if not req_ids:
            st.info("Create a request first.")
        else:
            req_id = st.selectbox("Select Request ID", req_ids)
            req = df("SELECT * FROM requests WHERE request_id=:id", {"id": req_id}).iloc[0].to_dict()

            st.markdown(f"**Request {req_id}** — {req['item_desc']}")
            st.write(f"Requester: {req['requester_name']} | Dept: {req['department']} | Est Cost: ${req['est_cost']:,.2f}")

            approver = st.text_input("Approver name", value="Isha")
            decision = st.radio("Decision", ["Approved", "Rejected"], horizontal=True)
            comments = st.text_area("Comments (required for rejection)", height=90,
                                    value=("Looks good." if decision=="Approved" else "Please revise / provide quote."))

            if st.button("Submit decision"):
                if decision == "Rejected" and not comments.strip():
                    st.error("Comments required for rejection.")
                else:
                    exec_sql("""
                        INSERT INTO approvals(request_id, approver_name, decision, comments, decided_at)
                        VALUES (:request_id, :approver_name, :decision, :comments, :decided_at)
                    """, {
                        "request_id": int(req_id),
                        "approver_name": approver.strip(),
                        "decision": decision,
                        "comments": comments.strip() or None,
                        "decided_at": now_iso()
                    })
                    exec_sql("UPDATE requests SET status=:s WHERE request_id=:id",
                             {"s": ("Approved" if decision=="Approved" else "Rejected"), "id": int(req_id)})
                    st.success(f"Request {req_id} updated ✅")

# ---------- Page 3 ----------
elif page.startswith("3)"):
    st.header("3) Generate & Manage Purchase Orders")

    col1, col2 = st.columns([1.2, 1])
    with col1:
        approved = df("""
            SELECT request_id, created_at, requester_name, department, item_desc, quantity, est_cost, vendor_name, status
            FROM requests WHERE status='Approved'
            ORDER BY request_id DESC
        """)
        st.subheader("Approved requests")
        if approved.empty:
            st.info("Approve a request first.")
        else:
            a2 = approved.copy()
            a2["status"] = a2["status"].apply(status_badge)
            st.dataframe(a2, use_container_width=True)

    with col2:
        st.subheader("Create / Update PO")
        ids = df("SELECT request_id FROM requests WHERE status='Approved' ORDER BY request_id DESC")["request_id"].tolist()
        if not ids:
            st.info("No approved requests.")
        else:
            req_id = st.selectbox("Approved Request ID", ids)
            req = df("SELECT * FROM requests WHERE request_id=:id", {"id": req_id}).iloc[0].to_dict()

            creator = st.text_input("Created by (Procurement)", value="Shalini")
            vendor = st.text_input("Vendor", value=(req.get("vendor_name") or "Amazon Business"))
            total = st.number_input("PO Total Amount (USD)", min_value=0.0, step=100.0, value=float(req["est_cost"]))
            po_number = st.text_input("PO Number (auto if blank)", value="")
            action = st.selectbox("PO action", ["Create PO", "Mark as Sent", "Close PO"])

            if st.button("Apply PO action"):
                if action == "Create PO":
                    if not po_number.strip():
                        po_number = f"PO-{int(req_id):06d}"
                    try:
                        exec_sql("""
                            INSERT INTO purchase_orders(request_id, po_number, created_at, created_by, vendor_name, total_amount, status)
                            VALUES (:request_id, :po_number, :created_at, :created_by, :vendor_name, :total_amount, 'Created')
                        """, {
                            "request_id": int(req_id),
                            "po_number": po_number.strip(),
                            "created_at": now_iso(),
                            "created_by": creator.strip(),
                            "vendor_name": vendor.strip(),
                            "total_amount": float(total)
                        })
                        exec_sql("UPDATE requests SET status='PO Created' WHERE request_id=:id", {"id": int(req_id)})
                        st.success(f"PO created: {po_number} ✅")
                    except Exception as e:
                        st.error(f"Could not create PO (maybe exists): {e}")
                else:
                    po = df("SELECT * FROM purchase_orders WHERE request_id=:id", {"id": int(req_id)})
                    if po.empty:
                        st.error("Create PO first.")
                    else:
                        po_num = po.iloc[0]["po_number"]
                        if action == "Mark as Sent":
                            exec_sql("UPDATE purchase_orders SET status='Sent' WHERE request_id=:id", {"id": int(req_id)})
                            exec_sql("UPDATE requests SET status='PO Sent' WHERE request_id=:id", {"id": int(req_id)})
                            st.success(f"PO {po_num} marked Sent ✅")
                        elif action == "Close PO":
                            exec_sql("UPDATE purchase_orders SET status='Closed' WHERE request_id=:id", {"id": int(req_id)})
                            exec_sql("UPDATE requests SET status='Closed' WHERE request_id=:id", {"id": int(req_id)})
                            st.success(f"PO {po_num} closed ✅")

    st.markdown("---")
    st.subheader("Recent Purchase Orders")
    po_df = df("SELECT po_number, request_id, vendor_name, total_amount, status, created_at, created_by FROM purchase_orders ORDER BY po_id DESC LIMIT 25")
    st.dataframe(po_df, use_container_width=True) 
    if not po_df.empty:
        st.dataframe(po_df, use_container_width=True)
    
    

# ---------- Page 4 ----------
elif page.startswith("4)"):
    st.header("4) Invoice Processing — «include» Match Invoice to PO")

    left, right = st.columns([1.2, 1])
    with left:
        po_numbers = df("SELECT po_number FROM purchase_orders ORDER BY po_id DESC")["po_number"].tolist()
        if not po_numbers:
            st.info("Create a PO first.")
        else:
            po_number = st.selectbox("PO Number", po_numbers)
            po = df("SELECT * FROM purchase_orders WHERE po_number=:p", {"p": po_number}).iloc[0].to_dict()

            vendor = st.text_input("Vendor", value=po["vendor_name"])
            invoice_number = st.text_input("Invoice number", value=f"INV-{po['request_id']:06d}-01")
            invoice_amount = st.number_input("Invoice amount (USD)", min_value=0.0, step=50.0, value=float(po["total_amount"]))
            invoice_date = st.date_input("Invoice date", value=datetime.now().date())
            tolerance = st.number_input("Tolerance (USD)", min_value=0.0, step=10.0, value=50.0)

            if st.button("Submit invoice (includes Match Invoice to PO)"):
                status = "Matched"
                reason = None

                # «include» Match Invoice to PO (always executed)
                if vendor.strip().lower() != str(po["vendor_name"]).strip().lower():
                    status = "Exception"
                    reason = f"Vendor mismatch: PO={po['vendor_name']} vs Invoice={vendor}"
                elif abs(float(invoice_amount) - float(po["total_amount"])) > float(tolerance):
                    status = "Exception"
                    reason = f"Amount mismatch beyond tolerance: PO=${po['total_amount']:.2f} vs Invoice=${invoice_amount:.2f}, tol=${tolerance:.2f}"

                exec_sql("""
                    INSERT INTO invoices(po_number, vendor_name, invoice_number, invoice_amount, invoice_date, status, exception_reason, created_at)
                    VALUES (:po_number, :vendor_name, :invoice_number, :invoice_amount, :invoice_date, :status, :exception_reason, :created_at)
                """, {
                    "po_number": po_number,
                    "vendor_name": vendor.strip(),
                    "invoice_number": invoice_number.strip(),
                    "invoice_amount": float(invoice_amount),
                    "invoice_date": invoice_date.strftime("%Y-%m-%d"),
                    "status": status,
                    "exception_reason": reason,
                    "created_at": now_iso()
                })

                if status == "Matched":
                    st.success("Invoice matched ✅ (include: Match Invoice to PO)")
                else:
                    st.warning("Invoice exception ⚠️ (extend: Handle Invoice Exception)")

    Reason: "{reason}"


    with right:
            st.subheader("Recent invoices")
            inv = df("SELECT invoice_number, po_number, vendor_name, invoice_amount, invoice_date, status, exception_reason FROM invoices ORDER BY invoice_id DESC LIMIT 25")
            st.dataframe(inv, use_container_width=True) 
            if not inv.empty:
                st.dataframe(inv, use_container_width=True)
else:
    st.info("No invoices yet.")

# ---------- Page 5 ----------


    st.header("5) Analytics & Audit")

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Requests", int(df("SELECT COUNT(*) c FROM requests").iloc[0]["c"]))
    # k2.metric("Approved", int(df("SELECT COUNT(*) c FROM requests WHERE status='Approved'").iloc[0]["c"]))
    k2.metric("Approved (Decisions)", int(df("SELECT COUNT(*) c FROM approvals WHERE decision='Approved'").iloc[0]["c"]))
    k3.metric("POs", int(df("SELECT COUNT(*) c FROM purchase_orders").iloc[0]["c"]))
    k4.metric("Invoices Matched", int(df("SELECT COUNT(*) c FROM invoices WHERE status='Matched'").iloc[0]["c"]))
    k5.metric("Invoice Exceptions", int(df("SELECT COUNT(*) c FROM invoices WHERE status='Exception'").iloc[0]["c"]))

    st.markdown("### Spend by vendor (PO totals)")
    spend = df("SELECT vendor_name, SUM(total_amount) AS total_spend FROM purchase_orders GROUP BY vendor_name ORDER BY total_spend DESC")
    if spend.empty:
        st.info("No spend data yet.")
    else:
        st.bar_chart(spend.set_index("vendor_name"))

        st.markdown("---")
        st.subheader("Audit trail (approvals)")
        approvals = df("""
            SELECT a.approval_id, a.request_id, r.requester_name, a.approver_name, a.decision, a.comments, a.decided_at
            FROM approvals a
            JOIN requests r ON r.request_id = a.request_id
            ORDER BY a.approval_id DESC
            LIMIT 50
        """)
        st.dataframe(approvals, use_container_width=True) 
        if not approvals.empty:
            st.dataframe(approvals, use_container_width=True)

        st.markdown("---")
        st.subheader("Traceability (Request → PO → Invoice)")
        trace = df("""
            SELECT r.request_id, r.item_desc, r.status AS request_status,
                po.po_number, po.status AS po_status, po.total_amount,
                inv.invoice_number, inv.status AS invoice_status, inv.exception_reason
            FROM requests r
            LEFT JOIN purchase_orders po ON po.request_id = r.request_id
            LEFT JOIN invoices inv ON inv.po_number = po.po_number
            ORDER BY r.request_id DESC
            LIMIT 50
        """)
        st.dataframe(trace, use_container_width=True)

st.markdown("### Export Reports")

if st.button("Download Full Report (Excel)"):
    output = io.BytesIO()

    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df("SELECT * FROM requests").to_excel(writer, sheet_name="Requests", index=False)
        df("SELECT * FROM approvals").to_excel(writer, sheet_name="Approvals", index=False)
        df("SELECT * FROM purchase_orders").to_excel(writer, sheet_name="POs", index=False)
        df("SELECT * FROM invoices").to_excel(writer, sheet_name="Invoices", index=False)

    st.download_button(
        label="Download Excel File",
        data=output.getvalue(),
        file_name="BuyIT_Hub_Report.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
