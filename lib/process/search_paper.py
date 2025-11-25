from openai import OpenAI
import time
from ..config import config_loader as config
import sys
from ..log import utils
import json
import re
from language import language


def _extract_json_payload(text: str) -> str:
    """尽最大可能从模型返回内容中提取 JSON 对象字符串。
    适配多种返回格式：
    - 三引号代码块 ```json ... ```
    - 纯文本前后包裹说明
    - 存在多余前后缀时，取第一个 '{' 到最后一个 '}' 之间内容
    """
    if not text:
        return text
    t = text.strip()
    # 去除三引号代码块
    if t.startswith("```"):
        # 兼容 ```json 或 ```
        # 去掉第一行到换行
        first_newline = t.find("\n")
        if first_newline != -1:
            t = t[first_newline + 1 :]
        # 去掉结尾 ```
        fence_idx = t.rfind("```")
        if fence_idx != -1:
            t = t[:fence_idx]
        t = t.strip()

    # 若已经是以 { 开头以 } 结尾，直接返回
    if t.startswith("{") and t.endswith("}"):
        return t

    # 尝试提取第一个 JSON 对象（第一个 '{' 到最后一个 '}'）
    first = t.find("{")
    last = t.rfind("}")
    if first != -1 and last != -1 and last > first:
        candidate = t[first : last + 1].strip()
        return candidate

    # 正则兜底：提取最外层花括号包裹内容（贪婪）
    m = re.search(r"\{[\s\S]*\}", t)
    if m:
        return m.group(0).strip()
    return t

def check_paper_relevance(research_direction, requirements, paper_title, paper_abstract, api_key=None, uid=None, query_index=None):    
    # 记录API调用开始时间
    api_start_time = time.time()
    
    # 从config导入系统提示词并根据当前语言设置填充占位符
    # Top-level preparation of language name and system prompt
    lang_text = language.get_text('zh_CN')
    language_name = "中文"
    system_prompt = config.system_prompt.replace("{language}", language_name)
    if config.LANGUAGE == 'en_US':
        language_name = "English"
    else:
        language_name = "中文"
    
    system_prompt = config.system_prompt.replace("{language}", language_name)
    
    # 构建user_prompt，根据配置决定是否包含关键词和要求
    # 注入会话隔离的元信息，要求模型在 JSON 中原样回显 uid 与 query_index
    session_meta = ""
    if uid is not None or query_index is not None:
        session_meta = f"""
#会话标识#：
uid: {uid if uid is not None else ''}
query_index: {query_index if query_index is not None else ''}

严格要求：你必须仅以 JSON 对象输出，并且除了原有字段外，还必须包含如下两个字段且与上面的值一致：
- uid: number
- query_index: number
如果任何字段无法确定，使用 0。
"""

    user_prompt = f"""#研究主题#：{research_direction}
{session_meta}
"""
    
    # 根据配置决定是否添加要求
    #if config.include_requirements_in_prompt and requirements:
    user_prompt += f"""#要求#：{requirements}

"""
    
    # 始终包含论文标题和摘要
    user_prompt += f"""#论文标题#：{paper_title}

#论文摘要#：{paper_abstract}
"""
    if config.unit_test_mode:
        # 单元测试模式：跳过模型调用，返回模拟结果。
        # 为保持与真实路径一致，补充回显 uid 与 query_index（若为空则回退为0）。
        default_response = ",".join(str(i) for i in range(1, 101))
        utils.print_and_log("Unit test mode enabled; skipping model call and returning default response.")
        ret_uid = int(uid) if uid is not None else 0
        ret_qidx = int(query_index) if query_index is not None else 0
        return 'N', 0, default_response, 0, 0, 0, 0, ret_uid, ret_qidx

    # 使用 Ark OpenAI 兼容 API 进行模型调用
    # 如果没有传入api_key，报错并终止程序
    if api_key is None:
        lang = language.get_text(config.LANGUAGE)
        utils.print_and_log(lang['api_key_not_provided'])
        utils.print_and_log(lang['api_key_usage_hint'])
        sys.exit(1)
        
    client = OpenAI(
        api_key=api_key, 
        base_url=config.api_base_url,
        timeout=config.api_timeout  # 使用配置文件中的超时设置
        )
    
    response = client.chat.completions.create(
        model=config.model_name,
        messages=[
            {
                'role': 'system',
                'content': system_prompt
            },
            {
                'role': 'user',
                'content': user_prompt
            },
        ],
        stream=False,  # 不使用流式响应
        temperature=1.0,
        response_format={
            'type': 'json_object'
        }
    )
    
    # 提取结果并清理
    response_text = response.choices[0].message.content.strip()
    # print(f"  ********************** 模型返回内容: {response_text} **********************")

    # response_text变量只保留"</think>"之后的内容
    if '</think>' in response_text:
        # 找到 </think> 的位置并截取之后的内容
        think_end_index = response_text.find('</think>')
        response_text = response_text[think_end_index + len('</think>'):].strip()
    
    # 解析JSON结果
    result = ''
    reason = ''
    returned_uid = None
    returned_qidx = None
    
    try:
        # 适配 Ark 可能返回的 ```json 代码块或带前后缀的文本
        json_payload = _extract_json_payload(response_text)
        # 解析JSON响应
        json_response = json.loads(json_payload)
        
        # 提取会话回显字段（可选但强烈建议）
        if 'uid' in json_response:
            try:
                returned_uid = int(json_response.get('uid') or 0)
            except Exception:
                returned_uid = 0
        if 'query_index' in json_response:
            try:
                returned_qidx = int(json_response.get('query_index') or 0)
            except Exception:
                returned_qidx = 0

        # 提取相关性判断结果
        if 'relevant' in json_response:
            result = json_response['relevant'].upper()
            if result not in ['Y', 'N']:
                lang = language.get_text(config.LANGUAGE)
                utils.print_and_log(lang['unexpected_relevant_value'].format(result=result))
                result = 'N'
        else:
            lang = language.get_text(config.LANGUAGE)
            utils.print_and_log(lang['missing_relevant_field'].format(response=json_payload))
            result = 'N'
        
        # 提取原因
        if 'reason' in json_response:
            reason = json_response['reason']
            # 根据结果类型添加前缀
            if result == 'Y':
                reason = f"相关原因：{reason}"
            else:
                reason = f"不相关原因：{reason}"
        else:
            lang = language.get_text(config.LANGUAGE)
            utils.print_and_log(lang['missing_reason_field'])
            
    except json.JSONDecodeError as e:
        lang = language.get_text(config.LANGUAGE)
        utils.print_and_log(lang['json_parse_error'].format(error=e))
        utils.print_and_log(lang['original_response'].format(response=response_text))
        result = 'N'
        reason = "不相关原因：模型响应格式错误"
    
    # 模型 API 返回的 token 信息（如未返回则使用估算值）
    tokens = 0
    prompt_tokens = 0
    completion_tokens = 0
    cache_hit_tokens = 0
    cache_miss_tokens = 0
    
    if hasattr(response, 'usage'):
        # 使用总token数（prompt_tokens + completion_tokens）
        tokens = response.usage.total_tokens
        prompt_tokens = response.usage.prompt_tokens if hasattr(response.usage, 'prompt_tokens') else 0
        completion_tokens = response.usage.completion_tokens if hasattr(response.usage, 'completion_tokens') else 0
        
        # 获取缓存信息（如果有）
        cache_hit_tokens = getattr(response.usage, 'prompt_cache_hit_tokens', 0)
        cache_miss_tokens = getattr(response.usage, 'prompt_cache_miss_tokens', 0)
    else:
        # 如果没有usage信息，使用估算值, 1 个英文字符 ≈ 0.3 个 token，1 个中文字符 ≈ 0.6 个 token
        lang = language.get_text(config.LANGUAGE)
        utils.print_and_log(lang['no_token_info'])
        total_chars = len(system_prompt + user_prompt + response_text)
        tokens = int(total_chars * 0.6)  # 假设平均每个字符占0.6个token
        # 估算输入输出比例（假设输入占80%，输出占20%）
        prompt_tokens = int(tokens * 0.8)
        completion_tokens = tokens - prompt_tokens
        cache_miss_tokens = prompt_tokens  # 估算时假设全部未命中
    
    return result, tokens, reason, prompt_tokens, completion_tokens, cache_hit_tokens, cache_miss_tokens, returned_uid, returned_qidx  # 返回相关原因与会话回显


def search_relevant_papers(paper_title: str, paper_abstract: str, research_question: str, requirements: str, api_key: str, uid: int = 0, query_index: int = 0) -> dict:
    """
    统一对外调用接口：根据论文标题/摘要与研究问题，调用模型判断是否相关。
    返回字段：
    - is_relevant: bool
    - reason: str
    - prompt_tokens, completion_tokens, cache_hit_tokens, cache_miss_tokens: int
    """
    from ..config import config_loader as _config

    # 单元测试模式：返回稳定伪造结果
    if getattr(_config, 'unit_test_mode', False):
        import random
        is_rel = random.random() > 0.5
        return {
            'is_relevant': is_rel,
            'reason': 'Unit test mode result',
            'prompt_tokens': 100,
            'completion_tokens': 50,
            'cache_hit_tokens': 0,
            'cache_miss_tokens': 100
        }

    # 调用底层检查函数并转换结果形态
    res, total_tokens, reason, p_tok, c_tok, cache_hit, cache_miss, _ret_uid, _ret_qidx = check_paper_relevance(
        research_question, requirements, paper_title, paper_abstract, api_key=api_key, uid=uid, query_index=query_index
    )
    is_rel = (str(res).upper() == 'Y' or res is True)
    return {
        'is_relevant': bool(is_rel),
        'reason': reason or '',
        'prompt_tokens': int(p_tok or 0),
        'completion_tokens': int(c_tok or 0),
        'cache_hit_tokens': int(cache_hit or 0),
        'cache_miss_tokens': int(cache_miss or 0)
    }
