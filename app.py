import os
from flask import Flask, request, jsonify, render_template, send_from_directory, abort
from flask_cors import CORS
import psycopg2
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app) 

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db_connection():
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        return psycopg2.connect(db_url)
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        database=os.environ.get("DB_NAME", "receipt_portal_db"),
        user=os.environ.get("DB_USER", "postgres"),
        password=os.environ.get("DB_PASSWORD", "1234")
    )

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/download/<filename>')
def download_file(filename):
    try:
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    except FileNotFoundError:
        abort(404)

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json or {}
    name, email, phone, dob, password = data.get('name'), data.get('email'), data.get('phone'), data.get('dob'), data.get('password')
    if not all([name, email, phone, dob, password]):
        return jsonify({"error": "All fields are required"}), 400
    
    hashed_password = generate_password_hash(password)
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (name, email, phone, dob, password_hash) VALUES (%s, %s, %s, %s, %s) RETURNING id;",
                (name, email, phone, dob, hashed_password)
            )
            user_id = cur.fetchone()[0]
            conn.commit()
            return jsonify({"message": "User registered successfully", "user_id": user_id}), 201
    except Exception as e:
        if conn: conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        if conn: conn.close()

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json or {}
    user_id_raw = data.get('userNumber') or data.get('userId')
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT id, password_hash FROM users WHERE id = %s;", (int(user_id_raw),))
            user = cur.fetchone()
            if user and check_password_hash(user[1], data.get('password')):
                return jsonify({"message": "Access granted", "user_id": user[0]}), 200
        return jsonify({"error": "Invalid user number or password"}), 401
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn: conn.close()

@app.route('/api/upload', methods=['POST'])
def upload_file():
    file = request.files.get('file')
    user_id = request.form.get('user_id')
    total_amount = float(request.form.get('total_amount', 0))
    points_earned = int(total_amount // 100)
    
    if file and allowed_file(file.filename):
        filename = f"user_{user_id}_{secure_filename(file.filename)}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor() as cur:
                cur.execute("INSERT INTO uploads (user_id, file_name, total_amount, points_earned) VALUES (%s, %s, %s, %s);",
                            (user_id, filename, total_amount, points_earned))
                cur.execute("UPDATE users SET total_points = total_points + %s WHERE id = %s;", (points_earned, user_id))
                conn.commit()
                return jsonify({"message": "Success", "points_earned": points_earned}), 200
        except Exception as e:
            if conn: conn.rollback()
            return jsonify({"error": str(e)}), 500
        finally:
            if conn: conn.close()
    return jsonify({"error": "File type not allowed."}), 400

@app.route('/api/dashboard/<int:user_id>', methods=['GET'])
def get_dashboard(user_id):
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT id, total_amount, points_earned, file_name FROM uploads WHERE user_id = %s;", (user_id,))
            receipts = cur.fetchall()
            cur.execute("SELECT total_points FROM users WHERE id = %s;", (user_id,))
            res = cur.fetchone()
            total_points = res[0] if res else 0
            
            return jsonify({
                "receipts": [{"id": r[0], "total_amount": float(r[1]), "points_earned": r[2], "file_name": r[3]} for r in receipts],
                "total_points": total_points
            }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn: conn.close()
        