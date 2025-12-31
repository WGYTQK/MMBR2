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

# ========== 全局表单管理 ==========
class GlobalFormManager:
    def __init__(self):
        self.pending_forms = []  # 全局表单列表，不分session
        self.lock = RLock()
        self.form_counter = 0

    def add_form(self, form_data):
        """添加表单到全局列表"""
        with self.lock:
            form_id = f"global_form_{int(time.time())}_{self.form_counter}"
            self.form_counter += 1
            
            form_data['form_id'] = form_id
            self.pending_forms.append(form_data)
            
            print(f"? 添加全局表单: {form_id}")
            print(f"   类型: {form_data.get('type')}, 问题: {form_data.get('question', '')}")
            print(f"   当前全局表单数量: {len(self.pending_forms)}")
            
            return form_id

    def get_all_forms(self):
        """获取所有全局表单"""
        with self.lock:
            return self.pending_forms.copy()

    def remove_form(self, form_id):
        """移除表单"""
        with self.lock:
            initial_count = len(self.pending_forms)
            self.pending_forms = [f for f in self.pending_forms if f['form_id'] != form_id]
            removed = initial_count - len(self.pending_forms)
            if removed > 0:
                print(f"?? 移除表单: {form_id}")
            return removed

    def clear_all_forms(self):
        """清空所有表单"""
        with self.lock:
            count = len(self.pending_forms)
            self.pending_forms = []
            print(f"? 清空所有表单: {count} 个")
            return count

# 初始化全局表单管理器
form_manager = GlobalFormManager()

# ========== 路由修改 ==========

@app.route('/api/forms', methods=['GET'])
def get_pending_forms():
    """获取所有待处理表单 - 全局"""
    forms = form_manager.get_all_forms()
    print(f"? 获取全局表单，数量: {len(forms)}")
    
    return jsonify({
        "status": "success",
        "forms": forms,
        "count": len(forms),
        "is_global": True  # 标识这是全局表单
    })

@app.route('/api/submit_form', methods=['POST'])
def submit_form():
    """提交单个表单"""
    try:
        data = request.get_json()
        form_id = data.get('form_id')
        
        if not form_id:
            return jsonify({"status": "error", "message": "缺少form_id"}), 400

        # 从全局表单中移除
        removed = form_manager.remove_form(form_id)
        
        if removed == 0:
            return jsonify({"status": "error", "message": "表单不存在"}), 404

        # 构建消息文本
        form_data = data.get('form_data', {})
        form_type = data.get('type', '1')
        message_text = ""

        if form_type == '1':
            message_text = form_data.get('selected_text', '')
        elif form_type == '2':
            inputs = []
            for key, value in form_data.items():
                if key not in ['type', 'selected_text']:
                    inputs.append(f"{key}: {value}")
            message_text = "; ".join(inputs)

        print(f"? 提交全局表单: {form_id}, 消息: {message_text[:50]}...")

        return jsonify({
            "status": "success",
            "message": "表单已提交",
            "form_id": form_id,
            "message_text": message_text,
            "remaining_forms": len(form_manager.get_all_forms())
        })

    except Exception as e:
        print(f"? 提交表单失败: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/submit_all', methods=['POST'])
def submit_all_forms():
    """提交所有待处理表单"""
    try:
        data = request.get_json()
        all_form_data = data.get('form_data', {})

        submitted_forms = []
        all_messages = []

        for form_id, form_data in all_form_data.items():
            # 从全局表单中移除
            removed = form_manager.remove_form(form_id)
            if removed > 0:
                # 构建消息文本
                form_type = form_data.get('type', '1')
                if form_type == '1':
                    message_text = form_data.get('selected_text', '')
                elif form_type == '2':
                    inputs = []
                    for key, value in form_data.get('form_data', {}).items():
                        inputs.append(f"{key}: {value}")
                    message_text = "; ".join(inputs)

                if message_text:
                    all_messages.append(message_text)
                    submitted_forms.append(form_id)

        # 合并所有消息
        combined_message = " | ".join(all_messages)

        print(f"? 批量提交 {len(submitted_forms)} 个全局表单")
        print(f"   剩余表单: {len(form_manager.get_all_forms())}")

        return jsonify({
            "status": "success",
            "message": f"已提交 {len(submitted_forms)} 个表单",
            "submitted_forms": submitted_forms,
            "combined_message": combined_message,
            "count": len(submitted_forms),
            "remaining_forms": len(form_manager.get_all_forms())
        })

    except Exception as e:
        print(f"? 批量提交失败: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/clear_forms', methods=['POST'])
def clear_forms():
    """清空所有表单"""
    try:
        count = form_manager.clear_all_forms()
        
        return jsonify({
            "status": "success",
            "message": f"已清空 {count} 个表单",
            "count": count
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/external/options', methods=['GET'])
def receive_external_options():
    """接收外部选项请求 - 全局版本"""
    print(f"\n? [{datetime.now().strftime('%H:%M:%S')}] 收到全局表单请求")
    
    # 从查询参数获取数据
    request_type = request.args.get('type', '1')
    message = request.args.get('message', '')
    question = request.args.get('question', '')
    options_str = request.args.get('options', '[]')
    update_data_str = request.args.get('update_data', '{}')

    try:
        options = json.loads(options_str)
        update_data = json.loads(update_data_str)
    except json.JSONDecodeError as e:
        print(f"    JSON解析错误: {e}")
        options = []
        update_data = {}

    print(f"   类型: {request_type}")
    print(f"   问题: {question}")
    print(f"   选项数量: {len(options)}")
    print(f"   来源IP: {request.remote_addr}")

    # 构建表单数据
    form_data = {
        "type": request_type,
        "message": message[:500],
        "question": question[:200],
        "options": options[:10],
        "update_data": update_data,
        "timestamp": datetime.now().isoformat(),
        "status": "pending",
        "source_ip": request.remote_addr,
        "is_global": True  # 标识这是全局表单
    }

    # 添加到全局表单管理器
    form_id = form_manager.add_form(form_data)
    
    # 获取当前表单数量
    current_count = len(form_manager.get_all_forms())
    
    return jsonify({
        "status": "success",
        "message": "全局表单请求已接收",
        "type": request_type,
        "form_id": form_id,
        "form_count": current_count,
        "is_global": True,
        "notice": "此表单将显示在所有连接的设备上"
    })

# ========== 其他路由保持不变 ==========
# 包括：/, /post, /reset, /api/health 等路由保持原样

# 健康检查端点也更新
@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查"""
    forms = form_manager.get_all_forms()
    
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "chatbot-global",
        "version": "3.0",
        "global_forms": len(forms),
        "is_global": True
    })

if __name__ == '__main__':
    print("=" * 50)
    print("? AUKS会议预约助手 - 全局弹窗版 v3.0")
    print(f"? 启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    # 显示全局表单特性
    print("? 特性: 全局表单系统")
    print("   ? 所有设备共享同一表单池")
    print("   ? 任何设备提交表单都会影响所有设备")
    print("   ? 适合团队协作场景")
    print("=" * 50)

    try:
        app.run(
            host="0.0.0.0",
            debug=True,
            port=5008,
            threaded=True
        )
    except KeyboardInterrupt:
        print("\n? 正在关闭应用...")
    except Exception as e:
        print(f"? 启动失败: {e}")
