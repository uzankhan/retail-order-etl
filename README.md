# Retail Order ETL Pipeline

An end-to-end ETL solution that ingests daily retail order CSV files from Amazon S3, validates and cleans the records in Python, loads the transformed data into a private Amazon RDS PostgreSQL instance, and publishes summary reports back to S3. The design follows cloud-native best practices with IAM role-based access, private database networking, and TLS-encrypted connectivity.

## Overview

Retail order data is generated daily and must flow through a reliable, auditable pipeline with data quality checks before landing in the warehouse. This project demonstrates a production-oriented ETL flow for:

- Extracting raw order files from S3
- Validating business rules and rejecting bad records
- Deduplicating repeated orders by `order_id`
- Calculating revenue for each order
- Loading clean data to PostgreSQL
- Publishing operational reports to S3

## Architecture

```text
S3 (raw/) ──▶ EC2 instance (Python ETL) ──▶ Private RDS PostgreSQL
      │                                      │
      └─────────────▶ Reports published to S3 (reports/) ───────┘
```

### Key design decisions

- EC2 instance uses an IAM role instead of hard-coded AWS credentials
- RDS is placed in private subnets and is not publicly reachable
- S3 access is routed through a VPC gateway endpoint
- PostgreSQL connections use TLS with `sslmode=verify-full`
- Data is validated before load to reduce downstream quality issues

## Tech Stack

| Layer | Technology |
| --- | --- |
| Cloud | AWS (S3, EC2, VPC, RDS, IAM) |
| Database | PostgreSQL 15 (Amazon RDS) |
| Language | Python 3.11 |
| ETL libraries | boto3, pandas, psycopg2-binary |
| OS | Amazon Linux 2023 |

## Features

- Automated daily extraction of `orders.csv` from S3
- Validation for:
  - positive `quantity`
  - positive `unit_price`
  - valid order status values
- Deduplication by `order_id`
- Revenue calculation: `quantity * unit_price`
- Row-level rejection tracking for bad records
- PostgreSQL data load with idempotent inserts
- Output report generation to S3:
  - `daily_sales.csv`
  - `rejected_orders.csv`
  - `metrics.json`
  - `_SUCCESS.json`

## Project Structure

```text
retail-order-etl/
├── pipeline.py              # Main ETL workflow
├── setup-db.py              # Database bootstrap for users and permissions
├── shema.sql                # SQL schema definition
├── requirements.txt         # Python dependencies
├── data/
│   └── orders.csv           # Sample retail data file
├── docs/
│   └── architecture.md      # Architecture notes
├── .gitignore
├── LICENSE
├── README.md
└── global-bundle.pem        # Downloaded RDS certificate (generated locally)
```

## Data Flow

1. Extract raw input file from `s3://<bucket>/raw/<batch_date>/orders.csv`
2. Read data into a Pandas DataFrame
3. Remove duplicate `order_id` values
4. Reject invalid rows based on defined business rules
5. Calculate `revenue = quantity * unit_price`
6. Insert clean records into `lab.orders`
7. Save aggregate and rejected outputs into `reports/<batch_date>/`

## Database Schema

The project stores cleaned orders in the `lab.orders` table.

| Column | Type | Description |
| --- | --- | --- |
| `order_id` | `VARCHAR(50)` | Primary key |
| `order_date` | `DATE` | Order creation date |
| `city` | `VARCHAR(100)` | Customer city |
| `category` | `VARCHAR(100)` | Product category |
| `quantity` | `INT` | Quantity sold |
| `unit_price` | `DECIMAL(10,2)` | Unit price |
| `status` | `VARCHAR(50)` | Order status |
| `revenue` | `DECIMAL(12,2)` | Computed order revenue |
| `loaded_at` | `TIMESTAMP` | Ingestion timestamp |

## Prerequisites

Before running this project, you need:

- An AWS account
- An EC2 instance with networking configured
- An S3 bucket for raw input and report output
- An Amazon RDS PostgreSQL instance in a private subnet
- IAM permissions for S3 and RDS access
- Python 3.11 or later

## Setup Instructions

### 1. Clone the repository

```bash
git clone https://github.com/<your-username>/retail-order-etl.git
cd retail-order-etl
```

### 2. Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Download the AWS RDS certificate

```bash
curl -L https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem -o global-bundle.pem
```

### 4. Configure environment variables

```bash
export PGHOST='<your-rds-endpoint>'
export PGPORT='5432'
export PGDATABASE='retail'
export PGUSER='sales_etl'
export PGPASSWORD='<your-db-password>'
export PGSSLROOTCERT="$PWD/global-bundle.pem"
```

### 5. Create the database and ETL user

Run the database bootstrap script once, using the RDS master/admin connection:

```bash
export PGDATABASE='postgres'
export PGUSER='lab_admin'
python setup-db.py
```

This script creates the `sales_etl` user, initializes the `lab` schema, creates the `lab.orders` table, and grants required permissions.

### 6. Upload sample input to S3

```bash
aws s3 cp data/orders.csv s3://<your-bucket>/raw/2026-10-03/orders.csv
```

### 7. Run the ETL pipeline

```bash
export PGDATABASE='retail'
export PGUSER='sales_etl'
python pipeline.py --bucket <your-bucket> --region us-east-1 --batch-date 2026-10-03
```

## Expected Output

The pipeline produces a summary metrics payload similar to:

```json
{
  "input_rows": 13,
  "accepted_rows": 7,
  "rejected_rows": 6,
  "duplicate_rows": 1,
  "database_rows": 7,
  "database_revenue_pkr": "18000.00"
}
```

The ETL also writes reports to S3 under:

```text
s3://<your-bucket>/reports/<batch-date>/
```

Files include:

- `daily_sales.csv`
- `rejected_orders.csv`
- `metrics.json`
- `_SUCCESS.json`

## Security

This project emphasizes secure cloud architecture:

- EC2 instance uses an IAM role; no static AWS keys are required
- RDS is not publicly exposed
- Database traffic is encrypted with TLS
- Secrets and local-generated certificates stay outside source control
- Network access is restricted to the minimum required path

## Operational Notes

The project is designed for batch ETL execution. It supports repeated daily runs, and records are inserted with `ON CONFLICT DO NOTHING` semantics to avoid duplicate writes for reprocessing the same order IDs.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.

## Author

Uzan Khan

## Contributing

Contributions are welcome. If you want to improve the pipeline, add validation rules, or extend the reporting model, please open a pull request with a clear description of the change.

---

Built for secure, auditable retail data processing in AWS.
