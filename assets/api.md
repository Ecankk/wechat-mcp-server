# 企业微信机器人 API 文档

## 发送文本消息 (`sendWeChatTextMessage`)

用于向指定的企业微信群聊或成员发送文本消息。

**参数:**

*   `webhookKey` (string, 必填): 企业微信机器人的 Webhook Key。
*   `content` (string, 必填): 消息内容。
*   `chatid` (string, 可选): 群聊的 ID。如果为空，则尝试发送给所有人 (取决于机器人配置)。默认为 "@all_group" (此值在企业微信中通常无效，具体看机器人配置，一般是指定群聊ID或让机器人发到默认群)。
*   `mentioned_list` (array of strings, 可选): 需要@的成员的 userid 列表。例如 `["zhangsan", "lisi"]`。
*   `mentioned_mobile_list` (array of strings, 可选): 需要@的成员的手机号列表。例如 `["13800000000", "13900000001"]`。

**示例:**

```json
{
  "tool": "sendWeChatTextMessage",
  "arguments": {
    "webhookKey": "YOUR_ACTUAL_WEBHOOK_KEY",
    "content": "大家好，这是一条测试消息！",
    "mentioned_list": ["wangwu"]
  }
}
