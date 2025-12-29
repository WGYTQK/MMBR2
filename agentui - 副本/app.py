from flask import Flask, render_template, request, jsonify
from datetime import datetime
import os
import requests
import json
from threading import Lock, RLock
from flask_cors import CORS
from concurrent.futures import ThreadPoolExecutor
import html
import time

app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)

# 确保必要的文件夹存在
os.makedirs('static/images', exist_ok=True)
os.makedirs('templates', exist_ok=True)


# ========== 会话管理 ==========
class SessionManager:
    def __init__(self):
        self.sessions = {}
        self.lock = RLock()
        self.message_counter = 0
        self.option_counter = 0

    def get_or_create_session(self, session_id):
        with self.lock:
            if session_id not in self.sessions:
                self.sessions[session_id] = {
                    "conversationId": "",
                    "lastMessageId": 0,
                    "messages": [],
                    "options": None,
                    "last_option_time": 0,
                    "created_at": datetime.now().isoformat(),
                    "last_activity": datetime.now().isoformat()
                }
            else:
                self.sessions[session_id]["last_activity"] = datetime.now().isoformat()
            return self.sessions[session_id]

    def update_session(self, session_id, updates):
        with self.lock:
            if session_id in self.sessions:
                self.sessions[session_id].update(updates)
                self.sessions[session_id]["last_activity"] = datetime.now().isoformat()

    def get_next_message_id(self):
        with self.lock:
            self.message_counter += 1
            return self.message_counter

    def get_next_option_id(self):
        with self.lock:
            self.option_counter += 1
            return self.option_counter

    def clear_options(self, session_id):
        """清除指定会话的选项"""
        with self.lock:
            if session_id in self.sessions:
                self.sessions[session_id]["options"] = None


session_manager = SessionManager()
next_id = 1
messages = []

# 外部选项存储
external_options = None
options_lock = Lock()

# 线程池
executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix="chat_worker")


# ========== 辅助函数 ==========
def sanitize_input(text):
    if not text:
        return ""
    return html.escape(text.strip())


def validate_message_length(text, max_length=2000):
    return len(text) <= max_length


def create_api_payload(user_input, conversation_id=""):
    return {
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
        "conversationId": conversation_id or "",
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


def process_stream_response(response):
    answer = ""
    conversation_id = ""

    for line in response.iter_lines():
        if line:
            decoded_line = line.decode('utf-8')
            if decoded_line.startswith('data:'):
                try:
                    data = json.loads(decoded_line[5:])
                    if data.get("event") == "workflow_finished":
                        answer = data.get("data", {}).get("outputs", {}).get("answer", "")
                        if "conversationId" in data:
                            conversation_id = data["conversationId"]
                except json.JSONDecodeError:
                    continue
    return answer, conversation_id


# ========== 路由 ==========
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/messages', methods=['POST'])
def get_messages():
    global messages
    try:
        data = request.get_json()
        last_id = data.get('last_message_id', 0)

        new_messages = [msg for msg in messages if msg['id'] > last_id]

        if new_messages:
            return jsonify(new_messages[-1])
        return jsonify({
            "status": "no_new_messages",
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"获取消息失败: {str(e)}"
        }), 500


@app.route('/api/options', methods=['GET'])
def get_options():
    """获取待处理选项 - 关键修复：type=1选项只返回一次"""
    global external_options

    session_id = request.remote_addr or "anonymous"
    session_data = session_manager.get_or_create_session(session_id)

    with options_lock:
        # 首先检查全局选项
        if external_options:
            options_data = external_options.copy()
            option_type = options_data.get('type', '1')

            print(
                f"[{datetime.now().strftime('%H:%M:%S')}] 返回选项: type={option_type}, question={options_data.get('question', '')[:50]}")

            # === 关键修复：type=1选项立即清理，确保只返回一次 ===
            if option_type == "1":
                print(f"处理type=1问题选项，返回后立即清理")
                # 清理全局选项（但先返回数据）
                external_options = None
                # 清理会话选项
                session_manager.clear_options(session_id)
                # 返回选项数据
                return jsonify(options_data)
            elif option_type == "0":
                # type=0（更新类型）也立即清理
                print(f"处理type=0更新选项，立即清理")
                external_options = None
                session_manager.clear_options(session_id)
                return jsonify(options_data)

        # 检查会话级别的选项
        if session_data.get("options"):
            options_data = session_data["options"].copy()
            option_type = options_data.get('type', '1')

            print(f"[{datetime.now().strftime('%H:%M:%S')}] 返回会话选项: type={option_type}")

            # 返回后立即清理
            if option_type in ["0", "1"]:
                print(f"处理会话选项，立即清理")
                session_manager.clear_options(session_id)
                return jsonify(options_data)

        # 都没有则返回无选项
        return jsonify({
            "status": "no_options",
            "timestamp": datetime.now().isoformat()
        })


@app.route('/external/options', methods=['GET'])
def receive_external_options():
    """接收外部选项请求 - 确保type=1选项只设置一次"""
    global external_options

    session_id = request.remote_addr or "anonymous"

    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 收到外部选项请求")
    print(f"会话ID: {session_id}")
    print(f"请求参数: type={request.args.get('type', '1')}")

    # 从查询参数获取数据
    request_type = request.args.get('type', '1')
    message = sanitize_input(request.args.get('message', ''))
    question = sanitize_input(request.args.get('question', ''))
    options_str = request.args.get('options', '[]')
    update_data_str = request.args.get('update_data', '{}')

    try:
        options = json.loads(options_str)
        update_data = json.loads(update_data_str)
    except json.JSONDecodeError as e:
        print(f"JSON解析错误: {e}")
        options = []
        update_data = {}

    # 生成选项ID
    option_id = session_manager.get_next_option_id()

    with options_lock:
        # === 关键修复：检查是否已经有相同type=1选项存在 ===
        if request_type == "1" and external_options:
            existing_type = external_options.get('type', '1')
            existing_question = external_options.get('question', '')
            if existing_type == "1" and existing_question == question:
                print(f"已有相同type=1选项存在，跳过设置: {question[:50]}")
                return jsonify({
                    "status": "warning",
                    "message": "相同选项已存在",
                    "type": request_type,
                    "option_id": option_id
                })

        # 创建选项数据
        options_data = {
            "status": "options",
            "type": request_type,
            "message": message[:500],
            "question": question[:200],
            "options": options[:10],
            "update_data": update_data,
            "timestamp": datetime.now().isoformat(),
            "option_id": option_id
        }

        print(f"设置选项: type={request_type}, id={option_id}, question={question[:50]}")

        # 设置选项
        external_options = options_data.copy()

    return jsonify({
        "status": "success",
        "message": "请求已接收",
        "type": request_type,
        "option_id": option_id
    })


@app.route('/reset', methods=['POST'])
def reset_conversation():
    global messages, next_id, external_options

    with options_lock:
        external_options = None

    messages = []
    next_id = 1

    # 清除会话管理器中的所有会话
    session_manager.sessions.clear()

    return jsonify({
        "status": "success",
        "message": "会话已重置",
        "timestamp": datetime.now().isoformat()
    })


@app.route('/post', methods=['POST'])
def post_message():
    global next_id, messages, external_options

    try:
        data = request.get_json()
        if not data:
            return jsonify({
                "status": "error",
                "message": "无效的请求数据"
            }), 400

        user_input = data.get("message", "").strip()
        option_value = data.get("option_value", "")

        if not user_input:
            return jsonify({
                "status": "error",
                "message": "消息不能为空"
            }), 400

        if not validate_message_length(user_input, 2000):
            return jsonify({
                "status": "error",
                "message": "消息过长，请缩短内容"
            }), 400

        user_input = sanitize_input(user_input)

        # 检查是否有未处理的选项
        session_id = request.remote_addr or "anonymous"
        session_data = session_manager.get_or_create_session(session_id)

        # === 关键修复：区分type=0和type=1的检查 ===
        has_pending_question = False
        with options_lock:
            # 检查全局选项
            if external_options:
                option_type = external_options.get('type', '1')
                if option_type == '1':  # 只检查type=1的问题类型
                    has_pending_question = True

        if has_pending_question:
            return jsonify({
                "status": "error",
                "message": "请先处理当前选项",
                "timestamp": datetime.now().isoformat(),
                "blocked_by_options": True
            })

        # 构建API请求体
        payload = create_api_payload(user_input, session_data["conversationId"])

        def call_external_api():
            try:
                response = requests.post(
                    "https://auodigital.corpnet.auo.com:8080/ex/api/dfApp/run",
                    json=payload,
                    headers={
                        "Authorization": "K2405124",
                        "Content-Type": "application/json"
                    },
                    verify=False,
                    stream=True,
                    timeout=30
                )
                response.raise_for_status()
                return response
            except requests.exceptions.Timeout:
                raise Exception("请求超时，请稍后重试")
            except requests.exceptions.RequestException as e:
                raise Exception(f"API请求失败: {str(e)}")

        future = executor.submit(call_external_api)
        response = future.result(timeout=35)

        answer, conversation_id = process_stream_response(response)

        if not answer:
            raise Exception("未获取到有效响应内容")

        if conversation_id:
            session_manager.update_session(session_id, {"conversationId": conversation_id})

        timestamp = datetime.now().isoformat()
        message_id = session_manager.get_next_message_id()

        new_message = {
            "id": message_id,
            "message": answer,
            "timestamp": timestamp,
            "session_id": session_id
        }

        messages.append(new_message)
        session_data["messages"].append(new_message)
        if len(session_data["messages"]) > 100:
            session_data["messages"] = session_data["messages"][-100:]

        next_id = message_id + 1

        # === 关键修复：成功处理后清理选项 ===
        # 只有当用户是通过选择选项发送消息时才清理
        if option_value:
            print(f"用户选择了选项 {option_value}，清理全局选项")
            with options_lock:
                external_options = None
            session_manager.clear_options(session_id)

        return jsonify({
            "status": "success",
            "message": answer,
            "timestamp": timestamp,
            "id": message_id,
            "conversationId": conversation_id
        })

    except Exception as e:
        error_msg = f"请求处理失败: {str(e)}"
        timestamp = datetime.now().isoformat()
        print(f"处理消息时出错: {error_msg}")

        error_message = {
            "id": session_manager.get_next_message_id(),
            "message": error_msg,
            "timestamp": timestamp,
            "type": "error"
        }
        messages.append(error_message)

        return jsonify({
            "status": "error",
            "message": error_msg,
            "timestamp": timestamp,
            "id": error_message["id"]
        }), 500


# ========== 清理任务 ==========
def cleanup_old_options():
    """定期清理过期的选项"""
    global external_options

    while True:
        time.sleep(30)  # 每30秒检查一次
        current_time = time.time()

        with options_lock:
            # 清理全局选项（超过2分钟未处理）
            if external_options:
                option_time_str = external_options.get("timestamp")
                if option_time_str:
                    try:
                        option_time = datetime.fromisoformat(option_time_str.replace('Z', '+00:00'))
                        option_age = (datetime.now() - option_time).total_seconds()

                        # type=0应该在1分钟内清理，type=1在2分钟内清理
                        option_type = external_options.get('type', '1')
                        max_age = 60 if option_type == '0' else 120

                        if option_age > max_age:
                            print(f"清理过期选项: type={option_type}, age={option_age:.0f}s")
                            external_options = None
                    except Exception as e:
                        print(f"清理选项时出错: {e}")
                        external_options = None

        # 清理会话中的过期选项
        with session_manager.lock:
            for session_id, session_data in list(session_manager.sessions.items()):
                if session_data.get("options"):
                    option_time_str = session_data["options"].get("timestamp")
                    if option_time_str:
                        try:
                            option_time = datetime.fromisoformat(option_time_str.replace('Z', '+00:00'))
                            option_age = (datetime.now() - option_time).total_seconds()
                            option_type = session_data["options"].get('type', '1')
                            max_age = 60 if option_type == '0' else 120

                            if option_age > max_age:
                                print(f"清理会话过期选项: session={session_id[:8]}, type={option_type}")
                                session_data["options"] = None
                        except:
                            session_data["options"] = None


# 启动清理线程
import threading

cleanup_thread = threading.Thread(target=cleanup_old_options, daemon=True)
cleanup_thread.start()

# ========== 启动应用 ==========
if __name__ == '__main__':
    print("=" * 50)
    print("AUKS会议预约助手 启动中...")
    print("修复说明: type=0更新选项会立即清理，type=1问题选项会等待用户选择")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    try:
        app.run(
            host="0.0.0.0",
            debug=True,
            port=5008,
            threaded=True
        )
    except KeyboardInterrupt:
        print("\n正在关闭应用...")
        executor.shutdown(wait=True)
        print("应用已关闭")
    except Exception as e:
        print(f"启动失败: {e}")
        executor.shutdown(wait=True)