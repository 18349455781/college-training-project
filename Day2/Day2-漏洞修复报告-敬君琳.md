# DAY2-用户信息管理平台——漏洞检测与修复报告

**课程名称**：网络安全技术与应用  
**实验项目**：用户信息管理平台（Flask Web应用）  
**检测工具**：BurpSuite、FOFA、NPS检测脚本  
**报告人**：敬君琳 
**学号**：2024141530063
**日期**：2026年7月19日

---

## 一、实验背景

本次实验是在课堂上搭建的一个简易用户信息管理平台（Flask框架），我们使用今天学到的网络安全知识，对这个项目进行安全检测，找出其中存在的漏洞并进行修复。

这个平台功能很简单：用户登录后可以查看自己的个人信息。虽然功能不多，但"麻雀虽小五脏俱全"，通过分析我发现里面藏了不少安全问题。

---

## 二、检测过程

### 2.1 信息收集——页面源码分析

首先打开浏览器访问登录页面，右键"查看网页源代码"，就发现了问题。

**漏洞发现：** 在 `login.html` 的页面源码第一行，直接以HTML注释的形式写死了默认管理员账号：

```html
<!-- 调试信息 - 默认管理员账号 用户名: admin 密码: admin123 -->
```

这就是老师上课讲的**信息泄露漏洞**。任何能访问到这个页面的人，按一下 F12 就能看到管理员的账号密码，这等于把家门钥匙挂在门外面。

### 2.2 BurpSuite 抓包分析

接下来启动 BurpSuite 设置代理，抓取登录请求的包进行分析。

**BurpSuite 操作步骤：**
1. 打开 BurpSuite，设置 Proxy 监听 127.0.0.1:8080
2. 浏览器设置代理指向 BurpSuite
3. 在登录页面输入用户名 admin、密码 admin123 提交
4. 在 BurpSuite 的 Proxy -> HTTP history 中看到登录请求

**漏洞发现（一）——密码明文传输：**

```
POST /login HTTP/1.1
Host: 127.0.0.1:5000
Content-Type: application/x-www-form-urlencoded

username=admin&password=admin123
```

密码在请求体中直接以明文形式发送。虽然我们现在的实验环境是本地 HTTP，但如果生产环境没有强制 HTTPS，密码在网络传输过程中就是裸奔的。

> 补充：其实严格说这节课还没教 HTTPS 配置，所以这个漏洞我们认识到就行，本次修复主要关注后端存储层面的问题。

**漏洞发现（二）——登录成功后返回密码：**

用 BurpSuite 查看登录成功后的响应报文，发现服务器直接把用户的所有信息（包括密码）返回到了前端页面上：

```html
<td>密码</td>
<td>admin123</td>
```

密码不仅存的是明文，还在前端页面直接展示给用户看。万一用户登录的是公共电脑，别人随便翻一下页面就看到密码了。

### 2.3 源码审计——直接读代码

在老师的指导下，我们直接查看了项目的源代码 `app.py`，发现了最核心的问题。

**漏洞发现——密码明文存储：**

```python
USERS = {
    "admin": {
        "password": "admin123",   # ← 明文！！！
        ...
    },
    "alice": {
        "password": "alice2025",  # ← 明文！！！
        ...
    }
}
```

这就是课程上讲过的**敏感数据明文存储**问题。密码直接以明文字符串写在代码里，而且比对的时候也是直接用 `==`：

```python
if username in USERS and USERS[username]["password"] == password:
```

这意味着：
- 如果数据库文件泄露，所有用户的密码直接暴露
- 如果攻击者通过 SQL 注入或其他方式读取了内存，也能直接拿到密码
- 开发人员能直接看到所有人的密码

### 2.4 其他安全配置问题

查看 `app.py` 最后几行，还发现：

```python
app.secret_key = "dev-key-2025"
```

这个 `secret_key` 是 Flask 用来加密 session 的密钥，设成 `"dev-key-2025"` 这种简单字符串，很容易被猜到或者被暴力破解。攻击者如果拿到了这个 key，可以伪造任意用户的 session 来登录系统。

启动方式也有问题：

```python
app.run(debug=True, host="0.0.0.0", port=5000)
```

`debug=True` 会开启 Flask 的调试模式，可以通过调试器交互界面执行任意 Python 代码，这是非常危险的。

---

## 三、漏洞汇总

经过以上检测，共发现 **6 个安全漏洞**：

| 编号 | 漏洞名称 | 严重程度 | 说明 |
|:----:|----------|:--------:|------|
| ① | **明文密码存储** | 高危 | USERS 字典中密码以明文存储 |
| ② | **HTML注释泄露默认账号** | 中危 | 登录页源码暴露 admin/admin123 |
| ③ | **密码明文展示在前端** | 高危 | 登录后用户信息页面直接显示密码 |
| ④ | **弱 Secret Key** | 中危 | 密钥 "dev-key-2025" 过于简单 |
| ⑤ | **Debug 模式开启** | 高危 | 调试器可被利用执行任意代码 |
| ⑥ | **密码直接 == 比较** | 中危 | 没有使用安全的哈希比较函数 |

---

## 四、漏洞修复方案

### 修复 ①⑥：密码哈希存储 + 安全比对

**问题：** 密码明文存储，直接 `==` 比较。

**修复方法：**
使用 `werkzeug.security` 库的 `generate_password_hash()` 对密码进行哈希处理，登录验证时用 `check_password_hash()` 进行安全比对。

密码经过哈希后，存储的是这样的字符串：

```
scrypt:32768:8:1$X4uOSO9mjZjbfsTx$e30e6a27f2771de2f6fe7db64dd4d8a4176a51f474f9614d213c376d25f524da...
```

这个哈希过程是**不可逆**的，就算数据库被拖走，攻击者也拿不到原始密码。

**代码对比：**

```python
# 修复前：明文存储 + 直接 == 比较
"password": "admin123",
if username in USERS and USERS[username]["password"] == password:

# 修复后：哈希存储 + 安全比对
"password": generate_password_hash("admin123"),
user = USERS.get(username)
if user and check_password_hash(user["password"], password):
```

### 修复 ②：删除调试注释

**问题：** `login.html` 第一行暴露了默认管理员账号。

**修复方法：** 直接删除这行注释。

修复后登录页源码不再泄露任何敏感信息。

### 修复 ③：用户信息不返回密码

**问题：** 登录成功后把包含密码的完整用户信息传给模板，并展示在页面上。

**修复方法：** 新增 `get_user_info()` 函数，只返回不包含密码字段的用户信息：

```python
def get_user_info(username):
    if username and username in USERS:
        user = USERS[username]
        return {
            "username": username,
            "role": user["role"],
            "email": user["email"],
            "phone": user["phone"],
            "balance": user["balance"]
            # 注意：password 字段不返回！
        }
    return None
```

同时修改 `index.html`，删除密码那一行表格：

```html
<!-- 修复前 -->
<td>密码</td>
<td>{{ user.password }}</td>

<!-- 修复后：这行已删除，不展示密码 -->
```

### 修复 ④：使用强密钥

**问题：** `secret_key = "dev-key-2025"` 过于简单。

**修复方法：** 使用 `os.urandom(24).hex()` 生成随机密钥：

```python
# 修复前
app.secret_key = "dev-key-2025"

# 修复后
app.secret_key = os.urandom(24).hex()
```

> 注意： `os.urandom()` 是系统提供的加密级随机数生成器，生成的密钥几乎不可能被猜到。

### 修复 ⑤：关闭 Debug 模式

**问题：** `debug=True` 开启调试模式。

**修复方法：** 设置为 `debug=False`：

```python
# 修复前
app.run(debug=True, host="0.0.0.0", port=5000)

# 修复后
app.run(debug=False, host="0.0.0.0", port=5000)
```

---

## 五、修复后的完整代码

### （一）app.py（主应用文件）

```python
from flask import Flask, render_template, request, redirect, session
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import timedelta
import os

app = Flask(__name__)
# 修复：使用随机生成的强密钥
app.secret_key = os.urandom(24).hex()
# 修复：设置会话有效期，30分钟无操作自动过期
app.permanent_session_lifetime = timedelta(minutes=30)

# 修复：密码经过哈希处理后存储
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

        # 修复：使用安全的 check_password_hash 比对
        # 修复：不管用户名存不存在，都返回一样的提示
        user = USERS.get(username)
        if user and check_password_hash(user["password"], password):
            session.permanent = True
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
    # 修复：关闭 debug 模式
    app.run(debug=False, host="0.0.0.0", port=5000)
```

### （二）templates/login.html（登录页）

```html
{% extends "base.html" %}

{% block title %}登录 - 用户管理系统{% endblock %}

{% block content %}
<div class="card login-card">
    <h2>用户登录</h2>
    <form method="post" action="/login" class="login-form">
        <div class="form-group">
            <label for="username">用户名</label>
            <input type="text" id="username" name="username" placeholder="请输入用户名" required>
        </div>
        <div class="form-group">
            <label for="password">密码</label>
            <input type="password" id="password" name="password" placeholder="请输入密码" required>
        </div>
        {% if error %}
        <div class="error-message">{{ error }}</div>
        {% endif %}
        <button type="submit" class="btn btn-primary">登 录</button>
    </form>
</div>
{% endblock %}
```

> 修复说明：删除了第一行的 `<!-- 调试信息 - 默认管理员账号 用户名: admin 密码: admin123 -->` 注释，不再泄露默认账号。

### （三）templates/index.html（首页）

```html
{% extends "base.html" %}

{% block title %}首页 - 用户管理系统{% endblock %}

{% block content %}
{% if user %}
<div class="card">
    <h2>欢迎回来，{{ user.username }}！</h2>
    <div class="user-info">
        <h3>用户信息</h3>
        <table class="info-table">
            <tr>
                <td>用户名</td>
                <td>{{ user.username }}</td>
            </tr>
            <tr>
                <td>邮箱</td>
                <td>{{ user.email }}</td>
            </tr>
            <tr>
                <td>手机</td>
                <td>{{ user.phone }}</td>
            </tr>
            <tr>
                <td>角色</td>
                <td><span class="role-badge">{{ user.role }}</span></td>
            </tr>
            <tr>
                <td>余额</td>
                <td>{{ user.balance }}</td>
            </tr>
        </table>
    </div>
    <a href="/logout" class="btn btn-logout">退出登录</a>
</div>
{% else %}
<div class="card welcome-card">
    <h2>欢迎来到用户管理系统</h2>
    <p>请先登录以查看您的信息。</p>
    <a href="/login" class="btn btn-primary">前往登录</a>
</div>
{% endif %}
{% endblock %}
```

> 修复说明：删除了原先的密码行 `<td>密码</td>` 和 `<td>{{ user.password }}</td>`，用户信息不再包含密码。

### （四）templates/base.html（基础模板）

> 不需修改，原代码无安全漏洞。

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}用户管理系统{% endblock %}</title>
    <link rel="stylesheet" href="/static/css/style.css">
</head>
<body>
    <nav class="navbar">
        <div class="nav-brand">用户管理系统</div>
        <div class="nav-menu">
            {% if session.username %}
            <span class="nav-welcome">欢迎，{{ session.username }}</span>
            <a href="/logout" class="nav-link">退出</a>
            {% else %}
            <a href="/login" class="nav-link">登录</a>
            {% endif %}
        </div>
    </nav>

    <main class="container">
        {% block content %}{% endblock %}
    </main>
</body>
</html>
```

### （五）static/css/style.css（样式文件）

> 不需修改，样式文件无安全漏洞，原样保留。

---

## 六、修复前后对比

| 检测项 | 修复前 | 修复后 |
|--------|--------|--------|
| 密码存储 | 明文 `"admin123"` | 哈希值 `scrypt:32768:...` |
| 密码比对 | `==` 直接比较 | `check_password_hash()` 安全比对 |
| 登录页源码 | 泄露 `admin/admin123` | 无敏感信息 |
| 用户信息页 | 显示密码明文 | 不显示密码 |
| Secret Key | `"dev-key-2025"` | `os.urandom(24).hex()` 随机密钥 |
| 会话有效期 | 无限制 | 30分钟无操作自动过期 |
| Debug 模式 | `True` | `False` |
| 用户名枚举 | 无防护（判断逻辑有区别） | 统一返回"用户名或密码错误" |

---

## 七、实验总结

通过这次实验，我深刻体会到了"**看起来很小的一个项目，安全问题却一点不少**"。

以前写代码的时候，总觉得功能跑通了就行，从来没想过密码为什么要哈希存储、为什么不能在页面上显示密码、为什么 debug 模式要关掉。这次用 BurpSuite 抓包看请求和响应、用 FOFA 搜索资产、用 NPS 检测脚本做测试，才真正理解了老师在课堂上反复强调的"**安全开发意识**"是什么意思。

几个关键的收获：

1. **密码绝对不能明文存** —— 一定要用哈希函数处理，而且要用 bcrypt/scrypt 这种带盐的算法
2. **敏感信息不要往前端传** —— 后端返回数据时要过滤掉密码等敏感字段
3. **默认账号不能留在代码里** —— 更不用说通过 HTML 注释暴露出来
4. **开发环境和生产环境要分开配置** —— debug 模式只在本地开发用

学习的路还很长，但这些基础的安全意识从现在就要建立起来。以后再写项目，至少不会把管理员密码直接写死在页面上让所有人都看到了 

---

## 八、项目文件清单

```
/opt/Class01/
├── app.py                 # 已修复 - 密码哈希、强密钥、关闭debug
├── templates/
│   ├── base.html          # 无需修改
│   ├── index.html         # 已修复 - 删除密码展示行
│   └── login.html         # 已修复 - 删除调试注释
└── static/
    └── css/
        └── style.css      # 无需修改
```

### 启动方式

```bash
cd /opt/Class01
python3 app.py
```

访问 http://localhost:5000 即可，预设账号 `admin / admin123` 和 `alice / alice2025` 均可正常登录。

---
