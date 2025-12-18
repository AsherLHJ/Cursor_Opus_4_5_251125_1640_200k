### 本地计算机如何向MySQL导入文献并上传云数据库
在用于开发的本地计算机（例如Win11系统）上，可先安装MySQL 8，配置好系统变量后，将文献的.bib文件通过下方“数据库刷新工具”的使用流程导入数据库。然后将导出SQL文件，直接上传至阿里云数据库RDS。

### 添加新的数据库流程
1. 在PaperAndTagInfo\InfoList.Paper.csv中添加期刊/会议的简称，全称，收录的时间范围，更新日期
2. 确保新的数据文件夹和简称一致，且在Data目录下
3. 在PaperAndTagInfo\InfoList.PaperWithTag.csv中添加刊物类型，一级分类，和二级分类（必填）。如有别的标签，可以选填补充，但是所有Tag值务必确保在PaperAndTagInfo\InfoList.Tag.csv中存在。
4. 如果是知网的数据，先用tools_txt_to_bib.py将txt文件转换为bib文件。
5. 用tools_check_bibtexparser.py检查数据是否符合要求，是否有缺失的字段。
6. 用tools_refresh_db_paper.py刷新论文数据库（仅处理 InfoList.Paper.csv 中存在的子文件夹；同步 ContentList 的 Name/FullName/DataRange/UpdateDate；解析 .bib 并写入 PaperInfo）
7. 用tools_refresh_db_tag.py刷新标签数据库（优先读取 UTF-8/UTF-8-SIG 的 InfoList.Tag.csv，兼容 GB2312；确保 info_tag 与 CSV 完全一致；主键列为 Tag，类型列为 TagType）
8. 用tools_refresh_db_paper_with_tag.py刷新论文标签数据库（优先读取 UTF-8/UTF-8-SIG 的 InfoList.PaperWithTag.csv，兼容 GB2312；校验 PaperInfo.Name 与 info_tag.Tag；唯一约束 Name+Tag；无效映射打印原因）

### 如何生成标签
以下是deepseek网页版生成标签的prompt
"""
对于 【期刊/会议的简称和全称】，帮我基于下面的分类信息 ，判断属于哪个刊物类型，哪个一级分类，和哪个二级分类，然后生成。分类时优先考虑中科院分区2025信息的分类标准。

分类信息：
刊物类型：【普通期刊；综述期刊；会议】
一级分类：【材料科学；地球科学；工程技术；管理学；化学；环境科学与生态学；计算机科学；教育学；经济学；历史学；农林科学；社会学；生物学；数学；文学；物理与天体；物理；心理学；医学；艺术学；哲学；综合性期刊】
二级分类：【声学；麻醉学；自然地理；地质学；地球科学:综合；老年医学；老年医学（社科）；绿色可持续发展技术；卫生保健与服务；卫生政策与服务；血液学；科学史与科学哲学；人类学；社会科学史；历史学(小类)；园艺；酒店-休闲-体育与旅游；人文科学；成像科学与照相技术；免疫学；人际关系学；传染病学；图书情报与档案管理；考古学；仪器仪表；全科医学与补充医学；国际关系学；语言与语言学；法学；湖沼学；语言学；文学评论；文学理论与文艺critical；其他形式的文学；建筑学；英联邦文学；美国文学；英国文学；日耳曼语系文学；罗曼语系文学；斯拉夫语系文学；逻辑学；管理学(小类)；海洋与淡水生物学；材料科学:生物材料；地域研究；材料科学:硅酸盐；材料科学:表征与测试；材料科学:膜；材料科学:复合；材料科学:综合；材料科学:纸与木材；材料科学:纺织；数学与计算生物学；数学；应用数学；艺术；数学跨学科应用；力学；医学:伦理；医学:信息；医学实验技术；医学:内科；医学:法；医学:研究与实验；中世纪与文艺复兴研究；冶金工程；亚洲研究；气象与大气科学；微生物学；显微镜技术；矿物学；矿业与矿物加工；综合性期刊(小类)；音乐；真菌学；纳米科技；神经成像；天文与天体物理；神经科学；核科学技术；护理；营养学；妇产科学；海洋学；肿瘤学；运筹学与管理科学；眼科学；光学；听力学与言语病理学；鸟类学；骨科；耳鼻喉科学；古生物学；寄生虫学；病理学；儿科；外周血管病；药学；哲学(小类)；自动化与控制系统；物理:应用；物理:原子-分子和化学物理；物理:凝聚态物理；物理:流体与等离子体；物理:数学物理；物理:综合；物理:核物理；物理:粒子与场物理；生理学；植物科学；农业经济与政策；行为科学；诗歌；政治学；高分子科学；初级卫生保健；精神病学；心理学(小类)；心理学:应用；心理学:生物；心理学:临床；心理学:发育；生化研究方法；心理学:教育；心理学:实验；心理学:数学(小类)；心理学:综合；心理学:分析；心理学:社会；公共管理；公共卫生-环境卫生与职业卫生；量子科技；核医学；生化与分子生物学；区域与城市规划；康复医学；宗教；遥感；生殖生物学；呼吸系统；风湿病学；机器人学；社会问题；社会科学:生物医学；生物多样性保护；社会科学:跨领域；社会科学:数理方法；社会工作；社会学(小类)；土壤科学；光谱学；运动科学；统计学与概率论；药物滥用；外科；生物学(小类)；电信学；戏剧；热力学；毒理学；移植；运输科技；交通运输；热带医学；城市研究；泌尿学与肾脏学；生物物理；兽医学；病毒学；水资源；女性研究；动物学；生物工程与应用微生物；商业:管理；商业:财政与金融；心脏和心血管系统；农业工程；细胞与组织工程；细胞生物学；分析化学；应用化学；无机化学与核化学；药物化学；化学:综合；有机化学；物理化学；古典文学；奶制品与动物科学；临床神经病学；传播学；计算机:人工智能；计算机:控制论；计算机:硬件；计算机:信息系统；计算机:跨学科应用；计算机:软件工程；计算机:理论方法；结构与建筑技术；农业综合；犯罪学与刑罚学；危重病医学；晶体学；文化研究；舞蹈；人口学；牙科与口腔外科；皮肤病学；发展研究；发育生物学；农艺学；生态学；经济学(小类)；教育学和教育研究；学科教育；特殊教育学；电化学；急救医学；内分泌学与代谢；能源与燃料；工程:宇航；过敏；工程:生物医学；工程:化工；工程:土木；工程:电子与电气；工程:环境；工程:地质；工程:工业；工程:制造；工程:海洋；工程:机械；解剖学与形态学；工程:综合；工程:大洋；工程:石油；昆虫学；环境科学；环境研究；人体工程学；伦理学；民族研究；进化生物学；男科学；家庭研究；电影-广播-电视；渔业；民俗学；食品科技；林学；胃肠肝病学；遗传学；地球化学与地球物理；地理学】

一个生成样例是：
CHI, 会议
CHI, 计算机科学
CHI, 计算机：跨学科应用

仅输出生成样例类的内容
"""

## 1. tools_refresh_db_paper.py - 数据库刷新工具

### 功能更新
- 读取 `PaperAndTagInfo/InfoList.Paper.csv`，只处理其中存在的 `Name` 对应的 `Data` 子文件夹，其他文件夹跳过并在结尾汇报。
- 保障 `ContentList` 结构包含 `Name, FullName, DataRange, UpdateDate`，老库缺列时自动 `ALTER TABLE` 补齐。
- 解析有效 `.bib` 条目并写入 `PaperInfo`（`DOI` 为主键，`Title` 唯一索引，`Name/Year` 索引）。

### 使用方法
### （这里只是介绍，不是创建本地数据库的第一步。若要创建本地数据库并上传到云，请从“1.1 修改配置信息”开始）
```bash
python tools_refresh_db_paper.py
```

### 必要条件
- `Data/{子文件夹名}` 必须与 `InfoList.Paper.csv` 的 `Name` 值完全一致。
- `.bib` 条目需包含 `title/abstract/author/doi/year` 等必要字段；缺失会被跳过。

### 输出与提示
- 打印成功处理的文件夹列表与跳过的文件夹原因。
- 显示每个 `.bib` 的解析条目数量与插入尝试数。

### 常见问题
- 报错 `Unknown column 'FullName' in 'field list'`：脚本已在 `ensure_contentlist_table()` 中自动补齐列；如果仍报错，请确认 MySQL 权限允许 `ALTER TABLE`。



### 请执行以下步骤以创建本地数据库并上传到云============

### 1.1 修改配置信息
需要在 `config.json` 中配置数据库连接信息：
```json
{
    "DB_HOST": "127.0.0.1",
    "DB_PORT": 3306,
    "DB_USER": "root",
    "DB_PASSWORD": "your_password",
    "DB_NAME": "paperdb"
}
```
### 1.2 安装conda-forge（conda的社区免费版本）并配置系统变量
https://conda-forge.org/download/

### 1.3 创建并激活conda虚拟环境

# 新建名为AI_tool_db的环境，指定Python 3.10版本
conda create -n AI_tool_db python=3.10 -y

# 激活该环境
conda activate AI_tool_db

# 转到本项目所在文件目录
cd 本项目所在目录

# 安装requirements.txt中的依赖（确保当前目录下有该文件）
conda install --file requirements.txt -y

# （若上一步出错）如果conda install安装依赖时出现问题（例如某些包 conda 源中没有），可以尝试使用 pip 安装：
pip install -r requirements.txt

### 1.4 把包含文献的.bib文件的文件夹加放入本项目（AutoPaperWeb_DB_Tool）内的Data目录下
目录结构示例：
Data
 |
 |---CHI
      |---CHI_2015.bib
      |---CHI_2016.bib      
 |---CVPR
      |---CVPR_2015.bib
      |---CVPR_2016.bib    

### 1.5 在命令行登录MySQL后，用以下命令创建三个表1.1 修改配置信息
# 登录MySQL
```bash
mysql -u root -p
```
# 确保当前命令行所在目录为本项目（AutoPaperWeb_DB_Tool）所在目录，然后执行以下命令创建 paperdb：
```sql
CREATE DATABASE paperdb 
     CHARACTER SET utf8mb4 
     COLLATE utf8mb4_0900_ai_ci;
```

# 查看数据库的字符集设置，确认是否生效：
```sql
SHOW CREATE DATABASE paperdb;
```

# 切换到刚刚创建的数据库paperdb:
```sql
use paperdb;
```

# 创建表 user_info
```sql
CREATE TABLE IF NOT EXISTS user_info (
     uid INT NOT NULL AUTO_INCREMENT,
     username VARCHAR(255) NOT NULL,
     password VARCHAR(255) NOT NULL,
     balance DECIMAL(10,2) DEFAULT 0.00,
     permission INT DEFAULT 0,
     PRIMARY KEY (uid),
     UNIQUE KEY uk_user_info_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
```

# 创建表 api_usage_minute
```sql
CREATE TABLE IF NOT EXISTS api_usage_minute (
     id BIGINT PRIMARY KEY AUTO_INCREMENT,
     account_name VARCHAR(128) NOT NULL,
     minute_ts DATETIME NOT NULL,
     used_req INT NOT NULL,
     used_tokens BIGINT NOT NULL,
     UNIQUE KEY uniq_usage (account_name, minute_ts)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
```

# 创建表 task_queue
```sql
CREATE TABLE IF NOT EXISTS task_queue (
     id BIGINT PRIMARY KEY AUTO_INCREMENT,
     uid INT NOT NULL,
     query_index BIGINT NOT NULL,
     doi VARCHAR(512) NOT NULL,
     priority INT DEFAULT 0,
     state ENUM('waiting','ready','running','done','failed','canceled') NOT NULL DEFAULT 'waiting',
     running_since DATETIME NULL,
     attempt_count INT NOT NULL DEFAULT 0,
     last_attempt_at DATETIME NULL,
     last_error TEXT NULL,
     eta_start_at DATETIME NULL,
     created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
     updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
     UNIQUE KEY uniq_task (query_index, doi),
     INDEX idx_uid (uid),
     INDEX idx_qi (query_index),
     INDEX idx_state (state),
     INDEX idx_state_uid (state, uid),
     INDEX idx_query_state (query_index, state)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
```

# 创建表 query_log
```sql
CREATE TABLE IF NOT EXISTS query_log (
     query_index INT NOT NULL AUTO_INCREMENT,
     uid INT NOT NULL DEFAULT 1,
     query_time VARCHAR(32) NULL,
     selected_folders TEXT NULL,
     year_range VARCHAR(64) NULL,
     research_question TEXT NULL,
     requirements TEXT NULL,
     query_table VARCHAR(128) NULL,
     start_time VARCHAR(32) NOT NULL,
     end_time VARCHAR(32) NULL,
     total_papers_count INT DEFAULT 0,
     is_distillation BOOLEAN DEFAULT FALSE,
     is_visible BOOLEAN DEFAULT TRUE,
     should_pause BOOLEAN DEFAULT FALSE,
     actual_cost DECIMAL(10,1) NOT NULL DEFAULT 0.0,
     total_cost DECIMAL(10,1) NOT NULL DEFAULT 0.0,
     PRIMARY KEY (query_index),
     INDEX idx_querylog_uid (uid)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
```
# 创建表 app_settings（）
```sql
CREATE TABLE IF NOT EXISTS app_settings (
     k VARCHAR(64) PRIMARY KEY,
     v VARCHAR(255) NOT NULL,
     updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
```

# 然后退出MySQL的交互式命令行
```sql
quit;
```

### 把API key导入数据库（项目后期会删掉这个功能，因为用不到这么多API key）
1）把包含所有APIKey的.txt文件放在APIKey目录下
2）运行
```bash
python tools_refresh_db_api.py
```

3）然后依次运行：
```bash
python tools_refresh_db_paper.py
python tools_refresh_db_tag.py
python tools_refresh_db_paper_with_tag.py
python tools_refresh_db_sentence.py
```
### 可选操作1：导出本地数据库中的指定表，但仅向对方数据库《插入新增数据》，不覆盖原有数据===========
# 下方示例中会导出“contentlist”，“contentlist_year_number”，“paperinfo”，“info_tag”，“info_paper_with_tag”这5个表（复制该命令前请修改"指定路径"和“sql文件名”）
```bash
# PowerShell 建议使用 --result-file，避免使用重定向 > 导致编码被更改
mysqldump -u root -p --default-character-set=utf8mb4 --no-create-info --skip-add-drop-table --insert-ignore --hex-blob --result-file="paperdb_YYYYMMDD.sql" paperdb contentlist contentlist_year_number paperinfo info_tag info_paper_with_tag
```
### 可选操作1（结束）

### 可选操作2：《危险操作，谨慎使用》导出本地数据库中的指定表，且《覆盖对方数据库原有数据》===========
# 下方示例中会导出“contentlist”，“contentlist_year_number”，“paperinfo”，“info_tag”，“info_paper_with_tag”这5个表（复制该命令前请修改"指定路径"和“sql文件名”）
# 注意：谨慎导出用户数据表“user_info”，防止覆盖生产环境的现存用户数据
```bash
# PowerShell 建议使用 --result-file，避免使用重定向 > 导致编码被更改
mysqldump -u root -p --default-character-set=utf8mb4 paperdb contentlist contentlist_year_number paperinfo info_tag info_paper_with_tag --add-drop-table --set-charset --result-file="C:\Users\Asher\Downloads\paperdb_YYYYMMDD.sql"
```
### 可选操作2（结束）

### 可选操作3：《危险操作，谨慎使用》导出本地完整数据库，会清除生产环境已存在的用户数据表===========
### 把paperdb数据库导出数据库为 SQL 文件，放在指定目录下（复制该命令前请修改"指定路径"和“sql文件名”）
```bash
# PowerShell 建议使用 --result-file，避免使用重定向 > 导致编码被更改
mysqldump -u root -p --default-character-set=utf8mb4 paperdb --add-drop-table --set-charset --result-file="C:\Users\Asher\Downloads\paperdb_YYYYMMDD.sql"
```
### 可选操作3（结束）

# 接下来上传到云数据库（云数据库在新建时也选择 utf8mb4 编码）
- 登录 RDS 控制台 → 数据导入 → 批量数据导入
- 数据库选择：`paperdb_YYYYMMDD` 或需导入的目标库
- 文件类型：SQL 脚本；编码：自动识别；模式：极速模式
6）点击“上传文件”，选择刚刚导出的sql文件（例如paperdb_20251027.sql）。注意，单次上传的文件大小不超过5GB。



### 以下是其他功能，与上传数据到云数据库无关===============================
### 以下是其他功能，与上传数据到云数据库无关===============================
### 以下是其他功能，与上传数据到云数据库无关===============================
### 以下是其他功能，与上传数据到云数据库无关===============================
### 以下是其他功能，与上传数据到云数据库无关===============================


# AutoPaperWeb 工具集说明

本项目包含多个用于处理 BibTeX 文件和数据库管理的工具。以下是各工具的详细说明和使用方法。

## 工具概览

| 工具名称 | 主要功能 | 输入 | 输出 |
|---------|---------|------|------|
| `tools_refresh_db.py` | 数据库初始化和数据导入 | Data 目录下的 .bib 文件 | MySQL 数据库表 |
| `tools_check_bibtexparser.py` | BibTeX 解析问题诊断 | .bib 文件 | 问题报告 CSV |
| `tools_fix_title.py` | 修复标题字段大括号 | .bib 文件 | 修复后的 .bib 文件 |
| `tools_merge_bib.py` | 合并多个 BibTeX 文件 | 文件夹内的 .bib 文件 | 单个合并的 .bib 文件 |
| `tools_split_bib.py` | 按年份拆分 BibTeX 文件 | 单个 .bib 文件 | 按年份分组的 .bib 文件 |
| `tools_refresh_db_tag.py` | 标签表全量同步（与 CSV 完全一致） | PaperAndTagInfo/InfoList.Tag.csv（GB2312） | `info_tag`（列：Tag, TagType；PK: Tag） |
| `tools_refresh_db_paper_with_tag.py` | 论文-标签映射导入与校验 | PaperAndTagInfo/InfoList.PaperWithTag.csv（默认GB2312） | `info_paper_with_tag`（id AI PK；唯一 Name+Tag） |

---

## 2. tools_check_bibtexparser.py - BibTeX 解析检查工具

### 功能描述
- 检查 bibtexparser 无法正确解析的 BibTeX 内容
- 识别文件级、条目级和字段级解析问题
- 检测 dataset 类型条目
- 生成详细的问题报告

### 使用方法
```bash
python tools_check_bibtexparser.py
```

### 输出文件
- `BibTexParser_Check_YYYYMMDD_HHMM.csv` - 详细问题报告
- `BibTexParser_Summary_YYYYMMDD_HHMM.csv` - 文件级汇总
- `Dataset_Entries_YYYYMMDD_HHMM.bib` - dataset 类型条目（如有）

### 检查项目
1. 文件级解析错误
2. 条目级解析错误  
3. 字段级缺失（title, abstract, author, doi, year）

---

## 3. tools_fix_title.py - 标题字段修复工具

### 功能描述
- 修复 title 和 shorttitle 字段中的多余大括号
- 将 `{Word1} {Word2} {Word3}` 格式修复为 `{Word1 Word2 Word3}` 格式
- 处理连字符情况：`{Word1}-{Word2}` → `Word1-Word2`
- 自动创建备份文件

### 使用方法
```bash
# 处理单个文件
python tools_fix_title.py "path/to/file.bib"

# 处理文件夹下所有 .bib 文件
python tools_fix_title.py "path/to/folder"

# 不创建备份文件
python tools_fix_title.py --no-backup "path/to/file.bib"
```

### 示例
```bash
python tools_fix_title.py "c:\Github\AutoPaperWeb\BibPreProcess\IJHCI_2021.bib"
```

### 修复规则
- `{Word}` → `Word`
- `{Word1} {Word2}` → `Word1 Word2`
- `{Word1}-{Word2}` → `Word1-Word2`
- 保持包含特殊字符的大括号不变

---

## 4. tools_merge_bib.py - BibTeX 文件合并工具

### 功能描述
- 合并指定文件夹下的所有 .bib 文件
- 按文件名排序合并
- 自动处理编码问题（UTF-8/GBK）
- 输出文件名为文件夹名

### 使用方法
```bash
# 命令行指定文件夹
python tools_merge_bib.py "path/to/folder"

# 使用默认示例文件夹
python tools_merge_bib.py
```

### 示例
```bash
python tools_merge_bib.py "c:\Github\AutoPaperWeb\BibPreProcess\TOCHI_2016"
```

### 输出
- 合并后的文件保存在文件夹的父目录
- 文件名格式：`{文件夹名}.bib`

---

## 5. tools_split_bib.py - BibTeX 文件拆分工具

### 功能描述
- 按年份将大型 .bib 文件拆分为多个小文件
- 从文件名或条目的 year 字段提取年份
- 跳过 string、preamble、comment 类型条目
- 支持大文件的分块处理

### 使用方法
```bash
# 命令行指定文件
python tools_split_bib.py "path/to/file.bib"

# 使用默认文件
python tools_split_bib.py
```

### 示例
```bash
python tools_split_bib.py "C:\Github\AutoPaperWeb\BibPreProcess\IMWUT.bib"
```

### 输出结构