import os 
import re 
import subprocess 
import tkinter as tk 
from tkinter import filedialog, messagebox, ttk
from scrapy.crawler import CrawlerProcess 
from scrapy.utils.project import get_project_settings 
from scrapy import Spider, Request 
import requests 
from urllib.parse import urlparse, urljoin 
import m3u8 
from concurrent.futures import ThreadPoolExecutor 

class UniversalSpider(Spider):
    name = "universal_spider"
    
    def __init__(self, start_url=None, output_dir=None, *args, **kwargs):
        super(UniversalSpider, self).__init__(*args, **kwargs)
        self.start_urls = [start_url] if start_url else []
        self.output_dir = output_dir 
        self.allowed_domains = [urlparse(start_url).netloc] if start_url else []
        self.visited_urls = set()
        self.resource_extensions = {
            # 图片 
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg',
            # 视频 
            '.mp4', '.webm', '.mov', '.avi', '.mkv', '.flv', '.m3u8',
            # 音频 
            '.mp3', '.wav', '.ogg', '.m4a', '.flac',
            # 文档 
            '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
            # 压缩文件 
            '.zip', '.rar', '.7z', '.tar', '.gz'
        }
        self.executor = ThreadPoolExecutor(max_workers=5)
    
    def parse(self, response):
        if response.url in self.visited_urls: 
            return 
        self.visited_urls.add(response.url) 
        
        # 保存HTML页面 
        self.save_resource(response.url, response.body, '.html')
        
        # 提取并处理所有链接 
        for link in response.css('a::attr(href)').getall(): 
            absolute_url = self.make_absolute_url(response.url, link)
            if self.is_same_domain(absolute_url): 
                if self.is_resource_link(absolute_url): 
                    yield Request(absolute_url, callback=self.save_resource_callback) 
                else:
                    yield Request(absolute_url, callback=self.parse) 
        
        # 提取并处理所有资源链接 
        for src in response.css('[src]::attr(src)').getall(): 
            absolute_url = self.make_absolute_url(response.url, src)
            if self.is_same_domain(absolute_url): 
                yield Request(absolute_url, callback=self.save_resource_callback) 
        
        # 处理M3U8文件 
        if response.url.endswith('.m3u8'): 
            self.process_m3u8(response.url, response.body) 
    
    def save_resource_callback(self, response):
        extension = self.get_extension(response.url) 
        if extension == '.m3u8':
            self.process_m3u8(response.url, response.body) 
        else:
            self.save_resource(response.url, response.body, extension)
    
    def make_absolute_url(self, base_url, relative_url):
        return urljoin(base_url, relative_url.split('#')[0].split('?')[0]) 
    
    def is_same_domain(self, url):
        if not self.allowed_domains: 
            return True 
        return urlparse(url).netloc in self.allowed_domains  
    
    def is_resource_link(self, url):
        extension = self.get_extension(url) 
        return extension in self.resource_extensions  
    
    def get_extension(self, url):
        path = urlparse(url).path 
        # 处理M3U8查询参数的情况 
        if '.m3u8' in path or 'm3u8' in url.lower(): 
            return '.m3u8'
        # 获取标准扩展名 
        _, ext = os.path.splitext(path) 
        return ext.lower() 
    
    def save_resource(self, url, content, extension):
        try:
            filename = self.generate_filename(url, extension)
            filepath = os.path.join(self.output_dir, filename)
            
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            with open(filepath, 'wb') as f:
                f.write(content) 
            
            print(f"保存资源: {filename}")
        except Exception as e:
            print(f"保存资源时出错: {e}")
    
    def generate_filename(self, url, extension):
        parsed = urlparse(url)
        path = parsed.path.lstrip('/') 
        
        # 替换特殊字符 
        path = re.sub(r'[^\w\-_.]', '_', path)
        
        # 如果没有扩展名，添加扩展名 
        if not os.path.splitext(path)[1] and extension:
            path += extension 
        
        return path 
    
    def process_m3u8(self, url, content):
        try:
            # 保存原始M3U8文件 
            self.save_resource(url, content, '.m3u8')
            
            # 解析M3U8文件 
            m3u8_obj = m3u8.loads(content.decode('utf-8')) 
            
            # 下载所有TS片段 
            base_url = url.rsplit('/', 1)[0] + '/'
            for segment in m3u8_obj.segments: 
                ts_url = urljoin(base_url, segment.uri) 
                self.executor.submit(self.download_ts, ts_url)
            
            print(f"开始下载M3U8视频片段: {url}")
        except Exception as e:
            print(f"处理M3U8文件时出错: {e}")
    
    def download_ts(self, url):
        try:
            response = requests.get(url, stream=True, timeout=30)
            if response.status_code == 200:
                filename = self.generate_filename(url, '.ts')
                filepath = os.path.join(self.output_dir, filename)
                
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                
                with open(filepath, 'wb') as f:
                    for chunk in response.iter_content(1024): 
                        f.write(chunk) 
                
                print(f"下载TS片段: {filename}")
        except Exception as e:
            print(f"下载TS片段时出错: {e}")

class ScrapyApp:
    def __init__(self, root):
        self.root = root 
        root.title("黑寡妇 - 全能网络爬虫")
        root.geometry("800x600")
        root.configure(bg='#121212')
        
        # 设置主题颜色
        self.primary_color = '#00ffaa'
        self.secondary_color = '#0077ff'
        self.dark_bg = '#121212'
        self.light_bg = '#1e1e1e'
        self.text_color = '#ffffff'
        
        # 创建UI元素 
        self.create_widgets() 
    
    def create_widgets(self):
        # 主框架
        main_frame = tk.Frame(self.root, bg=self.dark_bg)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 标题
        title_frame = tk.Frame(main_frame, bg=self.dark_bg)
        title_frame.pack(fill=tk.X, pady=(0, 20))
        
        tk.Label(
            title_frame, 
            text="黑寡妇", 
            font=('Helvetica', 24, 'bold'), 
            fg=self.primary_color, 
            bg=self.dark_bg
        ).pack(side=tk.LEFT)
        
        tk.Label(
            title_frame, 
            text="全能网络资源爬取工具", 
            font=('Helvetica', 12), 
            fg=self.text_color, 
            bg=self.dark_bg
        ).pack(side=tk.LEFT, padx=10)
        
        # 输入区域
        input_frame = tk.Frame(main_frame, bg=self.dark_bg)
        input_frame.pack(fill=tk.X, pady=(0, 15))
        
        # URL输入
        url_frame = tk.Frame(input_frame, bg=self.dark_bg)
        url_frame.pack(fill=tk.X, pady=5)
        
        tk.Label(
            url_frame, 
            text="目标网址:", 
            font=('Helvetica', 10), 
            fg=self.text_color, 
            bg=self.dark_bg
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        self.url_entry = tk.Entry(
            url_frame, 
            width=70, 
            bg=self.light_bg, 
            fg=self.text_color, 
            insertbackground=self.text_color,
            relief=tk.FLAT
        )
        self.url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # 输出目录
        dir_frame = tk.Frame(input_frame, bg=self.dark_bg)
        dir_frame.pack(fill=tk.X, pady=5)
        
        tk.Label(
            dir_frame, 
            text="保存目录:", 
            font=('Helvetica', 10), 
            fg=self.text_color, 
            bg=self.dark_bg
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        self.dir_entry = tk.Entry(
            dir_frame, 
            width=60, 
            bg=self.light_bg, 
            fg=self.text_color, 
            insertbackground=self.text_color,
            relief=tk.FLAT
        )
        self.dir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.browse_button = tk.Button(
            dir_frame,  
            text="浏览", 
            command=self.browse_directory,
            bg=self.secondary_color,
            fg='white',
            activebackground=self.primary_color,
            activeforeground='white',
            relief=tk.FLAT,
            padx=10
        )
        self.browse_button.pack(side=tk.LEFT, padx=(10, 0))
        
        # 爬取按钮
        button_frame = tk.Frame(main_frame, bg=self.dark_bg)
        button_frame.pack(fill=tk.X, pady=(10, 20))
        
        self.crawl_button = tk.Button(
            button_frame,  
            text="开始爬取", 
            command=self.start_crawling, 
            bg=self.primary_color,
            fg='black',
            activebackground='#00cc88',
            activeforeground='black',
            font=('Helvetica', 12, 'bold'),
            relief=tk.FLAT,
            padx=20,
            pady=5
        )
        self.crawl_button.pack(pady=10)
        
        # 进度条
        self.progress = ttk.Progressbar(
            button_frame,
            orient='horizontal',
            mode='determinate',
            length=400,
            style='custom.Horizontal.TProgressbar'
        )
        self.progress.pack(pady=(0, 10))
        
        # 日志输出
        log_frame = tk.Frame(main_frame, bg=self.dark_bg)
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        tk.Label(
            log_frame, 
            text="爬取日志:", 
            font=('Helvetica', 10), 
            fg=self.text_color, 
            bg=self.dark_bg
        ).pack(anchor=tk.W)
        
        self.log_text = tk.Text(
            log_frame, 
            height=15, 
            state=tk.DISABLED,
            bg=self.light_bg,
            fg=self.text_color,
            insertbackground=self.text_color,
            relief=tk.FLAT,
            wrap=tk.WORD
        )
        
        scrollbar = tk.Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.log_text.config(yscrollcommand=scrollbar.set)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # 设置自定义进度条样式
        style = ttk.Style()
        style.theme_use('clam')
        style.configure(
            'custom.Horizontal.TProgressbar',
            background=self.primary_color,
            troughcolor=self.light_bg,
            bordercolor=self.dark_bg,
            lightcolor=self.primary_color,
            darkcolor=self.primary_color
        )
        
        # 设置默认目录为当前目录下的downloads文件夹 
        default_dir = os.path.join(os.getcwd(), "downloads")
        self.dir_entry.insert(0, default_dir)
    
    def browse_directory(self):
        directory = filedialog.askdirectory() 
        if directory:
            self.dir_entry.delete(0, tk.END)
            self.dir_entry.insert(0, directory)
    
    def start_crawling(self):
        url = self.url_entry.get().strip() 
        output_dir = self.dir_entry.get().strip() 
        
        if not url:
            messagebox.showerror("错误", "请输入目标网址")
            return 
        
        if not output_dir:
            messagebox.showerror("错误", "请选择保存目录")
            return 
        
        # 创建输出目录 
        try:
            os.makedirs(output_dir, exist_ok=True)
        except Exception as e:
            messagebox.showerror("错误", f"创建目录失败: {e}")
            return 
        
        # 禁用按钮防止重复点击 
        self.crawl_button.config(state=tk.DISABLED) 
        
        # 清空日志 
        self.log_text.config(state=tk.NORMAL) 
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED) 
        
        # 重置进度条
        self.progress['value'] = 0
        
        # 在后台运行爬虫 
        self.root.after(100, lambda: self.run_spider(url, output_dir))
    
    def log_message(self, message):
        self.log_text.config(state=tk.NORMAL) 
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END) 
        self.log_text.config(state=tk.DISABLED) 
        self.root.update() 
    
    def run_spider(self, url, output_dir):
        try:
            # 配置Scrapy设置 
            settings = get_project_settings()
            settings.setdict({ 
                'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'ROBOTSTXT_OBEY': False,
                'DOWNLOAD_DELAY': 0.5,
                'CONCURRENT_REQUESTS': 5,
                'LOG_LEVEL': 'INFO',
                'FEED_FORMAT': None,
                'DEPTH_LIMIT': 3,
            })
            
            # 创建并运行爬虫 
            process = CrawlerProcess(settings)
            
            def log_callback(spider, message):
                self.log_message(message) 
            
            process.crawl( 
                UniversalSpider,
                start_url=url,
                output_dir=output_dir 
            )
            
            self.log_message(f"开始爬取: {url}")
            self.log_message(f"保存到: {output_dir}")
            
            # 模拟进度更新
            self.update_progress()
            
            process.start() 
            
            self.log_message("爬取完成!")
            messagebox.showinfo("完成", "爬取任务已完成!")
            
        except Exception as e:
            self.log_message(f"发生错误: {e}")
            messagebox.showerror("错误", f"爬取过程中发生错误: {e}")
        
        finally:
            self.crawl_button.config(state=tk.NORMAL) 
            self.progress['value'] = 100
    
    def update_progress(self):
        current = self.progress['value']
        if current < 90:  # 不要到100%，留待完成时设置
            self.progress['value'] = current + 5
            self.root.after(500, self.update_progress)

if __name__ == "__main__":
    # 检查并安装依赖 
    try:
        import scrapy 
        import m3u8 
        import requests 
    except ImportError:
        print("正在安装所需依赖...")
        subprocess.check_call(["pip", "install", "scrapy", "m3u8", "requests", "tk"])
    
    # 运行GUI应用 
    root = tk.Tk()
    app = ScrapyApp(root)
    root.mainloop()