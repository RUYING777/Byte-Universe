from flask import Flask, request, jsonify, send_from_directory
import os
import threading
import tkinter as tk
from tkinter import scrolledtext, messagebox, filedialog, ttk
import psutil
import socket
from contextlib import closing
from werkzeug.utils import secure_filename
import mimetypes
import uuid
from datetime import datetime
import zipfile
import shutil
import re

class FileServerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("虫洞穿透传输器")
        
        # 先创建界面元素
        self.create_widgets()
        
        # 然后获取磁盘信息并选择最佳保存路径
        self.best_disk = self.select_best_disk()
        self.default_save_dir = os.path.join(self.best_disk, "server_data")
        self.dir_entry.delete(0, tk.END)  # 清空原有内容
        self.dir_entry.insert(0, self.default_save_dir)  # 设置默认路径
        
        # 获取本机IP地址并设置到界面
        self.local_ip = self.get_local_ip()
        self.host_entry.delete(0, tk.END)
        self.host_entry.insert(0, self.local_ip)
        
        # 获取可用端口并设置到界面
        self.available_port = self.find_available_port()
        self.port_entry.delete(0, tk.END)
        self.port_entry.insert(0, str(self.available_port))
        
        # 初始化Flask应用
        self.app = Flask(__name__)
        self.app.config['MAX_CONTENT_LENGTH'] = None  # 解除文件大小限制
        
        # 确保保存目录存在
        if not os.path.exists(self.default_save_dir):
            os.makedirs(self.default_save_dir)
        
        # 设置路由
        @self.app.route('/upload', methods=['POST'])
        def upload_file():
            try:
                current_save_dir = self.dir_entry.get()
                if not os.path.exists(current_save_dir):
                    os.makedirs(current_save_dir)
                
                # 获取上传的数据类型
                data_type = request.form.get('data_type', 'file')
                
                if data_type == 'text':
                    # 处理文本数据
                    content = request.form.get('content', '')
                    filename = request.form.get('filename', f'text_{datetime.now().strftime("%Y%m%d%H%M%S")}.txt')
                    
                    # 改进文件名处理
                    filename = self.sanitize_filename(filename)
                    save_path = os.path.join(current_save_dir, filename)
                    
                    with open(save_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    
                    log_msg = f"文本保存成功: {save_path} (大小: {len(content)}字节)"
                    self.log_message(log_msg)
                    return jsonify({
                        'status': 'success',
                        'message': '文本保存成功',
                        'path': save_path,
                        'size': len(content)
                    })
                elif data_type == 'folder':
                    # 处理文件夹上传
                    if 'file' not in request.files:
                        return jsonify({
                            'status': 'error',
                            'message': '没有上传文件'
                        }), 400
                    
                    zip_file = request.files['file']
                    if zip_file.filename == '':
                        return jsonify({
                            'status': 'error',
                            'message': '没有选择文件'
                        }), 400
                    
                    # 获取原始文件夹名
                    folder_name = request.form.get('original_folder_name', 'unnamed_folder')
                    folder_name = self.sanitize_filename(folder_name, is_folder=True)
                    
                    # 如果文件夹名已存在，添加随机前缀
                    if os.path.exists(os.path.join(current_save_dir, folder_name)):
                        random_prefix = uuid.uuid4().hex[:4]
                        folder_name = f"{random_prefix}_{folder_name}"
                    
                    # 创建临时zip文件
                    temp_zip = os.path.join(current_save_dir, f"{folder_name}.zip")
                    zip_file.save(temp_zip)
                    
                    # 解压zip文件
                    save_path = os.path.join(current_save_dir, folder_name)
                    with zipfile.ZipFile(temp_zip, 'r') as zip_ref:
                        zip_ref.extractall(save_path)
                    
                    # 删除临时zip文件
                    os.remove(temp_zip)
                    
                    # 计算文件夹大小
                    folder_size = sum(os.path.getsize(os.path.join(dirpath, filename)) 
                                   for dirpath, dirnames, filenames in os.walk(save_path) 
                                   for filename in filenames)
                    
                    log_msg = (f"文件夹保存成功: {save_path} "
                             f"(大小: {folder_size/1024/1024:.2f}MB, "
                             f"剩余空间: {self.get_free_space(current_save_dir)}GB)")
                    self.log_message(log_msg)
                    
                    return jsonify({
                        'status': 'success',
                        'message': '文件夹保存成功',
                        'path': save_path,
                        'size': folder_size,
                        'original_folder_name': folder_name
                    })
                else:
                    # 处理文件上传(包括视频、压缩包等)
                    if 'file' not in request.files:
                        return jsonify({
                            'status': 'error',
                            'message': '没有上传文件'
                        }), 400
                    
                    file = request.files['file']
                    if file.filename == '':
                        return jsonify({
                            'status': 'error',
                            'message': '没有选择文件'
                        }), 400
                    
                    # 获取原始文件名或生成新文件名
                    original_filename = request.form.get('original_filename', file.filename)
                    filename = self.sanitize_filename(original_filename)
                    
                    # 如果文件名已存在，添加随机前缀
                    if os.path.exists(os.path.join(current_save_dir, filename)):
                        random_prefix = uuid.uuid4().hex[:4]
                        filename = f"{random_prefix}_{filename}"
                    
                    save_path = os.path.join(current_save_dir, filename)
                    file.save(save_path)
                    
                    # 获取文件大小
                    file_size = os.path.getsize(save_path)
                    
                    log_msg = (f"文件保存成功: {save_path} "
                             f"(大小: {file_size/1024/1024:.2f}MB, "
                             f"类型: {mimetypes.guess_type(save_path)[0]}, "
                             f"剩余空间: {self.get_free_space(current_save_dir)}GB)")
                    self.log_message(log_msg)
                    
                    return jsonify({
                        'status': 'success',
                        'message': '文件保存成功',
                        'path': save_path,
                        'size': file_size,
                        'original_filename': original_filename,
                        'type': mimetypes.guess_type(save_path)[0]
                    })
            
            except Exception as e:
                error_msg = f"保存失败: {str(e)}"
                self.log_message(error_msg)
                return jsonify({
                    'status': 'error',
                    'message': error_msg
                }), 500
        
        @self.app.route('/download', methods=['GET'])
        def download_file():
            try:
                current_save_dir = os.path.normpath(self.dir_entry.get())
                requested_path = request.args.get('path')
                
                if not requested_path:
                    return jsonify({'status': 'error', 'message': 'Missing path parameter'}), 400

                # 规范化并解析请求路径
                requested_path = os.path.normpath(requested_path)
                absolute_requested = os.path.abspath(os.path.join(current_save_dir, requested_path))
                absolute_save_dir = os.path.abspath(current_save_dir)

                # 更智能的路径安全检查
                if not absolute_requested.startswith(absolute_save_dir):
                    self.log_message(f"Path traversal attempt: {absolute_requested}")
                    return jsonify({'status': 'error', 'message': 'Access denied'}), 403

                if not os.path.exists(absolute_requested):
                    return jsonify({'status': 'error', 'message': 'File not found'}), 404

                # 检查读取权限
                if not os.access(absolute_requested, os.R_OK):
                    self.log_message(f"Permission denied: {absolute_requested}")
                    return jsonify({'status': 'error', 'message': 'Permission denied'}), 403

                # 处理目录下载
                if os.path.isdir(absolute_requested):
                    return self._handle_directory_download(absolute_requested, current_save_dir)
                
                # 处理文件下载
                return send_from_directory(
                    directory=os.path.dirname(absolute_requested),
                    path=os.path.basename(absolute_requested),
                    as_attachment=True
                )

            except Exception as e:
                self.log_message(f"Download error: {str(e)}")
                return jsonify({'status': 'error', 'message': str(e)}), 500

        @self.app.route('/delete', methods=['POST'])
        def delete_file():
            try:
                current_save_dir = os.path.normpath(self.dir_entry.get())
                requested_path = request.form.get('path')
                
                if not requested_path:
                    return jsonify({'status': 'error', 'message': 'Missing path parameter'}), 400

                # 规范化并解析请求路径
                requested_path = os.path.normpath(requested_path)
                absolute_requested = os.path.abspath(os.path.join(current_save_dir, requested_path))
                absolute_save_dir = os.path.abspath(current_save_dir)

                # 路径安全检查
                if not absolute_requested.startswith(absolute_save_dir):
                    self.log_message(f"Path traversal attempt: {absolute_requested}")
                    return jsonify({'status': 'error', 'message': 'Access denied'}), 403

                if not os.path.exists(absolute_requested):
                    return jsonify({'status': 'error', 'message': 'File not found'}), 404

                # 检查删除权限
                if not os.access(absolute_requested, os.W_OK):
                    self.log_message(f"Permission denied: {absolute_requested}")
                    return jsonify({'status': 'error', 'message': 'Permission denied'}), 403

                # 执行删除操作
                if os.path.isdir(absolute_requested):
                    shutil.rmtree(absolute_requested)
                    self.log_message(f"已删除文件夹: {absolute_requested}")
                else:
                    os.remove(absolute_requested)
                    self.log_message(f"已删除文件: {absolute_requested}")

                return jsonify({
                    'status': 'success',
                    'message': '删除成功'
                })

            except Exception as e:
                self.log_message(f"删除失败: {str(e)}")
                return jsonify({'status': 'error', 'message': str(e)}), 500

        @self.app.route('/update_file', methods=['POST'])
        def update_file():
            try:
                current_save_dir = os.path.normpath(self.dir_entry.get())
                requested_path = request.form.get('path')
                new_content = request.form.get('content', '')
                
                if not requested_path:
                    return jsonify({'status': 'error', 'message': 'Missing path parameter'}), 400

                # 规范化并解析请求路径
                requested_path = os.path.normpath(requested_path)
                absolute_requested = os.path.abspath(os.path.join(current_save_dir, requested_path))
                absolute_save_dir = os.path.abspath(current_save_dir)

                # 路径安全检查
                if not absolute_requested.startswith(absolute_save_dir):
                    self.log_message(f"Path traversal attempt: {absolute_requested}")
                    return jsonify({'status': 'error', 'message': 'Access denied'}), 403

                if not os.path.exists(absolute_requested):
                    return jsonify({'status': 'error', 'message': 'File not found'}), 404

                # 检查写入权限
                if not os.access(absolute_requested, os.W_OK):
                    self.log_message(f"Permission denied: {absolute_requested}")
                    return jsonify({'status': 'error', 'message': 'Permission denied'}), 403

                # 检查是否是文件(不能修改文件夹)
                if os.path.isdir(absolute_requested):
                    return jsonify({'status': 'error', 'message': 'Cannot update a directory'}), 400

                # 执行更新操作
                with open(absolute_requested, 'w', encoding='utf-8') as f:
                    f.write(new_content)

                self.log_message(f"已更新文件: {absolute_requested}")
                return jsonify({
                    'status': 'success',
                    'message': '文件更新成功',
                    'size': len(new_content)
                })

            except Exception as e:
                self.log_message(f"更新文件失败: {str(e)}")
                return jsonify({'status': 'error', 'message': str(e)}), 500
        
        def _handle_directory_download(self, dir_path, save_dir):
            """处理目录下载逻辑"""
            dir_name = os.path.basename(dir_path)
            temp_zip = os.path.join(save_dir, f"{dir_name}.zip")
            
            # 确保临时文件名唯一
            temp_zip = self._get_unique_filename(temp_zip)
            
            # 创建压缩文件
            with zipfile.ZipFile(temp_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, _, files in os.walk(dir_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, start=dir_path)
                        zipf.write(file_path, arcname)
            
            # 异步删除临时文件
            threading.Thread(
                target=self._delete_temp_file,
                args=(temp_zip,),
                daemon=True
            ).start()
            
            return send_from_directory(
                directory=os.path.dirname(temp_zip),
                path=os.path.basename(temp_zip),
                as_attachment=True
            )
        
        @self.app.route('/list_files', methods=['GET'])
        def list_files():
            try:
                current_save_dir = self.dir_entry.get()
                path = request.args.get('path', '')
                
                full_path = os.path.join(current_save_dir, path)
                
                # 安全检查
                if not os.path.abspath(full_path).startswith(os.path.abspath(current_save_dir)):
                    return jsonify({'status': 'error', 'message': '无权访问该路径'}), 403
                
                if not os.path.exists(full_path):
                    return jsonify({'status': 'error', 'message': '路径不存在'}), 404
                
                items = []
                for item in os.listdir(full_path):
                    item_path = os.path.join(full_path, item)
                    item_info = {
                        'name': item,
                        'is_dir': os.path.isdir(item_path),
                        'size': os.path.getsize(item_path) if not os.path.isdir(item_path) else 0,
                        'modified': os.path.getmtime(item_path),
                        'path': os.path.relpath(item_path, start=current_save_dir)
                    }
                    items.append(item_info)
                
                return jsonify({
                    'status': 'success',
                    'path': path,
                    'items': items
                })
            
            except Exception as e:
                return jsonify({'status': 'error', 'message': str(e)}), 500
    
    def _get_unique_filename(self, path):
        """确保文件名唯一，避免覆盖"""
        if not os.path.exists(path):
            return path
        
        base, ext = os.path.splitext(path)
        counter = 1
        while True:
            new_path = f"{base}_{counter}{ext}"
            if not os.path.exists(new_path):
                return new_path
            counter += 1
    
    def _delete_temp_file(self, file_path, delay=30):
        """延迟删除临时文件"""
        import time
        time.sleep(delay)
        try:
            os.remove(file_path)
            self.log_message(f"已删除临时文件: {file_path}")
        except Exception as e:
            self.log_message(f"删除临时文件失败: {str(e)}")
    
    def sanitize_filename(self, filename, is_folder=False):
        """安全处理文件名，保留更多原始字符"""
        # 保留中文、字母、数字、下划线、点、短横线等常见字符
        if is_folder:
            # 对于文件夹，允许更多字符
            filename = re.sub(r'[\\/:*?"<>|\x00-\x1f]', '_', filename)
        else:
            # 对于文件，保留扩展名
            basename, ext = os.path.splitext(filename)
            basename = re.sub(r'[\\/:*?"<>|\x00-\x1f]', '_', basename)
            filename = basename + ext
        
        # 移除首尾空格和点
        filename = filename.strip('. ')
        
        # 如果处理后为空，生成随机名称
        if not filename:
            filename = uuid.uuid4().hex[:8]
            if is_folder:
                filename = f"folder_{filename}"
            else:
                filename = f"file_{filename}"
        
        return filename
    
    def get_local_ip(self):
        """获取本机IP地址"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception as e:
            self.log_message(f"获取本地IP失败: {str(e)}，将使用127.0.0.1")
            return "127.0.0.1"
    
    def find_available_port(self, start_port=5000, end_port=6000):
        """自动查找可用的端口号"""
        for port in range(start_port, end_port + 1):
            with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
                try:
                    sock.bind(('', port))
                    self.log_message(f"找到可用端口: {port}")
                    return port
                except socket.error:
                    continue
        self.log_message(f"在{start_port}-{end_port}范围内未找到可用端口，使用默认5000")
        return 5000
    
    def select_best_disk(self):
        """自动选择剩余空间最多的磁盘"""
        disks = {}
        for part in psutil.disk_partitions():
            if 'cdrom' in part.opts or part.fstype == '':
                continue
            usage = psutil.disk_usage(part.mountpoint)
            disks[part.mountpoint] = usage.free
        
        if not disks:
            return os.path.expanduser("~")  # 如果没有找到磁盘，使用用户目录
        
        best_disk = max(disks.items(), key=lambda x: x[1])[0]
        self.log_message(f"自动选择存储路径: {best_disk} (剩余空间: {disks[best_disk]/1024/1024/1024:.2f}GB)")
        return best_disk
    
    def get_free_space(self, path):
        """获取指定路径的剩余空间(GB)"""
        try:
            usage = psutil.disk_usage(path)
            return f"{usage.free/1024/1024/1024:.2f}"
        except:
            return "未知"
    
    def create_widgets(self):
        # 配置面板
        config_frame = tk.LabelFrame(self.root, text="服务器配置", padx=10, pady=10)
        config_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # 监听地址
        tk.Label(config_frame, text="监听地址:").grid(row=0, column=0, sticky=tk.W)
        self.host_entry = tk.Entry(config_frame)
        self.host_entry.grid(row=0, column=1, sticky=tk.EW)
        
        # 获取IP按钮
        get_ip_btn = tk.Button(config_frame, text="获取本机IP", command=self.update_local_ip)
        get_ip_btn.grid(row=0, column=2, padx=5)
        
        # 端口号
        tk.Label(config_frame, text="端口号:").grid(row=1, column=0, sticky=tk.W)
        self.port_entry = tk.Entry(config_frame)
        self.port_entry.grid(row=1, column=1, sticky=tk.EW)
        
        # 获取端口按钮
        get_port_btn = tk.Button(config_frame, text="获取可用端口", command=self.update_available_port)
        get_port_btn.grid(row=1, column=2, padx=5)
        
        # 保存目录
        tk.Label(config_frame, text="保存目录:").grid(row=2, column=0, sticky=tk.W)
        self.dir_entry = tk.Entry(config_frame)
        self.dir_entry.grid(row=2, column=1, sticky=tk.EW)
        
        # 浏览按钮
        browse_btn = tk.Button(config_frame, text="浏览...", command=self.browse_directory)
        browse_btn.grid(row=2, column=2, padx=5)
        
        # 磁盘信息按钮
        disk_info_btn = tk.Button(config_frame, text="查看磁盘信息", command=self.show_disk_info)
        disk_info_btn.grid(row=3, column=0, columnspan=3, pady=5)
        
        # 下载面板
        download_frame = tk.LabelFrame(self.root, text="下载文件", padx=10, pady=10)
        download_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(download_frame, text="文件路径:").grid(row=0, column=0, sticky=tk.W)
        self.download_entry = tk.Entry(download_frame)
        self.download_entry.grid(row=0, column=1, sticky=tk.EW)
        
        browse_download_btn = tk.Button(download_frame, text="浏览...", command=self.browse_download_file)
        browse_download_btn.grid(row=0, column=2, padx=5)
        
        download_btn = tk.Button(download_frame, text="生成下载链接", command=self.generate_download_link)
        download_btn.grid(row=1, column=0, columnspan=3, pady=5)
        
        self.download_link_var = tk.StringVar()
        tk.Label(download_frame, text="下载链接:").grid(row=2, column=0, sticky=tk.W)
        download_link_entry = tk.Entry(download_frame, textvariable=self.download_link_var, state='readonly')
        download_link_entry.grid(row=2, column=1, columnspan=2, sticky=tk.EW)
        
        # 文件浏览器面板
        browser_frame = tk.LabelFrame(self.root, text="服务器文件浏览器", padx=10, pady=10)
        browser_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 创建Treeview和滚动条
        self.tree = ttk.Treeview(browser_frame, columns=('size', 'modified'), selectmode='browse')
        self.tree.heading('#0', text='名称')
        self.tree.heading('size', text='大小')
        self.tree.heading('modified', text='修改时间')
        
        # 设置列宽
        self.tree.column('#0', width=300)
        self.tree.column('size', width=100)
        self.tree.column('modified', width=150)
        
        # 添加滚动条
        scrollbar = ttk.Scrollbar(browser_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        # 布局Treeview和滚动条
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 添加右键菜单
        self.popup_menu = tk.Menu(self.root, tearoff=0)
        self.popup_menu.add_command(label="下载", command=self.download_selected_item)
        self.popup_menu.add_command(label="删除", command=self.delete_selected_item)
        self.popup_menu.add_command(label="编辑", command=self.edit_selected_file)
        self.popup_menu.add_command(label="刷新", command=self.refresh_file_browser)
        
        # 绑定事件
        self.tree.bind("<Button-3>", self.show_popup_menu)
        self.tree.bind("<Double-1>", self.on_tree_double_click)
        
        # 日志区域
        log_frame = tk.LabelFrame(self.root, text="服务器日志", padx=10, pady=10)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.log_area = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, width=60, height=15)
        self.log_area.pack(fill=tk.BOTH, expand=True)
        
        # 状态栏
        self.status_bar = tk.Label(self.root, text="服务器准备启动...", bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(fill=tk.X, padx=10, pady=5)
        
        # 调整布局
        config_frame.columnconfigure(1, weight=1)
        download_frame.columnconfigure(1, weight=1)
    
    def update_local_ip(self):
        """更新本地IP地址"""
        self.local_ip = self.get_local_ip()
        self.host_entry.delete(0, tk.END)
        self.host_entry.insert(0, self.local_ip)
        self.log_message(f"更新本地IP地址为: {self.local_ip}")
    
    def update_available_port(self):
        """更新可用端口号"""
        self.available_port = self.find_available_port()
        self.port_entry.delete(0, tk.END)
        self.port_entry.insert(0, str(self.available_port))
        self.log_message(f"更新可用端口为: {self.available_port}")
    
    def browse_directory(self):
        """打开目录选择对话框"""
        selected_dir = filedialog.askdirectory(initialdir=self.dir_entry.get())
        if selected_dir:
            self.dir_entry.delete(0, tk.END)
            self.dir_entry.insert(0, selected_dir)
            self.log_message(f"保存目录更改为: {selected_dir}")
            self.log_message(f"该目录剩余空间: {self.get_free_space(selected_dir)}GB")
            self.refresh_file_browser()
    
    def browse_download_file(self):
        """打开文件选择对话框"""
        current_save_dir = self.dir_entry.get()
        selected_path = filedialog.askopenfilename(initialdir=current_save_dir)
        if not selected_path:
            return
        
        # 确保选择的文件在保存目录内
        if not os.path.abspath(selected_path).startswith(os.path.abspath(current_save_dir)):
            messagebox.showerror("错误", "只能选择保存目录内的文件")
            return
        
        self.download_entry.delete(0, tk.END)
        self.download_entry.insert(0, selected_path)
    
    def generate_download_link(self):
        """生成下载链接"""
        file_path = self.download_entry.get()
        if not file_path or not os.path.exists(file_path):
            messagebox.showerror("错误", "请选择有效的文件路径")
            return
        
        host = self.host_entry.get()
        port = self.port_entry.get()
        
        download_url = f"http://{host}:{port}/download?path={file_path}"
        self.download_link_var.set(download_url)
        self.log_message(f"生成的下载链接: {download_url}")
    
    def show_disk_info(self):
        """显示所有磁盘信息"""
        disk_info = "磁盘空间信息:\n"
        for part in psutil.disk_partitions():
            if 'cdrom' in part.opts or part.fstype == '':
                continue
            usage = psutil.disk_usage(part.mountpoint)
            disk_info += (
                f"磁盘: {part.mountpoint}\n"
                f"总空间: {usage.total/1024/1024/1024:.2f}GB | "
                f"已用: {usage.used/1024/1024/1024:.2f}GB | "
                f"剩余: {usage.free/1024/1024/1024:.2f}GB\n"
                f"文件系统: {part.fstype}\n\n"
            )
        
        # 在新窗口中显示磁盘信息
        info_window = tk.Toplevel(self.root)
        info_window.title("磁盘空间信息")
        
        text_area = scrolledtext.ScrolledText(info_window, wrap=tk.WORD, width=70, height=15)
        text_area.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        text_area.insert(tk.END, disk_info)
        text_area.config(state=tk.DISABLED)
        
        close_btn = tk.Button(info_window, text="关闭", command=info_window.destroy)
        close_btn.pack(pady=5)
    
    def refresh_file_browser(self):
        """刷新文件浏览器"""
        current_save_dir = self.dir_entry.get()
        
        # 清空现有内容
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # 添加根节点
        root_node = self.tree.insert('', 'end', text=current_save_dir, open=True)
        
        # 添加文件和子目录
        try:
            for item in os.listdir(current_save_dir):
                item_path = os.path.join(current_save_dir, item)
                if os.path.isdir(item_path):
                    node = self.tree.insert(root_node, 'end', text=item, values=('文件夹', ''))
                    # 预加载一级子目录
                    self.load_subdirectories(node, item_path)
                else:
                    size = os.path.getsize(item_path)
                    modified = datetime.fromtimestamp(os.path.getmtime(item_path)).strftime('%Y-%m-%d %H:%M:%S')
                    self.tree.insert(root_node, 'end', text=item, values=(self.format_size(size), modified))
        except Exception as e:
            self.log_message(f"刷新文件浏览器失败: {str(e)}")
    
    def load_subdirectories(self, parent_node, path):
        """加载子目录"""
        try:
            for item in os.listdir(path):
                item_path = os.path.join(path, item)
                if os.path.isdir(item_path):
                    self.tree.insert(parent_node, 'end', text=item, values=('文件夹', ''))
        except:
            pass
    
    def on_tree_double_click(self, event):
        """双击树节点事件"""
        item = self.tree.selection()[0]
        text = self.tree.item(item, 'text')
        parent = self.tree.parent(item)
        
        # 如果是文件夹，展开/折叠
        if self.tree.item(item, 'values')[0] == '文件夹':
            if self.tree.item(item, 'open'):
                self.tree.item(item, open=False)
                # 清除子节点以便下次展开时重新加载
                for child in self.tree.get_children(item):
                    self.tree.delete(child)
            else:
                # 加载子目录
                path = self.get_full_path(item)
                try:
                    for sub_item in os.listdir(path):
                        sub_item_path = os.path.join(path, sub_item)
                        if os.path.isdir(sub_item_path):
                            self.tree.insert(item, 'end', text=sub_item, values=('文件夹', ''))
                        else:
                            size = os.path.getsize(sub_item_path)
                            modified = datetime.fromtimestamp(os.path.getmtime(sub_item_path)).strftime('%Y-%m-%d %H:%M:%S')
                            self.tree.insert(item, 'end', text=sub_item, values=(self.format_size(size), modified))
                    self.tree.item(item, open=True)
                except Exception as e:
                    self.log_message(f"无法打开目录 {path}: {str(e)}")
    
    def get_full_path(self, item):
        """获取树节点的完整路径"""
        path_parts = []
        while item:
            path_parts.append(self.tree.item(item, 'text'))
            item = self.tree.parent(item)
        return os.path.join(*reversed(path_parts))
    
    def show_popup_menu(self, event):
        """显示右键菜单"""
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.popup_menu.post(event.x_root, event.y_root)
    
    def download_selected_item(self):
        """下载选中的文件或文件夹"""
        selected_item = self.tree.selection()
        if not selected_item:
            return
        
        item = selected_item[0]
        item_text = self.tree.item(item, 'text')
        item_values = self.tree.item(item, 'values')
        
        # 获取完整路径
        full_path = self.get_full_path(item)
        
        # 设置下载路径
        self.download_entry.delete(0, tk.END)
        self.download_entry.insert(0, full_path)
        
        # 生成下载链接
        self.generate_download_link()
    
    def delete_selected_item(self):
        """删除选中的文件或文件夹"""
        selected_item = self.tree.selection()
        if not selected_item:
            return
        
        item = selected_item[0]
        item_text = self.tree.item(item, 'text')
        item_values = self.tree.item(item, 'values')
        
        # 获取完整路径
        full_path = self.get_full_path(item)
        
        # 确认删除
        if not messagebox.askyesno("确认删除", f"确定要删除 {item_text} 吗？"):
            return
        
        try:
            if item_values[0] == '文件夹':
                shutil.rmtree(full_path)
            else:
                os.remove(full_path)
            
            self.log_message(f"已删除: {full_path}")
            self.refresh_file_browser()
        except Exception as e:
            self.log_message(f"删除失败: {str(e)}")
            messagebox.showerror("错误", f"删除失败: {str(e)}")
    
    def edit_selected_file(self):
        """编辑选中的文件"""
        selected_item = self.tree.selection()
        if not selected_item:
            return
        
        item = selected_item[0]
        item_text = self.tree.item(item, 'text')
        item_values = self.tree.item(item, 'values')
        
        # 检查是否是文件夹
        if item_values[0] == '文件夹':
            messagebox.showerror("错误", "不能编辑文件夹")
            return
        
        # 获取完整路径
        full_path = self.get_full_path(item)
        
        # 读取文件内容
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            messagebox.showerror("错误", f"无法读取文件: {str(e)}")
            return
        
        # 创建编辑窗口
        edit_window = tk.Toplevel(self.root)
        edit_window.title(f"编辑文件: {item_text}")
        
        # 文本编辑区域
        text_area = scrolledtext.ScrolledText(edit_window, wrap=tk.WORD, width=80, height=30)
        text_area.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        text_area.insert(tk.END, content)
        
        # 保存按钮
        def save_changes():
            new_content = text_area.get("1.0", tk.END)
            try:
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                self.log_message(f"已更新文件: {full_path}")
                edit_window.destroy()
            except Exception as e:
                messagebox.showerror("错误", f"保存失败: {str(e)}")
        
        save_btn = tk.Button(edit_window, text="保存", command=save_changes)
        save_btn.pack(pady=5)
    
    def format_size(self, size):
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
    
    def start_server(self):
        host = self.host_entry.get()
        port = self.port_entry.get()
        
        try:
            port = int(port)
        except ValueError:
            messagebox.showerror("错误", "端口号必须是数字")
            return
        
        # 在后台线程中启动服务器
        server_thread = threading.Thread(
            target=self.app.run,
            kwargs={'host': '0.0.0.0', 'port': port, 'debug': False, 'use_reloader': False},
            daemon=True
        )
        server_thread.start()
        
        self.status_bar.config(text="服务器运行中...")
        self.log_message(f"服务器已启动，监听 {host}:{port}")
        self.log_message(f"默认保存目录: {self.default_save_dir}")
        self.log_message(f"当前保存目录剩余空间: {self.get_free_space(self.dir_entry.get())}GB")
        self.log_message("等待连接...")
        
        # 刷新文件浏览器
        self.refresh_file_browser()
    
    def log_message(self, message):
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.see(tk.END)
        self.root.update()

if __name__ == '__main__':
    root = tk.Tk()
    app = FileServerApp(root)
    # 在界面创建完成后再启动服务器
    app.start_server()
    root.mainloop()