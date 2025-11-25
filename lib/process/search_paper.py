"""
论文搜索模块 (新架构)
封装AI调用逻辑，提供统一的文献相关性判断接口
"""

import json
import time
from typing import Dict, Optional, Any, Callable
from ..config import config_loader as config


def create_ai_processor(uid: int, qid: str) -> Callable:
    """
    创建AI处理函数
    
    Returns:
        处理函数 (doi, title, abstract) -> {relevant, reason, _tokens}
    """
    # 获取查询参数
    from ..load_data.query_dao import get_query_log
    
    query_info = get_query_log(qid) or {}
    search_params = query_info.get('search_params', {})
    
    research_question = search_params.get('research_question', '')
    requirements = search_params.get('requirements', '')
    
    def processor(doi: str, title: str, abstract: str) -> Dict:
        """AI处理函数"""
        return search_relevant_papers(
            doi=doi,
            title=title,
            abstract=abstract,
            research_question=research_question,
            requirements=requirements,
            uid=uid,
            qid=qid
        )
    
    return processor


def search_relevant_papers(doi: str, title: str, abstract: str,
                          research_question: str, requirements: str,
                          uid: int = None, qid: str = None) -> Dict:
    """
    判断论文与研究问题的相关性
    
    Args:
        doi: 文献DOI
        title: 文献标题
        abstract: 文献摘要
        research_question: 研究问题
        requirements: 筛选要求
        uid: 用户ID（用于会话隔离）
        qid: 查询ID（用于会话隔离）
        
    Returns:
        {
            relevant: "Y" 或 "N",
            reason: 判断理由,
            _tokens: 消耗的Token数
        }
    """
    if not abstract:
        return {
            'relevant': 'N',
            'reason': 'No abstract available',
            '_tokens': 0
        }
    
    # 构造Prompt
    prompt = _build_prompt(title, abstract, research_question, requirements, uid, qid)
    
    # 调用AI
    try:
        result = _call_ai_api(prompt)
        return result
    except Exception as e:
        print(f"[SearchPaper] AI调用失败: {e}")
        return {
            'relevant': 'N',
            'reason': f'AI error: {str(e)}',
            '_tokens': 0
        }


def _build_prompt(title: str, abstract: str, 
                  research_question: str, requirements: str,
                  uid: int = None, qid: str = None) -> str:
    """构造AI Prompt"""
    
    system_prompt = getattr(config, 'system_prompt', '') or """
You are an academic paper relevance evaluator. Analyze the given paper and determine if it is relevant to the research question.

Output format (JSON):
{
    "relevant": "Y" or "N",
    "reason": "Brief explanation of your judgment",
    "uid": <echo back the uid>,
    "query_index": <echo back the query_index>
}
"""
    
    user_prompt = f"""
Research Question: {research_question}

Requirements: {requirements}

Paper Title: {title}

Paper Abstract: {abstract}

Session Info (please echo back in response):
- uid: {uid}
- query_index: {qid}

Please determine if this paper is relevant to the research question.
"""
    
    return json.dumps({
        'system': system_prompt,
        'user': user_prompt
    })


def _call_ai_api(prompt: str) -> Dict:
    """
    调用AI API
    
    实际实现应该使用OpenAI兼容的API
    """
    try:
        import openai
        
        prompt_data = json.loads(prompt)
        system_msg = prompt_data.get('system', '')
        user_msg = prompt_data.get('user', '')
        
        # 获取API配置
        api_key = _get_api_key()
        api_base = getattr(config, 'api_base_url', None)
        model_name = getattr(config, 'model_name', 'gpt-3.5-turbo')
        
        if not api_key:
            raise ValueError("No API key available")
        
        # 创建客户端
        client = openai.OpenAI(
            api_key=api_key,
            base_url=api_base
        )
        
        # 调用API
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg}
            ],
            temperature=0.1,
            max_tokens=500
        )
        
        # 解析响应
        content = response.choices[0].message.content
        tokens_used = response.usage.total_tokens if response.usage else 0
        
        # 尝试解析JSON响应
        result = _parse_ai_response(content)
        result['_tokens'] = tokens_used
        
        return result
        
    except ImportError:
        # openai库未安装，返回模拟结果
        return {
            'relevant': 'N',
            'reason': 'OpenAI library not installed',
            '_tokens': 0
        }
    except Exception as e:
        return {
            'relevant': 'N',
            'reason': f'API call failed: {str(e)}',
            '_tokens': 0
        }


def _get_api_key() -> Optional[str]:
    """获取可用的API Key"""
    # 优先从config获取
    api_keys = getattr(config, 'API_KEYS', [])
    if api_keys:
        return api_keys[0]
    
    # 从数据库获取
    try:
        from ..load_data.db_base import _get_connection
        conn = _get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT api_key FROM api_list WHERE is_active = 1 LIMIT 1"
        )
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        return row[0] if row else None
    except Exception:
        return None


def _parse_ai_response(content: str) -> Dict:
    """解析AI响应"""
    try:
        # 尝试直接解析JSON
        data = json.loads(content)
        return {
            'relevant': data.get('relevant', 'N'),
            'reason': data.get('reason', ''),
        }
    except json.JSONDecodeError:
        pass
    
    # 尝试提取JSON块
    import re
    json_match = re.search(r'\{[^}]+\}', content, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group())
            return {
                'relevant': data.get('relevant', 'N'),
                'reason': data.get('reason', ''),
            }
        except json.JSONDecodeError:
            pass
    
    # 简单的关键词判断
    content_lower = content.lower()
    if 'relevant' in content_lower and 'yes' in content_lower:
        return {'relevant': 'Y', 'reason': content[:200]}
    
    return {'relevant': 'N', 'reason': content[:200]}
