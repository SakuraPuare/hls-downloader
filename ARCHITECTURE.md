# HLS Downloader 项目架构文档

## 架构重构总结

本项目已完成架构重构，将原来的单一模块结构拆分为清晰的分层架构，提高了代码的可维护性和可扩展性。

## 新架构结构

```
src/hls_downloader/
├── __init__.py                 # 主包入口，导出公共API
├── cli.py                      # 命令行接口
├── core/                       # 核心功能模块
│   ├── __init__.py
│   ├── detector.py             # HLS切片探测器
│   ├── downloader.py           # 异步下载器
│   ├── manager.py              # 下载管理器（原download_manager.py）
│   ├── merger.py               # 视频合并器
│   ├── progress.py             # 进度显示（原progress_display.py）
│   └── state_manager.py        # 状态管理器
├── models/                     # 数据模型
│   ├── __init__.py
│   ├── config.py               # 配置数据模型
│   ├── segment.py              # 切片信息模型
│   ├── stats.py                # 统计数据模型
│   └── state.py                # 下载状态模型
├── exceptions/                 # 异常处理体系
│   ├── __init__.py
│   ├── base.py                 # 基础异常类
│   ├── download.py             # 下载相关异常
│   ├── manager.py              # 管理器异常
│   ├── merger.py               # 合并器异常
│   └── validation.py           # 验证异常
├── interfaces/                 # 接口定义
│   ├── __init__.py
│   ├── detector.py             # 探测器接口
│   ├── downloader.py           # 下载器接口
│   ├── merger.py               # 合并器接口
│   └── progress.py             # 进度显示接口
├── config/                     # 配置管理
│   ├── __init__.py
│   ├── loader.py               # 配置加载器
│   └── settings.py             # 默认配置
└── utils/                      # 工具函数
    ├── __init__.py
    ├── error_handler.py         # 错误处理工具（原error_handler.py）
    ├── file_utils.py            # 文件工具
    ├── logging_config.py        # 日志配置（原logging_config.py）
    ├── network_utils.py         # 网络工具
    ├── resume_validator.py      # 断点续传验证（原resume_validator.py）
    ├── user_messages.py         # 用户消息显示（原user_messages.py）
    └── validation.py            # 验证工具
```

## 架构设计原则

### 1. 分层架构
- **接口层 (interfaces/)**: 定义组件间的契约
- **核心层 (core/)**: 实现主要业务逻辑
- **模型层 (models/)**: 数据结构和业务对象
- **工具层 (utils/)**: 通用工具函数
- **配置层 (config/)**: 配置管理
- **异常层 (exceptions/)**: 统一异常处理

### 2. 关注点分离
- **数据模型**: 按功能域分离（配置、切片、统计、状态）
- **异常处理**: 按异常类型分类（下载、管理、合并、验证）
- **工具函数**: 按功能分组（文件、网络、验证）

### 3. 依赖方向
```
CLI → Core → Models + Interfaces
     ↓
   Utils ← Config ← Exceptions
```

## 主要改进

### 1. 模块化设计
- 将大型单一文件拆分为功能明确的小模块
- 每个模块职责单一，便于测试和维护

### 2. 接口驱动
- 定义清晰的接口契约
- 支持依赖注入和模拟测试
- 便于扩展和替换实现

### 3. 统一异常体系
- 分层的异常继承结构
- 统一的错误处理机制
- 更好的错误信息和调试支持

### 4. 配置管理
- 支持多种配置源
- 配置验证和默认值处理
- 配置文件的加载和保存

### 5. 工具函数提取
- 通用功能的复用
- 降低模块间耦合
- 便于单元测试

## 使用示例

### 基本用法（保持向后兼容）
```python
from hls_downloader import DownloadManager, DownloadConfig

config = DownloadConfig(max_concurrent=5)
manager = DownloadManager(config)
await manager.download("https://example.com/playlist.m3u8", "output/")
```

### 使用新架构的灵活性
```python
from hls_downloader.core import HLSDetector, AsyncDownloader
from hls_downloader.models import DownloadConfig
from hls_downloader.config import ConfigLoader

# 使用配置加载器
config_loader = ConfigLoader()
config = config_loader.load("custom_config.json")

# 独立使用各个组件
detector = HLSDetector()
downloader = AsyncDownloader(config)

# 探测切片
segments = await detector.detect_segments("https://example.com/seg{}.ts")

# 下载切片
stats = await downloader.download_segments(segments, Path("output/"))
```

## 测试改进

新架构支持更好的测试：

1. **单元测试**: 每个模块可以独立测试
2. **接口模拟**: 使用接口进行依赖注入和模拟
3. **集成测试**: 清晰的模块边界便于集成测试

## 迁移指南

### 对于现有用户
- 主要API保持不变，现有代码无需修改
- 导入路径已更新，但向后兼容

### 对于开发者
- 新功能开发应遵循新架构
- 使用接口定义新组件
- 遵循分层原则添加新功能

## 未来扩展

新架构为以下扩展提供了良好基础：

1. **插件系统**: 通过接口实现插件机制
2. **多协议支持**: 扩展探测器支持其他流媒体协议
3. **存储后端**: 支持不同的存储方式（本地、云存储等）
4. **监控集成**: 添加监控和指标收集
5. **GUI界面**: 基于核心模块构建图形界面

## 总结

通过这次架构重构，项目实现了：
- ✅ 更清晰的代码组织
- ✅ 更好的可维护性
- ✅ 更强的可扩展性
- ✅ 更完善的测试支持
- ✅ 更统一的错误处理
- ✅ 更灵活的配置管理

新架构为项目的长期发展奠定了坚实基础。
