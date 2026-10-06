"""
Create sales_etl user and lab schema/table
Run this after creating the `retail` database
"""
import getpass
import os
import sys

from pipeline import connect_db


def main():
    master_password = getpass.getpass('RDS master password: ')
    etl_password = getpass.getpass('New sales_etl password: ')

    conn = connect_db(user='lab_admin', password=master_password)
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            # Create ETL user
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname = 'sales_etl'")
            if not cur.fetchone():
                cur.execute(f"CREATE USER sales_etl WITH PASSWORD %s", (etl_password,))
                print('✅ sales_etl user created')
            else:
                cur.execute(f"ALTER USER sales_etl WITH PASSWORD %s", (etl_password,))
                print('✅ sales_etl user updated')

            # Create schema
            cur.execute("CREATE SCHEMA IF NOT EXISTS lab")
            print('✅ Schema lab created')

            # Create table
            cur.execute("""
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
            print('✅ Table lab.orders created')

            # Grant permissions
            cur.execute("GRANT USAGE ON SCHEMA lab TO sales_etl")
            cur.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON lab.orders TO sales_etl")
            cur.execute("GRANT USAGE ON ALL SEQUENCES IN SCHEMA lab TO sales_etl")
            print('✅ Permissions granted to sales_etl')

    finally:
        conn.close()

    print('\n✅ Setup complete!')


if __name__ == '__main__':
    main()