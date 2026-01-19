#@mcp.tool()
def process_ftp_file(ftp_host="10.12.128.102", ftp_user="PTMS_L6K", ftp_pass="Auks$1234",
                     file_path=None, filename=None, content=None, operation=None):
    """
    多功能FTP文件处理工具（优化版）
    修复bug并扩展功能，支持：XML/JSON/TXT等多种格式，自动处理BOM，完善错误处理
    
    参数:
        ftp_host: FTP服务器地址
        ftp_user: FTP用户名
        ftp_pass: FTP密码
        file_path: FTP文件路径
        filename: 目标文件名
        content: 要操作的内容
        operation: 操作类型（append/update/read/search/search_files/delete/list）
    """
    import os
    import re
    import json
    import chardet
    from ftplib import FTP
    from xml.etree import ElementTree as ET
    from io import StringIO, BytesIO
    import tempfile
    import warnings
    
    # 忽略chardet警告
    warnings.filterwarnings('ignore', module='chardet')

    # --- 改进的类型检测 ---
    def detect_file_type(filename, raw_content):
        """通过后缀和内容自动判断文件类型"""
        if not filename:
            return 'unknown'
            
        ext = os.path.splitext(filename)[1].lower()
        
        # 通过后缀判断
        type_map = {
            '.json': 'json',
            '.xml': 'xml',
            '.txt': 'text',
            '.log': 'text',
            '.ini': 'text',
            '.conf': 'text',
            '.csv': 'text',
            '.yaml': 'text',
            '.yml': 'text',
            '.html': 'text',
            '.htm': 'text'
        }
        
        if ext in type_map:
            return type_map[ext]
            
        # 无法通过后缀判断时，分析内容
        if not raw_content or len(raw_content.strip()) == 0:
            return 'text'  # 空文件视为文本
            
        # 尝试解析JSON
        try:
            json.loads(raw_content)
            return 'json'
        except:
            pass
            
        # 尝试解析XML
        try:
            # 移除BOM和空白字符
            content_clean = raw_content.strip()
            if content_clean.startswith('\ufeff'):
                content_clean = content_clean[1:]
            if content_clean.startswith('<?xml') or content_clean.startswith('<'):
                ET.fromstring(content_clean)
                return 'xml'
        except:
            pass
            
        # 默认为文本
        return 'text'

    # --- 改进的自动解码 ---
    def auto_decode(byte_content):
        """自动检测编码并解码，处理BOM"""
        if not byte_content:
            return ""
            
        # 先尝试UTF-8 BOM
        if byte_content.startswith(b'\xef\xbb\xbf'):
            try:
                return byte_content.decode('utf-8-sig')
            except:
                pass
        # 尝试UTF-16 BOM
        elif byte_content.startswith(b'\xff\xfe'):
            try:
                return byte_content.decode('utf-16')
            except:
                pass
        elif byte_content.startswith(b'\xfe\xff'):
            try:
                return byte_content.decode('utf-16-be')
            except:
                pass
                
        # 使用chardet检测
        try:
            detect_result = chardet.detect(byte_content)
            if detect_result['confidence'] > 0.7 and detect_result['encoding']:
                return byte_content.decode(detect_result['encoding'], errors='ignore')
        except:
            pass
            
        # 最终尝试UTF-8和回退方案
        for encoding in ['utf-8', 'latin-1', 'cp1252', 'gbk']:
            try:
                return byte_content.decode(encoding, errors='ignore')
            except:
                continue
                
        # 如果都失败，使用替换错误处理
        return byte_content.decode('utf-8', errors='replace')

    # --- 改进的内容加载 ---
    def load_content(filename, raw_content, file_type=None):
        """根据类型加载结构化内容"""
        if not file_type:
            file_type = detect_file_type(filename, raw_content)
            
        if not raw_content:
            if file_type == 'json':
                return {}
            elif file_type == 'xml':
                return ET.Element('root')
            else:
                return ""
                
        try:
            if file_type == 'json':
                # 移除可能的BOM
                if raw_content.startswith('\ufeff'):
                    raw_content = raw_content[1:]
                return json.loads(raw_content)
            elif file_type == 'xml':
                # 移除BOM
                if raw_content.startswith('\ufeff'):
                    raw_content = raw_content[1:]
                # 如果内容没有根标签，添加一个临时的
                if not raw_content.strip().startswith('<?xml') and not raw_content.strip().startswith('<'):
                    raw_content = f'<root>{raw_content}</root>'
                return ET.fromstring(raw_content)
            else:
                return raw_content
        except Exception as e:
            # 如果解析失败，返回原始内容
            return raw_content

    # --- 改进的内容保存 ---
    def save_content(content, file_type, original_filename=None):
        """根据类型序列化内容"""
        try:
            if file_type == 'json':
                if isinstance(content, (dict, list)):
                    return json.dumps(content, ensure_ascii=False, indent=2)
                else:
                    # 如果不是JSON结构，转换为字符串
                    return str(content)
            elif file_type == 'xml':
                if isinstance(content, ET.Element):
                    # 美化XML输出
                    try:
                        from xml.dom import minidom
                        rough_string = ET.tostring(content, 'unicode')
                        reparsed = minidom.parseString(rough_string)
                        return reparsed.toprettyxml(indent="  ")
                    except:
                        return ET.tostring(content, encoding='unicode', method='xml')
                else:
                    return str(content)
            else:
                return str(content)
        except Exception as e:
            # 保存失败时返回原始内容
            return str(content)

    # --- 新增功能：文件检查 ---
    def check_file_exists(ftp, filename):
        """检查文件是否存在"""
        try:
            files = []
            ftp.retrlines('LIST', lambda x: files.append(x.split()[-1]))
            return filename in files
        except:
            return False

    # --- 新增功能：获取文件大小 ---
    def get_file_size(ftp, filename):
        """获取文件大小"""
        try:
            ftp.sendcmd(f"SIZE {filename}")
            response = ftp.getmultiline().split()[1]
            return int(response)
        except:
            return 0

    # --- 主逻辑 ---
    try:
        # 参数验证
        if not operation:
            return {'error': 'MISSING_OPERATION', 'message': '请指定操作类型'}
            
        valid_operations = ['append', 'update', 'read', 'search', 'list', 'delete', 'search_files']
        if operation not in valid_operations:
            return {'error': 'INVALID_OPERATION', 
                   'message': f'操作类型无效。支持的操作: {", ".join(valid_operations)}'}
        
        # 连接FTP（增加重试机制）
        ftp = None
        try:
            ftp = FTP(ftp_host, timeout=30)
            ftp.login(ftp_user, ftp_pass)
            ftp.set_pasv(True)  # 使用被动模式
        except Exception as e:
            return {'error': 'FTP_CONNECTION_FAILED', 'message': f'FTP连接失败: {str(e)}'}
        
        # 切换目录（如果指定）
        if file_path:
            try:
                ftp.cwd(file_path)
            except Exception as e:
                return {'error': 'DIRECTORY_ERROR', 'message': f'无法切换到目录 {file_path}: {str(e)}'}

        # 处理list操作
        if operation == 'list' or operation == 'search_files':
            try:
                files = []
                dirs = []
                
                def parse_list_line(line):
                    """解析LIST命令的输出"""
                    parts = line.split()
                    if len(parts) < 9:
                        return None
                    
                    # 检查是否为目录
                    is_dir = parts[0].startswith('d')
                    name = ' '.join(parts[8:])
                    
                    if is_dir:
                        dirs.append(name)
                    else:
                        files.append(name)
                
                ftp.retrlines('LIST', parse_list_line)
                
                # 如果是文件搜索
                if operation == 'search_files' and content:
                    search_pattern = str(content).lower()
                    files = [f for f in files if search_pattern in f.lower()]
                    dirs = [d for d in dirs if search_pattern in d.lower()]
                
                return {
                    'status': 'success',
                    'files': files,
                    'directories': dirs,
                    'total_files': len(files),
                    'total_directories': len(dirs)
                }
            except Exception as e:
                return {'error': 'LIST_ERROR', 'message': f'列出文件失败: {str(e)}'}

        # 验证filename（除list/search_files操作外都需要）
        if operation not in ['list', 'search_files']:
            if not filename:
                return {'error': 'MISSING_FILENAME', 'message': '需要指定文件名'}
            
            # 检查文件是否存在（对于读取、追加、搜索操作）
            if operation in ['read', 'append', 'search', 'update']:
                if not check_file_exists(ftp, filename):
                    return {'error': 'FILE_NOT_FOUND', 'message': f'文件 {filename} 不存在'}

        # 处理delete操作
        if operation == 'delete':
            try:
                ftp.delete(filename)
                return {'status': 'success', 'message': f'文件 {filename} 已删除'}
            except Exception as e:
                return {'error': 'DELETE_ERROR', 'message': f'删除文件失败: {str(e)}'}

        # 对于需要文件内容的操作，下载文件
        byte_content = b""
        raw_content = ""
        file_type = "unknown"
        file_content = None
        
        if operation in ['read', 'append', 'update', 'search']:
            try:
                # 获取文件大小
                file_size = get_file_size(ftp, filename)
                
                # 下载文件内容
                byte_content = BytesIO()
                ftp.retrbinary(f'RETR {filename}', byte_content.write)
                byte_content = byte_content.getvalue()
                
                if len(byte_content) != file_size and file_size > 0:
                    return {'error': 'DOWNLOAD_ERROR', 'message': '文件下载不完整'}
                    
                raw_content = auto_decode(byte_content)
                file_type = detect_file_type(filename, raw_content)
                file_content = load_content(filename, raw_content, file_type)
                
            except Exception as e:
                return {'error': 'DOWNLOAD_ERROR', 'message': f'下载文件失败: {str(e)}'}

        # 执行具体操作
        result = None
        
        if operation == 'read':
            result = {
                'status': 'success',
                'filename': filename,
                'type': file_type,
                'size': len(byte_content),
                'content': file_content,
                'raw_content': raw_content if file_type == 'text' else None
            }

        elif operation == 'append':
            if not content:
                return {'error': 'MISSING_CONTENT', 'message': '追加操作需要内容参数'}
            
            try:
                new_content_str = str(content)
                new_content_parsed = load_content(filename, new_content_str, file_type)
                
                # 根据文件类型处理追加逻辑
                if file_type == 'json':
                    if isinstance(file_content, dict) and isinstance(new_content_parsed, dict):
                        # 合并字典
                        file_content.update(new_content_parsed)
                    elif isinstance(file_content, list):
                        # 追加到列表
                        file_content.append(new_content_parsed)
                    else:
                        # 其他情况，转换为字符串追加
                        file_content = str(file_content) + '\n' + new_content_str
                        
                elif file_type == 'xml':
                    if isinstance(new_content_parsed, ET.Element):
                        file_content.append(new_content_parsed)
                    else:
                        # 如果是字符串，创建一个新的文本元素
                        new_elem = ET.Element('addition')
                        new_elem.text = new_content_str
                        file_content.append(new_elem)
                else:
                    # 文本文件直接追加
                    file_content = raw_content + '\n' + new_content_str

                # 上传更新后的内容
                updated_content = save_content(file_content, file_type, filename)
                ftp.storbinary(f'STOR {filename}', BytesIO(updated_content.encode('utf-8')))
                
                result = {'status': 'success', 'message': f'已成功追加内容到 {filename}'}
                
            except Exception as e:
                return {'error': 'APPEND_ERROR', 'message': f'追加内容失败: {str(e)}'}

        elif operation == 'update':
            if not content:
                return {'error': 'MISSING_CONTENT', 'message': '更新操作需要内容参数'}
            
            try:
                new_content_str = str(content)
                new_content_parsed = load_content(filename, new_content_str, file_type)
                
                # 上传新内容
                updated_content = save_content(new_content_parsed, file_type, filename)
                ftp.storbinary(f'STOR {filename}', BytesIO(updated_content.encode('utf-8')))
                
                result = {'status': 'success', 'message': f'已成功更新 {filename}'}
                
            except Exception as e:
                return {'error': 'UPDATE_ERROR', 'message': f'更新文件失败: {str(e)}'}

        elif operation == 'search':
            if not content:
                return {'error': 'MISSING_SEARCH_TERM', 'message': '搜索操作需要搜索词'}
            
            try:
                matches = []
                search_str = str(content).lower()
                
                if file_type == 'json':
                    def _search_json(data, path=""):
                        if isinstance(data, dict):
                            for k, v in data.items():
                                new_path = f"{path}.{k}" if path else k
                                if search_str in str(k).lower():
                                    matches.append({
                                        'type': 'key',
                                        'path': new_path,
                                        'key': k,
                                        'value': v
                                    })
                                _search_json(v, new_path)
                        elif isinstance(data, list):
                            for i, v in enumerate(data):
                                new_path = f"{path}[{i}]"
                                _search_json(v, new_path)
                        elif isinstance(data, (str, int, float, bool)) and search_str in str(data).lower():
                            matches.append({
                                'type': 'value',
                                'path': path,
                                'value': data
                            })
                    
                    _search_json(file_content)
                    
                elif file_type == 'xml':
                    def _search_xml(elem, path=""):
                        current_path = f"{path}/{elem.tag}" if path else elem.tag
                        
                        # 搜索元素文本
                        if elem.text and search_str in elem.text.lower():
                            matches.append({
                                'type': 'text',
                                'path': current_path,
                                'text': elem.text.strip()
                            })
                        
                        # 搜索属性
                        for attr_name, attr_value in elem.attrib.items():
                            if search_str in attr_value.lower():
                                matches.append({
                                    'type': 'attribute',
                                    'path': f"{current_path}@{attr_name}",
                                    'attribute': attr_name,
                                    'value': attr_value
                                })
                            if search_str in attr_name.lower():
                                matches.append({
                                    'type': 'attribute_name',
                                    'path': f"{current_path}@{attr_name}",
                                    'attribute': attr_name,
                                    'value': attr_value
                                })
                        
                        # 递归搜索子元素
                        for child in elem:
                            _search_xml(child, current_path)
                    
                    _search_xml(file_content)
                    
                else:
                    # 文本文件搜索
                    lines = raw_content.split('\n')
                    for i, line in enumerate(lines):
                        if search_str in line.lower():
                            matches.append({
                                'type': 'line',
                                'line_number': i + 1,
                                'content': line.strip(),
                                'start_index': line.lower().find(search_str) + 1
                            })
                
                result = {
                    'status': 'success',
                    'filename': filename,
                    'search_term': search_str,
                    'matches_found': len(matches),
                    'matches': matches,
                    'file_type': file_type
                }
                
            except Exception as e:
                return {'error': 'SEARCH_ERROR', 'message': f'搜索失败: {str(e)}'}

        return result or {'status': 'success', 'message': '操作完成'}

    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        return {
            'error': 'UNEXPECTED_ERROR',
            'message': f'处理过程中发生错误: {str(e)}',
            'detail': error_detail
        }

    finally:
        if 'ftp' in locals() and ftp:
            try:
                ftp.quit()
            except:
                try:
                    ftp.close()
                except:
                    pass


if __name__ == '__main__':
    # 测试各种操作
    test_config = {
        'ftp_host': "10.12.14.221",
        'ftp_user': "java",
        'ftp_pass': "cimbc"
    }
    
    # 1. 列出文件
    print("1. 列出文件:")
    result = process_ftp_file(
        ftp_host=test_config['ftp_host'],
        ftp_user=test_config['ftp_user'],
        ftp_pass=test_config['ftp_pass'],
        file_path="/test/1/",
        operation="list"
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    # 2. 读取JSON文件
    print("\n2. 读取JSON文件:")
    result = process_ftp_file(
        ftp_host=test_config['ftp_host'],
        ftp_user=test_config['ftp_user'],
        ftp_pass=test_config['ftp_pass'],
        file_path="/test/1/",
        filename="224.json",
        operation="read"
    )
    print(f"文件内容类型: {result.get('type')}")
    
    # 3. 追加内容到文件
    print("\n3. 追加内容到文件:")
    result = process_ftp_file(
        ftp_host=test_config['ftp_host'],
        ftp_user=test_config['ftp_user'],
        ftp_pass=test_config['ftp_host'],
        file_path="/test/1/",
        filename="224.json",
        content={"timestamp": "2024-01-19", "status": "updated"},
        operation="append"
    )
    print(result)
    
    # 4. 搜索文件内容
    print("\n4. 搜索文件内容:")
    result = process_ftp_file(
        ftp_host=test_config['ftp_host'],
        ftp_user=test_config['ftp_user'],
        ftp_pass=test_config['ftp_pass'],
        file_path="/test/1/",
        filename="224.json",
        content="status",
        operation="search"
    )
    print(f"找到 {result.get('matches_found', 0)} 个匹配项")
    
    # 5. 搜索文件名
    print("\n5. 搜索文件名:")
    result = process_ftp_file(
        ftp_host=test_config['ftp_host'],
        ftp_user=test_config['ftp_user'],
        ftp_pass=test_config['ftp_pass'],
        file_path="/test/1/",
        content=".json",
        operation="search_files"
    )
    print(f"找到 {result.get('total_files', 0)} 个文件")
