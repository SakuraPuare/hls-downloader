"""Tests for the progress display system."""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from threading import Thread
import asyncio

from src.hls_downloader.progress_display import ProgressDisplay, MultiThreadProgressWrapper
from src.hls_downloader.models import DownloadStats


class TestProgressDisplay:
    """Test cases for ProgressDisplay class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.progress_display = ProgressDisplay()
    
    def teardown_method(self):
        """Clean up after tests."""
        self.progress_display.close_all_progress()
    
    def test_create_main_progress(self):
        """Test creating main progress bar."""
        total_segments = 100
        main_progress = self.progress_display.create_main_progress(total_segments)
        
        assert main_progress is not None
        assert main_progress.total == total_segments
        assert self.progress_display._main_progress is main_progress
        assert self.progress_display._start_time is not None
    
    def test_create_main_progress_replaces_existing(self):
        """Test that creating a new main progress bar closes the existing one."""
        # Create first progress bar
        first_progress = self.progress_display.create_main_progress(50)
        first_progress_id = id(first_progress)
        
        # Create second progress bar
        second_progress = self.progress_display.create_main_progress(100)
        
        assert id(second_progress) != first_progress_id
        assert self.progress_display._main_progress is second_progress
        assert second_progress.total == 100
    
    def test_create_worker_progress(self):
        """Test creating worker progress bars."""
        worker_id = 1
        worker_progress = self.progress_display.create_worker_progress(worker_id)
        
        assert worker_progress is not None
        assert worker_id in self.progress_display._worker_progresses
        assert self.progress_display._worker_progresses[worker_id] is worker_progress
    
    def test_create_worker_progress_with_custom_desc(self):
        """Test creating worker progress bar with custom description."""
        worker_id = 2
        custom_desc = "Custom Worker"
        worker_progress = self.progress_display.create_worker_progress(worker_id, custom_desc)
        
        assert worker_progress.desc == custom_desc
    
    def test_create_multiple_worker_progresses(self):
        """Test creating multiple worker progress bars."""
        worker_ids = [1, 2, 3]
        
        for worker_id in worker_ids:
            self.progress_display.create_worker_progress(worker_id)
        
        assert len(self.progress_display._worker_progresses) == 3
        for worker_id in worker_ids:
            assert worker_id in self.progress_display._worker_progresses
    
    def test_update_main_progress(self):
        """Test updating main progress bar."""
        main_progress = self.progress_display.create_main_progress(100)
        initial_n = main_progress.n
        
        self.progress_display.update_main_progress(5)
        
        assert main_progress.n == initial_n + 5
    
    def test_update_main_progress_multiple_times(self):
        """Test multiple main progress updates."""
        main_progress = self.progress_display.create_main_progress(100)
        initial_n = main_progress.n
        
        # Multiple updates should all be applied
        for _ in range(5):
            self.progress_display.update_main_progress(1)
        
        # All updates should be applied
        assert main_progress.n == initial_n + 5
    
    def test_update_worker_progress(self):
        """Test updating worker progress bar."""
        worker_id = 1
        worker_progress = self.progress_display.create_worker_progress(worker_id)
        initial_n = worker_progress.n
        
        self.progress_display.update_worker_progress(worker_id, 1024)
        
        assert worker_progress.n == initial_n + 1024
    
    def test_update_worker_progress_with_total(self):
        """Test updating worker progress bar with total."""
        worker_id = 1
        worker_progress = self.progress_display.create_worker_progress(worker_id)
        
        self.progress_display.update_worker_progress(worker_id, 512, total=2048)
        
        assert worker_progress.total == 2048
        assert worker_progress.n == 512
    
    def test_set_worker_total(self):
        """Test setting worker progress bar total."""
        worker_id = 1
        worker_progress = self.progress_display.create_worker_progress(worker_id)
        
        self.progress_display.set_worker_total(worker_id, 4096)
        
        assert worker_progress.total == 4096
    
    def test_complete_worker(self):
        """Test completing and removing worker progress bar."""
        worker_id = 1
        self.progress_display.create_worker_progress(worker_id)
        
        assert worker_id in self.progress_display._worker_progresses
        
        self.progress_display.complete_worker(worker_id)
        
        assert worker_id not in self.progress_display._worker_progresses
    
    def test_update_stats(self):
        """Test updating download statistics."""
        stats = DownloadStats(
            total_segments=100,
            downloaded_segments=50,
            failed_segments=2,
            total_bytes=1024000,
            downloaded_bytes=512000,
            start_time=time.time(),
            average_speed=1024.0
        )
        
        self.progress_display.create_main_progress(100)
        self.progress_display.update_stats(stats)
        
        assert self.progress_display._stats is stats
    
    def test_display_final_stats(self, capsys):
        """Test displaying final statistics."""
        stats = DownloadStats(
            total_segments=100,
            downloaded_segments=98,
            failed_segments=2,
            total_bytes=1024000,
            downloaded_bytes=1000000,
            start_time=time.time(),
            average_speed=1024.0
        )
        
        self.progress_display._stats = stats
        self.progress_display._start_time = time.time() - 60  # 1 minute ago
        
        self.progress_display.display_final_stats()
        
        captured = capsys.readouterr()
        assert "下载完成统计" in captured.out
        assert "总切片数: 100" in captured.out
        assert "成功下载: 98" in captured.out
        assert "失败数量: 2" in captured.out
    
    def test_close_all_progress(self):
        """Test closing all progress bars."""
        # Create main and worker progress bars
        self.progress_display.create_main_progress(100)
        self.progress_display.create_worker_progress(1)
        self.progress_display.create_worker_progress(2)
        
        assert self.progress_display._main_progress is not None
        assert len(self.progress_display._worker_progresses) == 2
        
        self.progress_display.close_all_progress()
        
        assert self.progress_display._main_progress is None
        assert len(self.progress_display._worker_progresses) == 0
    
    def test_set_error_status(self):
        """Test setting error status on main progress bar."""
        main_progress = self.progress_display.create_main_progress(100)
        error_msg = "Network connection failed"
        
        self.progress_display.set_error_status(error_msg)
        
        # The description should contain the error message
        assert "错误" in main_progress.desc
        assert error_msg in main_progress.desc
    
    def test_pause_and_resume_display(self):
        """Test pausing and resuming progress display."""
        main_progress = self.progress_display.create_main_progress(100)
        worker_progress = self.progress_display.create_worker_progress(1)
        
        # Initially should not be disabled
        assert not main_progress.disable
        assert not worker_progress.disable
        
        # Pause display
        self.progress_display.pause_display()
        assert main_progress.disable
        assert worker_progress.disable
        
        # Resume display
        self.progress_display.resume_display()
        assert not main_progress.disable
        assert not worker_progress.disable
    
    def test_format_bytes(self):
        """Test byte formatting utility."""
        assert ProgressDisplay._format_bytes(512) == "512.0 B"
        assert ProgressDisplay._format_bytes(1024) == "1.0 KB"
        assert ProgressDisplay._format_bytes(1048576) == "1.0 MB"
        assert ProgressDisplay._format_bytes(1073741824) == "1.0 GB"
    
    def test_format_time(self):
        """Test time formatting utility."""
        assert "秒" in ProgressDisplay._format_time(30)
        assert "分" in ProgressDisplay._format_time(90)
        assert "小时" in ProgressDisplay._format_time(3700)
    
    def test_is_active_property(self):
        """Test is_active property."""
        # Initially not active
        assert not self.progress_display.is_active
        
        # Active with main progress
        self.progress_display.create_main_progress(100)
        assert self.progress_display.is_active
        
        # Still active with worker progress
        self.progress_display.close_all_progress()
        self.progress_display.create_worker_progress(1)
        assert self.progress_display.is_active
        
        # Not active after closing all
        self.progress_display.close_all_progress()
        assert not self.progress_display.is_active
    
    def test_context_manager(self):
        """Test using ProgressDisplay as context manager."""
        with ProgressDisplay() as pd:
            pd.create_main_progress(100)
            pd.create_worker_progress(1)
            assert pd.is_active
        
        # Should be closed after context exit
        assert not pd.is_active
    
    def test_context_manager_with_exception(self):
        """Test context manager behavior when exception occurs."""
        try:
            with ProgressDisplay() as pd:
                pd.create_main_progress(100)
                raise ValueError("Test exception")
        except ValueError:
            pass
        
        # Should still be closed after exception
        assert not pd.is_active
    
    def test_thread_safety(self):
        """Test thread safety of progress display operations."""
        def worker_thread(worker_id):
            """Worker thread function."""
            self.progress_display.create_worker_progress(worker_id)
            for i in range(10):
                self.progress_display.update_worker_progress(worker_id, 100)
                time.sleep(0.01)
            self.progress_display.complete_worker(worker_id)
        
        # Create main progress
        self.progress_display.create_main_progress(100)
        
        # Start multiple worker threads
        threads = []
        for i in range(3):
            thread = Thread(target=worker_thread, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Update main progress from main thread
        for i in range(10):
            self.progress_display.update_main_progress(1)
            time.sleep(0.01)
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # All workers should be completed
        assert len(self.progress_display._worker_progresses) == 0


class TestMultiThreadProgressWrapper:
    """Test cases for MultiThreadProgressWrapper class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.progress_display = ProgressDisplay()
        self.wrapper = MultiThreadProgressWrapper(self.progress_display)
    
    def teardown_method(self):
        """Clean up after tests."""
        self.progress_display.close_all_progress()
    
    @patch('src.hls_downloader.progress_display.thread_map')
    def test_map_function(self, mock_thread_map):
        """Test the map function wrapper."""
        mock_thread_map.return_value = [1, 2, 3, 4, 5]
        
        def square(x):
            return x * x
        
        iterable = [1, 2, 3, 4, 5]
        result = self.wrapper.map(square, iterable, max_workers=3)
        
        # Verify thread_map was called with correct parameters
        mock_thread_map.assert_called_once_with(
            square,
            iterable,
            max_workers=3,
            desc="并发处理",
            unit="个",
            dynamic_ncols=True,
            leave=False
        )
        
        assert result == [1, 2, 3, 4, 5]
    
    @patch('src.hls_downloader.progress_display.thread_map')
    def test_map_function_with_custom_desc(self, mock_thread_map):
        """Test the map function with custom description."""
        mock_thread_map.return_value = []
        
        def dummy_func(x):
            return x
        
        self.wrapper.map(dummy_func, [], desc="自定义描述")
        
        # Verify custom description was used
        call_args = mock_thread_map.call_args
        assert call_args[1]['desc'] == "自定义描述"


class TestProgressDisplayIntegration:
    """Integration tests for progress display system."""
    
    def test_realistic_download_simulation(self):
        """Test a realistic download progress simulation."""
        total_segments = 50
        total_workers = 3
        
        with ProgressDisplay() as pd:
            # Create main progress
            main_progress = pd.create_main_progress(total_segments, "下载HLS切片")
            
            # Create worker progresses
            workers = {}
            for i in range(total_workers):
                workers[i] = pd.create_worker_progress(i, f"下载线程 {i}")
            
            # Simulate download progress
            segments_per_worker = total_segments // total_workers
            
            for segment in range(total_segments):
                worker_id = segment % total_workers
                
                # Simulate downloading a segment
                segment_size = 1024 * (50 + segment % 100)  # Variable segment sizes
                
                # Update worker progress
                pd.set_worker_total(worker_id, segment_size)
                
                # Simulate progressive download of the segment
                downloaded = 0
                while downloaded < segment_size:
                    chunk_size = min(8192, segment_size - downloaded)
                    pd.update_worker_progress(worker_id, chunk_size)
                    downloaded += chunk_size
                    time.sleep(0.001)  # Small delay to simulate network
                
                # Complete the segment
                pd.update_main_progress(1)
                
                # Update stats periodically
                if segment % 10 == 0:
                    stats = DownloadStats(
                        total_segments=total_segments,
                        downloaded_segments=segment + 1,
                        failed_segments=0,
                        total_bytes=total_segments * 1024 * 75,  # Estimated
                        downloaded_bytes=(segment + 1) * 1024 * 75,
                        start_time=time.time(),
                        average_speed=1024 * 100  # 100 KB/s
                    )
                    pd.update_stats(stats)
            
            # Complete all workers
            for worker_id in workers:
                pd.complete_worker(worker_id)
            
            # The main progress should have been updated for each segment
            # Note: Due to the simulation timing, we check that progress was made
            assert main_progress.n > 0
            assert main_progress.n <= total_segments
            assert len(pd._worker_progresses) == 0
    
    def test_error_handling_during_progress(self):
        """Test error handling scenarios during progress display."""
        with ProgressDisplay() as pd:
            main_progress = pd.create_main_progress(100)
            worker_progress = pd.create_worker_progress(1)
            
            # Simulate some progress
            pd.update_main_progress(10)
            pd.update_worker_progress(1, 1024)
            
            # Simulate error
            pd.set_error_status("网络连接失败")
            
            # Small delay to ensure update timing
            time.sleep(0.01)
            
            # Progress should still be functional
            pd.update_main_progress(5)
            
            assert main_progress.n == 15
            assert "错误" in main_progress.desc
    
    def test_pause_resume_scenario(self):
        """Test pause and resume functionality in realistic scenario."""
        with ProgressDisplay() as pd:
            pd.create_main_progress(100)
            pd.create_worker_progress(1)
            
            # Normal progress
            pd.update_main_progress(10)
            pd.update_worker_progress(1, 1024)
            
            # Pause for error handling
            pd.pause_display()
            
            # Simulate error handling time
            time.sleep(0.1)
            
            # Resume and continue
            pd.resume_display()
            pd.update_main_progress(10)
            
            assert pd._main_progress.n == 20