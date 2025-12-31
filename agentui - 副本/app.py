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
CORS(app, origins="*")

# 确保必要的文件夹存在
os.makedirs('static/images', exist_ok=True)
os.makedirs('templates', exist_ok=True)

# ========== 全局表单管理 ==========
class GlobalFormManager:
    def __init__(self):
        self.pending_forms = []  # 全局表单列表，不分session
        self.lock = RLock()
        self.form_counter = 0
        self.max_forms = 100  # 最大表单数量限制

    def add_form(self, form_data):
        """添加表单到全局列表"""
        with self.lock:
            # 清理过期的表单（超过30分钟）
            self._cleanup_old_forms()
            
            # 检查是否达到最大限制
            if len(self.pending_forms) >= self.max_forms:
                # 移除最旧的表单
                removed = self.pending_forms.pop(0)
                print(f"?? 达到表单上限，移除旧表单: {removed.get('form_id')}")
            
            # 生成表单ID
            form_id = f"global_form_{int(time.time())}_{self.form_counter}"
            self.form_counter += 1
            
            # 完善表单数据
            form_data['form_id'] = form_id
            form_data['created_at'] = datetime.now().isoformat()
            
            # 添加到列表
            self.pending_forms.append(form_data)
            
            # 记录日志
            print(f"? 添加全局表单: {form_id}")
            print(f"   类型: {form_data.get('type')}, 问题: {form_data.get('question', '')}")
            print(f"   来源IP: {form_data.get('source_ip', 'unknown')}")
            print(f"   当前全局表单数量: {len(self.pending_forms)}")
            
            return form_id

    def get_all_forms(self):
        """获取所有全局表单"""
        with self.lock:
            self._cleanup_old_forms()  # 清理过期的表单
            return self.pending_forms.copy()

    def get_form(self, form_id):
        """获取特定表单"""
        with self.lock:
            for form in self.pending_forms:
                if form.get('form_id') == form_id:
                    return form.copy()
            return None

    def remove_form(self, form_id):
        """移除表单"""
        with self.lock:
            initial_count = len(self.pending_forms)
            self.pending_forms = [f for f in self.pending_forms if f['form_id'] != form_id]
            removed = initial_count - len(self.pending_forms)
            if removed > 0:
                print(f"?? 移除表单: {form_id}")
                print(f"   剩余表单数量: {len(self.pending_forms)}")
            return removed

    def clear_all_forms(self):
        """清空所有表单"""
        with self.lock:
            count = len(self.pending_forms)
            self.pending_forms = []
            print(f"? 清空所有表单: {count} 个")
            return count

    def _cleanup_old_forms(self, max_age_minutes=30):
        """清理过期的表单"""
        with self.lock:
            current_time = datetime.now()
            initial_count = len(self.pending_forms)
            
            self.pending_forms = [
                f for f in self.pending_forms
                if self._is_form_valid(f, current_time, max_age_minutes)
            ]
            
            cleaned = initial_count - len(self.pending_forms)
            if cleaned > 0:
                print(f"? 清理过期表单: {cleaned} 个")

    def _is_form_valid(self, form, current_time, max_age_minutes):
        """检查表单是否过期"""
        try:
            created_at_str = form.get('created_at')
            if not created_at_str:
                return True  # 如果没有创建时间，保留表单
            
            created_at = datetime.fromisoformat(created_at_str)
            age_minutes = (current_time - created_at).total_seconds() / 60
            
            return age_minutes <= max_age_minutes
        except:
            return True  # 如果解析失败，保留表单

# 初始化全局表单管理器
form_manager = GlobalFormManager()

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

def log_request_info(endpoint, request):
    """记录请求信息"""
    print(f"\n? [{datetime.now().strftime('%H:%M:%S')}] {endpoint}")
    print(f"   来源IP: {request.remote_addr}")
    print(f"   方法: {request.method}")
    print(f"   路径: {request.path}")
    if request.args:
        print(f"   参数: {dict(request.args)}")

# ========== 路由 ==========
@app.route('/')
def index():
    """主页"""
    return render_template('index.html')

@app.route('/api/forms', methods=['GET'])
def get_pending_forms():
    """获取所有待处理表单 - 全局"""
    log_request_info('获取全局表单', request)
    
    forms = form_manager.get_all_forms()
    print(f"? 返回表单数量: {len(forms)}")
    
    return jsonify({
        "status": "success",
        "forms": forms,
        "count": len(forms),
        "is_global": True,
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/submit_form', methods=['POST'])
def submit_form():
    """提交单个表单"""
    try:
        log_request_info('提交单个表单', request)
        
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "无效的请求数据"}), 400
        
        form_id = data.get('form_id')
        if not form_id:
            return jsonify({"status": "error", "message": "缺少form_id"}), 400

        # 从全局表单中移除
        removed = form_manager.remove_form(form_id)
        
        if removed == 0:
            return jsonify({"status": "error", "message": "表单不存在或已被处理"}), 404

        # 构建消息文本
        form_data = data.get('form_data', {})
        form_type = data.get('type', '1')
        message_text = ""

        if form_type == '1':
            # 选择题
            message_text = form_data.get('selected_text', '')
        elif form_type == '2':
            # 输入框
            inputs = []
            for key, value in form_data.items():
                if key not in ['type', 'selected_text']:
                    inputs.append(f"{key}: {value}")
            message_text = "; ".join(inputs)

        print(f"? 提交表单: {form_id}")
        print(f"   类型: {form_type}, 消息: {message_text[:100]}...")
        print(f"   剩余全局表单: {len(form_manager.get_all_forms())}")

        return jsonify({
            "status": "success",
            "message": "表单已提交",
            "form_id": form_id,
            "message_text": message_text,
            "form_type": form_type,
            "remaining_forms": len(form_manager.get_all_forms()),
            "timestamp": datetime.now().isoformat()
        })

    except Exception as e:
        print(f"? 提交表单失败: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/submit_all', methods=['POST'])
def submit_all_forms():
    """提交所有待处理表单"""
    try:
        log_request_info('批量提交表单', request)
        
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "无效的请求数据"}), 400
        
        all_form_data = data.get('form_data', {})

        submitted_forms = []
        all_messages = []
        failed_forms = []

        for form_id, form_data in all_form_data.items():
            # 尝试从全局表单中移除
            removed = form_manager.remove_form(form_id)
            if removed > 0:
                # 构建消息文本
                form_type = form_data.get('type', '1')
                message_text = ""
                
                if form_type == '1':
                    message_text = form_data.get('selected_text', '')
                elif form_type == '2':
                    inputs = []
                    form_inputs = form_data.get('form_data', {})
                    for key, value in form_inputs.items():
                        inputs.append(f"{key}: {value}")
                    message_text = "; ".join(inputs)

                if message_text:
                    all_messages.append(message_text)
                    submitted_forms.append(form_id)
                    print(f"? 成功处理表单: {form_id}")
                else:
                    failed_forms.append(form_id)
                    print(f"??  表单无内容: {form_id}")
            else:
                failed_forms.append(form_id)
                print(f"??  表单不存在: {form_id}")

        # 合并所有消息
        combined_message = " | ".join(all_messages) if all_messages else ""

        print(f"? 批量提交完成")
        print(f"   成功: {len(submitted_forms)} 个")
        print(f"   失败: {len(failed_forms)} 个")
        print(f"   剩余全局表单: {len(form_manager.get_all_forms())}")

        return jsonify({
            "status": "success",
            "message": f"已提交 {len(submitted_forms)} 个表单",
            "submitted_forms": submitted_forms,
            "failed_forms": failed_forms,
            "combined_message": combined_message,
            "count": len(submitted_forms),
            "remaining_forms": len(form_manager.get_all_forms()),
            "timestamp": datetime.now().isoformat()
        })

    except Exception as e:
        print(f"? 批量提交失败: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/clear_forms', methods=['POST'])
def clear_forms():
    """清空所有表单"""
    try:
        log_request_info('清空表单', request)
        
        count = form_manager.clear_all_forms()
        
        return jsonify({
            "status": "success",
            "message": f"已清空 {count} 个表单",
            "count": count,
            "timestamp": datetime.now().isoformat()
        })

    except Exception as e:
        print(f"? 清空表单失败: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/external/options', methods=['GET'])
def receive_external_options():
    """接收外部选项请求 - 全局版本"""
    log_request_info('外部表单请求', request)
    
    # 从查询参数获取数据
    request_type = request.args.get('type', '1')
    message = request.args.get('message', '')
    question = request.args.get('question', '')
    options_str = request.args.get('options', '[]')
    update_data_str = request.args.get('update_data', '{}')

    print(f"   请求类型: {request_type}")
    print(f"   问题: {question}")
    print(f"   消息: {message[:50]}..." if message else "   消息: (空)")

    # 解析选项
    try:
        options = json.loads(options_str)
    except json.JSONDecodeError as e:
        print(f"? 选项JSON解析错误: {e}")
        print(f"   原始数据: {options_str[:100]}...")
        options = []

    # 解析更新数据
    try:
        update_data = json.loads(update_data_str)
    except json.JSONDecodeError:
        update_data = {}

    print(f"   选项数量: {len(options)}")
    if options:
        for i, opt in enumerate(options[:3]):  # 只显示前3个选项
            print(f"     选项{i+1}: {opt.get('text', 'N/A')}")

    # 构建表单数据
    form_data = {
        "type": request_type,
        "message": sanitize_input(message)[:500],
        "question": sanitize_input(question)[:200],
        "options": options[:10],  # 限制选项数量
        "update_data": update_data,
        "timestamp": datetime.now().isoformat(),
        "status": "pending",
        "source_ip": request.remote_addr or "unknown",
        "is_global": True
    }

    # 添加到全局表单管理器
    try:
        form_id = form_manager.add_form(form_data)
        current_count = len(form_manager.get_all_forms())
        
        response_data = {
            "status": "success",
            "message": "全局表单请求已接收",
            "type": request_type,
            "form_id": form_id,
            "form_count": current_count,
            "is_global": True,
            "notice": "此表单将显示在所有连接的设备上",
            "timestamp": datetime.now().isoformat()
        }
        
        print(f"? 表单创建成功: {form_id}")
        print(f"   当前全局表单总数: {current_count}")
        
        return jsonify(response_data)
        
    except Exception as e:
        print(f"? 表单创建失败: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "message": f"表单创建失败: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }), 500

@app.route('/post', methods=['POST'])
def post_message():
    """处理用户消息 - 流式输出"""
    try:
        log_request_info('发送消息', request)
        
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

        # 获取conversationId
        conversation_id = data.get("conversation_id", "")

        print(f"? 用户消息: {user_input[:100]}...")
        print(f"   conversation_id: {conversation_id}")
        print(f"   选项来源: {option_value}")

        # 构建API请求体
        payload = create_api_payload(user_input, conversation_id)

        def generate_stream():
            """生成流式响应"""
            try:
                print(f"? 开始流式请求...")
                
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
                received_data = False

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
                                        print(f"? 更新conversationId: {new_conversation_id}")
                                    
                                    # 流式输出的最后一部分：完整答案
                                    yield f"data: {json.dumps({'type': 'complete', 'answer': answer,'conversation_id': new_conversation_id})}\n\n"
                                    received_data = True

                                elif data.get("event") == "stream_start":
                                    # 流式输出开始
                                    yield f"data: {json.dumps({'type': 'start','message': '开始接收回答...'})}\n\n"
                                    received_data = True

                                elif data.get("event") == "stream_chunk":
                                    # 流式输出中间片段
                                    chunk = data.get("data", {}).get("chunk", "")
                                    if chunk:
                                        yield f"data: {json.dumps({'type': 'chunk','chunk': chunk})}\n\n"
                                        received_data = True

                            except json.JSONDecodeError as e:
                                print(f"? JSON解析错误: {e}")
                                print(f"   原始数据: {decoded_line[:100]}...")
                                continue
                
                if not received_data:
                    print(f"??  未收到有效数据")
                    yield f"data: {json.dumps({'type': 'error','message': '未获取到有效响应数据'})}\n\n"

            except requests.exceptions.Timeout:
                print(f"? 请求超时")
                yield f"data: {json.dumps({'type': 'error','message': '请求超时，请稍后重试'})}\n\n"
            except requests.exceptions.RequestException as e:
                print(f"? 网络请求失败: {e}")
                yield f"data: {json.dumps({'type': 'error','message': f'API请求失败: {str(e)}'})}\n\n"
            except Exception as e:
                print(f"? 流式处理失败: {e}")
                yield f"data: {json.dumps({'type': 'error','message': f'处理失败: {str(e)}'})}\n\n"

        # 返回流式响应
        return Response(generate_stream(), mimetype='text/event-stream')

    except Exception as e:
        error_msg = f"请求处理失败: {str(e)}"
        timestamp = datetime.now().isoformat()
        print(f"? 处理消息时出错: {error_msg}")
        import traceback
        traceback.print_exc()

        return jsonify({
            "status": "error",
            "message": error_msg,
            "timestamp": timestamp
        }), 500

@app.route('/reset', methods=['POST'])
def reset_conversation():
    """重置会话"""
    log_request_info('重置会话', request)
    
    # 注意：这里不清空全局表单，因为全局表单是共享的
    # 如果需要清空全局表单，请使用 /api/clear_forms
    
    print(f"? 重置会话请求，来源IP: {request.remote_addr}")
    print(f"   当前全局表单数量: {len(form_manager.get_all_forms())}")

    return jsonify({
        "status": "success",
        "message": "会话已重置（全局表单不受影响）",
        "timestamp": datetime.now().isoformat(),
        "global_forms_count": len(form_manager.get_all_forms()),
        "notice": "全局表单未清除，如需清空请使用表单清空功能"
    })

@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查"""
    forms = form_manager.get_all_forms()
    
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "chatbot-global-form",
        "version": "3.0",
        "global_forms": len(forms),
        "is_global": True,
        "max_forms": form_manager.max_forms,
        "uptime": datetime.now().isoformat()  # 简化的运行时间
    })

@app.route('/api/debug', methods=['GET'])
def debug_info():
    """调试信息"""
    forms = form_manager.get_all_forms()
    
    return jsonify({
        "status": "success",
        "timestamp": datetime.now().isoformat(),
        "server_info": {
            "python_version": "3.x",
            "flask_version": "2.3.3",
            "max_forms": form_manager.max_forms
        },
        "forms_summary": {
            "total_count": len(forms),
            "type_1_count": len([f for f in forms if f.get('type') == '1']),
            "type_2_count": len([f for f in forms if f.get('type') == '2']),
            "recent_forms": [
                {
                    "id": f.get('form_id', 'N/A'),
                    "type": f.get('type'),
                    "question": f.get('question', '')[:50],
                    "created_at": f.get('created_at', 'N/A'),
                    "source": f.get('source_ip', 'unknown')
                }
                for f in forms[:5]  # 显示最近5个表单
            ]
        }
    })

# ========== 错误处理 ==========
@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "status": "error",
        "message": "资源未找到",
        "path": request.path,
        "timestamp": datetime.now().isoformat()
    }), 404

@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({
        "status": "error",
        "message": "方法不允许",
        "allowed_methods": error.get_allowed_methods(),
        "timestamp": datetime.now().isoformat()
    }), 405

@app.errorhandler(500)
def internal_error(error):
    print(f"? 服务器内部错误: {str(error)}")
    import traceback
    traceback.print_exc()
    
    return jsonify({
        "status": "error",
        "message": "服务器内部错误",
        "timestamp": datetime.now().isoformat(),
        "error": str(error) if app.debug else "Internal server error"
    }), 500

# ========== 启动应用 ==========
if __name__ == '__main__':
    print("=" * 60)
    print("? AUKS会议预约助手 - 全局弹窗版 v3.0")
    print(f"? 启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # 显示服务器信息
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except:
        local_ip = "127.0.0.1"
    
    print("? 服务器信息:")
    print(f"   本地访问: http://localhost:5008")
    print(f"   网络访问: http://{local_ip}:5008")
    print("")
    print("? 全局表单特性:")
    print("   ? 所有设备共享同一表单池")
    print("   ? 表单自动清理: 30分钟过期")
    print("   ? 最大表单数: 100个")
    print("   ? 实时同步: 任何操作立即生效")
    print("")
    print("??  可用接口:")
    print("   GET  /                    - 主页面")
    print("   GET  /api/forms           - 获取全局表单")
    print("   POST /api/submit_form     - 提交单个表单")
    print("   POST /api/submit_all      - 批量提交表单")
    print("   POST /api/clear_forms     - 清空所有表单")
    print("   GET  /external/options    - 外部系统调用接口")
    print("   POST /post                - 发送消息到AI")
    print("   POST /reset               - 重置会话")
    print("   GET  /api/health          - 健康检查")
    print("   GET  /api/debug           - 调试信息")
    print("=" * 60)

    try:
        app.run(
            host="0.0.0.0",
            debug=True,
            port=5008,
            threaded=True
        )
    except KeyboardInterrupt:
        print("\n? 正在关闭应用...")
        executor.shutdown(wait=True)
        print("? 应用已关闭")
    except Exception as e:
        print(f"? 启动失败: {e}")
        executor.shutdown(wait=True)
