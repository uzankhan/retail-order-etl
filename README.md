# 🛒 Retail Order ETL Pipeline

An end-to-end ETL pipeline that ingests daily retail order CSVs from **AWS S3**, cleans and validates them in Python, and loads the results into a **private Amazon RDS PostgreSQL** database. Summary reports are published back to S3.

The entire pipeline runs on a **single EC2 instance** in a public subnet, with the database isolated in private subnets.

---

## 📌 Project Overview

Retail operations generate order data every day. This pipeline:

1. Extracts `orders.csv` from S3
2. Validates the data (quantities, prices, statuses)
3. Deduplicates by `order_id`
4. Calculates revenue per order
5. Loads clean rows into PostgreSQL
6. Writes daily sales, rejected rows, and metrics back to S3

---

## 🏗️ Architecture
S3 (raw/) ──▶ EC2 (Python) ──▶ RDS PostgreSQL (private)
│
▼
S3 (reports/)

---


- **EC2** uses an IAM role — no static AWS keys
- **RDS** is not publicly accessible; only the EC2 security group can reach it
- **S3** access from private subnet goes through a VPC gateway endpoint

---

## 🛠️ Tech Stack

| Layer | Technology |
| :--- | :--- |
| Cloud | AWS (VPC, EC2, S3, RDS, IAM) |
| Database | PostgreSQL 15 (RDS) |
| Language | Python 3.11 |
| Libraries | boto3, pandas, psycopg2 |
| OS | Amazon Linux 2023 |

---

## 📁 Project Structure
retail-order-etl/
├── pipeline.py # Main ETL pipeline
├── setup_db.py # DB + user bootstrap script
├── schema.sql # Table schema & indexes
├── requirements.txt # Python dependencies
├── data/
│ └── orders.csv # Sample input
├── docs/
│ └── architecture.md # Detailed architecture
├── .gitignore
├── LICENSE
└── README.md

---

## 🔄 Data Flow

1. **Extract** — `boto3` downloads `raw/YYYY-MM-DD/orders.csv`
2. **Transform** — pandas:
   - Drops duplicates on `order_id`
   - Rejects `quantity <= 0` or `unit_price <= 0`
   - Enforces allowed `status` values
   - Computes `revenue = quantity * unit_price`
3. **Load** — inserts into `lab.orders` via `psycopg2`
4. **Report** — publishes to `s3://.../reports/YYYY-MM-DD/`:
   - `daily_sales.csv`
   - `rejected_orders.csv`
   - `metrics.json`
   - `_SUCCESS.json`

---

## 🧩 Database Schema

**Table:** `lab.orders`

| Column | Type | Notes |
| :--- | :--- | :--- |
| order_id | VARCHAR(50) | Primary key |
| order_date | DATE | |
| city | VARCHAR(100) | |
| category | VARCHAR(100) | |
| quantity | INT | CHECK > 0 |
| unit_price | DECIMAL(10,2) | CHECK > 0 |
| status | VARCHAR(50) | |
| revenue | DECIMAL(12,2) | quantity × unit_price |
| loaded_at | TIMESTAMP | Defaults to now |

Indexes on `order_date`, `category`, `status`.

---

## 🚀 Setup

### Prerequisites

- AWS account with VPC, EC2, S3, RDS, IAM
- RDS PostgreSQL (private subnets)
- EC2 instance with `retail-etl-role` attached

### 1. Clone

```bash
git clone https://github.com/<your-username>/retail-order-etl.git
cd retail-order-etl

2. Python environment
bash
sudo dnf install -y python3.11 python3.11-pip
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
3. RDS certificate
bash
curl -L https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem -o global-bundle.pem
4. Environment variables
bash
export PGHOST='<your-rds-endpoint>'
export PGDATABASE='retail'
export PGUSER='sales_etl'
export PGSSLROOTCERT="$PWD/global-bundle.pem"
5. Create database & user
bash
# Run once as master user
export PGDATABASE='postgres'
export PGUSER='lab_admin'
python setup_db.py
6. Upload CSV to S3
bash
aws s3 cp data/orders.csv s3://<bucket>/raw/2026-10-03/orders.csv
7. Run pipeline
bash
export PGDATABASE='retail'
export PGUSER='sales_etl'
python pipeline.py --bucket <bucket> --region us-east-1 --batch-date 2026-10-03
📊 Expected Output
json
{
  "input_rows": 13,
  "accepted_rows": 7,
  "rejected_rows": 6,
  "duplicate_rows": 1,
  "database_rows": 7,
  "database_revenue_pkr": "18000.00"
}
🔐 Security
EC2 uses an IAM role — no static keys in code

RDS not publicly accessible

TLS enforced (sslmode=verify-full)

Secrets kept out of git via .gitignore

📈 Reporting
daily_sales.csv:

order_date	category	status	total_orders	total_quantity	total_revenue
metrics.json — row counts and total revenue.

🧠 Lessons Learned
Building a secure private RDS deployment

Using IAM roles instead of access keys

Enforcing data quality at the ETL boundary

Publishing run metadata for observability

Writing idempotent loads with ON CONFLICT

👨‍💻 Author
Uzan Khan — Cloud Data Engineering, SMIT Batch 2

📄 License
MIT

---