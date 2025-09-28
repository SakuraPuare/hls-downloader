# Design Document

## Overview

HLS下载器是一个基于Python异步编程的流媒体切片下载工具。系统采用模块化设计，包含切片探测、并发下载、进度显示和文件合并四个核心模块。使用uv进行现代化的Python环境管理，httpx作为HTTP客户端库，tqdm提供现代化进度显示，asyncio实现并发控制，ffmpeg进行最终的文件合并。项目采用二分查找算法优化切片探测效率。

## Architecture

系统采用分层架构设计：

```
┌─────────────────────────────────────┐
│           CLI Interface             │  命令行接口层
├─────────────────────────────────────┤
│         Download Manager            │  下载管理层
├─────────────────────────────────────┤
│  ┌─────────────┐ ┌─────────────────┐ │
│  │   Detector  │ │   Downloader    │ │  核心业务层
│  └─────────────┘ └─────────────────┘ │
├─────────────────────────────────────┤
│  ┌─────────────┐ ┌─────────────────┐ │
│  │   Progress  │ │     Merger      │ │  工具服务层
│  │   Display   │ │                 │ │
│  └─────────────┘ └─────────────────┘ │
├─────────────────────────────────────┤
│        HTTP Client (httpx)          │  网络传输层
└─────────────────────────────────────┘
```

## Components and Interfaces

### 1. HLSDetector (切片探测器)

**职责：** 自动探测HLS切片的可用范围

**接口：**
```python
class HLSDetector:
    async def detect_segments(self, url_template: str) -> List[str]
    async def _binary_search_max_segment(self, url_pattern: str) -> int
    async def _check_segment_exists(self, url: str) -> bool
    async def _batch_check_segments(self, urls: List[str]) -> List[bool]
    def _extract_url_pattern(self, url: str) -> Tuple[str, str, str]
    def _generate_segment_url(self, pattern: str, index: int) -> str
```

**二分探测算法详细设计：**
```python
async def _binary_search_max_segment(self, url_pattern: str) -> int:
    """
    使用二分查找确定最大有效切片索引
    
    算法步骤：
    1. 快速探测：检查 [1, 10, 100, 1000, 10000] 确定大致范围
    2. 二分查找：在确定范围内精确定位最后一个有效切片
    3. 边界处理：处理连续缺失切片的情况
    """
    # 第一阶段：快速确定上界
    upper_bound = await self._find_upper_bound(url_pattern)
    
    # 第二阶段：二分查找精确位置
    left, right = 1, upper_bound
    max_valid = 0
    
    while left <= right:
        mid = (left + right) // 2
        batch_urls = [self._generate_segment_url(url_pattern, i) 
                     for i in range(max(1, mid-2), mid+3)]
        exists_list = await self._batch_check_segments(batch_urls)
        
        if exists_list[2]:  # mid exists
            max_valid = mid
            left = mid + 1
        else:
            right = mid - 1
    
    return max_valid
```

**实现策略：**
- 解析URL模板，提取基础URL、文件名模式和扩展名
- **二分查找优化探测**：
  - 首先快速探测较大的数值（如1000, 2000）确定上界
  - 使用二分查找精确定位最后一个有效切片
  - 并发验证切片存在性，减少总探测时间
  - 智能处理连续缺失切片的情况
- 支持多种URL模式（数字递增、零填充、十六进制等）
- 缓存探测结果，避免重复请求

### 2. AsyncDownloader (异步下载器)

**职责：** 管理并发下载任务

**接口：**
```python
class AsyncDownloader:
    async def download_segments(self, urls: List[str], output_dir: str) -> None
    async def _download_single_segment(self, session: httpx.AsyncClient, url: str, filepath: str) -> None
    async def _retry_download(self, session: httpx.AsyncClient, url: str, filepath: str, max_retries: int) -> None
```

**实现策略：**
- 使用asyncio.Semaphore控制并发数量
- 实现指数退避重试机制
- 支持断点续传（Range请求）
- 文件完整性校验（文件大小验证）

### 3. ProgressDisplay (进度显示器)

**职责：** 提供现代化的下载进度显示

**接口：**
```python
class ProgressDisplay:
    def create_main_progress(self, total: int) -> tqdm
    def create_worker_progress(self, worker_id: int) -> tqdm
    def update_progress(self, progress_bar: tqdm, increment: int) -> None
    def close_all_progress(self) -> None
```

**实现策略：**
- 主进度条显示总体下载进度
- 多个工作进度条显示各并发任务状态
- 实时显示下载速度、ETA、已完成数量
- 支持动态调整显示格式

### 4. VideoMerger (视频合并器)

**职责：** 使用ffmpeg合并切片文件

**接口：**
```python
class VideoMerger:
    async def merge_segments(self, segment_dir: str, output_file: str) -> None
    def _generate_concat_file(self, segment_files: List[str]) -> str
    def _check_ffmpeg_available(self) -> bool
```

**实现策略：**
- 生成ffmpeg concat文件列表
- 异步执行ffmpeg命令
- 监控合并进度
- 错误处理和日志记录

### 5. DownloadManager (下载管理器)

**职责：** 协调各组件，管理整个下载流程

**接口：**
```python
class DownloadManager:
    async def download_hls(self, url: str, output_dir: str, config: DownloadConfig) -> None
    async def _setup_output_directory(self, output_dir: str) -> None
    def _validate_config(self, config: DownloadConfig) -> None
```

## Data Models

### DownloadConfig
```python
@dataclass
class DownloadConfig:
    max_concurrent: int = 10          # 最大并发数
    max_retries: int = 3              # 最大重试次数
    timeout: int = 30                 # 请求超时时间
    chunk_size: int = 8192           # 下载块大小
    auto_merge: bool = True          # 自动合并
    cleanup_segments: bool = False    # 清理切片文件
    output_format: str = "mp4"       # 输出格式
```

### SegmentInfo
```python
@dataclass
class SegmentInfo:
    url: str                         # 切片URL
    index: int                       # 切片索引
    filename: str                    # 本地文件名
    size: Optional[int] = None       # 文件大小
    downloaded: bool = False         # 下载状态
```

### DownloadStats
```python
@dataclass
class DownloadStats:
    total_segments: int              # 总切片数
    downloaded_segments: int         # 已下载数
    failed_segments: int             # 失败数
    total_bytes: int                 # 总字节数
    downloaded_bytes: int            # 已下载字节数
    start_time: float               # 开始时间
    average_speed: float            # 平均速度
```

## Error Handling

### 错误分类和处理策略

1. **网络错误**
   - 连接超时：自动重试，指数退避
   - HTTP错误：根据状态码决定重试策略
   - DNS解析失败：记录错误，跳过该切片

2. **文件系统错误**
   - 磁盘空间不足：暂停下载，提示用户
   - 权限错误：提供清晰的错误信息
   - 路径不存在：自动创建目录

3. **ffmpeg错误**
   - 未安装：提供安装指导
   - 合并失败：保留切片文件，提供手动合并指导
   - 格式不支持：提供格式转换建议

### 错误恢复机制

```python
class ErrorHandler:
    async def handle_download_error(self, error: Exception, segment: SegmentInfo) -> bool
    async def handle_merge_error(self, error: Exception, segments_dir: str) -> None
    def log_error(self, error: Exception, context: str) -> None
```

## Testing Strategy

### 单元测试
- **HLSDetector测试**：模拟不同URL模式的探测
- **AsyncDownloader测试**：测试并发下载和重试机制
- **ProgressDisplay测试**：验证进度显示逻辑
- **VideoMerger测试**：测试ffmpeg调用和错误处理

### 集成测试
- **端到端下载测试**：使用测试HLS流进行完整下载流程测试
- **错误场景测试**：模拟网络中断、磁盘满等异常情况
- **性能测试**：测试不同并发数下的下载性能

### 开发环境和工具
- **uv**：现代化Python包管理和虚拟环境工具
- **pyproject.toml**：项目配置和依赖管理
- **pytest**：主要测试框架
- **pytest-asyncio**：异步测试支持
- **aioresponses**：模拟HTTP响应
- **pytest-mock**：模拟外部依赖

### 测试数据
- 创建测试用的HLS切片文件
- 模拟不同的URL模式和切片数量
- 准备各种错误场景的测试用例

## Performance Considerations

### 并发控制
- 默认并发数设置为10，可根据网络条件调整
- 使用连接池复用HTTP连接
- 实现自适应并发数调整机制

### 内存管理
- 流式下载，避免将大文件完全加载到内存
- 及时释放已完成任务的资源
- 监控内存使用情况

### 网络优化
- 支持HTTP/2多路复用
- 实现智能重试策略
- 连接超时和读取超时分别设置

## Security Considerations

### 输入验证
- URL格式验证
- 文件路径安全检查
- 参数范围验证

### 文件安全
- 防止路径遍历攻击
- 限制下载文件大小
- 验证文件类型

### 网络安全
- 支持HTTPS
- 验证SSL证书
- 防止SSRF攻击