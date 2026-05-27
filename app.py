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

# ... (Keep your existing /api/register, /api/login, /api/upload routes here) ...

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

# FIXED: Now correctly defined at the module level
@app.route('/api/update-profile', methods=['POST'])
def update_profile():
    data = request.json
    user_id = data.get('user_id')
    email = data.get('email')
    phone = data.get('phone')
    
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET email = %s, phone = %s WHERE id = %s;", 
                        (email, phone, user_id))
            conn.commit()
            return jsonify({"message": "Profile updated"}), 200
    except Exception as e:
        if conn: conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        if conn: conn.close()

if __name__ == '__main__':
    app.run(debug=True)