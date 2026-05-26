import os
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import psycopg2
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# 1. Initialize the Flask App Engine FIRST
app = Flask(__name__)

# Allows your HTML frontend to communicate across local server ports or live domains
CORS(app) 

# 2. Configuration Settings
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Create the uploads folder if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# 3. Helper Functions
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_db_connection():
    # Production Check: Most cloud hosts provide a single 'DATABASE_URL' string
    db_url = os.environ.get("DATABASE_URL")
    
    if db_url:
        # Connect directly using the database URL string
        return psycopg2.connect(db_url)
    else:
        # Fallback to individual local settings if no single URL is found
        return psycopg2.connect(
            host=os.environ.get("DB_HOST", "localhost"),
            database=os.environ.get("DB_NAME", "receipt_portal_db"),
            user=os.environ.get("DB_USER", "postgres"),
            password=os.environ.get("DB_PASSWORD", "1234")
        )


# ==============================================================================
# 4. APPLICATION ROUTES
# ==============================================================================

@app.route('/')
def home():
    # Looks inside your 'templates' folder for index.html
    return render_template('index.html')


@app.route('/api/register', methods=['POST'])
def register():
    data = request.json or {}
    name = data.get('name')
    email = data.get('email')
    phone = data.get('phone')
    dob = data.get('dob')
    password = data.get('password')

    if not all([name, email, phone, dob, password]):
        return jsonify({"error": "All fields are required"}), 400

    hashed_password = generate_password_hash(password)
    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Insert user data and immediately return their unique ID
        cur.execute(
            "INSERT INTO users (name, email, phone, dob, password_hash) VALUES (%s, %s, %s, %s, %s) RETURNING id;",
            (name, email, phone, dob, hashed_password)
        )
        user_id = cur.fetchone()[0]
        conn.commit()
        
        return jsonify({"message": "User registered successfully", "user_id": user_id}), 201

    except psycopg2.IntegrityError:
        if conn:
            conn.rollback()
        return jsonify({"error": "An account with this email already exists."}), 400
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        if cur: cur.close()
        if conn: conn.close()


@app.route('/api/login', methods=['POST'])
def login():
    data = request.json or {}
    user_id_raw = data.get('userNumber') or data.get('userId') 
    password = data.get('password')

    if not user_id_raw or not password:
        return jsonify({"error": "User number and password are required"}), 400

    conn = None
    cur = None

    try:
        # Safely convert to integer to match database SERIAL type
        user_id = int(user_id_raw)
    except ValueError:
        return jsonify({"error": "User number must be a valid ID number"}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Grab user hash validation mapping
        cur.execute("SELECT id, password_hash FROM users WHERE id = %s;", (user_id,))
        user = cur.fetchone()
        
        if user and check_password_hash(user[1], password):
            return jsonify({"message": "Access granted", "user_id": user[0]}), 200
        else:
            return jsonify({"error": "Invalid user number or password"}), 401

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if cur: cur.close()
        if conn: conn.close()


@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file chunk found"}), 400
        
    file = request.files['file']
    user_id = request.form.get('user_id')

    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    if not user_id:
        return jsonify({"error": "User ID is missing from upload request"}), 400

    if file and allowed_file(file.filename):
        # Extract file extension safely and secure the name string
        file_ext = file.filename.rsplit('.', 1)[1].lower()
        clean_name = secure_filename(file.filename.rsplit('.', 1)[0])
        filename = f"user_{user_id}_{clean_name}.{file_ext}"
        
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        conn = None
        cur = None
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            
            # Track file link path against user index
            cur.execute(
                "INSERT INTO uploads (user_id, file_name) VALUES (%s, %s);",
                (user_id, filename)
            )
            conn.commit()
            
            return jsonify({"message": "File uploaded and tracked successfully"}), 200
        except Exception as e:
            if conn:
                conn.rollback()
            return jsonify({"error": str(e)}), 500
        finally:
            if cur: cur.close()
            if conn: conn.close()

    return jsonify({"error": "File type not allowed. Please upload a PDF, PNG, JPG, or JPEG."}), 400


if __name__ == '__main__':
    app.run(debug=True)