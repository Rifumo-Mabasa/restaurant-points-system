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
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO users (name, email, phone, dob, password_hash) VALUES (%s, %s, %s, %s, %s) RETURNING id;", (name, email, phone, dob, hashed_password))
            user_id = cur.fetchone()[0]
            conn.commit()
            return jsonify({"user_id": user_id}), 201
    finally:
        conn.close()

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json or {}
    user_id_raw = data.get('userNumber')
    password = data.get('password')
    
    if not user_id_raw or not password:
        return jsonify({"error": "User ID and password are required"}), 400
        
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Added "name" to the SELECT statement
            cur.execute("SELECT id, password_hash, name FROM users WHERE id = %s;", (int(user_id_raw),))
            user = cur.fetchone()
            
            if user and check_password_hash(user[1], password):
                # Return the user_id AND the name to the frontend
                return jsonify({
                    "user_id": user[0], 
                    "name": user[2]
                }), 200
        return jsonify({"error": "Invalid credentials"}), 401
    except (ValueError, psycopg2.Error):
        return jsonify({"error": "Invalid User ID format"}), 400
    finally:
        conn.close()

@app.route('/api/upload', methods=['POST'])
def upload_file():
    file = request.files.get('file')
    user_id = request.form.get('user_id')
    amount = float(request.form.get('total_amount', 0))
    if file and allowed_file(file.filename):
        filename = f"user_{user_id}_{secure_filename(file.filename)}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO uploads (user_id, file_name, total_amount, points_earned) VALUES (%s, %s, %s, %s);", (user_id, filename, amount, int(amount // 100)))
                cur.execute("UPDATE users SET total_points = total_points + %s WHERE id = %s;", (int(amount // 100), user_id))
                conn.commit()
            return jsonify({"points_earned": int(amount // 100)}), 200
        finally:
            conn.close()
    return jsonify({"error": "File invalid"}), 400

@app.route('/api/dashboard/<int:user_id>', methods=['GET'])
def get_dashboard(user_id):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, total_amount, points_earned, file_name FROM uploads WHERE user_id = %s;", (user_id,))
            receipts = [{"id": r[0], "total_amount": float(r[1]), "points_earned": r[2], "file_name": r[3]} for r in cur.fetchall()]
            cur.execute("SELECT total_points FROM users WHERE id = %s;", (user_id,))
            total_points = cur.fetchone()[0]
            return jsonify({"receipts": receipts, "total_points": total_points}), 200
    finally:
        conn.close()

@app.route('/api/update-profile', methods=['POST'])
def update_profile():
    data = request.json
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET email = %s, phone = %s WHERE id = %s;", (data.get('email'), data.get('phone'), data.get('user_id')))
            conn.commit()
            return jsonify({"message": "Profile updated"}), 200
    finally:
        conn.close()

if __name__ == '__main__':
    app.run(debug=True)