"""Progress display system for HLS downloader using tqdm."""

import time
from typing import Dict, Optional, Any
from threading import Lock
from tqdm import tqdm
from tqdm.contrib.concurrent import thread_map

from .models import DownloadStats


class ProgressDisplay:
    """Modern progress display system with main and worker progress bars."""
    
    def __init__(self):
        """Initialize the progress display system."""
        self._main_progress: Optional[tqdm] = None
        self._worker_progresses: Dict[int, tqdm] = {}
        self._stats: Optional[DownloadStats] = None
        self._lock = Lock()
        self._start_time: Optional[float] = None
        self._last_update_time: float = 0
        self._update_interval: float = 0.1  # Update every 100ms
        
    def create_main_progress(self, total: int, desc: str = "总体进度") -> tqdm:
        """
        Create the main progress bar for overall download progress.
        
        Args:
            total: Total number of segments to download
            desc: Description for the progress bar
            
        Returns:
            The main progress bar instance
        """
        with self._lock:
            if self._main_progress is not None:
                self._main_progress.close()
                
            self._main_progress = tqdm(
                total=total,
                desc=desc,
                unit="个",
                unit_scale=False,
                dynamic_ncols=True,
                bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]",
                position=0,
                leave=True
            )
            self._start_time = time.time()
            return self._main_progress
    
    def create_worker_progress(self, worker_id: int, desc: str = None) -> tqdm:
        """
        Create a worker progress bar for individual download threads.
        
        Args:
            worker_id: Unique identifier for the worker
            desc: Description for the worker progress bar
            
        Returns:
            The worker progress bar instance
        """
        if desc is None:
            desc = f"工作线程 {worker_id}"
            
        with self._lock:
            if worker_id in self._worker_progresses:
                self._worker_progresses[worker_id].close()
                
            worker_progress = tqdm(
                desc=desc,
                unit="B",
                unit_scale=True,
                unit_divisor=1024,
                dynamic_ncols=True,
                bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}, {rate_fmt}]",
                position=worker_id + 1,
                leave=False
            )
            self._worker_progresses[worker_id] = worker_progress
            return worker_progress
    
    def update_main_progress(self, increment: int = 1) -> None:
        """
        Update the main progress bar.
        
        Args:
            increment: Number of segments completed
        """
        with self._lock:
            if self._main_progress is not None:
                self._main_progress.update(increment)
                current_time = time.time()
                self._last_update_time = current_time
    
    def update_worker_progress(self, worker_id: int, increment: int, total: Optional[int] = None) -> None:
        """
        Update a worker progress bar.
        
        Args:
            worker_id: Worker identifier
            increment: Bytes downloaded
            total: Total bytes for this worker (optional)
        """
        with self._lock:
            if worker_id in self._worker_progresses:
                worker_progress = self._worker_progresses[worker_id]
                if total is not None and worker_progress.total != total:
                    worker_progress.total = total
                worker_progress.update(increment)
    
    def set_worker_total(self, worker_id: int, total: int) -> None:
        """
        Set the total for a worker progress bar.
        
        Args:
            worker_id: Worker identifier
            total: Total bytes for this worker
        """
        with self._lock:
            if worker_id in self._worker_progresses:
                self._worker_progresses[worker_id].total = total
    
    def complete_worker(self, worker_id: int) -> None:
        """
        Mark a worker as completed and close its progress bar.
        
        Args:
            worker_id: Worker identifier
        """
        with self._lock:
            if worker_id in self._worker_progresses:
                worker_progress = self._worker_progresses[worker_id]
                worker_progress.close()
                del self._worker_progresses[worker_id]
    
    def update_stats(self, stats: DownloadStats) -> None:
        """
        Update download statistics and refresh display.
        
        Args:
            stats: Current download statistics
        """
        self._stats = stats
        self._update_main_progress_description()
    
    def _update_main_progress_description(self) -> None:
        """Update the main progress bar description with current stats."""
        if self._main_progress is None or self._stats is None:
            return
            
        elapsed_time = time.time() - (self._start_time or time.time())
        
        # Calculate current speed
        if elapsed_time > 0:
            current_speed = self._stats.downloaded_bytes / elapsed_time
            speed_str = self._format_bytes(current_speed) + "/s"
        else:
            speed_str = "0 B/s"
        
        # Calculate ETA
        if self._stats.downloaded_segments > 0 and self._stats.total_segments > 0:
            progress_ratio = self._stats.downloaded_segments / self._stats.total_segments
            if progress_ratio > 0:
                eta_seconds = elapsed_time * (1 - progress_ratio) / progress_ratio
                eta_str = self._format_time(eta_seconds)
            else:
                eta_str = "未知"
        else:
            eta_str = "未知"
        
        # Update description with rich information
        desc = (f"下载进度 | "
                f"速度: {speed_str} | "
                f"已完成: {self._stats.downloaded_segments}/{self._stats.total_segments} | "
                f"预计剩余: {eta_str}")
        
        self._main_progress.set_description(desc)
    
    def display_final_stats(self) -> None:
        """Display final download statistics."""
        if self._stats is None or self._start_time is None:
            return
            
        total_time = time.time() - self._start_time
        average_speed = self._stats.downloaded_bytes / total_time if total_time > 0 else 0
        
        print(f"\n{'='*60}")
        print(f"下载完成统计:")
        print(f"  总切片数: {self._stats.total_segments}")
        print(f"  成功下载: {self._stats.downloaded_segments}")
        print(f"  失败数量: {self._stats.failed_segments}")
        print(f"  总下载量: {self._format_bytes(self._stats.downloaded_bytes)}")
        print(f"  总耗时: {self._format_time(total_time)}")
        print(f"  平均速度: {self._format_bytes(average_speed)}/s")
        print(f"{'='*60}")
    
    def close_all_progress(self) -> None:
        """Close all progress bars and clean up resources."""
        with self._lock:
            # Close main progress bar
            if self._main_progress is not None:
                self._main_progress.close()
                self._main_progress = None
            
            # Close all worker progress bars
            for worker_progress in self._worker_progresses.values():
                worker_progress.close()
            self._worker_progresses.clear()
    
    def set_error_status(self, error_msg: str) -> None:
        """
        Set error status on the main progress bar.
        
        Args:
            error_msg: Error message to display
        """
        with self._lock:
            if self._main_progress is not None:
                self._main_progress.set_description(f"错误: {error_msg}")
    
    def pause_display(self) -> None:
        """Pause the progress display (useful during error handling)."""
        with self._lock:
            if self._main_progress is not None:
                self._main_progress.disable = True
            for worker_progress in self._worker_progresses.values():
                worker_progress.disable = True
    
    def resume_display(self) -> None:
        """Resume the progress display."""
        with self._lock:
            if self._main_progress is not None:
                self._main_progress.disable = False
            for worker_progress in self._worker_progresses.values():
                worker_progress.disable = False
    
    @staticmethod
    def _format_bytes(bytes_value: float) -> str:
        """Format bytes into human readable format."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_value < 1024.0:
                return f"{bytes_value:.1f} {unit}"
            bytes_value /= 1024.0
        return f"{bytes_value:.1f} PB"
    
    @staticmethod
    def _format_time(seconds: float) -> str:
        """Format seconds into human readable time format."""
        if seconds < 60:
            return f"{seconds:.1f}秒"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes}分{secs}秒"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}小时{minutes}分钟"
    
    @property
    def is_active(self) -> bool:
        """Check if any progress bars are currently active."""
        with self._lock:
            return (self._main_progress is not None or 
                   len(self._worker_progresses) > 0)
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - clean up all progress bars."""
        self.close_all_progress()
        if exc_type is None:
            self.display_final_stats()


class MultiThreadProgressWrapper:
    """Wrapper for tqdm's thread_map functionality with custom progress display."""
    
    def __init__(self, progress_display: ProgressDisplay):
        """
        Initialize the multi-thread progress wrapper.
        
        Args:
            progress_display: The main progress display instance
        """
        self.progress_display = progress_display
    
    def map(self, func, iterable, max_workers: int = None, desc: str = "并发处理"):
        """
        Execute function over iterable using thread pool with progress display.
        
        Args:
            func: Function to execute
            iterable: Iterable to process
            max_workers: Maximum number of worker threads
            desc: Description for the progress bar
            
        Returns:
            Results from the function execution
        """
        return thread_map(
            func, 
            iterable,
            max_workers=max_workers,
            desc=desc,
            unit="个",
            dynamic_ncols=True,
            leave=False
        )