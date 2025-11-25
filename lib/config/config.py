import os

# 控制是否在提示词中包含要求
include_requirements_in_prompt = True  # 是否在提示词中包含要求
# 已移除：include_keywords_in_prompt（阶段C）

# 界面语言设置（'zh_CN'为中文，'en_US'为英文）
LANGUAGE = 'zh_CN'

# 研究问题
ResearchQuestion = "Explore the caption / subtitle design"

# 要求（对论文筛选的额外要求）
Requirements = """
1. Should conduct user study.
2. Should display subtitle / caption.
"""
# 示例：Requirements = "必须包含用户研究或实验评估"

# 已移除：Keywords（阶段C）

# 系统提示词 - 用于判断论文相关性（已移除关键词相关的第3步与说明，阶段C）
system_prompt = """你是一个学术论文相关性判断专家。你需要判断论文是否与用户的研究问题要找的答案相关。

判断标准（按照数字顺序依次判断）：
1. 如果你判断摘要的内容与用户的研究问题的相关性很高，则相关。不进入下一步判断。否则进入下一步判断。
2. 如果用户给出的#要求#为空，则跳过该步骤。如果你判断摘要的内容符合用户的要求，则相关。不进入下一步判断。否则不相关。

你必须以JSON格式输出判断结果。

输出格式示例（相关）：
{
    "relevant": "Y",
    "reason": "论文探讨了VST技术在混合现实应用中的使用"
}

输出格式示例（不相关）：
{
    "relevant": "N", 
    "reason": "论文仅涉及OST技术，未提及VST或视频透视技术"
}

注意：relevant字段只能是"Y"或"N"，reason字段必须是一句简短精炼的理由。
"""

# 模型名称（火山引擎 Ark OpenAI 兼容接口）
model_name = 'ep-20251105185121-w8d2z'

# API base URL（Ark 平台）
api_base_url = "https://ark.cn-beijing.volces.com/api/v3"

# API密钥列表（将从APIKey文件夹中的txt文件自动加载）
API_KEYS = []
# 原始密钥已移除，请将密钥保存在APIKey文件夹中的txt文件里
# 格式：每行一个密钥（无固定前缀），例如：<YOUR_ARK_API_KEY>

# 注册功能开关已迁移至数据库(app_settings.registration_enabled)的表“app_settings”，此处不再维护副本