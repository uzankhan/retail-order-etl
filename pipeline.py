"""
Retail Order ETL Pipeline
Extracts CSV from S3, transforms data, loads into PostgreSQL RDS
"""
import argparse
import getpass
import json
import os
import sys
from datetime import datetime

import boto3
import pandas as pd
import psycopg2


def connect_db(user=None, password=None):
    """Connect to PostgreSQL RDS with SSL"""
    return psycopg2.connect(
        host=os.environ.get('PGHOST'),
        port=os.environ.get('PGPORT', '5432'),
        dbname=os.environ.get('PGDATABASE', 'retail'),
        user=user or os.environ.get('PGUSER'),
        password=password or os.environ.get('PGPASSWORD'),
        sslmode='verify-full',
        sslrootcert=os.environ.get('PGSSLROOTCERT'),
    )


def extract_from_s3(bucket, batch_date, region):
    """Download orders.csv from S3"""
    s3 = boto3.client('s3', region_name=region)
    key = f'raw/{batch_date}/orders.csv'
    try:
        obj = s3.get_object(Bucket=bucket, Key=key)
        df = pd.read_csv(obj['Body'])
        print(f"✅ Extracted {len(df)} rows from s3://{bucket}/{key}")
        return df
    except s3.exceptions.NoSuchKey:
        print(f"❌ File not found: s3://{bucket}/{key}")
        sys.exit(1)


def transform(df):
    """Clean, validate, and enrich data"""
    input_rows = len(df)
    rejected_rows = []

    # 1. Remove duplicates by order_id
    df = df.drop_duplicates(subset=['order_id'], keep='first')
    duplicate_count = input_rows - len(df)

    # 2. Validate quantity > 0
    invalid_qty = df[df['quantity'] <= 0]
    rejected_rows.append(invalid_qty)
    df = df[df['quantity'] > 0]

    # 3. Validate unit_price > 0
    invalid_price = df[df['unit_price'] <= 0]
    rejected_rows.append(invalid_price)
    df = df[df['unit_price'] > 0]

    # 4. Validate status
    valid_statuses = ['completed', 'pending', 'shipped', 'cancelled']
    invalid_status = df[~df['status'].isin(valid_statuses)]
    rejected_rows.append(invalid_status)
    df = df[df['status'].isin(valid_statuses)]

    # 5. Calculate revenue
    df['revenue'] = (df['quantity'] * df['unit_price']).round(2)

    rejected_df = pd.concat(rejected_rows) if rejected_rows else pd.DataFrame()
    rejected_count = len(rejected_df)

    print(f"✅ Transformed: {len(df)} accepted, {rejected_count} rejected, {duplicate_count} duplicates")

    return df, rejected_df, {
        'input_rows': input_rows,
        'accepted_rows': len(df),
        'rejected_rows': rejected_count,
        'duplicate_rows': duplicate_count,
    }


def load_to_db(df, conn):
    """Bulk insert into lab.orders table"""
    cursor = conn.cursor()
    cursor.execute("CREATE SCHEMA IF NOT EXISTS lab")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lab.orders (
            order_id VARCHAR(50) PRIMARY KEY,
            order_date DATE NOT NULL,
            city VARCHAR(100),
            category VARCHAR(100),
            quantity INT NOT NULL,
            unit_price DECIMAL(10,2) NOT NULL,
            status VARCHAR(50),
            revenue DECIMAL(12,2),
            loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()

    inserted = 0
    for _, row in df.iterrows():
        cursor.execute("""
            INSERT INTO lab.orders
            (order_id, order_date, city, category, quantity, unit_price, status, revenue)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (order_id) DO NOTHING
        """, (
            row['order_id'], row['order_date'], row['city'], row['category'],
            int(row['quantity']), float(row['unit_price']), row['status'], float(row['revenue'])
        ))
        inserted += cursor.rowcount
    conn.commit()

    print(f"✅ Loaded {inserted} new rows to lab.orders")
    return inserted


def save_reports_to_s3(df, rejected_df, metrics, bucket, batch_date, region):
    """Save daily sales, rejected orders, and metrics to S3"""
    s3 = boto3.client('s3', region_name=region)
    prefix = f'reports/{batch_date}'

    # Daily sales
    daily_sales = df.groupby(['category', 'status']).agg(
        total_orders=('order_id', 'count'),
        total_quantity=('quantity', 'sum'),
        total_revenue=('revenue', 'sum'),
    ).reset_index()
    s3.put_object(Bucket=bucket, Key=f'{prefix}/daily_sales.csv',
                  Body=daily_sales.to_csv(index=False))

    # Rejected orders
    if not rejected_df.empty:
        s3.put_object(Bucket=bucket, Key=f'{prefix}/rejected_orders.csv',
                      Body=rejected_df.to_csv(index=False))

    # Metrics
    s3.put_object(Bucket=bucket, Key=f'{prefix}/metrics.json',
                  Body=json.dumps(metrics, indent=2))

    # Success marker
    s3.put_object(Bucket=bucket, Key=f'{prefix}/_SUCCESS.json',
                  Body=json.dumps({
                      'status': 'success',
                      'timestamp': datetime.utcnow().isoformat(),
                      'batch_date': batch_date,
                  }))

    print(f"✅ Reports saved to s3://{bucket}/{prefix}/")


def main():
    parser = argparse.ArgumentParser(description='Retail Order ETL Pipeline')
    parser.add_argument('--bucket', required=True, help='S3 bucket name')
    parser.add_argument('--region', default='us-east-1', help='AWS region')
    parser.add_argument('--batch-date', required=True, help='Batch date (YYYY-MM-DD)')
    args = parser.parse_args()

    # Extract
    df = extract_from_s3(args.bucket, args.batch_date, args.region)

    # Transform
    df_clean, df_rejected, metrics = transform(df)

    # Load
    conn = connect_db()
    try:
        load_to_db(df_clean, conn)

        # Database verification
        with conn.cursor() as cur:
            cur.execute('SELECT COUNT(*), COALESCE(SUM(revenue), 0) FROM lab.orders')
            db_rows, db_revenue = cur.fetchone()
            metrics['database_rows'] = db_rows
            metrics['database_revenue_pkr'] = str(db_revenue)
    finally:
        conn.close()

    # Save reports
    save_reports_to_s3(df_clean, df_rejected, metrics, args.bucket, args.batch_date, args.region)

    print(f"\n✅ Complete: {json.dumps(metrics, indent=2)}")


if __name__ == '__main__':
    main()