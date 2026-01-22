import os
import re
import json
import chardet
import configparser
from ftplib import FTP
from xml.etree import ElementTree as ET
from io import StringIO, BytesIO
import tempfile
import warnings
from typing import Dict, List, Any, Optional, Union, Tuple

# 忽略chardet警告
warnings.filterwarnings('ignore', module='chardet')

# 全局打印函数，用于监测执行过程
def debug_print(*args, **kwargs):
    """打印调试信息"""
    print("[DEBUG]", *args, **kwargs)

#@mcp.tool()
def process_ftp_file(ftp_host="10.12.128.102", ftp_user="PTMS_L6K", ftp_pass="Auks$1234",
                     file_path=None, filename=None, content=None, operation=None):
    """
    多功能FTP文件处理工具（优化版）
    修复bug并扩展功能，支持：XML/JSON/TXT/INI等多种格式，自动处理BOM，完善错误处理
    
    新增功能：
    1. INI格式支持：解析content以&ini&为分隔符，追加至多个栏位
    2. UPDATE功能增强：先检索再替换，content以&update&作为分隔符
    3. 执行过程监测：增加debug_print输出
    4. INI文件强制使用configparser解析
    
    参数:
        ftp_host: FTP服务器地址
        ftp_user: FTP用户名
        ftp_pass: FTP密码
        file_path: FTP文件路径
        filename: 目标文件名
        content: 要操作的内容
        operation: 操作类型（append/update/read/search/search_files/delete/list）
    """
    
    # --- 改进的类型检测 ---
    def detect_file_type(filename, raw_content):
        """通过后缀和内容自动判断文件类型"""
        if not filename:
            return 'unknown'
            
        ext = os.path.splitext(filename)[1].lower()
        
        # 通过后缀判断 - INI文件优先
        type_map = {
            '.json': 'json',
            '.xml': 'xml',
            '.txt': 'text',
            '.log': 'text',
            '.ini': 'ini',
            '.conf': 'ini',
            '.cfg': 'ini',
            '.properties': 'ini',
            '.csv': 'text',
            '.yaml': 'text',
            '.yml': 'text',
            '.html': 'text',
            '.htm': 'text'
        }
        
        if ext in type_map:
            file_type = type_map[ext]
            debug_print(f"通过文件后缀检测到类型: {file_type}")
            
            # 如果是INI后缀，直接返回ini类型
            if file_type == 'ini':
                debug_print("INI文件后缀，使用INI解析器")
                return 'ini'
                
            return file_type
            
        # 无法通过后缀判断时，分析内容
        if not raw_content or len(raw_content.strip()) == 0:
            debug_print("空文件，默认为文本类型")
            return 'text'  # 空文件视为文本
            
        # 尝试解析JSON
        try:
            json.loads(raw_content)
            debug_print("通过内容检测到JSON类型")
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
                debug_print("通过内容检测到XML类型")
                return 'xml'
        except:
            pass
            
        # 尝试解析INI格式（仅针对非INI后缀的文件）
        try:
            content_clean = raw_content.strip()
            if any(line.strip().startswith('[') and line.strip().endswith(']') for line in content_clean.split('\n')):
                debug_print("通过内容检测到INI类型（包含section）")
                return 'ini'
            elif '=' in content_clean and not content_clean.startswith('{') and not content_clean.startswith('<'):
                debug_print("通过内容检测到INI类型（包含等号）")
                return 'ini'
        except:
            pass
            
        # 默认为文本
        debug_print("默认为文本类型")
        return 'text'

    # --- 改进的自动解码 ---
    def auto_decode(byte_content):
        """自动检测编码并解码，处理BOM"""
        if not byte_content:
            return ""
            
        debug_print(f"解码字节内容，长度: {len(byte_content)}")
        
        # 先尝试UTF-8 BOM
        if byte_content.startswith(b'\xef\xbb\xbf'):
            debug_print("检测到UTF-8 BOM")
            try:
                return byte_content.decode('utf-8-sig')
            except:
                debug_print("UTF-8 BOM解码失败")
                pass
        # 尝试UTF-16 BOM
        elif byte_content.startswith(b'\xff\xfe'):
            debug_print("检测到UTF-16 LE BOM")
            try:
                return byte_content.decode('utf-16')
            except:
                debug_print("UTF-16 LE BOM解码失败")
                pass
        elif byte_content.startswith(b'\xfe\xff'):
            debug_print("检测到UTF-16 BE BOM")
            try:
                return byte_content.decode('utf-16-be')
            except:
                debug_print("UTF-16 BE BOM解码失败")
                pass
                
        # 使用chardet检测
        try:
            detect_result = chardet.detect(byte_content)
            debug_print(f"chardet检测结果: {detect_result}")
            if detect_result['confidence'] > 0.7 and detect_result['encoding']:
                return byte_content.decode(detect_result['encoding'], errors='ignore')
        except Exception as e:
            debug_print(f"chardet检测失败: {e}")
            pass
            
        # 最终尝试UTF-8和回退方案
        for encoding in ['utf-8', 'latin-1', 'cp1252', 'gbk', 'gb2312', 'gb18030']:
            try:
                result = byte_content.decode(encoding, errors='ignore')
                debug_print(f"使用{encoding}编码成功解码")
                return result
            except Exception as e:
                debug_print(f"{encoding}编码解码失败: {e}")
                continue
                
        # 如果都失败，使用替换错误处理
        debug_print("所有解码尝试失败，使用utf-8 with replace")
        return byte_content.decode('utf-8', errors='replace')

    # --- 改进的内容加载 ---
    def load_content(filename, raw_content, file_type=None):
        """根据类型加载结构化内容"""
        if not file_type:
            file_type = detect_file_type(filename, raw_content)
            
        debug_print(f"加载内容，类型: {file_type}, 长度: {len(raw_content) if raw_content else 0}")
            
        if not raw_content:
            if file_type == 'json':
                return {}
            elif file_type == 'xml':
                return ET.Element('root')
            elif file_type == 'ini':
                config = configparser.ConfigParser()
                # 保留大小写
                config.optionxform = str
                return config
            else:
                return ""
                
        try:
            if file_type == 'json':
                # 移除可能的BOM
                if raw_content.startswith('\ufeff'):
                    raw_content = raw_content[1:]
                result = json.loads(raw_content)
                debug_print("JSON解析成功")
                return result
            elif file_type == 'xml':
                # 移除BOM
                if raw_content.startswith('\ufeff'):
                    raw_content = raw_content[1:]
                # 如果内容没有根标签，添加一个临时的
                if not raw_content.strip().startswith('<?xml') and not raw_content.strip().startswith('<'):
                    raw_content = f'<root>{raw_content}</root>'
                result = ET.fromstring(raw_content)
                debug_print("XML解析成功")
                return result
            elif file_type == 'ini':
                config = configparser.ConfigParser()
                # 保留大小写
                config.optionxform = str
                try:
                    config.read_string(raw_content)
                    debug_print("INI解析成功")
                except configparser.MissingSectionHeaderError:
                    # 如果没有section，添加默认section
                    config.read_string(f'[DEFAULT]\n{raw_content}')
                    debug_print("INI解析成功（添加了DEFAULT section）")
                return config
            else:
                # 对于其他后缀（非ini），使用原有逻辑
                debug_print(f"使用文本模式处理 {file_type} 文件")
                return raw_content
        except Exception as e:
            debug_print(f"解析失败，返回原始内容: {e}")
            # 如果解析失败，返回原始内容
            return raw_content

    # --- 改进的内容保存 ---
    def save_content(content, file_type, original_filename=None):
        """根据类型序列化内容"""
        debug_print(f"保存内容，类型: {file_type}")
        try:
            if file_type == 'json':
                if isinstance(content, (dict, list)):
                    result = json.dumps(content, ensure_ascii=False, indent=2)
                    debug_print("JSON序列化成功")
                    return result
                else:
                    # 如果不是JSON结构，转换为字符串
                    debug_print("内容不是JSON结构，转换为字符串")
                    return str(content)
            elif file_type == 'xml':
                if isinstance(content, ET.Element):
                    # 美化XML输出
                    try:
                        from xml.dom import minidom
                        rough_string = ET.tostring(content, 'unicode')
                        reparsed = minidom.parseString(rough_string)
                        result = reparsed.toprettyxml(indent="  ")
                        debug_print("XML美化输出成功")
                        return result
                    except:
                        result = ET.tostring(content, encoding='unicode', method='xml')
                        debug_print("XML普通输出成功")
                        return result
                else:
                    debug_print("内容不是XML元素，转换为字符串")
                    return str(content)
            elif file_type == 'ini':
                if isinstance(content, configparser.ConfigParser):
                    # 使用StringIO保存INI格式
                    string_io = StringIO()
                    content.write(string_io)
                    result = string_io.getvalue()
                    debug_print("INI序列化成功")
                    return result
                else:
                    debug_print("内容不是ConfigParser，转换为字符串")
                    return str(content)
            else:
                debug_print("使用文本模式保存")
                return str(content)
        except Exception as e:
            debug_print(f"保存失败，返回原始内容: {e}")
            # 保存失败时返回原始内容
            return str(content)

    # --- INI格式特殊处理 ---
    def handle_ini_content(filename, file_content, new_content_str, operation_type='append'):
        """处理INI格式的内容追加/更新"""
        debug_print(f"处理INI内容，操作类型: {operation_type}")
        
        if not isinstance(file_content, configparser.ConfigParser):
            debug_print("文件内容不是ConfigParser对象，重新解析")
            file_content = load_content(filename, file_content, 'ini')
        
        # 解析传入的内容，使用&ini&作为分隔符
        content_parts = new_content_str.split('&ini&')
        debug_print(f"解析到 {len(content_parts)} 个栏位内容")
        
        for i, part in enumerate(content_parts):
            debug_print(f"栏位 {i+1}: {part}")
            
            # 如果是None或空字符串，跳过
            if part.strip().upper() == 'NONE' or not part.strip():
                debug_print(f"栏位 {i+1} 为None或空，跳过")
                continue
                
            # 尝试解析栏位内容
            try:
                # 尝试解析为键值对
                if '=' in part:
                    lines = part.strip().split('\n')
                    for line in lines:
                        line = line.strip()
                        if not line or line.startswith('#') or line.startswith(';'):
                            continue
                            
                        if '=' in line:
                            key, value = line.split('=', 1)
                            key = key.strip()
                            value = value.strip()
                            
                            # 检查是否有section标记
                            if key.startswith('[') and key.endswith(']'):
                                section = key[1:-1]
                                debug_print(f"检测到section: {section}")
                                if not file_content.has_section(section):
                                    file_content.add_section(section)
                            elif '[' in key and ']' in key:
                                # 格式: section[key]=value
                                section_start = key.find('[')
                                section_end = key.find(']')
                                section = key[:section_start]
                                option = key[section_start+1:section_end]
                                if not file_content.has_section(section):
                                    file_content.add_section(section)
                                file_content.set(section, option, value)
                                debug_print(f"设置 {section}[{option}] = {value}")
                            else:
                                # 使用DEFAULT section
                                if not file_content.has_section('DEFAULT'):
                                    file_content.add_section('DEFAULT')
                                file_content.set('DEFAULT', key, value)
                                debug_print(f"设置 DEFAULT[{key}] = {value}")
                else:
                    # 如果不是键值对格式，作为注释或section处理
                    if part.startswith('[') and part.endswith(']'):
                        section = part[1:-1].strip()
                        if not file_content.has_section(section):
                            file_content.add_section(section)
                            debug_print(f"添加section: {section}")
            except Exception as e:
                debug_print(f"处理栏位 {i+1} 时出错: {e}")
                continue
        
        return file_content

    # --- UPDATE功能增强 ---
    def handle_update_content(filename, file_content, new_content_str, file_type):
        """处理更新操作，先检索再替换"""
        debug_print(f"处理UPDATE操作，文件类型: {file_type}")
        
        # 解析传入的内容，使用&update&作为分隔符
        parts = new_content_str.split('&update&')
        debug_print(f"解析到 {len(parts)} 个更新部分")
        
        if len(parts) != 2:
            debug_print("UPDATE格式错误，需要: 检索内容&update&新内容")
            return file_content
            
        search_content = parts[0].strip()
        replace_content = parts[1].strip()
        
        debug_print(f"检索内容: {search_content}")
        debug_print(f"新内容: {replace_content}")
        
        if file_type == 'ini':
            # INI文件的更新逻辑
            if isinstance(file_content, configparser.ConfigParser):
                debug_print("在INI文件中搜索内容")
                found = False
                
                # 遍历所有section和option
                for section in file_content.sections():
                    for option in file_content.options(section):
                        value = file_content.get(section, option)
                        
                        # 如果找到匹配的内容
                        if search_content in value or search_content == option or search_content == section:
                            debug_print(f"找到匹配: {section}[{option}] = {value}")
                            file_content.set(section, option, replace_content)
                            found = True
                            debug_print(f"更新为: {replace_content}")
                
                # 检查DEFAULT section
                if 'DEFAULT' in file_content:
                    for option in file_content.options('DEFAULT'):
                        value = file_content.get('DEFAULT', option)
                        if search_content in value or search_content == option:
                            debug_print(f"在DEFAULT中找到匹配: {option} = {value}")
                            file_content.set('DEFAULT', option, replace_content)
                            found = True
                
                if not found:
                    debug_print(f"未找到匹配 '{search_content}' 的内容")
                    # 如果没有找到，作为新内容添加到DEFAULT
                    if not file_content.has_section('DEFAULT'):
                        file_content.add_section('DEFAULT')
                    file_content.set('DEFAULT', 'new_' + str(len(file_content.options('DEFAULT')) + 1), replace_content)
                    debug_print(f"作为新内容添加到DEFAULT")
            
        elif file_type == 'json':
            # JSON文件的更新逻辑
            debug_print("在JSON文件中搜索内容")
            json_str = json.dumps(file_content)
            if search_content in json_str:
                debug_print(f"在JSON中找到匹配")
                # 简单替换字符串中的内容
                updated_str = json_str.replace(search_content, replace_content)
                try:
                    file_content = json.loads(updated_str)
                    debug_print("JSON更新成功")
                except:
                    debug_print("JSON解析失败，保持原内容")
        
        elif file_type == 'xml':
            # XML文件的更新逻辑
            debug_print("在XML文件中搜索内容")
            xml_str = ET.tostring(file_content, encoding='unicode')
            if search_content in xml_str:
                debug_print(f"在XML中找到匹配")
                # 简单替换字符串中的内容
                updated_str = xml_str.replace(search_content, replace_content)
                try:
                    file_content = ET.fromstring(updated_str)
                    debug_print("XML更新成功")
                except:
                    debug_print("XML解析失败，保持原内容")
        
        else:
            # 文本文件的更新逻辑
            debug_print("在文本文件中搜索内容")
            if search_content in file_content:
                debug_print(f"在文本中找到匹配")
                file_content = file_content.replace(search_content, replace_content)
                debug_print("文本更新成功")
            else:
                debug_print(f"未找到匹配 '{search_content}' 的内容")
        
        return file_content

    # --- 新增功能：文件检查 ---
    def check_file_exists(ftp, filename):
        """检查文件是否存在"""
        try:
            files = []
            ftp.retrlines('LIST', lambda x: files.append(x.split()[-1]))
            exists = filename in files
            debug_print(f"检查文件 {filename} 是否存在: {exists}")
            return exists
        except Exception as e:
            debug_print(f"检查文件存在性时出错: {e}")
            return False

    # --- 新增功能：获取文件大小 ---
    def get_file_size(ftp, filename):
        """获取文件大小"""
        try:
            ftp.sendcmd(f"SIZE {filename}")
            response = ftp.getmultiline().split()[1]
            size = int(response)
            debug_print(f"文件 {filename} 大小: {size} bytes")
            return size
        except Exception as e:
            debug_print(f"获取文件大小时出错: {e}")
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
        
        debug_print(f"开始执行 {operation} 操作")
        debug_print(f"FTP主机: {ftp_host}, 用户: {ftp_user}")
        debug_print(f"文件路径: {file_path}, 文件名: {filename}")
        
        # 连接FTP（增加重试机制）
        ftp = None
        try:
            debug_print("正在连接FTP...")
            ftp = FTP(ftp_host, timeout=30)
            ftp.login(ftp_user, ftp_pass)
            ftp.set_pasv(True)  # 使用被动模式
            debug_print("FTP连接成功")
        except Exception as e:
            debug_print(f"FTP连接失败: {e}")
            return {'error': 'FTP_CONNECTION_FAILED', 'message': f'FTP连接失败: {str(e)}'}
        
        # 切换目录（如果指定）
        if file_path:
            try:
                debug_print(f"切换到目录: {file_path}")
                ftp.cwd(file_path)
                debug_print("目录切换成功")
            except Exception as e:
                debug_print(f"目录切换失败: {e}")
                return {'error': 'DIRECTORY_ERROR', 'message': f'无法切换到目录 {file_path}: {str(e)}'}

        # 处理list操作
        if operation == 'list' or operation == 'search_files':
            try:
                debug_print("执行LIST操作")
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
                debug_print(f"找到 {len(files)} 个文件, {len(dirs)} 个目录")
                
                # 如果是文件搜索
                if operation == 'search_files' and content:
                    search_pattern = str(content).lower()
                    debug_print(f"搜索文件模式: {search_pattern}")
                    filtered_files = [f for f in files if search_pattern in f.lower()]
                    filtered_dirs = [d for d in dirs if search_pattern in d.lower()]
                    debug_print(f"筛选后: {len(filtered_files)} 个文件, {len(filtered_dirs)} 个目录")
                    files = filtered_files
                    dirs = filtered_dirs
                
                return {
                    'status': 'success',
                    'files': files,
                    'directories': dirs,
                    'total_files': len(files),
                    'total_directories': len(dirs)
                }
            except Exception as e:
                debug_print(f"LIST操作失败: {e}")
                return {'error': 'LIST_ERROR', 'message': f'列出文件失败: {str(e)}'}

        # 验证filename（除list/search_files操作外都需要）
        if operation not in ['list', 'search_files']:
            if not filename:
                return {'error': 'MISSING_FILENAME', 'message': '需要指定文件名'}
            
            # 检查文件是否存在（对于读取、追加、搜索、更新操作）
            if operation in ['read', 'append', 'search', 'update']:
                if not check_file_exists(ftp, filename):
                    return {'error': 'FILE_NOT_FOUND', 'message': f'文件 {filename} 不存在'}

        # 处理delete操作
        if operation == 'delete':
            try:
                debug_print(f"删除文件: {filename}")
                ftp.delete(filename)
                debug_print("文件删除成功")
                return {'status': 'success', 'message': f'文件 {filename} 已删除'}
            except Exception as e:
                debug_print(f"删除文件失败: {e}")
                return {'error': 'DELETE_ERROR', 'message': f'删除文件失败: {str(e)}'}

        # 对于需要文件内容的操作，下载文件
        byte_content = b""
        raw_content = ""
        file_type = "unknown"
        file_content = None
        
        if operation in ['read', 'append', 'update', 'search']:
            try:
                debug_print(f"下载文件: {filename}")
                
                # 获取文件大小
                file_size = get_file_size(ftp, filename)
                debug_print(f"文件大小: {file_size} bytes")
                
                # 下载文件内容
                byte_content = BytesIO()
                ftp.retrbinary(f'RETR {filename}', byte_content.write)
                byte_content = byte_content.getvalue()
                debug_print(f"下载完成，实际大小: {len(byte_content)} bytes")
                
                if len(byte_content) != file_size and file_size > 0:
                    debug_print("警告: 文件下载不完整")
                    return {'error': 'DOWNLOAD_ERROR', 'message': '文件下载不完整'}
                    
                raw_content = auto_decode(byte_content)
                file_type = detect_file_type(filename, raw_content)
                file_content = load_content(filename, raw_content, file_type)
                debug_print(f"文件类型: {file_type}, 内容加载成功")
                
            except Exception as e:
                debug_print(f"下载文件失败: {e}")
                return {'error': 'DOWNLOAD_ERROR', 'message': f'下载文件失败: {str(e)}'}

        # 执行具体操作
        result = None
        
        if operation == 'read':
            debug_print("执行READ操作")
            result = {
                'status': 'success',
                'filename': filename,
                'type': file_type,
                'size': len(byte_content),
                'content': file_content,
                'raw_content': raw_content if file_type == 'text' else None
            }
            debug_print(f"读取成功，文件类型: {file_type}")

        elif operation == 'append':
            if not content:
                return {'error': 'MISSING_CONTENT', 'message': '追加操作需要内容参数'}
            
            debug_print("执行APPEND操作")
            try:
                new_content_str = str(content)
                debug_print(f"追加内容: {new_content_str[:100]}...")
                new_content_parsed = load_content(filename, new_content_str, file_type)
                
                # 根据文件类型处理追加逻辑
                if file_type == 'json':
                    debug_print("处理JSON追加")
                    if isinstance(file_content, dict) and isinstance(new_content_parsed, dict):
                        # 合并字典
                        file_content.update(new_content_parsed)
                        debug_print("JSON字典合并成功")
                    elif isinstance(file_content, list):
                        # 追加到列表
                        file_content.append(new_content_parsed)
                        debug_print("JSON列表追加成功")
                    else:
                        # 其他情况，转换为字符串追加
                        file_content = str(file_content) + '\n' + new_content_str
                        debug_print("JSON转换为字符串追加")
                        
                elif file_type == 'xml':
                    debug_print("处理XML追加")
                    if isinstance(new_content_parsed, ET.Element):
                        file_content.append(new_content_parsed)
                        debug_print("XML元素追加成功")
                    else:
                        # 如果是字符串，创建一个新的文本元素
                        new_elem = ET.Element('addition')
                        new_elem.text = new_content_str
                        file_content.append(new_elem)
                        debug_print("XML字符串追加成功")
                        
                elif file_type == 'ini':
                    debug_print("处理INI追加")
                    file_content = handle_ini_content(filename, file_content, new_content_str, 'append')
                    
                else:
                    # 文本文件直接追加
                    debug_print("处理文本追加")
                    file_content = raw_content + '\n' + new_content_str

                # 上传更新后的内容
                updated_content = save_content(file_content, file_type, filename)
                debug_print(f"上传更新内容，大小: {len(updated_content)} 字符")
                
                ftp.storbinary(f'STOR {filename}', BytesIO(updated_content.encode('utf-8')))
                debug_print("文件上传成功")
                
                result = {'status': 'success', 'message': f'已成功追加内容到 {filename}'}
                
            except Exception as e:
                debug_print(f"追加内容失败: {e}")
                return {'error': 'APPEND_ERROR', 'message': f'追加内容失败: {str(e)}'}

        elif operation == 'update':
            if not content:
                return {'error': 'MISSING_CONTENT', 'message': '更新操作需要内容参数'}
            
            debug_print("执行UPDATE操作")
            try:
                new_content_str = str(content)
                debug_print(f"更新内容: {new_content_str[:100]}...")
                
                # 检查是否使用新的UPDATE格式
                if '&update&' in new_content_str:
                    debug_print("检测到新的UPDATE格式，使用检索替换模式")
                    file_content = handle_update_content(filename, file_content, new_content_str, file_type)
                else:
                    debug_print("使用旧的UPDATE格式，直接替换")
                    new_content_parsed = load_content(filename, new_content_str, file_type)
                    file_content = new_content_parsed
                
                # 上传新内容
                updated_content = save_content(file_content, file_type, filename)
                debug_print(f"上传更新内容，大小: {len(updated_content)} 字符")
                
                ftp.storbinary(f'STOR {filename}', BytesIO(updated_content.encode('utf-8')))
                debug_print("文件上传成功")
                
                result = {'status': 'success', 'message': f'已成功更新 {filename}'}
                
            except Exception as e:
                debug_print(f"更新文件失败: {e}")
                return {'error': 'UPDATE_ERROR', 'message': f'更新文件失败: {str(e)}'}

        elif operation == 'search':
            if not content:
                return {'error': 'MISSING_SEARCH_TERM', 'message': '搜索操作需要搜索词'}
            
            debug_print("执行SEARCH操作")
            try:
                matches = []
                search_str = str(content).lower()
                debug_print(f"搜索词: {search_str}")
                
                if file_type == 'json':
                    debug_print("在JSON中搜索")
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
                    debug_print(f"在JSON中找到 {len(matches)} 个匹配")
                    
                elif file_type == 'xml':
                    debug_print("在XML中搜索")
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
                    debug_print(f"在XML中找到 {len(matches)} 个匹配")
                    
                elif file_type == 'ini':
                    debug_print("在INI中搜索")
                    if isinstance(file_content, configparser.ConfigParser):
                        for section in file_content.sections():
                            if search_str in section.lower():
                                matches.append({
                                    'type': 'section',
                                    'section': section,
                                    'path': f"[{section}]"
                                })
                            for option in file_content.options(section):
                                value = file_content.get(section, option)
                                if search_str in option.lower():
                                    matches.append({
                                        'type': 'option',
                                        'section': section,
                                        'option': option,
                                        'value': value,
                                        'path': f"[{section}].{option}"
                                    })
                                if search_str in value.lower():
                                    matches.append({
                                        'type': 'value',
                                        'section': section,
                                        'option': option,
                                        'value': value,
                                        'path': f"[{section}].{option}"
                                    })
                        
                        # 检查DEFAULT section
                        if 'DEFAULT' in file_content:
                            for option in file_content.options('DEFAULT'):
                                value = file_content.get('DEFAULT', option)
                                if search_str in option.lower() or search_str in value.lower():
                                    matches.append({
                                        'type': 'default',
                                        'option': option,
                                        'value': value,
                                        'path': f"[DEFAULT].{option}"
                                    })
                    debug_print(f"在INI中找到 {len(matches)} 个匹配")
                    
                else:
                    # 文本文件搜索
                    debug_print("在文本中搜索")
                    lines = raw_content.split('\n')
                    for i, line in enumerate(lines):
                        if search_str in line.lower():
                            matches.append({
                                'type': 'line',
                                'line_number': i + 1,
                                'content': line.strip(),
                                'start_index': line.lower().find(search_str) + 1
                            })
                    debug_print(f"在文本中找到 {len(matches)} 个匹配")
                
                result = {
                    'status': 'success',
                    'filename': filename,
                    'search_term': search_str,
                    'matches_found': len(matches),
                    'matches': matches,
                    'file_type': file_type
                }
                
            except Exception as e:
                debug_print(f"搜索失败: {e}")
                return {'error': 'SEARCH_ERROR', 'message': f'搜索失败: {str(e)}'}

        debug_print("操作执行完成")
        return result or {'status': 'success', 'message': '操作完成'}

    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        debug_print(f"发生未预期错误: {e}")
        debug_print(f"错误详情: {error_detail}")
        return {
            'error': 'UNEXPECTED_ERROR',
            'message': f'处理过程中发生错误: {str(e)}',
            'detail': error_detail
        }

    finally:
        if 'ftp' in locals() and ftp:
            try:
                debug_print("关闭FTP连接")
                ftp.quit()
                debug_print("FTP连接关闭成功")
            except:
                try:
                    ftp.close()
                    debug_print("FTP连接强制关闭")
                except:
                    debug_print("FTP连接关闭失败")


# 测试代码
if __name__ == '__main__':
    import json
    
    # 测试各种操作
    test_config = {
        'ftp_host': "10.12.14.221",
        'ftp_user': "java",
        'ftp_pass': "cimbc"
    }
    
    print("=" * 60)
    print("FTP文件处理工具测试")
    print("=" * 60)
    
    # 1. 列出文件
    print("\n1. 列出文件:")
    result = process_ftp_file(
        ftp_host=test_config['ftp_host'],
        ftp_user=test_config['ftp_user'],
        ftp_pass=test_config['ftp_pass'],
        file_path="/test/1/",
        operation="list"
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    # 2. 测试INI文件操作
    print("\n2. 测试INI文件操作:")
    
    # 假设有一个test.ini文件
    ini_content = "[section1]\nkey1=value1\nkey2=value2\n\n[section2]\nkey3=value3"
    
    # 追加INI内容
    append_content = "new_key=new_value&ini&None&ini&[section3]\nkey4=value4"
    
    print(f"追加内容格式: {append_content}")
    print("解析: 第一个栏位添加到DEFAULT, 第二个栏位跳过(None), 第三个栏位添加新的section")
    
    # 3. 测试UPDATE新格式
    print("\n3. 测试UPDATE新格式:")
    update_content = "old_value&update&new_value"
    print(f"UPDATE格式: {update_content}")
    print("说明: 搜索包含'old_value'的内容，替换为'new_value'")
