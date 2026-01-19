#@mcp.tool()
def process_ftp_file(ftp_host="10.12.128.102", ftp_user="PTMS_L6K", ftp_pass="Auks$1234",
                     file_path=None, filename=None, content=None, operation=None):
    """
    多功能FTP文件处理工具（完整版）
    支持：XML/JSON/TXT等多种格式，自动处理BOM，完善错误处理

    参数:
        ftp_host: FTP服务器地址
        ftp_user: FTP用户名
        ftp_pass: FTP密码
        file_path: FTP文件路径
        filename: 目标文件名
        content: 要操作的内容
        operation: 操作类型（append/update/read/search_content/search_files）
    """
    import os
    import re
    import json
    import chardet
    from ftplib import FTP
    from xml.etree import ElementTree as ET
    from io import StringIO, BytesIO

    # --- 类型自动检测 ---
    def detect_file_type(filename, raw_content):
        """通过后缀和内容自动判断文件类型"""
        # 优先通过后缀判断
        ext = os.path.splitext(filename)[1].lower()
        if ext == '.json':
            return 'json'
        elif ext == '.xml':
            return 'xml'
        elif ext in ('.txt', '.log', '.ini', '.conf'):
            return 'text'

        # 无法通过后缀判断时，分析内容
        try:
            json.loads(raw_content)
            return 'json'
        except:
            try:
                ET.fromstring(raw_content)
                return 'xml'
            except:
                return 'text'

    # --- 自动解码 ---
    def auto_decode(byte_content):
        """自动检测编码并解码"""
        # 先尝试UTF-8 BOM
        if byte_content.startswith(b'\xef\xbb\xbf'):
            return byte_content.decode('utf-8-sig')

        # 使用chardet检测
        detect_result = chardet.detect(byte_content)
        try:
            return byte_content.decode(detect_result['encoding'])
        except:
            # 最终回退方案
            return byte_content.decode('utf-8', errors='replace')

    # --- 内容加载 ---
    def load_content(filename, raw_content):
        """根据类型加载结构化内容"""
        file_type = detect_file_type(filename, raw_content)

        if file_type == 'json':
            return json.loads(raw_content)
        elif file_type == 'xml':
            try:
                return ET.fromstring(raw_content)
            except ET.ParseError:
                # 移除可能的BOM
                if raw_content.startswith('\ufeff'):
                    raw_content = raw_content[1:]
                return ET.fromstring(raw_content)
        return raw_content

    # --- 内容保存 ---
    def save_content(content, file_type):
        """根据类型序列化内容"""
        if file_type == 'json':
            return json.dumps(content, ensure_ascii=False, indent=2)
        elif file_type == 'xml':
            if isinstance(content, ET.Element):
                return ET.tostring(content, encoding='unicode')
            return str(content)
        return str(content)

    # --- 主逻辑 ---
    try:
        # 参数验证
        if not operation or operation not in ['append', 'update', 'read', 'search', 'list']:
            return {'error': 'INVALID_OPERATION', 'message': '操作类型无效'}

        if operation != 'list' and not filename:
            return {'error': 'MISSING_FILENAME', 'message': '需要指定文件名'}

        # 连接FTP
        ftp = FTP(ftp_host, timeout=30)
        ftp.login(ftp_user, ftp_pass)

        # 切换目录
        if file_path:
            ftp.cwd(file_path)

        # 处理不同操作
        if operation == 'list':
            files = []
            ftp.retrlines('LIST', lambda x: files.append(x.split()[-1]))
            return {'status': 'success', 'files': files}

        # 下载文件内容
        byte_content = BytesIO()
        ftp.retrbinary(f'RETR {filename}', byte_content.write)
        byte_content = byte_content.getvalue()
        raw_content = auto_decode(byte_content)
        file_type = detect_file_type(filename, raw_content)
        file_content = load_content(filename, raw_content)

        # 执行操作
        result = None
        if operation == 'read':
            result = {'status': 'success', 'content': file_content, 'type': file_type}

        elif operation == 'append':
            new_content = load_content(filename, str(content))
            if file_type == 'json':
                if isinstance(file_content, dict) and isinstance(new_content, dict):
                    file_content.update(new_content)
                elif isinstance(file_content, list):
                    file_content.append(new_content)
            elif file_type == 'xml' and isinstance(new_content, ET.Element):
                file_content.append(new_content)
            else:
                file_content += '\n' + str(content)

            # 上传更新
            updated_content = save_content(file_content, file_type)
            ftp.storbinary(f'STOR {filename}', BytesIO(updated_content.encode('utf-8')))
            result = {'status': 'success'}

        elif operation == 'update':
            new_content = load_content(filename, str(content))
            updated_content = save_content(new_content, file_type)
            ftp.storbinary(f'STOR {filename}', BytesIO(updated_content.encode('utf-8')))
            result = {'status': 'success'}

        elif operation == 'search':
            matches = []
            search_str = str(content).lower()

            if file_type == 'json':
                def _search(data, path=""):
                    if isinstance(data, dict):
                        for k, v in data.items():
                            _search(v, f"{path}.{k}" if path else k)
                    elif isinstance(data, list):
                        for i, v in enumerate(data):
                            _search(v, f"{path}[{i}]")
                    elif search_str in str(data).lower():
                        matches.append({'path': path, 'value': data})

                _search(file_content)

            elif file_type == 'xml':
                def _search(elem, path=""):
                    path = f"{path}/{elem.tag}" if path else elem.tag
                    if elem.text and search_str in elem.text.lower():
                        matches.append({'path': path, 'text': elem.text})
                    for k, v in elem.attrib.items():
                        if search_str in v.lower():
                            matches.append({'path': f"{path}@{k}", 'value': v})
                    for child in elem:
                        _search(child, path)

                _search(file_content)

            else:
                for i, line in enumerate(raw_content.split('\n')):
                    if search_str in line.lower():
                        matches.append({'line': i + 1, 'content': line})

            result = {'status': 'success', 'matches': matches}

        return result or {'status': 'success'}

    except Exception as e:
        return {'error': 'PROCESS_ERROR', 'message': str(e)}

    finally:
        if 'ftp' in locals():
            ftp.quit()

if __name__ == '__main__':
    # 读取JSON文件
    Ftp_host = "10.12.14.221"
    Ftp_user = "java"
    Ftp_pass = "cimbc"

    result = process_ftp_file(
        ftp_host = Ftp_host,
        ftp_user = Ftp_user,
        ftp_pass= Ftp_pass,
        file_path="/test/1/",
        filename="224.json",
        content="****************************",
        operation="append"
    )

    # 更新XML文件
    new_content = """
    <config>
        <server ip="192.168.1.100" port="8080"/>
    </config>
    """
    result = process_ftp_file(
        file_path="/server/config",
        filename="config.xml",
        content=new_content,
        operation="update"
    )

    # 在JSON文件中搜索
    result = process_ftp_file(
        file_path="/logs",
        filename="app_log.json",
        content="error",
        operation="search_content"
    )

    # 追加文本到日志文件
    result = process_ftp_file(
        file_path="/logs",
        filename="system.log",
        content="2023-11-15 14:30:00 [INFO] System started",
        operation="append"
    )
