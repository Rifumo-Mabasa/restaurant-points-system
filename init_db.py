import os
import psycopg2

print("--- Script Started ---")

# Pull the cloud database URL if it exists, otherwise fall back to local settings
db_url = os.environ.get("DATABASE_URL")

try:
    if db_url:
        print("Attempting to connect to Render Cloud Database...")
        conn = psycopg2.connect(db_url)
    else:
        print("No DATABASE_URL found. Falling back to localhost...")
        conn = psycopg2.connect(
            host="localhost",
            database="receipt_portal_db",
            user="postgres",
            password="1234"
        )
        
    cur = conn.cursor()
    print("Connected successfully!")

    # SQL commands (Matching your app.py schema perfectly)
    users_table = """
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        email VARCHAR(255) UNIQUE NOT NULL,
        phone VARCHAR(50) NOT NULL,
        dob DATE NOT NULL,
        password_hash VARCHAR(255) NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
    print("--- Success! All tables are ready and synchronized. ---")

except Exception as e:
    print("\n[ERROR] Database setup failed!")
    print(f"Details: {e}\n")

finally:
    if 'cur' in locals(): cur.close()
    if 'conn' in locals(): conn.close()
    print("Connection closed.")