# 大二实训Day6：路径遍历漏洞实验报告

**姓名**：敬君琳 &nbsp;&nbsp;&nbsp;&nbsp; **学院**：网络空间安全学院  
**专业**：网络空间安全 &nbsp;&nbsp;&nbsp;&nbsp; **学号**：2024141530063  
**实验日期**：2026年7月23日 &nbsp;&nbsp;&nbsp;&nbsp; **指导老师**：陈腾  
**实验名称**：路径遍历漏洞分析与利用  

---

## 一、实验目的

1. 了解路径遍历漏洞（Path Traversal，又称目录遍历漏洞）的基本概念和原理。
2. 掌握通过修改URL参数中的文件名来实现任意文件读取的攻击方法。
3. 理解在使用 `os.path.join` 拼接路径时，如果不对用户输入进行校验，攻击者可以通过 `../` 等方式穿越到上级目录。
4. 通过实际编写存在漏洞的代码和攻击演示，加深对路径遍历漏洞危害的认识。
5. 学习路径遍历漏洞的防御措施，包括输入校验、路径规范化和白名单机制。

---

## 二、实验环境

- 操作系统：Windows 11 Pro
- 开发语言：Python 3.x + Flask 框架
- 数据库：SQLite 3
- 开发工具：Visual Studio Code
- 测试工具：Burp Suite Professional / Community
- 浏览器：Google Chrome
- 端口：5000（Flask 本地服务）

---

## 三、实验原理

路径遍历漏洞（Path Traversal），也称为目录遍历（Directory Traversal），是指 Web 应用程序在构建文件路径时，将用户输入直接拼接到路径中，而没有对输入内容进行充分的过滤和校验，导致攻击者可以通过构造特殊的字符序列（如 `../`）来访问应用程序预期目录之外的文件。

路径遍历漏洞的产生通常与以下代码模式有关：
- 使用用户输入直接拼接文件路径（如 `os.path.join(base_dir, user_input)`）
- 没有过滤 `../`、`..\` 等路径遍历字符
- 没有使用 `os.path.abspath` 或 `os.path.realpath` 对路径进行规范化
- 没有将访问范围限制在指定的目录内

在 Python 中，`os.path.join` 函数的一个特殊行为是：如果第二个参数以 `/` 或盘符开头，它会忽略第一个参数，直接返回第二个参数的绝对路径。此外，当用户输入包含 `../` 序列时，`os.path.join` 不会自动消除这些序列，而是保留在拼接后的路径中。这意味着攻击者可以通过 `../../../etc/passwd` 等方式访问系统上的任意文件。

本次实验在一套 Flask 用户管理系统上进行。系统新增了 `/page` 路由，使用 `os.path.join("pages", name)` 拼接用户输入的页面名称来加载 HTML 文件。由于没有对 `name` 参数做路径校验或过滤，攻击者可以构造恶意的 `name` 值来读取服务器上的任意文件。

---

## 四、实验内容与步骤

### 4.1 新增动态页面加载功能（/page 路由）

**步骤1**：在 `app.py` 中新增 `/page` 路由，支持 GET 请求。该路由从 URL 参数获取页面名称（如 `/page?name=help`），使用 `os.path.join(PAGES_FOLDER, name)` 拼接文件路径。如果文件存在则读取内容并通过 `render_template` 传递到首页的 `page_content` 变量中显示。如果文件不存在，则尝试在名称后添加 `.html` 后缀再查找一次；如果仍然找不到则显示"页面不存在"。

**步骤2**：创建 `pages/` 目录，在目录中新建 `help.html` 文件。该文件是一个完整的帮助中心页面，包含系统简介、账号注册与登录、个人信息查看、用户搜索、文件上传、账户充值、注意事项和技术架构等使用指南内容。

**步骤3**：修改 `templates/base.html` 导航栏，在导航菜单中添加"帮助中心"链接（`/page?name=help`），登录和未登录状态下均可访问。

**步骤4**：修改 `templates/index.html` 首页模板，在已登录状态的快捷操作区域添加"帮助中心"按钮入口；在未登录状态的欢迎页面也添加"帮助中心"入口；在页面底部（所有内容之后）添加 `page_content` 显示区域，当该变量存在时，使用 `{{ page_content | safe }}` 渲染动态加载的页面内容。

**步骤5**：修改 `static/css/style.css`，新增 `.page-content-card` 样式，为动态页面内容区域添加左侧彩色边框以区分于其他卡片。

**关键代码（/page 路由）**：

```python
@app.route("/page")
def page():
    # 从 URL 参数获取页面名称（如 /page?name=help）
    name = request.args.get("name", "")

    # 直接拼接用户输入的 name 到路径中
    # 不做任何路径校验，不检查 ../ 等路径遍历字符
    filepath = os.path.join(PAGES_FOLDER, name)

    # 如果文件存在则读取内容
    if os.path.isfile(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        return render_template("index.html", user=user_info, page_content=content)

    # 如果文件不存在，尝试加上 .html 后缀再找一次
    html_filepath = os.path.join(PAGES_FOLDER, name + ".html")
    if os.path.isfile(html_filepath):
        with open(html_filepath, "r", encoding="utf-8") as f:
            content = f.read()
        return render_template("index.html", user=user_info, page_content=content)

    # 如果仍然找不到则显示"页面不存在"
    return render_template("index.html", user=user_info, page_content="<p>页面不存在</p>")
```

### 4.2 正常功能测试

启动 Flask 应用后，访问以下 URL 测试正常功能：

- 访问 `http://localhost:5000/page?name=help`：页面成功加载了 `pages/help.html` 的内容，显示帮助中心页面。
- 访问 `http://localhost:5000/page?name=help.html`：由于文件精确存在，直接读取成功。
- 访问 `http://localhost:5000/page?name=nonexistent`：显示"页面不存在"。

### 4.3 路径遍历漏洞验证

完成以上功能开发后，我对系统中存在的路径遍历漏洞进行了验证测试。

**验证一：读取上级目录文件（使用 ../）**

- 在浏览器中访问 `http://localhost:5000/page?name=../app.py`
- 由于 `os.path.join` 不会过滤 `../`，实际拼接路径为 `pages/../app.py`，即 `Day6/app.py`。
- 页面成功返回了 `app.py` 的完整源代码，包括数据库密码（admin123、alice2025）、密钥生成逻辑、所有路由代码等敏感信息。
- 这说明攻击者可以通过路径遍历读取 Web 应用程序的源代码，从而分析出其他漏洞和敏感数据。

**验证二：读取数据库文件**

- 访问 `http://localhost:5000/page?name=../data/users.db`
- 虽然数据库文件是二进制格式，浏览器中显示为乱码，但攻击者可以通过脚本或工具下载该文件。
- 如果攻击者成功获取了 `users.db` 文件，可以使用 SQLite 工具打开，查看所有用户的密码哈希、邮箱、手机等敏感信息。

**验证三：多层路径遍历读取系统文件**

- 访问 `http://localhost:5000/page?name=../../../../Windows/System32/drivers/etc/hosts` 尝试读取系统 hosts 文件。
- 在 Windows 系统上，经过多层 `../` 可以突破项目目录，访问操作系统级别的文件。
- 这说明如果应用以较高权限运行，攻击者可能读取到操作系统的敏感配置文件。

**验证四：读取模板文件**

- 访问 `http://localhost:5000/page?name=../templates/base.html`
- 成功读取了 `base.html` 模板文件的源代码，攻击者可以了解到系统的页面结构和 Jinja2 模板语法，为进一步的模板注入攻击提供信息。

**验证五：Burp Suite 抓包验证**

- 配置浏览器代理为 `127.0.0.1:8080`，启动 Burp Suite 拦截请求。
- 在浏览器中访问 `http://localhost:5000/page?name=help`，在 Burp Suite 的 Proxy 标签页中拦截到 GET 请求。
- 将请求中的 `name` 参数值从 `help` 修改为 `../app.py`，然后转发请求。
- 响应中包含了 `app.py` 的完整源代码，证明了通过修改 HTTP 请求参数可以实现路径遍历攻击。

---

## 五、漏洞分析

本次实验中的路径遍历漏洞主要由以下几个原因造成：

**用户输入直接拼接到文件路径**：在 `/page` 路由中，`name` 参数直接从 URL 查询参数（`request.args`）中获取，然后直接传递给 `os.path.join(PAGES_FOLDER, name)`。代码中没有任何对 `name` 参数的校验逻辑，没有过滤 `../`、`..\` 等路径遍历字符。攻击者可以随意构造包含路径遍历序列的文件名来访问任意文件。

**os.path.join 的路径覆盖特性**：Python 的 `os.path.join` 函数有一个容易被忽略的特性——如果第二个参数以 `/` 或盘符（如 `C:`）开头，它会忽略第一个参数，直接返回第二个参数的绝对路径。这意味着如果攻击者传入 `name=/etc/passwd` 或 `name=C:\Windows\System32\config\SAM`，`os.path.join("pages", "/etc/passwd")` 将直接返回 `/etc/passwd`，完全绕过了 `pages/` 目录的限制。

**未使用路径规范化函数**：代码中没有使用 `os.path.abspath` 或 `os.path.realpath` 对拼接后的路径进行规范化解析。如果使用了这些函数，`../` 序列会被解析为实际的目录位置，然后可以与预期的基准目录进行比对来判断是否发生了路径穿越。

**没有白名单机制**：系统没有维护一个允许访问的页面文件名白名单。如果使用白名单机制（如只允许 `help`、`about` 等预定义的页面名称），攻击者即使传入 `../app.py`，也会因为不在白名单中而被拒绝。

**文件存在性检查不够严格**：代码使用 `os.path.isfile` 检查文件是否存在，但没有检查解析后的真实路径是否仍然位于预期的 `pages/` 目录下。攻击者利用路径遍历访问任意文件时，只要文件存在就会被读取并返回。

---

## 六、修复建议

1. **使用白名单机制**：维护一个允许访问的页面名称列表（如 `["help", "about", "faq"]`），只允许加载白名单中的页面。这是最安全的做法，因为它从根本上杜绝了任意文件访问的可能性。

```python
ALLOWED_PAGES = {"help", "about", "faq"}

@app.route("/page")
def page():
    name = request.args.get("name", "")
    if name not in ALLOWED_PAGES:
        return render_template("index.html", user=user_info, page_content="<p>页面不存在</p>")
    # 从白名单中安全地加载页面
    filepath = os.path.join(PAGES_FOLDER, name + ".html")
    ...
```

2. **路径规范化与范围校验**：使用 `os.path.realpath` 将用户输入拼接后的路径解析为真实的绝对路径，然后使用 `startswith` 或 `commonpath` 检查解析后的路径是否仍然位于预期的 `pages/` 目录下。如果不在预期目录中，则拒绝访问。

```python
import os

real_path = os.path.realpath(os.path.join(PAGES_FOLDER, name))
expected_dir = os.path.realpath(PAGES_FOLDER)
if not real_path.startswith(expected_dir + os.sep):
    return "页面不存在"
```

3. **过滤危险字符**：在拼接路径之前，对用户输入进行过滤，移除或拒绝包含 `../`、`..\`、`/`、`\` 等路径相关字符的输入。但需要注意的是，黑名单过滤方式通常不够安全，攻击者可能通过 URL 编码（`%2e%2e%2f`）、双写（`....//`）等方式绕过。白名单机制是更好的选择。

4. **使用安全的文件读取函数**：如果业务场景允许，可以使用 `send_from_directory` 等 Flask 内置的安全函数，这些函数内部已经实现了路径遍历防护。

5. **最小权限原则**：运行 Web 应用的操作系统用户应该具有最小的文件访问权限。即使存在路径遍历漏洞，攻击者也只能读取 Web 应用用户有权访问的文件，无法读取系统级别的敏感文件。

6. **禁用目录列表**：确保 Web 服务器配置中关闭了目录列表功能，防止攻击者通过路径遍历获取目录结构信息。

---

## 七、实验总结

通过本次实验，我深入理解了路径遍历漏洞（Path Traversal）的原理和危害。在开发 Web 应用时，如果开发者为了方便而将用户输入直接拼接到文件路径中，且没有进行任何输入校验或路径范围限制，就很容易产生路径遍历漏洞。攻击者只需要在 URL 参数中加入 `../` 序列，就可以像浏览本地文件系统一样读取服务器上的任意文件。

本次实验中，我在已有的登录、注册、搜索、文件上传、个人中心和充值功能基础上，新增了动态页面加载功能。在编写代码时，我按照要求故意没有对 `name` 参数做任何路径校验，不使用 `os.path.abspath` 或 `os.path.realpath` 规范化路径，也不检查路径中是否包含 `../`。通过这些有意留下的漏洞，我实际验证了多种路径遍历攻击场景：读取上级目录的源代码文件（`../app.py`）、读取数据库文件（`../data/users.db`）、以及多层路径遍历尝试读取系统文件。

通过这次实验，我深刻认识到以下安全开发原则：
- 永远不要信任用户的输入，所有来自客户端的参数都可能包含恶意的路径遍历序列。
- 使用白名单而非黑名单来限制用户可访问的资源范围。
- 在拼接文件路径时，始终进行路径规范化和范围校验，确保最终访问的文件位于预期的目录之内。
- `os.path.join` 不是安全的——它不会阻止路径遍历攻击。
- 安全校验必须在服务端进行，客户端的任何限制都可以被绕过。

这些经验对于今后从事 Web 安全开发和安全测试工作具有重要的指导意义。

---

## 八、附录

### 8.1 项目文件结构

```
Day6/
├── app.py                 # Flask 主程序（含 /page 路由）
├── pages/                 # 动态页面目录
│   └── help.html          # 帮助中心页面
├── templates/             # Jinja2 模板
│   ├── base.html          # 基础模板（导航栏含帮助中心入口）
│   ├── index.html         # 首页模板（含 page_content 显示区域）
│   ├── login.html         # 登录页
│   ├── register.html      # 注册页
│   ├── upload.html        # 文件上传页
│   └── profile.html       # 个人中心
├── static/                # 静态资源
│   ├── css/
│   │   └── style.css      # 样式表（含 .page-content-card 样式）
│   └── uploads/           # 上传文件目录
└── data/                  # 数据目录
    └── users.db           # SQLite 数据库
```

### 8.2 漏洞利用 Payload 示例

| 攻击目标 | Payload | 说明 |
|----------|---------|------|
| 读取应用源码 | `?name=../app.py` | 读取项目根目录的 app.py |
| 读取数据库 | `?name=../data/users.db` | 读取 SQLite 数据库文件 |
| 读取模板文件 | `?name=../templates/base.html` | 读取模板源代码 |
| 多层穿越 | `?name=../../../etc/passwd` | Linux 系统文件读取 |
| 绝对路径绕过 | `?name=/etc/passwd` | 利用 os.path.join 特性绕过 |
| URL 编码绕过 | `?name=%2e%2e%2fapp%2epy` | 编码后的 ../app.py |
