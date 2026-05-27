import os
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import psycopg2
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# 1. Initialize the Flask App Engine
app = Flask(__name__)
CORS(app) 

# 2. Configuration Settings
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# 3. Helper Functions
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db_connection():
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        return psycopg2.connect(db_url)
    else:
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
    return render_template('index.html')

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json or {}
    name, email, phone = data.get('name'), data.get('email'), data.get('phone')
    dob, password = data.get('dob'), data.get('password')

    if not all([name, email, phone, dob, password]):
        return jsonify({"error": "All fields are required"}), 400

    hashed_password = generate_password_hash(password)
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users (name, email, phone, dob, password_hash) VALUES (%s, %s, %s, %s, %s) RETURNING id;",
            (name, email, phone, dob, hashed_password)
        )
        user_id = cur.fetchone()[0]
        conn.commit()
        return jsonify({"message": "User registered successfully", "user_id": user_id}), 201
    except psycopg2.IntegrityError:
        if conn: conn.rollback()
        return jsonify({"error": "An account with this email already exists."}), 400
    except Exception as e:
        if conn: conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        if cur: cur.close()
        if conn: conn.close()

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json or {}
    user_id_raw = data.get('userNumber') or data.get('userId')
    password = data.get('password')

    try:
        user_id = int(user_id_raw)
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, password_hash FROM users WHERE id = %s;", (user_id,))
        user = cur.fetchone()
        
        if user and check_password_hash(user[1], password):
            return jsonify({"message": "Access granted", "user_id": user[0]}), 200
        return jsonify({"error": "Invalid user number or password"}), 401
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if cur: cur.close()
        if conn: conn.close()

@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files: return jsonify({"error": "No file chunk found"}), 400
        
    file = request.files['file']
    user_id = request.form.get('user_id')
    total_amount = float(request.form.get('total_amount', 0))
    points_earned = int(total_amount // 100)

    if file and allowed_file(file.filename):
        filename = f"user_{user_id}_{secure_filename(file.filename)}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        conn = None
        cur = None
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO uploads (user_id, file_name, total_amount, points_earned) VALUES (%s, %s, %s, %s);",
                (user_id, filename, total_amount, points_earned)
            )
            cur.execute("UPDATE users SET total_points = total_points + %s WHERE id = %s;", (points_earned, user_id))
            conn.commit()
            return jsonify({"message": "Success", "points_earned": points_earned}), 200
        except Exception as e:
            if conn: conn.rollback()
            return jsonify({"error": str(e)}), 500
        finally:
            if cur: cur.close()
            if conn: conn.close()
    return jsonify({"error": "File type not allowed."}), 400

@app.route('/api/dashboard/<int:user_id>', methods=['GET'])
def get_dashboard(user_id):
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, total_amount, points_earned FROM uploads WHERE user_id = %s;", (user_id,))
        receipts = cur.fetchall()
        cur.execute("SELECT total_points FROM users WHERE id = %s;", (user_id,))
        total_points = cur.fetchone()[0]
        
        return jsonify({
            "receipts": [{"id": r[0], "total_amount": float(r[1]), "points_earned": r[2]} for r in receipts],
            "total_points": total_points
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if cur: cur.close()
        if conn: conn.close()