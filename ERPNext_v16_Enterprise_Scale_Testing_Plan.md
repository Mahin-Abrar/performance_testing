# ERPNext v16 Enterprise-Scale Testing Plan
## 35-Company Oracle EBS / SAP Replacement PoC

**Purpose:** Build a realistic multi-company ERPNext v16 test environment and progressively validate functional correctness, data volume, reporting, performance, concurrency, and enterprise scalability.

---

## 1. Objective

The goal is to determine whether ERPNext v16 can support an enterprise group with approximately **35 legal entities/companies**, similar to a large Oracle EBS or SAP ERP deployment.

The test must cover:

- Multi-company accounting
- Inter-company transactions
- Sales
- Purchase
- Inventory
- Manufacturing
- Fixed Assets
- Multi-currency
- Cost centers / accounting dimensions
- Financial reporting
- Consolidation
- Security and company-wise access
- Large data volumes
- Concurrent users
- Background jobs
- Backup / restore
- Database and application performance

### Important

Do **not** start by creating 1 million records.

First build a correct **35-company functional environment**, then progressively increase the data volume:

```text
35-company functional environment
        ↓
Baseline Desk concurrent test (10 → 100 users)  ← Phase 19; may start here
        ↓
100K records
        ↓
500K records
        ↓
1M records
        ↓
5M records
        ↓
10M+ records
        ↓
Re-run concurrent-user testing at each data stage
        ↓
Enterprise benchmark
```

---

# 2. Overall Test Phases

| Phase | Objective |
|---|---|
| Phase 1 | Prepare ERPNext v16 test environment |
| Phase 2 | Design 35-company enterprise structure |
| Phase 3 | Create organizational structure |
| Phase 4 | Create master data |
| Phase 5 | Validate accounting |
| Phase 6 | Validate sales |
| Phase 7 | Validate purchase |
| Phase 8 | Validate inventory |
| Phase 9 | Validate manufacturing |
| Phase 10 | Validate inter-company transactions |
| Phase 11 | Validate financial and operational reports |
| Phase 12 | Generate large-scale data |
| Phase 13 | Performance testing |
| Phase 14 | Concurrent-user testing (desk mix; see §22 Phase 19 — may start after Stage 1) |
| Phase 15 | Month-end / year-end stress testing |
| Phase 16 | Backup / restore / recovery |
| Phase 17 | Compare against Oracle EBS / SAP requirements |
| Phase 18 | Final enterprise feasibility report |

---

# 3. Phase 1 — Prepare ERPNext v16 Environment

## 3.1 Create a Dedicated Test Server

Initial benchmark server:

```text
CPU:        16–24 cores
RAM:        64 GB
Storage:    500 GB – 1 TB SSD/NVMe
Database:   MariaDB
OS:         Ubuntu Linux
ERPNext:    v16
```

This is an initial benchmark environment. The final production architecture should be decided after the test results.

## 3.2 Install

Install:

```text
Frappe v16
ERPNext v16
HRMS v16 (if HR is part of the final scope)
```

Create a dedicated site, for example:

```text
erp-scale-test.local
```

## 3.3 Record the Baseline

Before creating data, record:

```text
CPU
RAM
Disk size
Disk IOPS
MariaDB version
Frappe version
ERPNext version
Python version
Node version
Redis version
Number of workers
Number of background workers
```

This information must remain in the benchmark documentation.

---

# 4. Phase 2 — Design the 35-Company Structure

Do not create 35 identical companies.

Build a realistic enterprise group.

Example:

```text
GLOBAL HOLDING GROUP
│
├── Company 01 - Manufacturing
├── Company 02 - Manufacturing
├── Company 03 - Manufacturing
├── Company 04 - Manufacturing
├── Company 05 - Manufacturing
│
├── Company 06 - Distribution
├── Company 07 - Distribution
├── Company 08 - Distribution
│
├── Company 09 - Trading
├── Company 10 - Trading
│
├── Company 11 - Services
│
├── ...
│
└── Company 35
```

The exact business types should eventually be based on the real Oracle EBS/SAP customer.

## 4.1 Company Categories

Recommended initial distribution:

```text
15 Manufacturing
10 Distribution / Trading
5 Service
5 Other / Holding / Support entities
```

This is only a test model. Replace it with the client's actual organizational structure when available.

## 4.2 Group Company

Create:

```text
Global Holding Group
    Is Group = Yes
```

Then create the 35 child companies.

## 4.3 First Validation

Before moving forward, verify:

- All 35 companies exist
- Parent/child relationship works
- Each company has correct accounting configuration
- Company-specific transactions work
- Company selection works
- Users can be restricted by company
- Group-level reporting works

---

# 5. Phase 3 — Organizational Structure

Create realistic warehouses, branches, cost centers and accounting dimensions.

## 5.1 Warehouse Structure

Example:

```text
Company 01
│
├── Factory 01
│   ├── Raw Material
│   ├── WIP
│   ├── Finished Goods
│   ├── Scrap
│   └── Rejected
│
└── Distribution
    ├── Main Warehouse
    ├── Transit
    └── Returns
```

## 5.2 Initial Quantity

Start with approximately:

```text
35 Companies
150–300 Warehouses
300–500 Cost Centers
```

Do not start with thousands of warehouses.

## 5.3 Accounting Dimensions

Test dimensions such as:

```text
Company
Branch
Department
Business Unit
Region
Cost Center
Project
Product Line
```

Determine which should be:

- Company
- Branch
- Warehouse
- Cost Center
- Accounting Dimension
- Project

Do not create a separate Company for every operational unit.

---

# 6. Phase 4 — Master Data

Create an initial realistic dataset.

## 6.1 Initial Master Data

```text
Items                 10,000
Customers              5,000
Suppliers              2,000
Warehouses               300
Cost Centers             500
Employees              1,000
BOMs                   1,000
Assets                 1,000
Projects               1,000
```

## 6.2 Shared vs Company-Specific Data

Test both scenarios.

Examples:

```text
Shared Item
    ↓
Used by Company 01
Used by Company 02
Used by Company 03
```

and:

```text
Company-specific customer
Company-specific supplier
Company-specific warehouse
Company-specific price
```

The final data model should reflect the actual business.

---

# 7. Phase 5 — Accounting Functional Test

Before creating huge data volumes, manually test the complete accounting cycle.

## 7.1 Sales Accounting

```text
Customer
   ↓
Sales Order
   ↓
Delivery Note
   ↓
Sales Invoice
   ↓
Payment Entry
```

Verify:

```text
Accounts Receivable
GL Entry
Customer Outstanding
Payment Ledger
Stock Ledger
COGS
```

## 7.2 Purchase Accounting

```text
Supplier
   ↓
Purchase Order
   ↓
Purchase Receipt
   ↓
Purchase Invoice
   ↓
Payment Entry
```

Verify:

```text
Accounts Payable
GL Entry
Supplier Outstanding
Payment Ledger
Stock Ledger
Inventory Value
```

## 7.3 Journal Entry

Test:

```text
Manual Journal
Adjustment
Accrual
Reversal
Inter-company Journal
Opening Entry
```

---

# 8. Phase 6 — Sales Testing

Run the complete sales cycle:

```text
Quotation
    ↓
Sales Order
    ↓
Delivery Note
    ↓
Sales Invoice
    ↓
Payment Entry
```

Test:

- Partial delivery
- Multiple deliveries
- Partial invoice
- Multiple invoices
- Partial payment
- Advance payment
- Returns
- Credit notes
- Cancellation
- Amendment

## 8.1 Initial Volume

Start with:

```text
Quotations          10,000
Sales Orders        10,000
Delivery Notes      10,000
Sales Invoices      10,000
Payments             8,000
```

Then increase progressively.

---

# 9. Phase 7 — Purchase Testing

Run:

```text
Material Request
    ↓
RFQ
    ↓
Supplier Quotation
    ↓
Purchase Order
    ↓
Purchase Receipt
    ↓
Purchase Invoice
    ↓
Payment
```

Test:

- Partial receipt
- Partial invoice
- Multiple receipts
- Multiple invoices
- Returns
- Supplier credit
- Cancellation
- Amendments
- Price changes
- Taxes

Initial volume:

```text
Material Requests       5,000
RFQs                    2,000
Supplier Quotations     5,000
Purchase Orders        10,000
Purchase Receipts       8,000
Purchase Invoices      10,000
Payments                8,000
```

---

# 10. Phase 8 — Inventory Testing

Inventory is one of the most important scalability areas.

## 10.1 Transactions

Test:

```text
Opening Stock
Purchase Receipt
Delivery Note
Material Receipt
Material Issue
Material Transfer
Stock Reconciliation
Manufacturing Consumption
Manufacturing Production
Sales Return
Purchase Return
```

## 10.2 Initial Volume

Start with approximately:

```text
100,000 Stock Ledger Entries
```

Then increase:

```text
100K
500K
1M
5M
10M+
```

## 10.3 Batch and Serial Testing

Create:

```text
Batch-controlled Items
Serial-controlled Items
```

Test:

```text
Purchase
Transfer
Manufacturing
Sales
Returns
Reconciliation
Traceability
```

Important questions:

```text
Where is Batch X?

Which customer received Batch X?

Which warehouse contains Batch X?

Which raw-material batch was used in Finished Product Y?
```

---

# 11. Phase 9 — Manufacturing Testing

Select several companies as manufacturing companies.

Start with:

```text
Items                 1,000
BOMs                    200
Operations              100
Workstations             50
Work Orders              100
Job Cards                500
```

## 11.1 Manufacturing Flow

```text
Sales Order
    ↓
Production Plan
    ↓
Work Order
    ↓
Material Transfer
    ↓
Job Card
    ↓
Material Consumption
    ↓
Manufacture
    ↓
Finished Goods
```

## 11.2 Manufacturing Scenarios

Test:

- Single-level BOM
- Multi-level BOM
- Large BOM
- Sub-assembly
- Scrap
- By-product
- Partial production
- Rework
- Overproduction
- Production cancellation
- Material shortage
- Alternative components

## 11.3 Costing

Compare:

```text
BOM expected cost
        ↓
Work Order expected cost
        ↓
Actual production cost
        ↓
Inventory valuation
        ↓
COGS
        ↓
GL
```

---

# 12. Phase 10 — Inter-Company Testing

This is mandatory for a 35-company ERP.

Start with:

```text
Company 01 → Company 02
Company 01 → Company 03
Company 02 → Company 04
```

Test:

```text
Inter-company Sales
Inter-company Purchase
Inter-company Journal Entry
Inter-company Receivable
Inter-company Payable
```

## 12.1 Example

```text
Company 01
    Sales
       ↓
Company 02
    Purchase
```

Verify:

```text
Company 01:
Receivable
Revenue

Company 02:
Payable
Purchase / Inventory
```

Then scale to all 35 companies.

---

# 13. Phase 11 — Multi-Currency

Create currencies such as:

```text
BDT
USD
EUR
GBP
INR
AED
SGD
CNY
JPY
```

Test:

```text
Foreign Currency Sales
Foreign Currency Purchase
Foreign Currency Bank
Inter-company Currency
Exchange Gain/Loss
Currency Revaluation
```

Verify:

```text
Transaction Currency
Company Base Currency
GL
AR/AP
Exchange Difference
Financial Reports
```

---

# 14. Phase 12 — Fixed Assets

Create:

```text
1,000 Assets
```

Then progressively increase.

Test:

```text
Asset Purchase
Capitalization
Depreciation
Monthly Depreciation
Asset Transfer
Asset Sale
Asset Scrapping
Asset Maintenance
```

Verify:

```text
Asset Register
Depreciation
GL
Balance Sheet
Asset Value
```

---

# 15. Phase 13 — Financial Reports

First test standard reports with small data.

## Accounting

Test:

```text
General Ledger
Trial Balance
Balance Sheet
Profit & Loss
Cash Flow
Accounts Receivable
Accounts Payable
Payment Ledger
Sales Register
Purchase Register
```

## Inventory

Test:

```text
Stock Balance
Stock Ledger
Stock Ageing
Stock Value
Warehouse-wise Stock
Item-wise Stock
Batch-wise Stock
Serial-wise Stock
Inventory Valuation
```

## Sales

Test:

```text
Sales Register
Customer Sales
Item Sales
Sales Order Outstanding
Delivery Outstanding
Invoice Outstanding
Returns
Credit Notes
```

## Purchase

Test:

```text
Purchase Register
Supplier Purchase
Item Purchase
PO Outstanding
Receipt Outstanding
Invoice Outstanding
Supplier Ageing
```

## Manufacturing

Test:

```text
Production Plan
Work Order Status
Material Consumption
Production Cost
BOM Cost
WIP
Scrap
Production Variance
```

---

# 16. Phase 14 — Group Consolidation Testing

Test:

```text
Company 01
Company 02
...
Company 35
        ↓
Group Consolidation
```

Run:

```text
Consolidated P&L
Consolidated Balance Sheet
Group Cash Flow
Inter-company Balances
```

Also test:

```text
Inter-company Revenue
Inter-company Receivable
Inter-company Payable
Inter-company Expense
Elimination requirements
```

Important:

The client's actual Oracle EBS/SAP consolidation rules must be documented separately. Standard ERPNext consolidation may not automatically reproduce every custom elimination/accounting rule used by the existing ERP.

---

# 17. Phase 15 — User and Security Testing

Create approximately:

```text
100 users initially
```

For the concurrent desk-mix runs in §22 Phase 19, create the named `perf_*` users (sales / purchase / stock / accounts / mfg / report) with the role mix described there. Security tests below still apply to those users.

Then later:

```text
200
300
500
```

Roles:

```text
CEO
Group CFO
Company CFO
Finance Manager
Accountant
Purchase Manager
Purchase User
Sales Manager
Sales User
Warehouse Manager
Warehouse User
Production Manager
Production Planner
Production User
Auditor
```

Test company-level access.

Example:

```text
Company CFO 01
    → Company 01 only

Company CFO 02
    → Company 02 only

Group CFO
    → All companies
```

Verify:

- Company visibility
- Customer visibility
- Supplier visibility
- Warehouse visibility
- GL visibility
- Invoice access
- Report access
- Submit permissions
- Cancel permissions
- Consolidated report access

---

# 18. Phase 16 — Generate Large Data

Only after the functional environment works correctly should large-scale data generation begin.

## Level 1

```text
100K records
```

## Level 2

```text
500K records
```

## Level 3

```text
1M records
```

## Level 4

```text
5M records
```

## Level 5

```text
10M records
```

## Level 6

```text
20M+ records
```

Do not simply create random records.

Create realistic document chains.

Example:

```text
100,000 Sales Orders
        ↓
80,000 Deliveries
        ↓
75,000 Sales Invoices
        ↓
65,000 Payments
        ↓
Millions of GL / Stock / Payment Ledger rows
```

---

# 19. Recommended Large-Scale Dataset

Eventually target approximately:

```text
Customers                 100,000+
Suppliers                  50,000+
Items                      50,000+
Warehouses                  1,000+
Employees                  10,000+
BOMs                       10,000+
Assets                     50,000+

Sales Orders              1,000,000
Sales Invoices             800,000
Purchase Orders            500,000
Purchase Invoices          500,000
Payments                   500,000+
Journal Entries            500,000+
Work Orders                250,000
Job Cards                1,000,000

GL Entries                10M+
Stock Ledger Entries      10M+
```

These are benchmark targets, not assumptions about the client's actual volumes.

---

# 20. Phase 17 — Create a Data Generator

Create a dedicated Frappe app:

```text
fusion_erp_scale_test
```

Suggested structure:

```text
fusion_erp_scale_test/
│
├── generators/
│   ├── company.py
│   ├── customer.py
│   ├── supplier.py
│   ├── item.py
│   ├── warehouse.py
│   ├── sales.py
│   ├── purchase.py
│   ├── inventory.py
│   ├── accounting.py
│   ├── manufacturing.py
│   └── intercompany.py
│
├── scenarios/
│   ├── sales_cycle.py
│   ├── purchase_cycle.py
│   ├── manufacturing_cycle.py
│   ├── intercompany_cycle.py
│   └── month_end.py
│
├── reports/
│   ├── benchmark.py
│   └── reconciliation.py
│
└── fixtures/
    └── enterprise_config.json
```

Use deterministic data generation.

Example:

```text
Seed = 1001
```

This allows the same benchmark to be reproduced.

---

# 21. Phase 18 — Performance Benchmark

For every test, record:

```text
Start Time
End Time
Execution Time
CPU
RAM
Disk I/O
Database Size
MariaDB Connections
Slow Queries
Locks
Deadlocks
Queue Length
Worker Usage
Error Count
```

Create a benchmark table:

| Operation | 100K | 500K | 1M | 5M | 10M |
|---|---:|---:|---:|---:|---:|
| Sales Invoice Submit | | | | | |
| Purchase Invoice Submit | | | | | |
| Stock Entry | | | | | |
| GL Report | | | | | |
| Stock Balance | | | | | |
| Stock Ledger | | | | | |
| P&L | | | | | |
| Balance Sheet | | | | | |
| AR Ageing | | | | | |
| AP Ageing | | | | | |
| Consolidated P&L | | | | | |

---

# 22. Phase 19 — Concurrent User Testing

**Primary target:** validate how Frappe / ERPNext Desk behaves under **~100 simultaneous users** with a **realistic desk mix** (list views, forms, saves/submits, and reports) — not API-only throughput.

Concurrent testing may start after **Stage 1 functional** (see §31) is working for at least one company. It does **not** require 10M rows first. Re-run the same mix later at 100K / 1M / 10M+ data volumes.

Higher concurrency (200 / 300 / 500) is optional after 100 users pass SLOs.

---

## 22.1 Prerequisites

Before any concurrent run:

### Functional readiness

- Stage 1 functional paths work for Desk: Sales Order → Delivery → Sales Invoice; Purchase Order → Purchase Receipt → Purchase Invoice; Stock Entry; Payment Entry / Journal Entry; at least one Work Order / BOM path if Manufacturing is in scope
- Enough master data for concurrent writes without collisions (customers, items, warehouses, suppliers) — Stage 1 volumes are enough for the first 100-user run

### Test users (~100)

Create named users with realistic roles (align with §17 Phase 15). Naming convention:

```text
perf_sales_01   … perf_sales_25
perf_purchase_01 … perf_purchase_15
perf_stock_01    … perf_stock_15
perf_accounts_01 … perf_accounts_20
perf_mfg_01      … perf_mfg_10
perf_report_01   … perf_report_15
```

Roles (minimum):

```text
Sales User / Sales Manager
Purchase User / Purchase Manager
Stock User / Stock Manager
Accounts User / Accounts Manager
Manufacturing User / Manufacturing Manager
Report Viewer / System Manager (read-heavy managers)
```

Shared passwords or API keys are for **later automation** only. This phase documents the manual / metric protocol first.

### Environment baseline (record every run)

Copy these fields into the run log before starting:

```text
Site name
Frappe / ERPNext version
MariaDB version
gunicorn_workers
background_workers
developer_mode (on/off)
webserver_port
Redis cache / queue endpoints
CPU cores / RAM / disk type
```

Example bench baseline (update if config changes):

```text
Site:                 performance
gunicorn_workers:     17
background_workers:   1
developer_mode:       1
webserver_port:       8006
```

**Important:** results with `developer_mode = 1` and a single background worker are a **bench baseline**, not a production / enterprise claim. Label every report accordingly.

### Reduce noise during the run

```text
bench --site <site> set-config pause_scheduler 1
```

Keep Redis and MariaDB monitoring ready. Do not change worker counts mid-run.

---

## 22.2 Realistic desk mix (100 concurrent users)

Fixed percentage mix (sums to 100). Scale the same percentages at 10 / 25 / 50 users.

| Persona | % of users | Concurrent at 100 | Primary Desk actions |
|---|---:|---:|---|
| Sales User | 25% | 25 | List Sales Order → open form → new Quotation / Sales Order → Delivery Note / Sales Invoice where allowed |
| Purchase User | 15% | 15 | List Purchase Order → new PO → Purchase Receipt / Purchase Invoice |
| Stock User | 15% | 15 | Stock Entry (Material Transfer / Issue / Receipt) → Stock Balance → Stock Ledger |
| Accounts User | 20% | 20 | Payment Entry → Journal Entry → GL / AR / AP list views |
| Manufacturing User | 10% | 10 | Work Order list → Job Card → BOM view |
| Report / Manager | 15% | 15 | Profit and Loss → Trial Balance → Stock Balance → Sales Register (read-heavy) |

### Overall read vs write

Inside the mix: **~40% mutating** (save / submit), **~60% read** (list / open form / report). This is closer to real ERP desks than “everyone submits invoices.”

### Virtual-user action loop

Think time: **3–8 seconds** between actions.

```text
1. Login (or reuse session)
2. Desk home / module page
3. List view (apply one filter; paginate once)
4. Open 1 document
5. Per persona: read-only report/list OR save/submit
6. ~5% of loops: logout + re-login (session / auth stress)
```

### Persona-specific loops (detail)

**Sales User**

```text
Login → Selling → Sales Order list → open SO
→ (40%) new Quotation or Sales Order → Save → (subset) Submit
→ (30%) Delivery Note or Sales Invoice from order where stock/AR allows
→ (30%) list-only / open Customer
```

**Purchase User**

```text
Login → Buying → Purchase Order list → open PO
→ (40%) new Purchase Order → Save → Submit
→ (30%) Purchase Receipt or Purchase Invoice
→ (30%) list-only / open Supplier
```

**Stock User**

```text
Login → Stock → Stock Entry list
→ (40%) new Stock Entry → Save → Submit
→ (30%) Stock Balance report
→ (30%) Stock Ledger report
```

**Accounts User**

```text
Login → Accounting
→ (35%) Payment Entry → Save → Submit
→ (25%) Journal Entry → Save → Submit
→ (40%) General Ledger / Accounts Receivable / Accounts Payable views
```

**Manufacturing User**

```text
Login → Manufacturing → Work Order list → open WO
→ (40%) Job Card list / open
→ (30%) BOM list / open
→ (30%) Work Order status only
```

**Report / Manager**

```text
Login → run (rotate):
  Profit and Loss (one company, current period)
  Trial Balance
  Stock Balance
  Sales Register
→ open Desk home between reports
```

---

## 22.3 Ramp schedule

Do **not** jump straight to 100 users. Stop and document if error rate or P95 fails SLOs at an earlier step.

```text
Warm-up:     5 users × 5 min
Step 1:     10 users × 10 min
Step 2:     25 users × 10 min
Step 3:     50 users × 15 min
Step 4:    100 users × 20 min   ← primary target
Cool-down:   stop load; wait until RQ queues return near-empty
```

Optional later (only if Step 4 passes):

```text
200 / 300 / 500 users — same desk mix percentages
```

If SLOs fail at 50 but pass at 25, record **max sustainable concurrent users** as the PoC result. That is a valid outcome.

---

## 22.4 Metrics (per ramp step)

### Client / UX

```text
Login time
List view TTFB / full load
Form open time
Document save time
Document submit time
Report run time (P&L, Stock Balance, GL)
```

Record **avg, P50, P95, P99** for each action class: login, list, form open, save, submit, report.

### Server

```text
CPU %
RAM %
Disk I/O
Gunicorn busy workers / request queue
MariaDB connections
Slow queries
Lock waits / deadlocks
Redis latency
RQ queue length / worker backlog
HTTP 4xx / 5xx rate
Frappe Error Log rate
```

### Evidence to capture

```text
Desk screenshots at peak (list + one submit + one report)
bench doctor
MariaDB: SHOW PROCESSLIST; (and lock/status if available)
Slow query log excerpt (if enabled)
sites/<site>/logs and Error Log DocType samples
Timestamped notes for start / end of each ramp step
```

---

## 22.5 Pass / fail SLOs (100 concurrent, Stage 1 data)

Initial acceptance bar for the **100-user / 20-min** step at Stage 1 data volume. Tune after the first baseline run, but do not loosen silently — document any change.

| Metric | Pass criterion |
|---|---|
| Error rate (5xx + unhandled Desk errors) | &lt; 1% |
| Login P95 | &lt; 3s |
| List / form open P95 | &lt; 2s |
| Document save P95 | &lt; 3s |
| Document submit P95 | &lt; 5s (flag Stock Entry / Invoice separately if higher) |
| Report P95 (one company, current period) | &lt; 10s |
| MariaDB deadlocks | No sustained deadlocks; investigate lock-wait spikes |
| RQ backlog after cool-down | Near-zero within 5 minutes |
| Spot reconciliation (AR / AP / stock sample) | No integrity failures |

**Step result:** Pass only if all rows above pass for that ramp step. Partial pass = record max sustainable concurrency.

---

## 22.6 Results template

Fill one row per ramp step. Attach evidence paths in the run folder.

| Step | Users | Duration | Error% | Login P95 | List P95 | Submit P95 | Report P95 | CPU% | DB locks | Pass? |
|---|---:|---|---:|---:|---:|---:|---:|---:|---|---|
| Warm-up | 5 | 5 min | | | | | | | | |
| Step 1 | 10 | 10 min | | | | | | | | |
| Step 2 | 25 | 10 min | | | | | | | | |
| Step 3 | 50 | 15 min | | | | | | | | |
| Step 4 | 100 | 20 min | | | | | | | | |
| Cool-down | 0 | until queues clear | | | | | | | | |

Run header (copy per run):

```text
Run ID:
Date / time:
Site:
Data stage:          Stage 1 / 100K / 500K / 1M / …
Labeled as:          bench baseline / production-like
Max sustainable CU:
Notes:
```

---

## 22.7 Locust automation (site `performance`)

Desk-mix Locust lives in this app:

```text
apps/performance_testing/locustfile.py
apps/performance_testing/loadtest/
apps/performance_testing/scripts/run_ramp.sh
```

### Setup

```bash
./env/bin/pip install -r apps/performance_testing/requirements-loadtest.txt
bench --site performance execute performance_testing.setup.seed_loadtest.seed
```

Seed creates:

```text
20 customers (PERF-CUST-*)
10 suppliers (PERF-SUPP-*)
20 items (PERF-ITEM-*)
100 users (perf_{persona}_NN@example.com) + API keys → loadtest/users.json
```

### Run

```bash
# UI
cd apps/performance_testing
../../env/bin/locust -f locustfile.py --host http://127.0.0.1:8006

# Full Phase 19 ramp (headless)
./scripts/run_ramp.sh
```

Host header is forced to `performance` (see `PERF_SITE_HOST`). Auth uses API tokens from `users.json` (Desk CSRF still loaded for form saves).

### Still out of scope

- Full Playwright browser chrome at 100 users
- 35-company / multi-million-row concurrent runs (re-use this mix at later data stages)
- Month-end stress with concurrent users (see Phase 20)

---

# 23. Phase 20 — Month-End Stress Test

This is one of the most important enterprise tests.

Simulate:

```text
Normal daily transactions
+
Payroll
+
Depreciation
+
Payment processing
+
Bank reconciliation
+
Stock reconciliation
+
GL reports
+
AR ageing
+
AP ageing
+
P&L
+
Balance Sheet
+
Consolidation
```

All at the same time.

The question is:

> Can normal users continue working while month-end processes and heavy reports are running?

---

# 24. Phase 21 — Year-End Test

Simulate:

```text
Fiscal Year Closing
Opening Balances
Retained Earnings
Asset Depreciation
AR/AP
Inventory Valuation
Stock Closing
GL Closing
Consolidation
```

Test historical data as well.

Use multiple years:

```text
2020
2021
2022
2023
2024
2025
2026
```

Then test:

```text
Current Year Reports
Multi-Year Reports
Comparative P&L
Historical GL
Historical Stock
Historical AR/AP
```

---

# 25. Phase 22 — Database Testing

Monitor the largest tables.

At minimum:

```text
tabGL Entry
tabStock Ledger Entry
tabPayment Ledger Entry
tabSales Invoice
tabSales Invoice Item
tabPurchase Invoice
tabPurchase Invoice Item
tabSales Order
tabSales Order Item
tabPurchase Order
tabPurchase Order Item
tabDelivery Note
tabDelivery Note Item
tabPurchase Receipt
tabPurchase Receipt Item
tabJournal Entry
tabJournal Entry Account
```

Record:

```text
Table Size
Index Size
Row Count
Query Time
Slow Queries
Lock Waits
Deadlocks
```

---

# 26. Phase 23 — Backup and Recovery

Test:

```text
Full Backup
Restore
MariaDB Restart
Redis Restart
Worker Restart
Server Restart
Failed Background Job
Interrupted Import
Database Recovery
```

Measure:

```text
Backup Time
Backup Size
Restore Time
Data Integrity
Downtime
Recovery Point
Recovery Time
```

---

# 27. Phase 24 — Data Integrity / Reconciliation

Create an automated reconciliation process.

## Sales

Verify:

```text
Sales Invoice
    ↓
AR
    ↓
Payment
    ↓
Payment Ledger
    ↓
GL
```

## Purchase

Verify:

```text
Purchase Invoice
    ↓
AP
    ↓
Payment
    ↓
Payment Ledger
    ↓
GL
```

## Inventory

Verify:

```text
Purchase / Manufacturing / Sales
    ↓
Stock Ledger
    ↓
Inventory Valuation
    ↓
COGS
    ↓
GL
```

## Inter-company

Verify:

```text
Company A Receivable
=
Company B Payable
```

Any mismatch must be recorded as a failed test.

---

# 28. Oracle EBS / SAP Comparison

Before the final PoC, obtain actual information from the existing Oracle EBS/SAP system.

Ask the client for:

## Organization

```text
Number of Legal Entities
Number of Operating Units
Number of Inventory Organizations
Number of Plants
Number of Warehouses
```

## Master Data

```text
Customers
Suppliers
Items
BOMs
Employees
Assets
```

## Annual Transactions

```text
Sales Orders/year
Sales Invoices/year
Purchase Orders/year
Purchase Invoices/year
Receipts/year
Payments/year
Stock Transactions/year
Journal Entries/year
Manufacturing Orders/year
```

## Database

```text
Oracle Database Size
Largest Tables
GL Rows
Inventory Transaction Rows
Historical Years
```

## Users

```text
Named Users
Average Concurrent Users
Peak Concurrent Users
Month-End Concurrent Users
```

## Reports

Ask:

> Which reports currently take more than 30 seconds in Oracle EBS/SAP?

These reports should become priority ERPNext benchmark reports.

---

# 29. Standard Reports to Compare

## Finance

```text
General Ledger
Trial Balance
Balance Sheet
Profit & Loss
Cash Flow
AR Ageing
AP Ageing
Bank Reconciliation
Budget vs Actual
Cost Center P&L
Project P&L
Inter-company Balance
```

## Sales

```text
Sales Register
Customer Sales
Item Sales
Sales by Company
Sales by Territory
Sales Order Outstanding
Delivery Outstanding
Invoice Outstanding
Returns
Credit Notes
Customer Profitability
```

## Purchase

```text
Purchase Register
Supplier Purchase
Item Purchase
PO Outstanding
Receipt Outstanding
Invoice Outstanding
Supplier Ageing
Purchase Price Variance
Supplier Performance
```

## Inventory

```text
Stock Balance
Stock Ledger
Stock Ageing
Stock Value
Warehouse-wise Stock
Item-wise Stock
Batch-wise Stock
Serial-wise Stock
Slow Moving Items
Fast Moving Items
Negative Stock
Inventory Valuation
```

## Manufacturing

```text
Production Plan
Work Order Status
Production Efficiency
Material Consumption
Production Cost
BOM Cost
WIP
Scrap
Rejection
Production Variance
```

---

# 30. Reports / Features That May Need Customization

Do not assume every Oracle EBS/SAP report has a direct ERPNext equivalent.

Evaluate requirements such as:

```text
Group Financial Dashboard
35-company Consolidated P&L
35-company Consolidated Balance Sheet
Inter-company Reconciliation
Inter-company Elimination
Group Cash Flow
Business Unit P&L
Profit Center Reporting
Advanced Management Reporting
Custom Regulatory Reports
Custom Tax Reports
Custom Operational KPIs
```

For each requirement, classify it:

```text
STANDARD
CONFIGURATION
CUSTOM REPORT
CUSTOM DOCTYPE
CUSTOM APP
EXTERNAL BI
```

Do not customize before confirming that standard ERPNext cannot meet the requirement.

---

# 31. Final Benchmark Progression

Use this exact progression.

## Stage 1 — Functional

```text
35 Companies
10K Items
5K Customers
2K Suppliers
300 Warehouses
```

Test all modules manually.

**Then run the first concurrent desk-mix test** (see §22 Phase 19): ramp 10 → 100 users against this Stage 1 dataset. Do not wait for Stage 6 / 10M rows.

---

## Stage 2 — Small Load

```text
100K transactional records
```

Test all standard reports.

---

## Stage 3 — Medium Load

```text
500K records
```

Repeat all tests.

---

## Stage 4 — Large Load

```text
1M records
```

Repeat all tests.

---

## Stage 5 — Very Large

```text
5M records
```

Repeat all tests.

---

## Stage 6 — Enterprise Scale

```text
10M+ ledger/transaction records
```

Run:

```text
Reports
Transactions
Consolidation
Inter-company
Manufacturing
Inventory
Concurrent users (re-run §22 Phase 19 desk mix at this volume)
```

---

## Stage 7 — Stress

```text
20M+ records
300–500 concurrent users
Month-end processing
Heavy reports
Background jobs
```

Only go beyond this if the client's actual requirements justify it.

---

# 32. Final Success Criteria

At the end, answer these questions.

### Functional

```text
Can all 35 companies operate independently?
Can they share required masters?
Can they perform inter-company transactions?
Can manufacturing operate correctly?
Can inventory remain accurate?
Can accounting remain accurate?
```

### Reporting

```text
Can company-level reports run correctly?
Can group reports run correctly?
Can consolidated financial statements run?
Can management reports run?
```

### Performance

```text
How fast are normal transactions?
How fast are reports?
What happens as data grows?
What happens at month-end?
```

### Scalability

```text
What happens at 100K?
What happens at 500K?
What happens at 1M?
What happens at 5M?
What happens at 10M+?
```

### Concurrency

```text
10 users?
50?
100?
200?
300?
500?
```

### Reliability

```text
Can backups be restored?
Can failed jobs recover?
Can the database recover?
Is data integrity maintained?
```

---

# 33. The First Things to Do Now

Do **only these tasks first**.

### Task 1

Prepare the ERPNext v16 test server.

### Task 2

Install a clean ERPNext v16 site.

### Task 3

Create:

```text
Global Holding Group
+
35 Companies
```

### Task 4

Create approximately:

```text
150–300 Warehouses
300–500 Cost Centers
```

### Task 5

Create:

```text
10,000 Items
5,000 Customers
2,000 Suppliers
```

### Task 6

Manually test:

```text
Sales
Purchase
Inventory
Accounting
Manufacturing
Inter-company
```

### Task 7

Run standard reports.

### Task 8

Record the baseline performance.

### Task 9 — First concurrent desk-mix test (§22 Phase 19)

After Tasks 1–8 work for at least one company (full 35-company set preferred):

```text
Create ~100 perf_* Desk users (roles per §22.2)
Pause scheduler for the run
Ramp: 5 → 10 → 25 → 50 → 100 concurrent users
Fill the §22.6 results table
Record max sustainable concurrent users if SLOs fail before 100
```

**Stop here for data scale-up.**

Do not generate 1 million records until these steps are working correctly. Re-run §22 Phase 19 at each later data stage (100K, 1M, 10M+).

---

# 34. After the First Milestone

Once the 35-company environment is working, the next development task should be:

```text
fusion_erp_scale_test
```

The app will generate realistic:

```text
Customers
Suppliers
Items
Sales
Purchases
Inventory
Accounting
Manufacturing
Inter-company transactions
```

and later automate:

```text
100K
500K
1M
5M
10M+
```

benchmarks.

The generator should also produce an automated reconciliation report so that increasing the data volume does not compromise accounting or stock integrity.

---

# Final Principle

The objective is **not**:

> "Can ERPNext create 1 million records?"

The real objective is:

> **Can ERPNext v16 operate a 35-company enterprise with realistic Oracle EBS/SAP-level business processes, large transaction volumes, consolidated reporting, inter-company accounting, manufacturing, inventory, and concurrent users while maintaining acceptable performance and data integrity?**

That is the question this PoC should answer.
