from flask import Flask, render_template, request, jsonify, Response
from datetime import datetime
import os
import requests
import json
import time
from threading import Lock, RLock
from flask_cors import CORS
from concurrent.futures import ThreadPoolExecutor
import html

app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)

# 确保必要的文件夹存在
os.makedirs('static/images', exist_ok=True)
os.makedirs('templates', exist_ok=True)


# ========== 会话管理 ==========
class SessionManager:
    def __init__(self):
        self.sessions = {}  # session_id -> session_data
        self.lock = RLock()
        self.message_counter = 0
        self.pending_forms = {}  # 存储待处理的表单

    def get_or_create_session(self, session_id):
        """获取或创建会话"""
        with self.lock:
            if session_id not in self.sessions:
                self.sessions[session_id] = {
                    "conversationId": "",
                    "lastMessageId": 0,
                    "messages": [],
                    "created_at": datetime.now().isoformat(),
                    "last_activity": datetime.now().isoformat()
                }
            else:
                self.sessions[session_id]["last_activity"] = datetime.now().isoformat()
            return self.sessions[session_id]

    def update_session(self, session_id, updates):
        """更新会话数据"""
        with self.lock:
            if session_id in self.sessions:
                self.sessions[session_id].update(updates)
                self.sessions[session_id]["last_activity"] = datetime.now().isoformat()

    def get_next_message_id(self):
        """获取下一个消息ID"""
        with self.lock:
            self.message_counter += 1
            return self.message_counter

    def add_pending_form(self, session_id, form_data):
        """添加待处理表单"""
        with self.lock:
            if session_id not in self.pending_forms:
                self.pending_forms[session_id] = []

            form_id = f"form_{int(time.time())}_{len(self.pending_forms[session_id])}"
            form_data['form_id'] = form_id
            self.pending_forms[session_id].append(form_data)
            print(f"✅ 添加表单: {form_id}, 类型: {form_data.get('type')}, 问题: {form_data.get('question', '')[:50]}")
            return form_id

    def get_pending_forms(self, session_id):
        """获取所有待处理表单"""
        with self.lock:
            return self.pending_forms.get(session_id, [])

    def remove_form(self, session_id, form_id):
        """移除已处理的表单"""
        with self.lock:
            if session_id in self.pending_forms:
                original_count = len(self.pending_forms[session_id])
                self.pending_forms[session_id] = [
                    f for f in self.pending_forms[session_id]
                    if f['form_id'] != form_id
                ]
                if len(self.pending_forms[session_id]) < original_count:
                    print(f"🗑️ 移除表单: {form_id}")

    def clear_all_forms(self, session_id):
        """清空所有表单"""
        with self.lock:
            if session_id in self.pending_forms:
                count = len(self.pending_forms[session_id])
                self.pending_forms[session_id] = []
                print(f"🧹 清空 {count} 个表单")
                return count
            return 0


session_manager = SessionManager()
messages = []  # 全局消息历史

# 线程池
executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix="chat_worker")


# ========== 辅助函数 ==========
def sanitize_input(text):
    """清理用户输入，防止XSS攻击"""
    if not text:
        return ""
    return html.escape(text.strip())


def validate_message_length(text, max_length=2000):
    """验证消息长度"""
    return len(text) <= max_length


def create_api_payload(user_input, conversation_id=""):
    """创建API请求负载"""
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


# ========== 路由 ==========
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/forms', methods=['GET'])
def get_pending_forms():
    """获取所有待处理表单"""
    session_id = request.remote_addr or "anonymous"
    forms = session_manager.get_pending_forms(session_id)
    return jsonify({
        "status": "success",
        "forms": forms,
        "count": len(forms)
    })


@app.route('/api/submit_form', methods=['POST'])
def submit_form():
    """提交单个表单"""
    try:
        data = request.get_json()
        session_id = request.remote_addr or "anonymous"
        form_id = data.get('form_id')
        form_data = data.get('form_data', {})
        form_type = data.get('type', '1')

        # 从前端直接获取完整消息（如果提供了）
        full_message = data.get('full_message', '')

        if not form_id:
            return jsonify({"status": "error", "message": "缺少form_id"}), 400

        # 标记表单为已处理
        session_manager.remove_form(session_id, form_id)

        # 构建消息文本
        message_text = ""

        if not full_message:
            # 如果没有提供完整消息，自己构建
            if form_type == '1':
                # 选择题：直接使用选项文本
                message_text = form_data.get('selected_text', '')
            elif form_type == '2':
                # 输入框：组合所有输入
                inputs = []
                for key, value in form_data.items():
                    if key not in ['type', 'selected_text']:
                        inputs.append(f"{key}: {value}")
                message_text = "; ".join(inputs)
        else:
            # 使用前端提供的完整消息
            message_text = full_message

        print(f"📤 提交表单: {form_id}, 类型: {form_type}")
        print(f"   消息: {message_text[:100]}...")

        return jsonify({
            "status": "success",
            "message": "表单已提交",
            "form_id": form_id,
            "message_text": message_text,
            "form_type": form_type
        })

    except Exception as e:
        print(f"❌ 提交表单失败: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/submit_all', methods=['POST'])
def submit_all_forms():
    """提交所有待处理表单"""
    try:
        data = request.get_json()
        session_id = request.remote_addr or "anonymous"
        all_form_data = data.get('form_data', {})

        # 从前端直接获取合并消息（如果提供了）
        combined_message = data.get('combined_message', '')

        submitted_forms = []
        all_messages = []

        for form_id, form_data in all_form_data.items():
            # 移除表单
            session_manager.remove_form(session_id, form_id)

            # 构建消息文本
            form_type = form_data.get('type', '1')

            if form_type == '1':
                # 选择题
                selected_text = form_data.get('selected_text', '')
                question = form_data.get('question', '选择题')
                if selected_text:
                    all_messages.append(f"【{question}】\n选择：{selected_text}")
            elif form_type == '2':
                # 输入框
                inputs = []
                form_data_obj = form_data.get('form_data', {})
                question = form_data.get('question', '输入表单')
                for key, value in form_data_obj.items():
                    inputs.append(f"{key}: {value}")
                if inputs:
                    all_messages.append(f"【{question}】\n" + "\n".join(inputs))

            submitted_forms.append(form_id)

        # 合并所有消息
        if combined_message:
            # 使用前端提供的合并消息
            final_message = combined_message
        else:
            # 后端自己合并
            final_message = "\n\n".join(all_messages)

        print(f"📤 批量提交 {len(submitted_forms)} 个表单")
        print(f"   合并消息: {final_message[:200]}...")

        return jsonify({
            "status": "success",
            "message": f"已提交 {len(submitted_forms)} 个表单",
            "submitted_forms": submitted_forms,
            "combined_message": final_message,
            "count": len(submitted_forms)
        })

    except Exception as e:
        print(f"❌ 批量提交失败: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/clear_forms', methods=['POST'])
def clear_forms():
    """清空所有表单"""
    try:
        session_id = request.remote_addr or "anonymous"
        count = session_manager.clear_all_forms(session_id)

        return jsonify({
            "status": "success",
            "message": f"已清空 {count} 个表单",
            "count": count
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/external/options', methods=['GET'])
def receive_external_options():
    """接收外部选项请求"""
    session_id = request.remote_addr or "anonymous"

    print(f"\n📩 [{datetime.now().strftime('%H:%M:%S')}] 收到外部请求")
    print(f"   会话ID: {session_id[:8]}")
    print(f"   请求类型: type={request.args.get('type', '1')}")

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
        print(f"    JSON解析错误: {e}")
        options = []
        update_data = {}

    # 构建表单数据
    form_data = {
        "type": request_type,
        "message": message[:500],
        "question": question[:200],
        "options": options[:10],  # 限制选项数量
        "update_data": update_data,
        "timestamp": datetime.now().isoformat(),
        "status": "pending"
    }

    # 添加到待处理表单
    form_id = session_manager.add_pending_form(session_id, form_data)

    return jsonify({
        "status": "success",
        "message": "请求已接收",
        "type": request_type,
        "form_id": form_id,
        "form_count": len(session_manager.get_pending_forms(session_id))
    })


@app.route('/post', methods=['POST'])
def post_message():
    """处理用户消息 - 流式输出"""
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

        # 获取会话
        session_id = request.remote_addr or "anonymous"
        session_data = session_manager.get_or_create_session(session_id)

        # 获取conversationId
        conversation_id = ""
        if data.get("conversation_id"):
            conversation_id = data["conversation_id"]
        elif session_data["conversationId"]:
            conversation_id = session_data["conversationId"]

        print(f"📤 用户消息: {user_input[:100]}...")
        print(f"   conversation_id: {conversation_id}")

        # 构建API请求体
        payload = create_api_payload(user_input, conversation_id)

        def generate_stream():
            """生成流式响应"""
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

                answer = ""
                new_conversation_id = conversation_id

                for line in response.iter_lines():
                    if line:
                        decoded_line = line.decode('utf-8')
                        if decoded_line.startswith('data:'):
                            try:
                                data = json.loads(decoded_line[5:])
                                if data.get("event") == "workflow_finished":
                                    answer = data.get("data", {}).get("outputs", {}).get("answer", "")

                                    # 更新conversationId
                                    if "conversationId" in data:
                                        new_conversation_id = data["conversationId"]
                                        session_manager.update_session(session_id, {
                                            "conversationId": new_conversation_id
                                        })
                                        print(f"   🔄 更新conversationId: {new_conversation_id}")

                                    # 流式输出的最后一部分：完整答案
                                    yield f"data: {json.dumps({'type': 'complete', 'answer': answer,'conversation_id': new_conversation_id})}\n\n"

                                    # 保存消息到历史记录
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

                                elif data.get("event") == "stream_start":
                                    # 流式输出开始
                                    yield f"data: {json.dumps({'type': 'start','message': '开始接收回答...'})}\n\n"

                                elif data.get("event") == "stream_chunk":
                                    # 流式输出中间片段
                                    chunk = data.get("data", {}).get("chunk", "")
                                    if chunk:
                                        yield f"data: {json.dumps({'type': 'chunk','chunk': chunk})}\n\n"

                            except json.JSONDecodeError:
                                continue
                else:
                    # 如果没有获取到完整答案，返回错误
                    yield f"data: {json.dumps({'type': 'error','message': '未获取到完整响应'})}\n\n"

            except requests.exceptions.Timeout:
                yield f"data: {json.dumps({'type': 'error','message': '请求超时，请稍后重试'})}\n\n"
            except requests.exceptions.RequestException as e:yield f"data: {json.dumps({'type': 'error','message': f'API请求失败: {str(e)}'})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error','message': f'处理失败: {str(e)}'})}\n\n"

        # 返回流式响应
        return Response(generate_stream(), mimetype='text/event-stream')

    except Exception as e:
        error_msg = f"请求处理失败: {str(e)}"
        timestamp = datetime.now().isoformat()
        print(f"❌ 处理消息时出错: {error_msg}")

        return jsonify({
            "status": "error",
            "message": error_msg,
            "timestamp": timestamp
        }), 500


@app.route('/reset', methods=['POST'])
def reset_conversation():
    """重置会话"""
    global messages

    session_id = request.remote_addr or "anonymous"

    # 清空消息历史
    messages = []

    # 清空会话
    session_manager.sessions.clear()

    # 清空待处理表单
    session_manager.clear_all_forms(session_id)

    print(f"🔄 重置会话: {session_id[:8]}")

    return jsonify({
        "status": "success",
        "message": "会话已重置",
        "timestamp": datetime.now().isoformat()
    })


@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查"""
    session_id = request.remote_addr or "anonymous"
    forms = session_manager.get_pending_forms(session_id)

    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "chatbot",
        "version": "2.0",
        "pending_forms": len(forms),
        "active_sessions": len(session_manager.sessions)
    })


# ========== 错误处理 ==========
@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "status": "error",
        "message": "资源未找到"
    }), 404


@app.errorhandler(500)
def internal_error(error):
    print(f"❌ 服务器内部错误: {str(error)}")
    return jsonify({
        "status": "error",
        "message": "服务器内部错误",
        "timestamp": datetime.now().isoformat()
    }), 500


# ========== 启动应用 ==========
if __name__ == '__main__':
    print("=" * 50)
    print("🤖 AUKS会议预约助手 v2.0")
    print(f"⏰ 启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    try:
        app.run(
            host="0.0.0.0",
            debug=True,
            port=5008,
            threaded=True
        )
    except KeyboardInterrupt:
        print("\n🛑 正在关闭应用...")
        executor.shutdown(wait=True)
        print("✅ 应用已关闭")
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        executor.shutdown(wait=True)