from flask import Flask, request, redirect, url_for, session, send_from_directory, flash, render_template_string, jsonify
from werkzeug.utils import secure_filename
from passlib.hash import pbkdf2_sha256
from flask_socketio import SocketIO, emit, join_room, leave_room
import sqlite3, os, uuid, datetime, mimetypes

app = Flask(__name__)
app.secret_key = 'super_secret_key'
socketio = SocketIO(app, cors_allowed_origins="*", manage_session=False)

UPLOAD_FOLDER = 'media_uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mp3', 'pdf', 'txt', 'zip'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db():
    conn = sqlite3.connect("social.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            email TEXT,
            profile_image TEXT)''')

        db.execute('''CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            filename TEXT,
            is_private INTEGER,
            timestamp TEXT)''')

        db.execute('''CREATE TABLE IF NOT EXISTS friends (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER,
            receiver_id INTEGER,
            status TEXT)''')

        db.execute('''CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER,
            receiver_id INTEGER,
            content TEXT,
            timestamp TEXT)''')
init_db()

@app.before_request
def require_login():
    allowed_routes = ['login', 'signup', 'uploaded_file', 'static']
    if request.endpoint not in allowed_routes and 'user_id' not in session:
        return redirect(url_for('login'))

@app.route('/')
def index():
    return redirect(url_for('home'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form['username']
        pwd = request.form['password']
        db = get_db()
        row = db.execute("SELECT * FROM users WHERE username=?", (user,)).fetchone()
        if row and pbkdf2_sha256.verify(pwd, row['password']):
            session['user_id'] = row['id']
            session['username'] = row['username']
            return redirect(url_for('home'))
        else:
            flash("Invalid login.")
    return render_template_string(LOGIN_PAGE)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        user = request.form['username']
        pwd = pbkdf2_sha256.hash(request.form['password'])
        email = request.form['email']
        profile_img = request.files['profile_image']
        filename = str(uuid.uuid4()) + "_" + secure_filename(profile_img.filename)
        profile_img.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        try:
            db = get_db()
            db.execute("INSERT INTO users (username, password, email, profile_image) VALUES (?, ?, ?, ?)",
                       (user, pwd, email, filename))
            db.commit()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash("Username already taken.")
    return render_template_string(SIGNUP_PAGE)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/home', methods=['GET', 'POST'])
def home():
    db = get_db()
    if request.method == 'POST':
        file = request.files['media']
        is_private = 1 if request.form.get('is_private') == 'on' else 0
        filename = str(uuid.uuid4()) + '_' + secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        db.execute("INSERT INTO posts (user_id, filename, is_private, timestamp) VALUES (?, ?, ?, ?)",
                   (session['user_id'], filename, is_private, datetime.datetime.now()))
        db.commit()
        return redirect(url_for('home'))
    
    user_id = session['user_id']
    posts = db.execute("""
        SELECT posts.*, users.username FROM posts
        JOIN users ON posts.user_id = users.id
        WHERE is_private = 0 OR user_id = ?
        ORDER BY timestamp DESC
    """, (user_id,)).fetchall()

    enriched_posts = []
    for post in posts:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], post['filename'])
        mime_type, _ = mimetypes.guess_type(filepath)
        media_type = "unknown"
        if mime_type:
            if mime_type.startswith('image'):
                media_type = "image"
            elif mime_type.startswith('video'):
                media_type = "video"
            elif mime_type.startswith('audio'):
                media_type = "audio"
        enriched_posts.append({**post, "media_type": media_type})

    friends = db.execute("""
        SELECT u.id, u.username FROM users u
        JOIN friends f ON (u.id = f.receiver_id AND f.sender_id = ?) OR (u.id = f.sender_id AND f.receiver_id = ?)
        WHERE f.status = 'accepted'
    """, (user_id, user_id)).fetchall()
    
    pending_count = db.execute("SELECT COUNT(*) FROM friends WHERE receiver_id=? AND status='pending'", (user_id,)).fetchone()[0]

    return render_template_string(HOME_PAGE, posts=enriched_posts, friends=friends, username=session['username'], pending_count=pending_count)


@app.route('/profile')
def profile():
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id=?", (session['user_id'],)).fetchone()
    return render_template_string(PROFILE_PAGE, user=user)

@app.route('/friends', methods=['GET', 'POST'])
def friends():
    db = get_db()
    user_id = session['user_id']
    message = ""
    if request.method == 'POST':
        action = request.form.get('action')
        target = int(request.form.get('target_id'))

        existing = db.execute("""
            SELECT * FROM friends WHERE
            (sender_id=? AND receiver_id=?) OR (sender_id=? AND receiver_id=?)
        """, (user_id, target, target, user_id)).fetchone()

        if action == 'send':
            if existing:
                if existing['status'] == 'pending':
                    message = "Friend request already sent."
                elif existing['status'] == 'accepted':
                    message = "You are already friends."
                else:
                    message = "Friend request already exists."
            else:
                db.execute("INSERT INTO friends (sender_id, receiver_id, status) VALUES (?, ?, 'pending')", (user_id, target))
                db.commit()
                return redirect(url_for('friends'))
        elif action == 'accept':
            db.execute("UPDATE friends SET status='accepted' WHERE sender_id=? AND receiver_id=?", (target, user_id))
            db.commit()
            return redirect(url_for('friends'))
        elif action == 'delete':
            db.execute("DELETE FROM friends WHERE (sender_id=? AND receiver_id=?) OR (sender_id=? AND receiver_id=?)",
                       (user_id, target, target, user_id))
            db.commit()
            return redirect(url_for('friends'))

    keyword = request.args.get('search', '')
    all_users = db.execute("SELECT id, username FROM users WHERE id != ? AND username LIKE ?", (user_id, f"%{keyword}%")).fetchall()

    status_map = {}
    for user in all_users:
        u_id = user['id']
        rel = db.execute("SELECT status FROM friends WHERE (sender_id=? AND receiver_id=?) OR (sender_id=? AND receiver_id=?)",
                         (user_id, u_id, u_id, user_id)).fetchone()
        status_map[u_id] = rel['status'] if rel else None

    requests = db.execute("""
        SELECT f.*, u.username AS sender_username FROM friends f
        JOIN users u ON f.sender_id = u.id
        WHERE f.receiver_id=? AND f.status='pending'
    """, (user_id,)).fetchall()
    friends_list = db.execute("""
        SELECT u.id, u.username FROM users u
        JOIN friends f ON (u.id = f.receiver_id AND f.sender_id = ?) OR (u.id = f.sender_id AND f.receiver_id = ?)
        WHERE f.status = 'accepted'
    """, (user_id, user_id)).fetchall()
    return render_template_string(FRIENDS_PAGE, users=all_users, requests=requests, friends=friends_list, user_id=user_id, search=keyword, message=message, status_map=status_map)

@app.route('/chat')
def chat():
    db = get_db()
    user_id = session['user_id']
    friends = db.execute("""
        SELECT u.id, u.username FROM users u
        JOIN friends f ON ((u.id = f.receiver_id AND f.sender_id = ?) OR (u.id = f.sender_id AND f.receiver_id = ?))
        WHERE f.status = 'accepted'
    """, (user_id, user_id)).fetchall()
    return render_template_string(CHAT_PAGE, friends=friends, username=session['username'], user_id=user_id)

@socketio.on('join')
def on_join(data):
    if 'user_id' not in session:
        return
    room = str(data['room']) if isinstance(data, dict) else str(data)
    join_room(room)

@socketio.on('leave')
def on_leave(data):
    if 'user_id' not in session:
        return
    room = str(data['room']) if isinstance(data, dict) else str(data)
    leave_room(room)

@socketio.on('private_message')
def private_message(data):
    if 'user_id' not in session:
        return
    sender_id = session['user_id']
    receiver_username = data.get('to')
    message = data.get('message')
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    db = get_db()
    receiver = db.execute("SELECT id FROM users WHERE username=?", (receiver_username,)).fetchone()
    if not receiver:
        return
    receiver_id = receiver['id']
    db.execute("INSERT INTO messages (sender_id, receiver_id, content, timestamp) VALUES (?, ?, ?, ?)",
               (sender_id, receiver_id, message, timestamp))
    db.commit()
    payload = {
        'from': session.get('username'),
        'message': message,
        'timestamp': timestamp
    }
    emit('private_message', payload, room=receiver_username)
    emit('private_message', payload, room=session.get('username'))


# -------------------- HTML Templates --------------------

LOGIN_PAGE = '''
<!DOCTYPE html>
<html>
<head>
  <title>Login</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
  <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons/font/bootstrap-icons.css" rel="stylesheet">
</head>
<body class="d-flex align-items-center justify-content-center" style="min-height: 100vh; background: #f7f7fc;">
  <div class="card shadow p-4" style="width: 100%; max-width: 400px;">
    <h2 class="mb-4 text-center">Login</h2>
    <form method="post">
      <div class="mb-3">
        <label class="form-label"><i class="bi bi-person-fill me-2"></i>Username</label>
        <input name="username" class="form-control" placeholder="Enter username">
      </div>
      <div class="mb-3">
        <label class="form-label"><i class="bi bi-lock-fill me-2"></i>Password</label>
        <input name="password" type="password" class="form-control" placeholder="Enter password">
      </div>
      <button class="btn btn-primary w-100">Login</button>
    </form>
    <p class="mt-3 text-center">No account? <a href="/signup">Signup</a></p>
  </div>
</body>
</html>
'''

SIGNUP_PAGE = '''
<!DOCTYPE html>
<html>
<head>
  <title>Signup</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
  <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons/font/bootstrap-icons.css" rel="stylesheet">
</head>
<body class="d-flex align-items-center justify-content-center" style="min-height: 100vh; background: #eef1f7;">
  <div class="card shadow p-4" style="width: 100%; max-width: 500px;">
    <h2 class="mb-4 text-center">Signup</h2>
    <form method="post" enctype="multipart/form-data">
      <div class="mb-3">
        <label class="form-label"><i class="bi bi-person-circle me-2"></i>Username</label>
        <input name="username" class="form-control">
      </div>
      <div class="mb-3">
        <label class="form-label"><i class="bi bi-lock-fill me-2"></i>Password</label>
        <input name="password" type="password" class="form-control">
      </div>
      <div class="mb-3">
        <label class="form-label"><i class="bi bi-envelope-fill me-2"></i>Email</label>
        <input name="email" class="form-control">
      </div>
      <div class="mb-4">
        <label class="form-label"><i class="bi bi-image me-2"></i>Profile Image</label>
        <input type="file" name="profile_image" class="form-control">
      </div>
      <button class="btn btn-success w-100">Signup</button>
    </form>
  </div>
</body>
</html>
'''

HOME_PAGE = '''
<!DOCTYPE html>
<html>
<head>
  <title>Home</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="container py-4">
  <div class="d-flex justify-content-between align-items-center mb-3">
    <h2>Welcome, {{ username }}</h2>
    <div>
      <a href="/logout" class="btn btn-danger btn-sm">Logout</a>
      <a href="/profile" class="btn btn-secondary btn-sm">Profile</a>
      <a href="/friends" class="btn btn-warning btn-sm">Friends</a>
      <a href="/chat" class="btn btn-info btn-sm">Chat</a>
    </div>
  </div>
  <hr>
  <h4>Post Media</h4>
  <form method="post" enctype="multipart/form-data" class="mb-4">
    <input type="file" name="media" class="form-control mb-2">
    <div class="form-check mb-2">
      <input class="form-check-input" type="checkbox" name="is_private" id="privateCheck">
      <label class="form-check-label" for="privateCheck">Private</label>
    </div>
    <button class="btn btn-primary">Upload</button>
  </form>
  <hr>
  <h4>Recent Posts</h4>
  {% for post in posts %}
  <div class="card mb-3">
    <div class="card-body">
      <h6 class="card-title">{{ post.username }}</h6>
      <a href="/uploads/{{ post.filename }}" class="card-link">{{ post.filename }}</a>
      <p class="card-text"><small class="text-muted">{{ post.timestamp }}</small></p>
    </div>
  </div>
  {% endfor %}
</body>
</html>
'''

PROFILE_PAGE = '''
<!DOCTYPE html>
<html>
<head>
  <title>Profile</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="container py-4">
  <div class="card shadow p-4">
    <h2>My Profile</h2>
    <p><strong>Username:</strong> {{ user.username }}</p>
    <p><strong>Email:</strong> {{ user.email }}</p>
    <img src="/uploads/{{ user.profile_image }}" width="100" class="rounded">
    <br><br>
    <a href="/home" class="btn btn-secondary">Back to Home</a>
  </div>
</body>
</html>
'''

FRIENDS_PAGE = '''
<!DOCTYPE html>
<html>
<head>
  <title>Friends</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="container py-4">
  <h2>Manage Friends</h2>
  <h4>All Users</h4>
  <form method="get" class="mb-3">
    <input type="text" name="search" class="form-control mb-3" placeholder="Search users..." value="{{ search }}">
    <button class="btn btn-secondary">Search</button>
  </form>
  <form method="post">
    {% for u in users %}
    <div class="d-flex justify-content-between align-items-center border p-2 rounded mb-2">
      <span>{{ u.username }}</span>
      <input type="hidden" name="target_id" value="{{ u.id }}">
      <button name="action" value="send" class="btn btn-sm btn-success">Send Request</button>
    </div>
    {% endfor %}
  </form>
  <h4>Friend Requests {% if requests|length > 0 %}<span class="badge bg-danger">{{ requests|length }}</span>{% endif %}</h4>
  <form method="post">
    {% for r in requests %}
    <div class="d-flex justify-content-between align-items-center border p-2 rounded mb-2">
      <span>From: {{ r.sender_username if r.sender_username else r.sender_id }}</span>
      <input type="hidden" name="target_id" value="{{ r.sender_id }}">
      <button name="action" value="accept" class="btn btn-sm btn-primary">Accept</button>
      <button name="action" value="delete" class="btn btn-sm btn-danger">Delete</button>
    </div>
    {% endfor %}
  </form>
  <h4>Friends List</h4>
  <form method="post">
    {% for f in friends %}
    <div class="d-flex justify-content-between align-items-center border p-2 rounded mb-2">
      <span>{{ f.username }}</span>
      <input type="hidden" name="target_id" value="{{ f.id }}">
      <button name="action" value="delete" class="btn btn-sm btn-outline-danger">Remove Friend</button>
    </div>
    {% endfor %}
  </form>
  <a href="/home" class="btn btn-secondary mt-4">Back</a>
</body>
</html>
'''

CHAT_PAGE = '''
<!DOCTYPE html>
<html>
<head>
  <title>Chat</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
  <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.min.js"></script>
</head>
<body class="container py-4">
  <div class="card shadow p-4">
    <h2 class="mb-4">Chat with Friends</h2>
    <form method="get" id="chat-form" class="mb-3">
      <label for="receiver" class="form-label">Select Friend:</label>
      <select class="form-select mb-3" id="receiver" onchange="switchChat(this.value)">
        {% for friend in friends %}
        <option value="{{ friend.username }}">{{ friend.username }}</option>
        {% endfor %}
      </select>
    </form>
    <div id="chat-box" class="border rounded p-2 mb-2" style="height:300px; overflow:auto; background:#f1f1f1;"></div>
    <div class="input-group mb-2">
      <input id="msg" class="form-control" placeholder="Enter message">
      <button onclick="sendMessage()" class="btn btn-primary">Send</button>
    </div>
    <a href="/home" class="btn btn-secondary">Back</a>
  </div>
  <script>
    var socket = io();
    var receiver = document.getElementById("receiver").value;
    socket.emit("join", receiver);

    function switchChat(newReceiver) {
      receiver = newReceiver;
      document.getElementById("chat-box").innerHTML = "";
      socket.emit("join", receiver);
    }

    function sendMessage() {
      var msg = document.getElementById("msg").value;
      if (msg.trim() === '') return;
      socket.emit("private_message", { to: receiver, message: msg });
      document.getElementById("msg").value = "";
    }

    socket.on("private_message", function(data) {
      var chat = document.getElementById("chat-box");
      var isMine = data.from === "{{ username }}";
      var msgHTML = `<div style="text-align:${isMine ? 'right' : 'left'};">
                      <b>${data.from}:</b> ${data.message}<br>
                      <small>${data.timestamp}</small></div>`;
      chat.innerHTML += msgHTML;
      chat.scrollTop = chat.scrollHeight;
    });
  </script>
</body>
</html>
'''
if __name__ == '__main__':
    socketio.run(app, debug=True)
    