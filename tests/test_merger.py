"""Tests for video merger functionality."""

import asyncio
import os
import subprocess
import tempfile
import unittest.mock
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.hls_downloader.merger import (
    FFmpegNotFoundError,
    MergeError,
    VideoMerger,
    VideoMergerError,
)


class TestVideoMerger:
    """Test cases for VideoMerger class."""

    @patch('shutil.which')
    @patch('subprocess.run')
    def test_init_ffmpeg_available(self, mock_run, mock_which):
        """Test VideoMerger initialization when ffmpeg is available."""
        mock_which.return_value = "/usr/bin/ffmpeg"
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        
        merger = VideoMerger()
        
        assert merger.is_available
        assert merger.ffmpeg_path == "/usr/bin/ffmpeg"
        mock_which.assert_called_once_with("ffmpeg")
        mock_run.assert_called_once()

    @patch('shutil.which')
    def test_init_ffmpeg_not_found(self, mock_which):
        """Test VideoMerger initialization when ffmpeg is not found."""
        mock_which.return_value = None
        
        with pytest.raises(FFmpegNotFoundError) as exc_info:
            VideoMerger()
        
        assert "ffmpeg not found in PATH" in str(exc_info.value)
        assert "brew install ffmpeg" in str(exc_info.value)

    @patch('shutil.which')
    @patch('subprocess.run')
    def test_init_ffmpeg_not_working(self, mock_run, mock_which):
        """Test VideoMerger initialization when ffmpeg is found but not working."""
        mock_which.return_value = "/usr/bin/ffmpeg"
        mock_run.return_value = MagicMock(returncode=1, stderr="Error message")
        
        with pytest.raises(FFmpegNotFoundError) as exc_info:
            VideoMerger()
        
        assert "ffmpeg found but not working properly" in str(exc_info.value)

    @patch('shutil.which')
    @patch('subprocess.run')
    def test_init_ffmpeg_timeout(self, mock_run, mock_which):
        """Test VideoMerger initialization when ffmpeg version check times out."""
        mock_which.return_value = "/usr/bin/ffmpeg"
        mock_run.side_effect = subprocess.TimeoutExpired("ffmpeg", 10)
        
        with pytest.raises(FFmpegNotFoundError) as exc_info:
            VideoMerger()
        
        assert "ffmpeg version check timed out" in str(exc_info.value)

    @patch('shutil.which')
    @patch('subprocess.run')
    def test_generate_concat_file_success(self, mock_run, mock_which):
        """Test successful concat file generation."""
        mock_which.return_value = "/usr/bin/ffmpeg"
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        
        merger = VideoMerger()
        
        # Create temporary segment files
        with tempfile.TemporaryDirectory() as temp_dir:
            segment_files = []
            for i in range(3):
                segment_path = os.path.join(temp_dir, f"segment_{i}.ts")
                Path(segment_path).touch()
                segment_files.append(segment_path)
            
            concat_file = merger._generate_concat_file(segment_files)
            
            try:
                assert os.path.exists(concat_file)
                
                # Verify concat file content
                with open(concat_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                for segment_file in segment_files:
                    abs_path = os.path.abspath(segment_file)
                    assert f"file '{abs_path}'" in content
                    
            finally:
                if os.path.exists(concat_file):
                    os.unlink(concat_file)

    @patch('shutil.which')
    @patch('subprocess.run')
    def test_generate_concat_file_empty_list(self, mock_run, mock_which):
        """Test concat file generation with empty segment list."""
        mock_which.return_value = "/usr/bin/ffmpeg"
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        
        merger = VideoMerger()
        
        with pytest.raises(ValueError) as exc_info:
            merger._generate_concat_file([])
        
        assert "segment_files cannot be empty" in str(exc_info.value)

    @patch('shutil.which')
    @patch('subprocess.run')
    def test_generate_concat_file_missing_files(self, mock_run, mock_which):
        """Test concat file generation with missing segment files."""
        mock_which.return_value = "/usr/bin/ffmpeg"
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        
        merger = VideoMerger()
        
        missing_files = ["/nonexistent/file1.ts", "/nonexistent/file2.ts"]
        
        with pytest.raises(ValueError) as exc_info:
            merger._generate_concat_file(missing_files)
        
        assert "Missing segment files" in str(exc_info.value)

    @patch('shutil.which')
    @patch('subprocess.run')
    def test_generate_concat_file_special_characters(self, mock_run, mock_which):
        """Test concat file generation with special characters in file paths."""
        mock_which.return_value = "/usr/bin/ffmpeg"
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        
        merger = VideoMerger()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create file with special characters
            special_name = "segment with spaces & 'quotes'.ts"
            segment_path = os.path.join(temp_dir, special_name)
            Path(segment_path).touch()
            
            concat_file = merger._generate_concat_file([segment_path])
            
            try:
                with open(concat_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Verify special characters are properly escaped
                assert "file '" in content
                assert special_name.replace("'", "'\"'\"'") in content or special_name in content
                
            finally:
                if os.path.exists(concat_file):
                    os.unlink(concat_file)

    @patch('shutil.which')
    @patch('subprocess.run')
    @pytest.mark.asyncio
    async def test_merge_segments_success(self, mock_run, mock_which):
        """Test successful segment merging."""
        mock_which.return_value = "/usr/bin/ffmpeg"
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        
        merger = VideoMerger()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create segment files
            segment_files = []
            for i in range(3):
                segment_path = os.path.join(temp_dir, f"segment_{i:03d}.ts")
                Path(segment_path).touch()
                segment_files.append(segment_path)
            
            output_file = os.path.join(temp_dir, "output.mp4")
            
            # Mock asyncio.create_subprocess_exec
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"", b"")
            mock_process.returncode = 0
            
            with patch('asyncio.create_subprocess_exec', return_value=mock_process):
                await merger.merge_segments(temp_dir, output_file)
            
            # Verify ffmpeg was called
            mock_process.communicate.assert_called_once()

    @patch('shutil.which')
    @patch('subprocess.run')
    @pytest.mark.asyncio
    async def test_merge_segments_invalid_directory(self, mock_run, mock_which):
        """Test merge_segments with invalid segment directory."""
        mock_which.return_value = "/usr/bin/ffmpeg"
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        
        merger = VideoMerger()
        
        with pytest.raises(ValueError) as exc_info:
            await merger.merge_segments("/nonexistent/dir", "output.mp4")
        
        assert "segment_dir does not exist" in str(exc_info.value)

    @patch('shutil.which')
    @patch('subprocess.run')
    @pytest.mark.asyncio
    async def test_merge_segments_no_segments(self, mock_run, mock_which):
        """Test merge_segments with no segment files."""
        mock_which.return_value = "/usr/bin/ffmpeg"
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        
        merger = VideoMerger()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with pytest.raises(ValueError) as exc_info:
                await merger.merge_segments(temp_dir, "output.mp4")
            
            assert "No segment files found" in str(exc_info.value)

    @patch('shutil.which')
    @patch('subprocess.run')
    @pytest.mark.asyncio
    async def test_merge_segments_with_cleanup(self, mock_run, mock_which):
        """Test segment merging with cleanup enabled."""
        mock_which.return_value = "/usr/bin/ffmpeg"
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        
        merger = VideoMerger()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create segment files
            segment_files = []
            for i in range(3):
                segment_path = os.path.join(temp_dir, f"segment_{i:03d}.ts")
                Path(segment_path).touch()
                segment_files.append(segment_path)
            
            output_file = os.path.join(temp_dir, "output.mp4")
            
            # Mock asyncio.create_subprocess_exec
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"", b"")
            mock_process.returncode = 0
            
            with patch('asyncio.create_subprocess_exec', return_value=mock_process):
                await merger.merge_segments(temp_dir, output_file, cleanup_segments=True)
            
            # Verify segment files were deleted
            for segment_file in segment_files:
                assert not os.path.exists(segment_file)

    @patch('shutil.which')
    @patch('subprocess.run')
    @pytest.mark.asyncio
    async def test_merge_segments_ffmpeg_failure(self, mock_run, mock_which):
        """Test merge_segments when ffmpeg fails."""
        mock_which.return_value = "/usr/bin/ffmpeg"
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        
        merger = VideoMerger()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create segment files
            segment_path = os.path.join(temp_dir, "segment_001.ts")
            Path(segment_path).touch()
            
            output_file = os.path.join(temp_dir, "output.mp4")
            
            # Mock failed ffmpeg process
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"", b"Error message")
            mock_process.returncode = 1
            
            with patch('asyncio.create_subprocess_exec', return_value=mock_process):
                with pytest.raises(MergeError) as exc_info:
                    await merger.merge_segments(temp_dir, output_file)
                
                assert "ffmpeg failed with return code 1" in str(exc_info.value)

    @patch('shutil.which')
    @patch('subprocess.run')
    @pytest.mark.asyncio
    async def test_merge_segments_with_progress_callback(self, mock_run, mock_which):
        """Test merge_segments with progress callback."""
        mock_which.return_value = "/usr/bin/ffmpeg"
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        
        merger = VideoMerger()
        progress_calls = []
        
        def progress_callback(seconds):
            progress_calls.append(seconds)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create segment files
            segment_path = os.path.join(temp_dir, "segment_001.ts")
            Path(segment_path).touch()
            
            output_file = os.path.join(temp_dir, "output.mp4")
            
            # Mock ffmpeg process with progress output
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"", b"")
            mock_process.returncode = 0
            
            # Mock stderr readline to simulate ffmpeg progress output
            progress_lines = [
                b"frame=  100 fps= 25 q=-1.0 size=    1024kB time=00:00:04.00 bitrate=2097.2kbits/s speed=   1x\n",
                b"frame=  200 fps= 25 q=-1.0 size=    2048kB time=00:00:08.00 bitrate=2097.2kbits/s speed=   1x\n",
                b""  # End of output
            ]
            mock_process.stderr.readline = AsyncMock(side_effect=progress_lines)
            
            with patch('asyncio.create_subprocess_exec', return_value=mock_process):
                await merger.merge_segments(temp_dir, output_file, progress_callback=progress_callback)
            
            # Verify progress callback was called
            assert len(progress_calls) >= 1

    @patch('shutil.which')
    @patch('subprocess.run')
    @pytest.mark.asyncio
    async def test_run_ffmpeg_merge_timeout(self, mock_run, mock_which):
        """Test _run_ffmpeg_merge with timeout."""
        mock_which.return_value = "/usr/bin/ffmpeg"
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        
        merger = VideoMerger()
        
        with tempfile.NamedTemporaryFile(suffix=".txt") as concat_file:
            concat_file.write(b"file 'test.ts'\n")
            concat_file.flush()
            
            # Mock asyncio.create_subprocess_exec to raise TimeoutError
            with patch('asyncio.create_subprocess_exec', side_effect=asyncio.TimeoutError):
                with pytest.raises(MergeError) as exc_info:
                    await merger._run_ffmpeg_merge(concat_file.name, "output.mp4")
                
                assert "ffmpeg merge operation timed out" in str(exc_info.value)

    @patch('shutil.which')
    @patch('subprocess.run')
    @pytest.mark.asyncio
    async def test_cleanup_segments_success(self, mock_run, mock_which):
        """Test successful segment cleanup."""
        mock_which.return_value = "/usr/bin/ffmpeg"
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        
        merger = VideoMerger()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create segment files
            segment_files = []
            for i in range(3):
                segment_path = os.path.join(temp_dir, f"segment_{i}.ts")
                Path(segment_path).touch()
                segment_files.append(segment_path)
            
            # Verify files exist before cleanup
            for segment_file in segment_files:
                assert os.path.exists(segment_file)
            
            await merger._cleanup_segments(segment_files)
            
            # Verify files are deleted after cleanup
            for segment_file in segment_files:
                assert not os.path.exists(segment_file)

    @patch('shutil.which')
    @patch('subprocess.run')
    @pytest.mark.asyncio
    async def test_cleanup_segments_missing_files(self, mock_run, mock_which):
        """Test segment cleanup with missing files (should not raise error)."""
        mock_which.return_value = "/usr/bin/ffmpeg"
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        
        merger = VideoMerger()
        
        # Try to cleanup non-existent files (should not raise error)
        missing_files = ["/nonexistent/file1.ts", "/nonexistent/file2.ts"]
        await merger._cleanup_segments(missing_files)  # Should complete without error

    @patch('shutil.which')
    @patch('subprocess.run')
    @pytest.mark.asyncio
    async def test_monitor_ffmpeg_progress_parsing(self, mock_run, mock_which):
        """Test ffmpeg progress monitoring and parsing."""
        mock_which.return_value = "/usr/bin/ffmpeg"
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        
        merger = VideoMerger()
        progress_values = []
        
        def progress_callback(seconds):
            progress_values.append(seconds)
        
        # Mock process with stderr output
        mock_process = AsyncMock()
        progress_lines = [
            b"frame=  100 fps= 25 q=-1.0 size=    1024kB time=00:01:30.50 bitrate=2097.2kbits/s speed=   1x\n",
            b"frame=  200 fps= 25 q=-1.0 size=    2048kB time=00:02:45.25 bitrate=2097.2kbits/s speed=   1x\n",
            b""  # End of output
        ]
        mock_process.stderr.readline = AsyncMock(side_effect=progress_lines)
        
        await merger._monitor_ffmpeg_progress(mock_process, progress_callback)
        
        # Verify progress values were parsed correctly
        assert len(progress_values) == 2
        assert abs(progress_values[0] - 90.5) < 0.1  # 00:01:30.50 = 90.5 seconds
        assert abs(progress_values[1] - 165.25) < 0.1  # 00:02:45.25 = 165.25 seconds


class TestVideoMergerExceptions:
    """Test cases for VideoMerger exception classes."""

    def test_video_merger_error_inheritance(self):
        """Test VideoMergerError is a proper Exception subclass."""
        error = VideoMergerError("test message")
        assert isinstance(error, Exception)
        assert str(error) == "test message"

    def test_ffmpeg_not_found_error_inheritance(self):
        """Test FFmpegNotFoundError is a proper VideoMergerError subclass."""
        error = FFmpegNotFoundError("ffmpeg not found")
        assert isinstance(error, VideoMergerError)
        assert isinstance(error, Exception)
        assert str(error) == "ffmpeg not found"

    def test_merge_error_inheritance(self):
        """Test MergeError is a proper VideoMergerError subclass."""
        error = MergeError("merge failed")
        assert isinstance(error, VideoMergerError)
        assert isinstance(error, Exception)
        assert str(error) == "merge failed"