from flask import Flask, render_template, request, redirect, session
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import timedelta
import os

app = Flask(__name__)
# 修复：使用随机生成的强密钥，替代原来的弱密钥 "dev-key-2025"
app.secret_key = os.urandom(24).hex()

# 修复：设置会话有效期，30分钟无操作自动过期
app.permanent_session_lifetime = timedelta(minutes=30)

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


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


if __name__ == "__main__":
    # 修复：关闭 debug 模式，防止调试器泄露代码信息
    app.run(debug=False, host="0.0.0.0", port=5000)
and you