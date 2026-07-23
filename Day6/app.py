from flask import Flask, render_template, request, redirect, session
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import timedelta
import sqlite3
import os

app = Flask(__name__)
# 修复：使用随机生成的强密钥，替代原来的弱密钥 "dev-key-2025"
app.secret_key = os.urandom(24).hex()

# 修复：设置会话有效期，30分钟无操作自动过期
app.permanent_session_lifetime = timedelta(minutes=30)

# Day4 新增：设置上传文件最大大小为 16MB
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# Day4 新增：上传文件保存目录
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Day6 新增：页面文件存放目录
PAGES_FOLDER = os.path.join(os.path.dirname(__file__), 'pages')
os.makedirs(PAGES_FOLDER, exist_ok=True)

# 修复：密码经过哈希处理后存储，不再存储明文密码
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

# ============================================================
# Day5 新增：用户余额存储（user_id -> balance）
# ============================================================
user_balances = {
    1: USERS["admin"]["balance"],    # admin: 99999
    2: USERS["alice"]["balance"]     # alice: 100
}


def get_user_by_id(user_id):
    """通过 user_id 查询用户信息，结合数据库和 USERS 字典"""
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
# 数据库初始化（Day3）
# ============================================================
DATABASE = os.path.join(os.path.dirname(__file__), 'data', 'users.db')


def get_db():
    """获取数据库连接"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """初始化数据库，创建 users 表并插入默认用户"""
    # 确保 data/ 目录存在
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

    # 使用哈希密码插入默认用户
    admin_pw = generate_password_hash("admin123")
    alice_pw = generate_password_hash("alice2025")

    # 【已修复】使用参数化查询（? 占位符），防止 SQL 注入
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
    return render_template("index.html", user=user_info)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")

        # 修复：使用安全的 check_password_hash 比对密码，不再直接 == 比较
        # 修复：不管用户名存不存在，都返回一样的提示，防止攻击者枚举用户名
        user = USERS.get(username)
        if user and check_password_hash(user["password"], password):
            session.permanent = True  # 启用会话有效期
            session["username"] = username
            user_info = get_user_info(username)
            return render_template("index.html", user=user_info)
        else:
            return render_template("login.html", error="用户名或密码错误")

    return render_template("login.html")


# ============================================================
# Day3：注册路由（【已修复】使用参数化查询防止 SQL 注入）
# ============================================================
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        email = request.form.get("email", "")
        phone = request.form.get("phone", "")

        # 对密码进行哈希处理
        hashed_pw = generate_password_hash(password)

        # 【已修复】使用参数化查询（? 占位符），防止 SQL 注入
        # 所有用户输入作为参数传递给 execute()，不会被当作 SQL 代码执行
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
            # 注册成功后跳转到登录页，显示提示信息
            return render_template("login.html", success="注册成功，请登录")
        except Exception as e:
            print(f"[REGISTER ERROR] {e}")
            return render_template("register.html", error=f"注册失败：{e}")

    return render_template("register.html")


# ============================================================
# Day3：搜索路由（【已修复】使用参数化查询防止 SQL 注入）
# ============================================================
@app.route("/search")
def search():
    keyword = request.args.get("keyword", "")

    username = session.get("username")
    user_info = get_user_info(username)

    results = []
    if keyword:
        # 【已修复】使用参数化查询（? 占位符），防止 SQL 注入
        # LIKE 通配符 % 在参数中拼接，不影响安全性
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


# ============================================================
# Day4 新增：文件上传路由
# ============================================================
@app.route("/upload", methods=["GET", "POST"])
def upload():
    # 需要登录才能访问，未登录跳转到登录页
    username = session.get("username")
    if not username:
        return redirect("/login")

    user_info = get_user_info(username)

    if request.method == "POST":
        # 检查是否有文件被上传
        if 'file' not in request.files:
            return render_template("upload.html", user=user_info, error="未选择文件")

        file = request.files['file']

        # 检查文件名是否为空
        if file.filename == '':
            return render_template("upload.html", user=user_info, error="未选择文件")

        # 使用用户上传的原始文件名保存（不重命名）
        filename = file.filename
        filepath = os.path.join(UPLOAD_FOLDER, filename)

        try:
            file.save(filepath)
            # 构造访问 URL
            file_url = f"/static/uploads/{filename}"
            print(f"[UPLOAD] 文件已保存: {filepath}")
            print(f"[UPLOAD] 访问 URL: {file_url}")
            return render_template("upload.html", user=user_info, success=True, file_url=file_url, filename=filename)
        except Exception as e:
            print(f"[UPLOAD ERROR] {e}")
            return render_template("upload.html", user=user_info, error=f"上传失败：{e}")

    return render_template("upload.html", user=user_info)


# ============================================================
# Day5 新增：个人中心路由（存在越权访问漏洞）
# ============================================================
@app.route("/profile")
def profile():
    # 从 URL 参数获取 user_id，不从 session 获取
    user_id = request.args.get("user_id", "")
    username = session.get("username")
    user_info = get_user_info(username)

    if not user_id:
        return render_template("profile.html", user=user_info, profile_user=None)

    # 根据 user_id 查询用户资料（不验证当前用户是否有权查看）
    profile_user = get_user_by_id(user_id)

    if not profile_user:
        return render_template("profile.html", user=user_info, profile_user=None, error=f"用户 ID {user_id} 不存在")

    return render_template("profile.html", user=user_info, profile_user=profile_user)


# ============================================================
# Day5 新增：充值路由（存在越权访问漏洞）
# ============================================================
@app.route("/recharge", methods=["POST"])
def recharge():
    # 从表单参数获取 user_id 和 amount，不从 session 获取
    user_id = request.form.get("user_id", "")
    amount_str = request.form.get("amount", "0")

    try:
        user_id_int = int(user_id)
        amount = int(amount_str)
    except (ValueError, TypeError):
        username = session.get("username")
        user_info = get_user_info(username)
        return render_template("profile.html", user=user_info, profile_user=None, error="参数格式错误")

    # 直接修改余额，不检查 amount 是否为负数
    if user_id_int in user_balances:
        user_balances[user_id_int] = user_balances[user_id_int] + amount
    else:
        user_balances[user_id_int] = amount

    print(f"[RECHARGE] user_id={user_id_int}, amount={amount}, new_balance={user_balances[user_id_int]}")

    # 充值成功后重定向到个人中心页面
    return redirect(f"/profile?user_id={user_id_int}")


# ============================================================
# Day6 新增：动态页面加载路由（存在路径遍历漏洞）
# ============================================================
@app.route("/page")
def page():
    # 从 URL 参数获取页面名称（如 /page?name=help）
    name = request.args.get("name", "")

    username = session.get("username")
    user_info = get_user_info(username)

    if not name:
        return render_template("index.html", user=user_info, page_content="<p>请指定页面名称参数，例如：/page?name=help</p>")

    # 直接拼接用户输入的 name 到路径中
    # 不做任何路径校验，不检查 ../ 等路径遍历字符
    filepath = os.path.join(PAGES_FOLDER, name)
    print(f"[PAGE] 请求页面: {name}")
    print(f"[PAGE] 拼接路径: {filepath}")

    # 如果文件存在则读取内容
    if os.path.isfile(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            print(f"[PAGE] 成功加载: {filepath}")
            return render_template("index.html", user=user_info, page_content=content)
        except Exception as e:
            print(f"[PAGE ERROR] 读取文件失败: {e}")
            return render_template("index.html", user=user_info, page_content=f"<p>读取页面失败：{e}</p>")

    # 如果文件不存在，尝试加上 .html 后缀再找一次
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

    # 如果仍然找不到则显示"页面不存在"
    print(f"[PAGE] 页面不存在: {name}")
    return render_template("index.html", user=user_info, page_content="<p>页面不存在</p>")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


if __name__ == "__main__":
    # 修复：关闭 debug 模式，防止调试器泄露代码信息
    app.run(debug=False, host="0.0.0.0", port=5000)
