import asyncio
import json
import os
from contextlib import AsyncExitStack
from typing import Any, List, Dict, Optional
import httpx
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

class Configuration:
    """管理环境变量和服务器配置。"""
    def __init__(self) -> None:
        load_dotenv()  # 从 .env 文件加载环境变量
        self.llm_api_key = os.getenv("LLM_API_KEY")
        self.wechat_webhook_key = os.getenv("WECHAT_WEBHOOK_KEY")
        self.wechat_chat_id = os.getenv("WECHAT_CHAT_ID")  # 可选的群聊ID

    @staticmethod
    def load_server_config(file_path: str) -> dict[str, Any]:
        """从 JSON 文件加载 MCP 服务器的配置。"""
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

class McpServerConnection:
    """管理与 MCP 服务器的连接和通信。"""
    def __init__(self, name: str, config: dict[str, Any]) -> None:
        self.name = name
        self.config = config
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
#启动mcp server服务器
    async def initialize(self) -> None:
        """启动 MCP 服务器子进程并建立连接。"""
        server_params = StdioServerParameters(
            command=self.config["command"],
            args=self.config["args"],
            env={**os.environ, **self.config.get("env", {})}
        )
        try:
            print(f"正在启动 MCP 服务器 '{self.name}'...")
            # `stdio_client` 帮助我们通过标准输入/输出与服务器进程通信
            stdio_transport = await self.exit_stack.enter_async_context(
                stdio_client(server_params)
            )
            read, write = stdio_transport
            # `ClientSession` 管理与服务器的 MCP 协议会话
            session = await self.exit_stack.enter_async_context(
                ClientSession(read, write)
            )
            await session.initialize()
            self.session = session
            print(f"MCP 服务器 '{self.name}' 连接成功！")
        except Exception as e:
            print(f"错误：无法初始化 MCP 服务器 '{self.name}': {e}")
            await self.cleanup()
            raise
#获取提示模板
    async def get_prompt_messages(self, prompt_name: str, arguments: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """从 MCP 服务器获取一个格式化的 prompt 模板。"""
        if not self.session:
            raise RuntimeError(f"服务器 '{self.name}' 未连接。")
        try:
            # 请求名为 prompt_name 的模板，并传入参数
            response = await self.session.get_prompt(prompt_name, arguments)
            # 将 MCP 的消息格式转换为 LLM API 需要的简单字典列表格式
            return [
                {"role": msg.role, "content": msg.content.text}
                for msg in response.messages
            ]
        except Exception as e:
            print(f"错误：获取 prompt '{prompt_name}' 失败: {e}")
            return None
#调用工具
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Optional[str]:
        """在 MCP 服务器上调用一个工具。"""
        if not self.session:
            raise RuntimeError(f"服务器 '{self.name}' 未连接。")
        try:
            print(f"正在 MCP 服务器上调用工具 '{tool_name}'...")
            response = await self.session.call_tool(tool_name, arguments)
            # 假设工具的输出总是在第一个内容的文本部分
            return response.content[0].text
        except Exception as e:
            print(f"错误：调用工具 '{tool_name}' 失败: {e}")
            return None
#关闭mcp server服务器
    async def cleanup(self) -> None:
        """关闭与 MCP 服务器的连接并停止子进程。"""
        print(f"正在关闭 MCP 服务器 '{self.name}'...")
        await self.exit_stack.aclose()
        self.session = None

class LLMInterface:
    """管理与 LLM API 的交互。"""
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    def get_llm_response(self, messages: List[Dict[str, str]], model: str = "qwen2.5-1.5b-instruct") -> str:
        """向 LLM 发送消息并获取回复。"""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload = {"model": model, "messages": messages}
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
                response.raise_for_status()  # 如果请求失败（如4xx或5xx错误），则抛出异常
                data = response.json()
                # 直接从响应中提取助手的回复内容
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"错误：请求 LLM API 失败: {e}")
            return "抱歉，我现在无法思考。"

class WeChatHumorBot:
    """协调 MCP 和 LLM 以生成幽默回复并发送到企业微信。"""
    def __init__(self, mcp_server: McpServerConnection, llm_client: LLMInterface, config: Configuration):
        self.mcp_server = mcp_server
        self.llm_client = llm_client
        self.config = config

    def _get_system_prompt_for_llm_tool_decision(self) -> str:
        """这是一个特殊的“系统指令”，告诉 LLM 如何决定是否要调用工具。"""
        return f"""
你有一个可用的工具：
- 工具名称: "sendWeChatTextMessage"
- 工具描述: "发送一条文本消息到企业微信群。"

如果你判断应该将生成的幽默回复发送出去，你必须【仅】使用以下严格的 JSON 格式进行回复，不要包含任何其他文字或解释：
{{
  "tool_call": {{
    "name": "sendWeChatTextMessage",
    "arguments": {{
      "content": "<这里是你认为应该发送的幽默回复内容>"
    }}
  }}
}}

如果不想发送，就直接用普通文本回答，例如 "这次不发送"。
"""

    async def start_chat(self) -> None:
        """启动与用户的交互式聊天循环。"""
        try:
            await self.mcp_server.initialize()
            # 仅当配置了 webhook key 时，我们才认为发送工具可用
            send_tool_available = bool(self.config.wechat_webhook_key)

            while True:
                user_dialogue = input("\n微信群聊对话内容 (输入 '退出' 来结束): ").strip()
                if user_dialogue.lower() in ["退出", "quit", "exit"]:
                    break
                if not user_dialogue:
                    continue

                # --- 步骤 1: 使用 MCP Prompt 模板和 LLM 生成一个幽默回复 ---
                print(">>> 步骤 1: 正在生成幽默回复...")
                prompt_messages = await self.mcp_server.get_prompt_messages(
                    prompt_name="generateHumorousReply",
                    arguments={"dialogue": user_dialogue}
                )

                if not prompt_messages:
                    print("机器人: 抱歉，我今天没灵感了。")
                    continue
                
                humorous_reply = self.llm_client.get_llm_response(messages=prompt_messages)
                print(f"机器人(生成的回复): {humorous_reply}")

                # --- 步骤 2: 询问 LLM 是否应该将此回复发送到企业微信 ---
                if not send_tool_available:
                    print("(提示: 未配置企业微信 Webhook Key，跳过发送步骤。)")
                    continue
                
                print(">>> 步骤 2: 正在让 LLM 决定是否发送...")
                system_prompt = self._get_system_prompt_for_llm_tool_decision()
                messages_for_decision = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"我已经为对话“{user_dialogue}”生成了回复：“{humorous_reply}”。\n你认为应该发送吗？如果发送，请提供工具调用JSON。"}
                ]
                llm_decision_str = self.llm_client.get_llm_response(messages_for_decision)
                
                # --- 步骤 3: 解析 LLM 的决定并执行工具 ---
                try:
                    # 尝试将 LLM 的回复解析为 JSON
                    decision_json = json.loads(llm_decision_str)
                    tool_call_data = decision_json.get("tool_call")

                    if tool_call_data and tool_call_data.get("name") == "sendWeChatTextMessage":
                        print(">>> 步骤 3: LLM 决定发送。正在调用工具...")
                        tool_arguments = {
                            "webhookKey": self.config.wechat_webhook_key,
                            "content": humorous_reply,  # 使用我们自己生成的回复，更安全
                        }
                        # 如果配置了默认群聊ID，则添加
                        if self.config.wechat_chat_id:
                            tool_arguments["chatid"] = self.config.wechat_chat_id

                        result = await self.mcp_server.call_tool(
                            tool_name="sendWeChatTextMessage",
                            arguments=tool_arguments
                        )
                        print(f"机器人: 消息已发送！(服务器响应: {result})")
                    else:
                        print("机器人: LLM 决定不发送消息。")

                except (json.JSONDecodeError, AttributeError):
                    # 如果 LLM 的回复不是我们期望的 JSON 格式，说明它不想调用工具
                    print(f"机器人: LLM 决定不发送消息 (它的建议是: {llm_decision_str})")

        except KeyboardInterrupt:
            print("\n用户中断，正在退出...")
        finally:
            await self.mcp_server.cleanup()
async def main() -> None:
    """主函数，负责设置和启动机器人。""" 
    # 初始化配置
    config = Configuration()
    if not config.llm_api_key:
        print("错误: 请在 .env 文件中设置 LLM_API_KEY。")
        return
    server_configs = Configuration.load_server_config("servers_config.json")
    # 我们只使用配置文件中的第一个 MCP 服务器
    server_name, server_conf = next(iter(server_configs["mcpServers"].items()))
    # 创建各个组件的实例
    mcp_connection = McpServerConnection(name=server_name, config=server_conf)
    llm_interface = LLMInterface(api_key=str(config.llm_api_key))
    bot = WeChatHumorBot(mcp_server=mcp_connection, llm_client=llm_interface, config=config)
    # 启动聊天机器人
    await bot.start_chat()
print("--- 机器人已关闭 ---")
if __name__ == "__main__":
    # 在 Windows 上运行 asyncio 
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main())
