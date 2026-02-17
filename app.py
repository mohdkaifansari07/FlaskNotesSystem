
from flask import Flask, render_template, request, redirect, session, flash, url_for, g
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer
from dotenv import load_dotenv
import os

load_dotenv()  # load .env file

app = Flask(__name__)

# 🔐 Secret key from .env
app.secret_key = os.getenv("SECRET_KEY", "fallback-secret-key")

# --------------------
# Mail Config (from .env)
# --------------------
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv("MAIL_USERNAME")
app.config['MAIL_PASSWORD'] = os.getenv("MAIL_PASSWORD")

mail = Mail(app)

serializer = URLSafeTimedSerializer(app.secret_key)

# --------------------
# SQLite DB Config
# --------------------
DATABASE = 'notes.db'
def init_db():
    conn = sqlite3.connect(DATABASE)
    with open('schema.sql') as f:
        conn.executescript(f.read())
    conn.close()

# Auto create DB if not exists (Railway fix)
if not os.path.exists(DATABASE):
    init_db()


def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row   # like dictionary=True
    return conn

# --------------------
# Root redirect
# --------------------
@app.route('/')
def check():
    if 'user_id' in session:
        return redirect('/viewall')
    return redirect('/login')

# --------------------
# Public Pages
# --------------------
@app.route('/home')
def home():
    return render_template('home.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

# --------------------
# Register
# --------------------
@app.route('/register', methods=['GET', 'POST'])    
def register():
    if request.method == 'POST':
        firstname = request.form['firstname'].strip()
        lastname = request.form['lastname'].strip()
        username = request.form['username'].strip()
        email = request.form['email'].strip()
        password = request.form['password']

        if not username or not email or not password:
            flash("Please fill all fields.", "danger")
            return redirect('/register')

        hashed_pw = generate_password_hash(password)

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT id FROM user WHERE username=?", (username,))
        if cur.fetchone():
            flash("Username already taken.", "danger")
            cur.close()
            conn.close()
            return redirect('/register')

        cur.execute(
            "INSERT INTO user (firstname, lastname, username, email, password) VALUES (?,?,?,?,?)",
            (firstname, lastname, username, email, hashed_pw)
        )
        conn.commit()
        cur.close()
        conn.close()

        flash("Registration successful! Please login.", "success")
        return redirect('/login')

    return render_template('register.html')

# --------------------
# Login
# --------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM user WHERE username=?", (username,))
        user = cur.fetchone()
        cur.close()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            flash("Login successful!", "success")
            return redirect('/viewall')

        flash("Invalid username or password.", "danger")
        return redirect('/login')

    return render_template('login.html')

# --------------------
# Logout
# --------------------
@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect('/login')

# --------------------
# Add Note
# --------------------
@app.route('/addnote', methods=['GET', 'POST'])
def addnote():
    if 'user_id' not in session:
        flash("Login required.", "warning")
        return redirect('/login')

    if request.method == 'POST':
        title = request.form['title'].strip()
        content = request.form['content'].strip()

        if not title or not content:
            flash("Title and content required.", "danger")
            return redirect('/addnote')

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO notes (title, content, user_id) VALUES (?,?,?)",
            (title, content, session['user_id'])
        )
        conn.commit()
        cur.close()
        conn.close()

        flash("Note added successfully.", "success")
        return redirect('/viewall')

    return render_template('addnote.html')

# --------------------
# View All Notes
# --------------------
@app.route('/viewall')
def viewall():
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id,title,content,created_at FROM notes WHERE user_id=? ORDER BY created_at DESC",
        (session['user_id'],)
    )
    notes = cur.fetchall()
    cur.close()
    conn.close()

    return render_template('viewnotes.html', notes=notes)

# --------------------
# View Single Note
# --------------------
@app.route('/viewnotes/<int:note_id>')
def viewnotes(note_id):
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM notes WHERE id=? AND user_id=?",
        (note_id, session['user_id'])
    )
    note = cur.fetchone()
    cur.close()
    conn.close()

    if not note:
        flash("Access denied.", "danger")
        return redirect('/viewall')

    return render_template('singlenote.html', note=note)

# --------------------
# Update Note
# --------------------
@app.route('/updatenote/<int:note_id>', methods=['GET', 'POST'])
def updatenote(note_id):
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM notes WHERE id=? AND user_id=?",
        (note_id, session['user_id'])
    )
    note = cur.fetchone()

    if not note:
        flash("Unauthorized access.", "danger")
        return redirect('/viewall')

    if request.method == 'POST':
        title = request.form['title'].strip()
        content = request.form['content'].strip()

        cur.execute(
            "UPDATE notes SET title=?, content=? WHERE id=? AND user_id=?",
            (title, content, note_id, session['user_id'])
        )
        conn.commit()
        cur.close()
        conn.close()

        flash("Note updated.", "success")
        return redirect('/viewall')

    cur.close()
    conn.close()
    return render_template('updatenote.html', note=note)

# --------------------
# Delete Note
# --------------------
@app.route('/deletenote/<int:note_id>', methods=['POST'])
def deletenote(note_id):
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM notes WHERE id=? AND user_id=?",
        (note_id, session['user_id'])
    )
    conn.commit()
    cur.close()
    conn.close()

    flash("Note deleted.", "info")
    return redirect('/viewall')

# --------------------
# Forgot Password
# --------------------
@app.route('/forgot', methods=['GET', 'POST'])
def forgot():
    if request.method == 'POST':
        email = request.form['email']
        token = serializer.dumps(email, salt='reset-password')

        reset_url = url_for('reset_password', token=token, _external=True)

        msg = Message('Password Reset', sender=app.config['MAIL_USERNAME'], recipients=[email])
        msg.body = f"Reset your password:\n{reset_url}"
        mail.send(msg)

        flash("Reset link sent to email.")
    return render_template('forgot.html')

# --------------------
# Reset Password
# --------------------
from werkzeug.security import generate_password_hash

@app.route('/reset/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        email = serializer.loads(token, salt='reset-password', max_age=3600)
    except:
        return "Invalid or expired link"

    if request.method == 'POST':
        new_password = request.form['password']
        hashed_pw = generate_password_hash(new_password)
        
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE user SET password=? WHERE email=?", (hashed_pw, email))
        conn.commit()
        cur.close()
        conn.close()

        flash("Password reset successful. Please login.")
        return redirect('/login')

    return render_template('reset.html')



# ---------------- SEARCH NOTES ----------------
# ---------------- SEARCH NOTES ----------------
@app.route('/search', methods=['GET'])
def search():
    if 'user_id' not in session:
        return redirect('/login')

    query = request.args.get('q', '').strip()
    user_id = session['user_id']

    conn = get_db_connection()
    cur = conn.cursor()

    if query:
        cur.execute("""
            SELECT id, title, content, created_at
            FROM notes
            WHERE user_id=? AND title LIKE ?
            ORDER BY created_at DESC
        """, (user_id, f"%{query}%"))
        notes = cur.fetchall()
    else:
        notes = []

    cur.close()
    conn.close()

    return render_template('search_notes.html', notes=notes, query=query)




# --------------------
# Run App (local only)
# --------------------

import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Render will set PORT
    debug_mode = os.environ.get("FLASK_DEBUG", "False") == "True"
    app.run(host="0.0.0.0", port=port, debug=debug_mode)


