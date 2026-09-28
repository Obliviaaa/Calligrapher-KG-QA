from typing import Union, Any
import os
from langchain_deepseek import ChatDeepSeek
import os
from IPython.display import Image
from IPython import display

import logging
import datetime
import json
from functools import wraps
from typing import Any, Dict, Callable

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("llm_interaction.log"),
        logging.StreamHandler()  # 同时输出到控制台
    ]
)
logger = logging.getLogger("LLM_Interaction")


def setup_llm():
    """
    设置DeepSeek LLM
    """
    # 加载环境变量（用于DeepSeek API密钥）
    from dotenv import load_dotenv
    load_dotenv()

    # 从环境变量获取DeepSeek API密钥
    deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
    if not deepseek_api_key:
        raise ValueError("请在.env文件中设置DEEPSEEK_API_KEY环境变量")

    # 创建LLM实例
    llm = ChatDeepSeek(
        api_key=deepseek_api_key,
        model="deepseek-chat",
        temperature=0.0,
    )

    return llm
def log_llm_interaction(func):
    """
    装饰器：记录LLM交互日志
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        # 记录请求
        request_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        request_data = args[0] if args else kwargs

        # 将请求转换为可记录的格式
        if hasattr(request_data, '__iter__') and not isinstance(request_data, (str, dict)):
            request_content = []
            for msg in request_data:
                if hasattr(msg, 'content'):
                    request_content.append({
                        "type": type(msg).__name__,
                        "content": msg.content
                    })
                else:
                    request_content.append(str(msg))
        else:
            request_content = str(request_data)

        logger.info(f"LLM Request [{request_time}]: {json.dumps(request_content, ensure_ascii=False, indent=2)}")

        # 调用原始函数
        response = func(*args, **kwargs)

        # 记录响应
        response_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        response_content = {
            "type": type(response).__name__,
            "content": response.content if hasattr(response, 'content') else str(response)
        }

        logger.info(f"LLM Response [{response_time}]: {json.dumps(response_content, ensure_ascii=False, indent=2)}")

        return response

    return wrapper


def log_state_change(node_name: str):
    """
    装饰器：记录AgentState的变化
    在节点函数执行前后记录状态信息
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(state: Dict[str, Any], *args, **kwargs) -> Dict[str, Any]:
            # 记录输入状态
            input_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")

            # 格式化输入消息
            input_messages = []
            if "messages" in state and state["messages"]:
                for msg in state["messages"]:
                    if hasattr(msg, "content"):
                        input_messages.append({
                            "type": type(msg).__name__,
                            "content": msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
                        })
                    else:
                        input_messages.append(str(msg))

            # 记录输入状态日志
            logger.info(f"节点[{node_name}] - 输入状态 [{input_time}]: "
                        f"messages={json.dumps(input_messages, ensure_ascii=False)}, "
                        f"context_keys={list(state.get('context', {}).keys())}, "
                        f"tool_calls_count={len(state.get('tool_calls', []))}")

            # 执行原始函数
            result = func(state, *args, **kwargs)

            # 记录输出状态
            output_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
            execution_time = datetime.datetime.strptime(output_time, "%Y-%m-%d %H:%M:%S.%f") - \
                             datetime.datetime.strptime(input_time, "%Y-%m-%d %H:%M:%S.%f")

            # 格式化输出消息
            output_messages = []
            if "messages" in result and result["messages"]:
                for msg in result["messages"]:
                    if hasattr(msg, "content"):
                        output_messages.append({
                            "type": type(msg).__name__,
                            "content": msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
                        })
                    else:
                        output_messages.append(str(msg))

            # 记录输出状态日志
            logger.info(f"节点[{node_name}] - 输出状态 [{output_time}]: "
                        f"messages={json.dumps(output_messages, ensure_ascii=False)}, "
                        f"execution_time={execution_time.total_seconds():.4f}s")

            return result

        return wrapper

    return decorator


# 绘制agent graph的功能函数
def draw_agent_graph(graph, filename="workflow_graph.png"):
    """
    绘制agent graph并保存到文件

    Args:
        graph: 创建的range_detection_graph对象
        filename: 保存图表的文件名

    Returns:
        graph_png: 图表的PNG数据，如果绘制失败则返回None
    """
    try:
        # 获取图表的PNG图像数据
        graph_png = graph.get_graph().draw_mermaid_png()
        # 将图表保存到本地文件
        with open(filename, "wb") as f:
            f.write(graph_png)
        print(f"图表已保存到: {filename}")
        # 在IPython中显示图表
        # display(Image(graph_png))
        return graph_png
    except Exception as e:
        print(f"获取图表时出错: {e}")
        return None
