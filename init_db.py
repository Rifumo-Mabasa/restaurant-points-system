import psycopg2

print("--- Script Started ---")

# 1. DOUBLE CHECK THESE DETAILS MATCH YOUR POSTGRES SYSTEM
DB_SETTINGS = {
    "host": "localhost",
    "database": "receipt_portal_db",  # <-- Change to your actual database name
    "user": "postgres",                # <-- Change to your actual database user
    "password": "1234"  # <-- Change to your actual database password
}

try:
    print(f"Attempting to connect to database '{DB_SETTINGS['database']}'...")
    conn = psycopg2.connect(**DB_SETTINGS)
    cur = conn.cursor()
    print("Connected successfully!")

    # SQL commands
    users_table = """
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        name VARCHAR(100),
        email VARCHAR(100) UNIQUE NOT NULL,
        phone VARCHAR(20),
        dob DATE,
        password_hash VARCHAR(255) NOT NULL
    );
    """
    
    uploads_table = """
    CREATE TABLE IF NOT EXISTS uploads (
        id SERIAL PRIMARY KEY,
        user_id INT REFERENCES users(id) ON DELETE CASCADE,
        file_name VARCHAR(255) NOT NULL,
        uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """

    print("Creating 'users' table...")
    cur.execute(users_table)
    
    print("Creating 'uploads' table...")
    cur.execute(uploads_table)

    conn.commit()
    print("--- Success! All tables are ready. ---")

except Exception as e:
    print("\n[ERROR] Database setup failed!")
    print(f"Details: {e}\n")

finally:
    if 'cur' in locals(): cur.close()
    if 'conn' in locals(): conn.close()
    print("Connection closed.")