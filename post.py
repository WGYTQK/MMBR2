from flask import Flask, request
import json
import time

app = Flask(__name__)


@app.route('/post', methods=['POST'])
def handle_post():
    """监听POST请求并返回流式响应"""
    print("\n" + "=" * 60)
    print("📨 收到POST请求")
    print("=" * 60)

    # 打印收到的数据
    try:
        data = request.get_json()
        print(f"📦 JSON数据:")
        print(json.dumps(data, indent=2, ensure_ascii=False))
    except:
        print("📦 原始数据:")
        print(request.get_data(as_text=True))

    print("=" * 60)
    print("=" * 60)

    from flask import Response
    return Response("[time]:{2020}569[topic]:{test}")


if __name__ == '__main__':
    print("🚀 监听程序启动: http://127.0.0.1:5000")
    print("📮 监听端点: POST /post")
    app.run(host='0.0.0.0', port=5000, debug=False)