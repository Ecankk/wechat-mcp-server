import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { sendWeChatTextMessage } from "./text.js";
import { z } from "zod";
import { fileURLToPath } from 'url';
import * as path from 'path';
import fs from 'fs';

export const server = new McpServer({
    name: "wechat-mcp-server",
    version: "0.0.1",
});


server.tool(
    "sendWeChatTextMessage",
    "发送企业微信文本消息",
    {
        webhookKey: z.string().describe("企业微信机器人webhookKey"),
        content: z.string().describe("消息内容"),
        chatid: z.string().describe("群聊ID").optional(), // optional 选填
        mentioned_list: z.array(z.string()).describe("@的成员ID列表").optional(),
        mentioned_mobile_list: z.array(z.string()).describe("@的成员手机号列表").optional(),
    },
    async ({ webhookKey, content, chatid, mentioned_list, mentioned_mobile_list }) => {
        const success = await sendWeChatTextMessage(webhookKey, content, chatid, mentioned_list,
            mentioned_mobile_list);

        if (!success) {
            return {
                content: [
                    {
                        type: "text",
                        text: "企业微信消息发送失败",
                    },
                ],
            };
        }
        return {
            content: [
                {
                    type: "text",
                    text: "企业微信消息发送成功",
                },
            ],
        };
    },
);

server.resource(
    "api",
    "file:///api.md",
    async (uri) => {
        try {
            console.info(uri)
            const __filename = fileURLToPath(import.meta.url);
            const __dirname = path.dirname(__filename);
            const filePath = path.join(__dirname, '..', 'assets', 'api.md');   // 读取资源文件目录
            const content = await fs.promises.readFile(filePath, 'utf-8');

            return {
                contents: [{
                    uri: uri.href,
                    text: content
                }]
            };
        } catch (error) {
            return {
                contents: [{
                    uri: uri.href,
                    text: "读取文件失败"
                }]
            };
        }
    }
);

server.prompt(
    "parameter_check",
    "参数检查",
    {
        param: z.string().describe("参数"),
        apiContent: z.string().describe("API文档")
    },
    ({ param, apiContent }) => ({
        messages: [{
            role: "user",
            content: {
                type: "text",
                text: `
                <instruction>
                  <instructions>
                      1. 接收API文档文本和用户数据作为输入。
                      2. 从API文档中提取所有参数的要求，包括参数名称、类型、是否必需、默认值等信息。
                      3. 对照用户提供的数据，检查每个参数是否满足API的要求。
                      4. 对于每个参数，记录以下信息：
                          - 参数名称
                          - 用户提供的值
                          - 是否满足API要求（是/否）
                          - 如果不满足，说明原因
                      5. 将所有检查结果整理成一个清晰的报告，确保输出不包含任何XML标签。
                      6. 确保报告的格式简洁明了，便于用户理解。
                  </instructions>
                  <examples>
                     <example>
                        <input>
                            API文档文本: "参数: username, 类型: string, 必需: 是; 参数: age, 类型: integer, 必需: 否;"
                            用户数据: "{\"username\": john_doe, \"age\": 25}"
                        </input>
                        <output>
                            "参数: username, 用户提供的值: john_doe, 满足要求: 是; 参数: age, 用户提供的值: 25, 满足要求: 是;"
                        </output>
                    </example>
                  </examples>
                </instruction>
                API文档文本：${apiContent}
                用户数据：${param}
                `
            }
        }]
    })
);
server.prompt(
    "generateHumorousReply",
    "根据群聊对话生成幽默回复",
    {
        dialogue: z.string().describe("用户提供的群聊对话内容"),
    },
    ({ dialogue }) => ({
        messages: [
            {
                role: "user",
                content: {
                    type: "text",
                    text: `请你扮演一个幽默风趣的聊天助手。你的任务是根据以下“当前的群聊对话内容”，生成一句简短、幽默且相关的回复。
                  你的回复应该适合在企业微信群聊中直接发送，不要包含任何解释性的前缀或后缀（例如，不要说“这是一个幽默的回复：”）。
                  请确保你的回复直接就是那句幽默的话。\n\n当前的群聊对话内容：\n“${dialogue}”`
                }
            }
        ]
    })
);
const transport = new StdioServerTransport();
await server.connect(transport);
console.log("✅ MCP Server 已通过 STDIO 启动");