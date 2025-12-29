from flask import Flask, render_template, request, jsonify
from datetime import datetime
import os
import requests
import json
from threading import Lock
from flask_cors import CORS  # 添加这行
app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)
# 确保必要的文件夹存在
os.makedirs('static/images', exist_ok=True)
os.makedirs('templates', exist_ok=True)

# 全局变量保存会话状态
conversation_state = {
    "conversationId": "",
    "lastMessageId": 0
}

messages = []  # 存储历史消息
next_id = 1  # 消息ID计数器

# 用于存储外部请求的选项
external_options = None
options_lock = Lock()


@app.route('/api/messages', methods=['POST'])
def get_messages():
    global next_id
    data = request.get_json()
    last_id = data.get('last_message_id', 0)

    new_messages = [msg for msg in messages if msg['id'] > last_id]

    if new_messages:
        return jsonify(new_messages[-1])
    return jsonify({"status": "no_new_messages"})


@app.route('/api/options', methods=['GET'])
def get_options():
    global external_options

    with options_lock:
        if external_options:
            # 返回外部请求的选项
            options_data = external_options.copy()
            external_options = None  # 清空已处理的选项
            return jsonify(options_data)

        # 如果没有外部选项，返回默认选项
        return jsonify({
            "status": "no_options",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })


@app.route('/external/options', methods=['GET'])
def receive_external_options():
    global external_options

    print("\n=== 收到外部选项请求 ===")
    print(f"请求参数: {request.args}")

    # 从查询参数获取数据
    request_type = request.args.get('type', '1')  # 默认为问题类(1)
    message = request.args.get('message', '')
    question = request.args.get('question', '')
    options_str = request.args.get('options', '[]')
    update_data_str = request.args.get('update_data', '{}')

    try:
        options = json.loads(options_str)
        update_data = json.loads(update_data_str)
    except json.JSONDecodeError:
        options = []
        update_data = {}

    with options_lock:
        external_options = {
            "status": "options",
            "type": request_type,  # 0=更新，1=问题
            "message": message,
            "question": question,
            "options": options,
            "update_data": update_data,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        print(f"设置的外部选项: {external_options}")

    return jsonify({
        "status": "success",
        "message": "Request received",
        "type": request_type
    })


@app.route('/reset', methods=['POST'])
def reset_conversation():
    global conversation_state
    conversation_state = {"conversationId": "", "lastMessageId": 0}  # 仅重置不生成新ID
    return jsonify({"status": "success"})

@app.route('/post', methods=['POST'])
def post_message():
    global next_id, conversation_state

    # 如果会话ID为空，说明是刷新后的第一次请求
    if conversation_state["conversationId"] is None:
        return jsonify({
            "status": "new_session",
            "conversationId": conversation_state["conversationId"],
            "message": "新会话已创建"
        })

    # 检查是否有未处理的选项
    with options_lock:
        if external_options:
            return jsonify({
                "status": "error",
                "message": "请先处理当前选项",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "blocked_by_options": True  # 新增标志
            })


    user_input = request.get_json().get("message", "").strip()
    if not user_input:
        return jsonify({"status": "error", "message": "消息不能为空"})

    # 构建API请求体
    payload = {
        "appId": 229,
        "inputParams": [
            {
                "name": "query",
                "type": "paragraph",
                "value": "222222"
            },
            {
                "name": "kk",
                "type": "select",
                "value": "o"
            },
            {
                "name": "fileTypes",
                "type": "file-list",
                "files": [
                    {
                        "fileType": "image",
                        "fileId": "96e71bc3-7a1d-466b-a969-b325eeef194a"
                    }
                ]
            }
        ],
        "query": user_input,
        "conversationId": conversation_state["conversationId"] or "",
        "files": [
            {
                "fileType": "document",
                "fileId": "96e23bc3-7a1d-466b-a223-b325eeef164a"
            },
            {
                "fileType": "image",
                "fileId": "96e71bc3-7a1d-466b-a969-b325eeef194a"
            }
        ]
    }

    try:
        # 发送请求到目标API
        response = requests.post(
            "https://auodigital.corpnet.auo.com:8080/ex/api/dfApp/run",
            json=payload,
            headers={
                "Authorization": "K2405124",
                "Content-Type": "application/json"
            },
            verify=False,
            stream=True
        )

        if response.status_code != 200:
            raise Exception(f"API返回错误状态码: {response.status_code}")

        # 处理流式响应
        answer = ""
        for line in response.iter_lines():
            if line:
                decoded_line = line.decode('utf-8')
                if decoded_line.startswith('data:'):
                    try:
                        data = json.loads(decoded_line[5:])
                        if data.get("event") == "workflow_finished":
                            answer = data.get("data", {}).get("outputs", {}).get("answer", "")
                            if "conversationId" in data:
                                conversation_state["conversationId"] = data["conversationId"]
                    except json.JSONDecodeError:
                        continue

        if not answer:
            raise Exception("未获取到有效响应内容")

        # 保存消息到历史记录
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        new_message = {
            "id": next_id,
            "message": answer,
            "timestamp": timestamp
        }
        messages.append(new_message)
        next_id += 1

        return jsonify({
            "status": "success",
            "message": answer,
            "timestamp": timestamp,
            "id": new_message["id"],
            "conversationId": conversation_state["conversationId"]
        })

    except Exception as e:
        error_msg = f"请求处理失败: {str(e)}"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        messages.append({
            "id": next_id,
            "message": error_msg,
            "timestamp": timestamp
        })
        next_id += 1
        return jsonify({
            "status": "error",
            "message": error_msg,
            "timestamp": timestamp,
            "id": next_id - 1
        })


@app.route('/')
def index():
    return render_template('index.html')


if __name__ == '__main__':
    app.run(host="0.0.0.0", debug=True, port=5008)
