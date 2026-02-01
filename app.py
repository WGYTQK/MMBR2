from flask import Flask, render_template, request, jsonify
from datetime import datetime
import os
import requests
import json
import html
import re

app = Flask(__name__, static_folder='static', template_folder='templates')

# 确保必要的文件夹存在
os.makedirs('static/images', exist_ok=True)

# 全局消息历史（简单存储）
messages = []


# ========== 辅助函数 ==========
def sanitize_input(text):
    """清理用户输入，防止XSS攻击"""
    if not text:
        return ""
    return html.escape(text.strip())


def parse_response_content(text):
    """
    解析AI回复内容，提取结构化信息
    规则：
    1. 提取 [标识]:{值} 格式的内容
    2. 非output关键字的值更新到左侧表单
    3. output关键字的值作为输出值
    4. 没有标识的默认作为output值
    """
    print(f"🔍 开始解析响应内容，原始文本: {text[:200]}...")

    # 定义所有可能的标识符
    all_identifiers = ['time', 'topic', 'participants', 'location', 'type', 'output']

    # 存储提取结果
    extracted_info = {}
    remaining_text = text

    # 1. 首先提取所有 [标识]:{值} 格式的内容
    for identifier in all_identifiers:
        pattern = r'\[' + identifier + r'\]:\{([^}]+)\}'
        matches = re.findall(pattern, text)

        if matches:
            # 只取第一个匹配的值
            value = matches[0].strip()
            if value:  # 只存储非空值
                extracted_info[identifier] = value
                print(f"✅ 提取到 [{identifier}]:{{{value}}}")

                # 从剩余文本中移除这个匹配项
                remaining_text = re.sub(pattern, '', remaining_text)

    # 2. 处理剩余文本（没有标识的部分）
    remaining_text = re.sub(r'\s+', ' ', remaining_text).strip()

    # 3. 如果没有output标识但有剩余文本，将其作为output
    if remaining_text and 'output' not in extracted_info:
        extracted_info['output'] = remaining_text
        print(f"📄 将剩余文本设为output: {remaining_text[:100]}...")
    elif not remaining_text and 'output' not in extracted_info:
        # 如果既没有output标识也没有剩余文本，output设为空
        extracted_info['output'] = ""

    print(f"📋 解析结果: {extracted_info}")
    return extracted_info


def create_api_payload(user_input):
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
            }
        ],
        "query": user_input,
        "conversationId": "",
        "files": [
            {
                "fileType": "document",
                "fileId": "96e23bc3-7a1d-466b-a223-b325eeef164a"
            }
        ]
    }


# ========== 路由 ==========
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/post', methods=['POST'])
def post_message():
    """处理用户消息 - 简化版，非流式"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                "status": "error",
                "message": "无效的请求数据"
            }), 400

        user_input = data.get("message", "").strip()

        if not user_input:
            return jsonify({
                "status": "error",
                "message": "消息不能为空"
            }), 400

        user_input = sanitize_input(user_input)
        print(f"📤 用户消息: {user_input[:300]}...")

        # 发送到AI服务
        payload = create_api_payload(user_input)

        try:
            # 这里使用您的真实API地址（请取消注释并修改）
            # response = requests.post(
            #     "https://auodigital.corpnet.auo.com:8080/ex/api/dfApp/run",
            #     json=payload,
            #     headers={
            #         "Authorization": "K2405124",
            #         "Content-Type": "application/json"
            #     },
            #     verify=False,
            #     timeout=30
            # )

            # 测试时使用模拟响应
            print(f"📤 发送请求到API: {payload}")
            response = requests.post(
                "http://127.0.0.1:5000/post",
                json=payload,
                headers={
                    "Authorization": "K2405124",
                    "Content-Type": "application/json"
                },
                timeout=30
            )

            response.raise_for_status()

            # 尝试解析响应为JSON，如果不是JSON则作为字符串处理
            ai_response = ""
            try:
                # 先尝试解析为JSON
                response_json = response.json()
                print(f"📥 API返回JSON: {response_json}")

                # 根据API的实际响应结构提取内容
                if isinstance(response_json, dict):
                    # 如果是字典，尝试获取常见的字段
                    if "answer" in response_json:
                        ai_response = response_json["answer"]
                    elif "response" in response_json:
                        ai_response = response_json["response"]
                    elif "data" in response_json:
                        ai_response = response_json["data"]
                    else:
                        # 转换为字符串
                        ai_response = str(response_json)
                elif isinstance(response_json, str):
                    ai_response = response_json
                else:
                    ai_response = str(response_json)

            except (json.JSONDecodeError, ValueError):
                # 如果不是JSON，直接使用文本内容
                print("📥 API返回文本（非JSON格式）")
                ai_response = response.text

            print(f"🤖 AI原始响应: {ai_response[:500]}...")

        except requests.exceptions.Timeout:
            return jsonify({
                "status": "error",
                "message": "请求超时，请稍后重试"
            }), 504
        except requests.exceptions.RequestException as e:
            print(f"❌ API请求异常: {str(e)}")
            return jsonify({
                "status": "error",
                "message": f"API请求失败: {str(e)}"
            }), 502
        except Exception as e:
            print(f"❌ 处理API响应时出错: {str(e)}")
            return jsonify({
                "status": "error",
                "message": f"处理API响应失败: {str(e)}"
            }), 500

        # 解析AI响应内容
        parsed_info = parse_response_content(ai_response)

        # 构建返回结果
        result = {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "answer": parsed_info.get('output', ai_response),  # 如果有output就用output，否则用整个响应
            "updates": {}
        }

        # 提取非output的关键字用于更新表单
        for key in ['time', 'topic', 'participants', 'location', 'type']:
            if key in parsed_info and parsed_info[key]:
                result["updates"][key] = parsed_info[key]

        # 保存消息历史
        timestamp = datetime.now().isoformat()
        new_message = {
            "id": len(messages) + 1,
            "user": user_input,
            "ai": result["answer"],
            "timestamp": timestamp,
            "parsed_info": parsed_info
        }
        messages.append(new_message)

        # 只保留最近的50条消息
        if len(messages) > 50:
            messages.pop(0)

        print(f"📤 返回结果: answer={result['answer'][:100]}..., updates={result['updates']}")
        return jsonify(result)

    except Exception as e:
        error_msg = f"请求处理失败: {str(e)}"
        print(f"❌ 处理消息时出错: {error_msg}")

        return jsonify({
            "status": "error",
            "message": error_msg,
            "timestamp": datetime.now().isoformat()
        }), 500


@app.route('/reset', methods=['POST'])
def reset_conversation():
    """重置会话"""
    global messages
    messages.clear()

    print("🔄 重置会话")

    return jsonify({
        "status": "success",
        "message": "会话已重置",
        "timestamp": datetime.now().isoformat()
    })


@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "AUKS会议预约助手",
        "version": "2.0",
        "message_count": len(messages)
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
    print("🤖 AUKS会议预约助手 v2.0 (简化版)")
    print(f"⏰ 启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    print("📋 优化特性:")
    print("  • 简化输出逻辑，非流式处理")
    print("  • 自动解析 [标识]:{值} 格式")
    print("  • 非output关键字值更新到左侧表单")
    print("  • output关键字值作为输出值")
    print("  • 没有标识的默认作为output值")
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
        print("✅ 应用已关闭")
    except Exception as e:
        print(f"❌ 启动失败: {e}")