# Architecture

## Overview

The retail-order-etl pipeline loads daily order CSVs from S3 into a private RDS PostgreSQL database, applies data quality rules, and publishes summary reports back to S3.

## Components

- **S3 bucket** — stores raw CSVs and report outputs
- **EC2 instance** — runs the Python pipeline (public subnet)
- **RDS PostgreSQL** — stores cleaned data (private subnet)
- **VPC endpoints** — S3 gateway endpoint for private S3 access
- **IAM role** — attaches to EC2 to grant S3 access (no static keys)

## Network Layout

- `retail-lab-vpc` (10.0.0.0/16)
  - `retail-public-a` — EC2 host
  - `retail-private-a` — RDS primary
  - `retail-private-b` — RDS standby (subnet group)
- Internet Gateway attached to public route table
- S3 Gateway Endpoint attached to public route table

## Security Groups

- `retail-etl-sg` — SSH (22) from admin IP; outbound to `retail-db-sg` on 5432
- `retail-db-sg` — PostgreSQL (5432) only from `retail-etl-sg`

## Data Flow

1. `orders.csv` uploaded to `s3://.../raw/YYYY-MM-DD/orders.csv`
2. EC2 pulls CSV via `boto3` (IAM role credentials, no keys)
3. Pipeline validates rows, calculates revenue, writes to `lab.orders`
4. Summary reports published to `s3://.../reports/YYYY-MM-DD/`