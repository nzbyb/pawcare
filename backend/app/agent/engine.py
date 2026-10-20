"""Agent 调度引擎选择。

``explicit``（默认）是 ``runtime.run_agent`` 里的显式工具调用循环，也是生产
主实现。``langgraph`` 仅用于对照实验与论文论证，按需懒加载；未安装
LangGraph 时生产路径不受影响。
"""

import logging

from app.agent import runtime
from app.config import settings

logger = logging.getLogger(__name__)

EXPLICIT = "explicit"
LANGGRAPH = "langgraph"
ENGINES = (EXPLICIT, LANGGRAPH)


def configured_engine() -> str:
    engine = (settings.AGENT_ENGINE or EXPLICIT).strip().lower()
    if engine not in ENGINES:
        logger.warning("未知 AGENT_ENGINE=%s，回退到 %s", engine, EXPLICIT)
        return EXPLICIT
    return engine


async def run_agent(*args, **kwargs):
    engine = configured_engine()
    if engine == LANGGRAPH:
        try:
            from app.agent.langgraph_runtime import run_agent as run_langgraph_agent
        except ImportError:
            logger.exception(
                "AGENT_ENGINE=langgraph 但 LangGraph 不可用，回退到 explicit"
            )
        else:
            return await run_langgraph_agent(*args, **kwargs)
    return await runtime.run_agent(*args, **kwargs)
