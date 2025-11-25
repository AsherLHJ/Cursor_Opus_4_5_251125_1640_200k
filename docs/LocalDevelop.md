# 本地开发者模式（Windows 11｜不使用 Docker）

本指南帮助你在 Windows 11 上“本地直接运行”后端服务并连接本机 MySQL 数据库，适用于开发调试与单机试用。该模式不依赖 Docker，也不访问服务器私网数据库。

---

## 1. 前置条件

- Windows 11（x86_64 / AMD64）
- 已安装 Python 3.9+（推荐 3.10/3.11）
- 已安装 MySQL 8.0+（本机运行）
- PowerShell 终端（以普通用户即可）

可选：安装 Git 便于拉取仓库。

---
## 跳过下方步骤2、3的条件
如果之前已经完成了项目AutoPaperWeb_DB_Tool的配置（包括本地MySQL数据库安装和数据完成导入），则可直接使用该项目已在本地计算机上创建的conda虚拟环境。不用再次进行下方步骤2和3的配置。

相关GitHub地址：
https://github.com/AsherLHJ/AutoPaperWeb_DB_Tool

## 2. 获取代码与安装依赖

# 1）克隆或下载仓库到本地：

```powershell
# 任选其一：
# git clone https://github.com/<your>/<repo>.git
# 或者下载 zip 并解压
cd C:\path\to\AutoPaperWeb_Server
```

# 2）安装 Python 依赖：

# 2.2.1 安装conda-forge（conda的社区免费版本）并配置系统变量
https://conda-forge.org/download/

# 2.2.2 创建并激活conda虚拟环境：

# 新建名为AI_tool_db的环境，指定Python 3.10版本
```powershell
conda create -n AI_tool_db python=3.10 -y
```

# 激活该环境
```powershell
conda activate AI_tool_db
```

# 转到本项目所在文件根目录
```powershell
cd 本项目所在目录
```
# 安装配置文件
```powershell
python .\install_requirements.py
```

脚本会安装以下库：
- openai（OpenAI 兼容 SDK）
- mysql-connector-python（MySQL 连接器）

并创建 Data/Result/Log 目录（如不存在）。

---

## 3. 准备本地 MySQL 数据库（如果已经配置好本地数据库，可跳过）

1）创建数据库与账号（示例）：

```sql
CREATE DATABASE IF NOT EXISTS PaperDB CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'paper_user'@'127.0.0.1' IDENTIFIED BY 'Paper2025';
CREATE USER IF NOT EXISTS 'paper_user'@'localhost' IDENTIFIED BY 'Paper2025';
GRANT ALL PRIVILEGES ON PaperDB.* TO 'paper_user'@'127.0.0.1';
GRANT ALL PRIVILEGES ON PaperDB.* TO 'paper_user'@'localhost';
FLUSH PRIVILEGES;
```

2）创建必要的数据表（根据当前代码用到的列最小集合）：

```sql
USE PaperDB;

-- 用户表（登录、权限/并发额度）
CREATE TABLE IF NOT EXISTS user_info (
  uid INT AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(64) NOT NULL UNIQUE,
  password VARCHAR(128) NOT NULL,
  balance DECIMAL(10,1) NOT NULL DEFAULT 0.0,
  permission INT NOT NULL DEFAULT 50
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- API Key 列表（从数据库读取 Ark API Key）
CREATE TABLE IF NOT EXISTS api_list (
  api_index INT AUTO_INCREMENT PRIMARY KEY,
  api_key VARCHAR(255) NOT NULL,
  up TINYINT(1) NOT NULL DEFAULT 1,
  query_table VARCHAR(128) NULL,
  search_id INT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 论文目录（数据源名称列表）
CREATE TABLE IF NOT EXISTS ContentList (
  Name VARCHAR(255) PRIMARY KEY
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 论文详情（最小字段集）
CREATE TABLE IF NOT EXISTS PaperInfo (
  Name VARCHAR(255) NOT NULL,
  Year INT NULL,
  Title TEXT,
  Author TEXT,
  DOI VARCHAR(255),
  Abstract TEXT,
  Bib MEDIUMTEXT,
  INDEX idx_name (Name),
  INDEX idx_doi (DOI)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 检索日志表由程序自动创建（db_reader.ensure_searchinglog_table）
-- 每日检索表 search_YYYYMMDD 由程序自动创建（db_reader.create_search_table）
```

3）导入你的数据：
- 向 `ContentList(Name)` 插入你的数据源名称（如 `ACM`, `IEEE`, `CHI2024` 等）。
- 向 `PaperInfo` 插入论文条目，至少包含 `Name, Title, Abstract`，推荐提供 `Year, DOI, Bib` 更多字段便于导出。

4）导入 API Key：
- 将你的 Ark 平台 API Key 写入 `api_list(api_key)`；
- 将 `up` 设为 `1` 表示可用；
- `query_table/search_id` 留空即可（程序会占用/释放）。

示例：
```sql
-- 无固定前缀，请直接粘贴火山引擎 Ark 控制台提供的完整密钥
INSERT INTO api_list(api_key, up) VALUES ('<YOUR_ARK_API_KEY>', 1);
```

---

## 4. 配置本地开发者模式

编辑项目根目录 `config.json`，新增/确认如下键：

```json
{
  "local_develop_mode": true,
  "DB_HOST": "127.0.0.1",
  "DB_PORT": 3306,
  "DB_USER": "root",
  "DB_PASSWORD": "123456",
  "DB_NAME": "paperdb",
  "LANGUAGE": "zh_CN",
  "DATA_FOLDER": "LocalDeveloper\\Data",
  "RESULT_FOLDER": "LocalDeveloper\\Result",
  "LOG_FOLDER": "LocalDeveloper\\Log"
}
```

说明：
- 当 `local_develop_mode=true` 时，程序会优先使用 `config.json` 中的 DB 配置，忽略环境变量（避免被 Docker 环境覆盖）。
- 其他字段可按需调整；Windows 路径请使用双反斜杠转义。

---

## 5. 启动服务（本地）
先确保conda激活了已安装相关依赖（install_requirements.py中提到的库）的虚拟环境
例如：
```powershell
conda activate AutoPaperWeb_DB_Tool
```

在项目根目录运行：

```powershell
python .\main.py
```

启动成功后输出类似：

```
WebServer running at http://127.0.0.1:8080/
```

在浏览器打开：
- http://127.0.0.1:8080/  即可访问内置页面 `lib/html/index.html`

---

## 6. 常见问题

- 启动报 MySQL 连接失败：
  - 确认 MySQL 服务已启动，账号/密码/数据库名称正确；
  - 确认 `config.json` 的 DB_* 配置与 “本地开发者模式” 开关已设置为 true；
  - 若使用非默认端口，请同时更新 `DB_PORT`。

- 提示缺少 API Key：
  - 在 `api_list` 表插入至少一条可用 Key；
  - 该 Key 会被任务调度器占用并在完成后释放。

- 页面空白或 404：
  - 确认访问 `http://127.0.0.1:8080/`；
  - 控制台查看输出日志；
  - 确认 `lib/html` 目录存在。

---

## 7. 关闭或切换到在线模式

- 将 `config.json` 的 `local_develop_mode` 改为 `false`，程序会允许环境变量覆盖数据库连接信息（用于 Docker/服务器部署）。
- 服务器部署参考：`docs/DEPLOYMENT.md`。
