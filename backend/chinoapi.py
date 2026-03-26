import requests
import json
import time
import os
from pathlib import Path
from typing import List, Dict, Optional, Any
from dotenv import load_dotenv

# 加载 .env 文件中的环境变量
# 尝试从多个位置加载 .env 文件
env_paths = [
    Path(__file__).parent / '.env',  # backend/.env
    Path(__file__).parent.parent / '.env',  # 项目根目录/.env
    Path.cwd() / '.env',  # 当前工作目录/.env
]

for env_path in env_paths:
    if env_path.exists():
        load_dotenv(env_path)
        break
else:
    load_dotenv()  # 使用默认加载方式

# 从环境变量加载配置
LLM_URL = os.getenv('LLM_URL', 'https://app.chino-ai.com/api/oai/v1/chat/completions')
LLM_TOKEN = os.getenv('LLM_TOKEN', '')
LLM_PROXY = os.getenv('LLM_PROXY', '')
LLM_MODEL = os.getenv('LLM_MODEL', 'claude-sonnet-4.5')
LLM_TIMEOUT = int(os.getenv('LLM_TIMEOUT', '180'))
LLM_MAX_RETRIES = int(os.getenv('LLM_MAX_RETRIES', '3'))
LLM_RETRY_BASE_DELAY = int(os.getenv('LLM_RETRY_BASE_DELAY', '2'))

def _get_module_config(module: Optional[str] = None) -> Dict[str, Any]:
    """获取LLM配置"""
    config = {
        "url": LLM_URL,
        "token": LLM_TOKEN,
        "model": LLM_MODEL,
        "timeout": LLM_TIMEOUT,
        "max_retries": LLM_MAX_RETRIES,
        "retry_delay": LLM_RETRY_BASE_DELAY,
        "proxy": LLM_PROXY
    }
    return config

def call_chino_api(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    max_retries: Optional[int] = None,
    retry_delay: Optional[float] = None
) -> Optional[Dict[str, Any]]:
    """调用 Chino AI API 的函数（带重试机制）"""
    # 使用默认配置
    if max_retries is None:
        max_retries = LLM_MAX_RETRIES
    if retry_delay is None:
        retry_delay = float(LLM_RETRY_BASE_DELAY)
    url = LLM_URL

    # 检查URL是否为空
    if not url or url.strip() == "":
        print("错误: LLM_URL 环境变量未设置或为空。请检查 .env 文件中的 LLM_URL 配置。")
        return None

    # 使用环境变量中的TOKEN，如果没有提供api_key参数
    token = api_key if api_key is not None else LLM_TOKEN
    if not token or token.strip() == "":
        print("错误: LLM_TOKEN 环境变量未设置或为空。请检查 .env 文件中的 LLM_TOKEN 配置。")
        return None

    # 使用环境变量中的MODEL，如果没有提供model参数
    model_name = model if model is not None else LLM_MODEL

    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {token}'
    }

    # 构建payload
    payload: Dict[str, Any] = {
        'messages': messages
    }

    # 如果模型名称有效，则添加到payload中
    if model_name and model_name.strip():
        payload['model'] = model_name

    # 设置代理配置
    proxies = None
    if LLM_PROXY:
        proxies = {
            'http': LLM_PROXY,
            'https': LLM_PROXY
        }

    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=LLM_TIMEOUT, proxies=proxies)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if response.status_code == 500 and attempt < max_retries - 1:
                print(f"服务器错误 (尝试 {attempt + 1}/{max_retries}): {e}")
                print(f"等待 {retry_delay} 秒后重试...")
                time.sleep(retry_delay)
                retry_delay *= 2
                continue
            else:
                print(f"API请求失败: {e}")
                return None
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                print(f"网络错误 (尝试 {attempt + 1}/{max_retries}): {e}")
                print(f"等待 {retry_delay} 秒后重试...")
                time.sleep(retry_delay)
                retry_delay *= 2
                continue
            else:
                print(f"API请求失败: {e}")
                return None
        except json.JSONDecodeError as e:
            print(f"JSON解析失败: {e}")
            return None

    return None

def simple_chat(content: str, model: Optional[str] = None, module: Optional[str] = None) -> Optional[str]:
    """简单的聊天函数，发送单条消息并返回回复内容"""
    # 获取模块配置
    config = _get_module_config(module)

    messages = [{'role': 'user', 'content': content}]
    response = call_chino_api(
        messages,
        model=model or config['model'],
        api_key=config['token'],
        max_retries=config['max_retries'],
        retry_delay=config['retry_delay']
    )

    if response and 'choices' in response and len(response['choices']) > 0:
        raw_content = response['choices'][0]['message']['content']

        # 过滤掉<think>...</think>部分
        if 'think>' in raw_content and '</think>' in raw_content:
            end_think_pos = raw_content.find('</think>')
            if end_think_pos != -1:
                filtered_content = raw_content[end_think_pos + len('</think>'):].strip()
                return filtered_content if filtered_content else raw_content

        return raw_content
    return None

if __name__ == "__main__":
    # 测试函数
    test_messages = [{'role': 'user', 'content': 'Hello!'}]
    result = call_chino_api(test_messages)
    if result:
        print("API调用成功:")
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("API调用失败")

    # 测试简单聊天函数
    print("\n简单聊天测试:")
    reply = simple_chat("你好，请介绍一下自己")
    if reply:
        print(f"AI回复: {reply}")
    else:
        print("聊天失败")
