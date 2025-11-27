# 本地开发者模式 (Windows)

本指南帮助你在 Windows 环境下快速搭建开发环境。

## 1. 环境准备

- Python 3.10+
- MySQL 8.0+
- Redis (推荐使用 Docker 或 WSL 安装，Windows 原生版较旧)

## 2. 初始化数据库

项目已提供标准化的数据库初始化套件，无需手动执行 SQL。

1. 确保 MySQL 服务已启动。
2. 确保 `DB_tools/config.json` 或项目根目录 `config.json` 配置正确 (local_develop_mode=true)。
3. 运行初始化脚本：

```powershell
python DB_tools/init_database.py
```

该脚本会自动：
- 创建所有必要的表 (user_info, paperinfo, query_log 等)
- 导入 `DB_tools/PaperAndTagInfo/` 下的元数据
- 导入 `DB_tools/Data/` 下的文献数据 (如有)
- 导入 `DB_tools/APIKey/` 下的 API Key

## 3. 运行后端服务

```powershell
python main.py
```

服务将启动在 `http://127.0.0.1:8080`。

## 4. 访问系统

- **前台**: [http://127.0.0.1:8080/](http://127.0.0.1:8080/)
- **后台管理**: [http://127.0.0.1:8080/admin/login.html](http://127.0.0.1:8080/admin/login.html)
  - 默认管理员账号需手动插入数据库 `admin_info` 表，或使用注册后的普通账号修改 `role='admin'`。

## 5. 开发调试

- 日志文件位于 `LocalDeveloper/Log/debug_console.log`。
- 可在 `config.json` 中开启 `enable_debug_website_console` 以访问 `/debugLog.html`。
