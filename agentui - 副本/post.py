import requests
import json

base_url = "http://192.168.10.101:5008/external/options"  # 注意修改为正确的端点

params1 = {
    "type": "0",
    "update_data": json.dumps({
        "date": "abcd1",
        "time": "17:30-19:30",
        "topic": "1",
        "attendees": "2"
    })

}

params2 = {
    "type": "1",
    "message": "请选择服务类型",
    "question": "您需要什么服务?",
    "options": json.dumps([
        {"value": "reminder", "text": "1讲个笑话"},
        {"value": "reminder", "text": "写篇小作文"},
        {"value": "reminder", "text": "随便说点什么"},
        {"value": "reminder", "text": "摸鱼小技巧"}
    ])
}

params3 = {
    "type": "1",
    "message": "请选择服务类型",
    "question": "您需要什么服务?",
    "options": json.dumps([
        {"value": "reminder", "text": "2讲个笑话"},
        {"value": "reminder", "text": "写篇小作文"},
        {"value": "reminder", "text": "随便说点什么"},
        {"value": "reminder", "text": "摸鱼小技巧"}
    ])
}

try:
    # response = requests.get(base_url, params=params1)
    response = requests.get(base_url, params=params2)
    response = requests.get(base_url, params=params3)
    print(f"状态码: {response.status_code}")

    if response.status_code == 200:
        try:
            print("响应内容:")
            print(json.dumps(response.json(), indent=2, ensure_ascii=False))
        except ValueError:
            print("响应不是有效的JSON:")
            print(response.text)
    else:
        print(f"请求失败，状态码: {response.status_code}")
        print("响应内容:")
        print(response.text)

except requests.exceptions.RequestException as e:
    print(f"请求发生异常: {str(e)}")
