# BuyIT Hub Streamlit Demo

## What this demo shows (maps to UML)
1) AI Intake: Create Procurement Request (free-text → structured)
2) Execute Approval Workflow (Approve/Reject + audit trail)
3) Generate & Manage Purchase Orders (create + status)
4) Process Invoices & Manage Contracts
   - «include» Match Invoice to PO (always executed on invoice submission)
   - «extend» Handle Invoice Exception (only when mismatch occurs)
5) Analytics & Audit (dashboards + traceability)

## Run
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Demo script (2–3 minutes)
1. Create a request (AI Intake) → Submit
2. Approve the request
3. Generate PO (auto PO-000001…)
4. Submit an invoice that matches → Matched 
5. Submit an invoice with wrong amount/vendor → Exception 
6. Show Analytics & Audit → traceability table updates


https://procurementautomation-4zfhosqj3vpuaydugfrxjs.streamlit.app/
