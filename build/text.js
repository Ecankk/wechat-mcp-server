export async function sendWeChatTextMessage(webhookKey, content, chatid, mentioned_list, mentioned_mobile_list) {
    const WECHAT_API_URL = `https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=${webhookKey}`;
    const headers = {
        "Content-Type": "application/json",
    };
    const bodyPayload = {
        "msgtype": "text",
        "text": {
            "content": content,
        }
    };
    if (mentioned_list && mentioned_list.length > 0) {
        bodyPayload.text.mentioned_list = mentioned_list;
    }
    if (mentioned_mobile_list && mentioned_mobile_list.length > 0) {
        bodyPayload.text.mentioned_mobile_list = mentioned_mobile_list;
    }
    const body = JSON.stringify(bodyPayload);
    try {
        const response = await fetch(WECHAT_API_URL, { headers, method: "POST", body });
        if (!response.ok) {
            const errorData = await response.text();
            console.error(`HTTP error! status: ${response.status}, data: ${errorData}`);
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const responseData = await response.json();
        if (responseData.errcode !== 0) {
            console.error("Error sending WeChat message:", responseData.errmsg);
            return false;
        }
        console.log("WeChat message sent successfully:", responseData);
        return true;
    }
    catch (error) {
        console.error("Error sending WeChat message:", error);
        return false;
    }
}
