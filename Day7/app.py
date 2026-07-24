from flask import Flask, render_template, request, redirect, session
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import timedelta, datetime
import sqlite3
import os

app = Flask(__name__)
app.secret_key = os.urandom(24).hex()

# 会话有效期30分钟
app.permanent_session_lifetime = timedelta(minutes=30)

# 上传文件最大大小 16MB
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# 上传文件保存目录
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# 页面文件存放目录
PAGES_FOLDER = os.path.join(os.path.dirname(__file__), 'pages')
os.makedirs(PAGES_FOLDER, exist_ok=True)

# 密码经过哈希处理后存储
USERS = {
    "admin": {
        "password": generate_password_hash("admin123"),
        "role": "admin",
        "email": "admin@example.com",
        "phone": "13800138000",
        "balance": 99999
    },
    "alice": {
        "password": generate_password_hash("alice2025"),
        "role": "user",
        "email": "alice@example.com",
        "phone": "13900139001",
        "balance": 100
    }
}

# 用户余额存储
user_balances = {
    1: USERS["admin"]["balance"],
    2: USERS["alice"]["balance"]
}


def get_user_by_id(user_id):
    """通过 user_id 查询用户信息"""
    try:
        user_id = int(user_id)
    except (ValueError, TypeError):
        return None

    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            username = row["username"]
            balance = user_balances.get(user_id, 0)
            return {
                "id": row["id"],
                "username": username,
                "email": row["email"] or "",
                "phone": row["phone"] or "",
                "balance": balance
            }
    except Exception as e:
        print(f"[get_user_by_id ERROR] {e}")

    return None


# ============================================================
# 数据库初始化
# ============================================================
DATABASE = os.path.join(os.path.dirname(__file__), 'data', 'users.db')


def get_db():
    """获取数据库连接"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """初始化数据库，创建 users 表和 comments 表"""
    os.makedirs(os.path.dirname(DATABASE), exist_ok=True)

    conn = get_db()
    cursor = conn.cursor()

    # 创建 users 表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            email TEXT,
            phone TEXT
        )
    ''')

    # Day7 新增：创建留言板评论表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    ''')

    # 使用哈希密码插入默认用户
    admin_pw = generate_password_hash("admin123")
    alice_pw = generate_password_hash("alice2025")

    cursor.execute(
        "INSERT OR IGNORE INTO users (username, password, email, phone) "
        "VALUES (?, ?, ?, ?)",
        ("admin", admin_pw, "admin@example.com", "13800138000")
    )
    cursor.execute(
        "INSERT OR IGNORE INTO users (username, password, email, phone) "
        "VALUES (?, ?, ?, ?)",
        ("alice", alice_pw, "alice@example.com", "13900139001")
    )

    conn.commit()
    conn.close()
    print("[DB] 数据库初始化完成")


# 启动时初始化数据库
init_db()


def get_user_info(username):
    """获取用户信息（不包含密码字段），供模板使用"""
    if username and username in USERS:
        user = USERS[username]
        return {
            "username": username,
            "role": user["role"],
            "email": user["email"],
            "phone": user["phone"],
            "balance": user["balance"]
        }
    return None


# ============================================================
# 路由
# ============================================================

@app.route("/")
def index():
    username = session.get("username")
    user_info = get_user_info(username)

    # Day7 新增：加载所有留言评论（用于XSS演示）
    comments = []
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM comments ORDER BY id DESC")
        rows = cursor.fetchall()
        comments = [dict(row) for row in rows]
        conn.close()
    except Exception as e:
        print(f"[INDEX ERROR] 加载评论失败: {e}")

    return render_template("index.html", user=user_info, comments=comments)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")

        user = USERS.get(username)
        if user and check_password_hash(user["password"], password):
            session.permanent = True
            session["username"] = username
            user_info = get_user_info(username)
            # 加载评论
            comments = []
            try:
                conn = get_db()
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM comments ORDER BY id DESC")
                rows = cursor.fetchall()
                comments = [dict(row) for row in rows]
                conn.close()
            except Exception as e:
                print(f"[LOGIN ERROR] 加载评论失败: {e}")
            return render_template("index.html", user=user_info, comments=comments)
        else:
            return render_template("login.html", error="用户名或密码错误")

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        email = request.form.get("email", "")
        phone = request.form.get("phone", "")

        # 对密码进行哈希处理
        hashed_pw = generate_password_hash(password)

        sql = "INSERT INTO users (username, password, email, phone) VALUES (?, ?, ?, ?)"
        params = (username, hashed_pw, email, phone)
        print(f"[REGISTER SQL] {sql}")
        print(f"[REGISTER PARAMS] {params}")

        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute(sql, params)
            conn.commit()
            conn.close()
            # 同时更新 USERS 字典，使新注册用户可以登录
            USERS[username] = {
                "password": hashed_pw,
                "role": "user",
                "email": email,
                "phone": phone,
                "balance": 0
            }
            return render_template("login.html", success="注册成功，请登录")
        except Exception as e:
            print(f"[REGISTER ERROR] {e}")
            return render_template("register.html", error=f"注册失败：{e}")

    return render_template("register.html")


@app.route("/search")
def search():
    keyword = request.args.get("keyword", "")

    username = session.get("username")
    user_info = get_user_info(username)

    results = []
    if keyword:
        sql = (
            "SELECT * FROM users "
            "WHERE username LIKE ? OR email LIKE ?"
        )
        params = (f"%{keyword}%", f"%{keyword}%")
        print(f"[SEARCH SQL] {sql}")
        print(f"[SEARCH PARAMS] {params}")

        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            results = [dict(row) for row in rows]
            conn.close()
        except Exception as e:
            print(f"[SEARCH ERROR] {e}")
            return render_template(
                "index.html",
                user=user_info,
                keyword=keyword,
                results=[],
                search_error=f"搜索出错：{e}"
            )

    return render_template(
        "index.html",
        user=user_info,
        keyword=keyword,
        results=results
    )


@app.route("/upload", methods=["GET", "POST"])
def upload():
    username = session.get("username")
    if not username:
        return redirect("/login")

    user_info = get_user_info(username)

    if request.method == "POST":
        if 'file' not in request.files:
            return render_template("upload.html", user=user_info, error="未选择文件")

        file = request.files['file']

        if file.filename == '':
            return render_template("upload.html", user=user_info, error="未选择文件")

        filename = file.filename
        filepath = os.path.join(UPLOAD_FOLDER, filename)

        try:
            file.save(filepath)
            file_url = f"/static/uploads/{filename}"
            print(f"[UPLOAD] 文件已保存: {filepath}")
            print(f"[UPLOAD] 访问 URL: {file_url}")
            return render_template("upload.html", user=user_info, success=True, file_url=file_url, filename=filename)
        except Exception as e:
            print(f"[UPLOAD ERROR] {e}")
            return render_template("upload.html", user=user_info, error=f"上传失败：{e}")

    return render_template("upload.html", user=user_info)


@app.route("/profile")
def profile():
    user_id = request.args.get("user_id", "")
    username = session.get("username")
    user_info = get_user_info(username)

    if not user_id:
        return render_template("profile.html", user=user_info, profile_user=None)

    profile_user = get_user_by_id(user_id)

    if not profile_user:
        return render_template("profile.html", user=user_info, profile_user=None, error=f"用户 ID {user_id} 不存在")

    return render_template("profile.html", user=user_info, profile_user=profile_user)


@app.route("/recharge", methods=["POST"])
def recharge():
    user_id = request.form.get("user_id", "")
    amount_str = request.form.get("amount", "0")

    try:
        user_id_int = int(user_id)
        amount = int(amount_str)
    except (ValueError, TypeError):
        username = session.get("username")
        user_info = get_user_info(username)
        return render_template("profile.html", user=user_info, profile_user=None, error="参数格式错误")

    if user_id_int in user_balances:
        user_balances[user_id_int] = user_balances[user_id_int] + amount
    else:
        user_balances[user_id_int] = amount

    print(f"[RECHARGE] user_id={user_id_int}, amount={amount}, new_balance={user_balances[user_id_int]}")

    return redirect(f"/profile?user_id={user_id_int}")


@app.route("/page")
def page():
    name = request.args.get("name", "")

    username = session.get("username")
    user_info = get_user_info(username)

    if not name:
        return render_template("index.html", user=user_info, page_content="<p>请指定页面名称参数，例如：/page?name=help</p>")

    filepath = os.path.join(PAGES_FOLDER, name)
    print(f"[PAGE] 请求页面: {name}")
    print(f"[PAGE] 拼接路径: {filepath}")

    if os.path.isfile(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            print(f"[PAGE] 成功加载: {filepath}")
            return render_template("index.html", user=user_info, page_content=content)
        except Exception as e:
            print(f"[PAGE ERROR] 读取文件失败: {e}")
            return render_template("index.html", user=user_info, page_content=f"<p>读取页面失败：{e}</p>")

    html_filepath = os.path.join(PAGES_FOLDER, name + ".html")
    print(f"[PAGE] 文件不存在，尝试 .html 后缀: {html_filepath}")

    if os.path.isfile(html_filepath):
        try:
            with open(html_filepath, "r", encoding="utf-8") as f:
                content = f.read()
            print(f"[PAGE] 成功加载: {html_filepath}")
            return render_template("index.html", user=user_info, page_content=content)
        except Exception as e:
            print(f"[PAGE ERROR] 读取文件失败: {e}")
            return render_template("index.html", user=user_info, page_content=f"<p>读取页面失败：{e}</p>")

    print(f"[PAGE] 页面不存在: {name}")
    return render_template("index.html", user=user_info, page_content="<p>页面不存在</p>")


# ============================================================
# Day7 新增：留言板路由（存在存储型XSS漏洞）
# ============================================================
@app.route("/post-comment", methods=["POST"])
def post_comment():
    # 需要登录才能留言
    username = session.get("username")
    if not username:
        return redirect("/login")

    content = request.form.get("content", "")

    if content:
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO comments (username, content, created_at) VALUES (?, ?, ?)",
                (username, content, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )
            conn.commit()
            conn.close()
            print(f"[COMMENT] {username} 发表了留言: {content[:50]}...")
        except Exception as e:
            print(f"[COMMENT ERROR] {e}")

    return redirect("/")


# ============================================================
# Day7 新增：修改密码路由（存在CSRF漏洞）
# 漏洞特征：
#   1. 无 CSRF Token 验证
#   2. 不验证原密码
#   3. 不校验 session 用户与提交 username 是否一致
#   4. 不验证 Referer 请求来源
#   5. 任何已登录用户都可以修改任何人的密码
# ============================================================
@app.route("/change-password", methods=["POST"])
def change_password():
    # 只检查是否登录，不检查其他任何内容
    username = session.get("username")
    if not username:
        return redirect("/login")

    target_username = request.form.get("username", "")
    new_password = request.form.get("new_password", "")

    if not target_username or not new_password:
        # 参数缺失时重定向到个人中心
        return redirect("/profile")

    # 直接更新密码，不验证原密码
    # 不校验当前登录用户是否有权限修改目标用户的密码
    hashed_pw = generate_password_hash(new_password)

    # 更新内存中的 USERS 字典
    if target_username in USERS:
        USERS[target_username]["password"] = hashed_pw
        print(f"[CHANGE-PASSWORD] 用户 {target_username} 的密码已被 {username} 修改（内存）")

    # 更新数据库中的密码
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET password = ? WHERE username = ?",
            (hashed_pw, target_username)
        )
        conn.commit()
        conn.close()
        print(f"[CHANGE-PASSWORD] 用户 {target_username} 的密码已被 {username} 修改（数据库）")
    except Exception as e:
        print(f"[CHANGE-PASSWORD ERROR] {e}")

    # 修改成功后重定向到个人中心
    return redirect("/profile")


# ============================================================
# Day7 新增：用户反馈/搜索回显路由（存在反射型XSS漏洞）
# 用户输入的内容直接回显到页面，使用 | safe 过滤器不做转义
# ============================================================
@app.route("/feedback", methods=["GET", "POST"])
def feedback():
    username = session.get("username")
    user_info = get_user_info(username)

    feedback_msg = ""
    echo_content = ""

    if request.method == "POST":
        feedback_msg = request.form.get("message", "")
        # 直接回显用户输入，不做HTML转义（反射型XSS漏洞）
        # 模板中使用 | safe 过滤器渲染
        echo_content = feedback_msg
        print(f"[FEEDBACK] 收到反馈: {feedback_msg[:100]}")

    # 支持 GET 方式的搜索回显（也是反射型XSS）
    search_query = request.args.get("q", "")

    return render_template(
        "index.html",
        user=user_info,
        feedback_msg=feedback_msg,
        echo_content=echo_content,
        search_query=search_query
    )


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5000)
