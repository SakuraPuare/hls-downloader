"""Integration tests for resume functionality."""

import asyncio
import tempfile
import time
from copy import deepcopy
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from src.hls_downloader.download_manager import DownloadManager
from src.hls_downloader.models import DownloadConfig, SegmentInfo
from src.hls_downloader.state_manager import StateManager


class TestResumeIntegration:
    """Integration tests for resume functionality."""

    def _setup_mocked_components(self, manager, temp_dir, mock_segments, remaining_segments=None, valid_segments=None, invalid_segments=None):
        """Helper to set up properly mocked components for download manager."""
        if remaining_segments is None:
            remaining_segments = []

        # Mock detector
        mock_detector_instance = AsyncMock()
        mock_detector_instance.__aenter__ = AsyncMock(return_value=mock_detector_instance)
        mock_detector_instance.__aexit__ = AsyncMock(return_value=None)
        mock_detector_instance.detect_segments.return_value = mock_segments

        # Mock downloader
        mock_downloader_instance = AsyncMock()
        mock_downloader_instance.download_segments.return_value = remaining_segments
        mock_downloader_instance.__aenter__ = AsyncMock(return_value=mock_downloader_instance)
        mock_downloader_instance.__aexit__ = AsyncMock(return_value=None)

        # Mock resume validator
        mock_resume_validator = AsyncMock()
        mock_resume_validator.__aenter__ = AsyncMock(return_value=mock_resume_validator)
        mock_resume_validator.__aexit__ = AsyncMock(return_value=None)

        # Setup validation results based on the scenario
        if valid_segments is None or invalid_segments is None:
            valid_segments = [s for s in mock_segments if s.downloaded]
            invalid_segments = [s for s in mock_segments if not s.downloaded]
        missing_segments = []

        mock_resume_validator.validate_segments.return_value = (valid_segments, invalid_segments, missing_segments)

        # get_resume_summary and cleanup_invalid_files are regular methods, not async
        from unittest.mock import Mock
        mock_resume_validator.get_resume_summary = Mock(return_value={
            "total_segments": len(mock_segments),
            "valid_segments": len(valid_segments),
            "invalid_segments": len(invalid_segments),
            "missing_segments": 0,
            "segments_to_download": len(invalid_segments),
            "completion_percentage": (len(valid_segments) / len(mock_segments) * 100) if mock_segments else 0,
            "valid_bytes": sum(s.size for s in valid_segments),
            "can_resume": len(invalid_segments) > 0 and len(valid_segments) > 0,
            "resume_benefit": (len(valid_segments) / len(mock_segments) * 100) if mock_segments else 0
        })
        mock_resume_validator.cleanup_invalid_files = Mock(return_value=len(invalid_segments))

        # Mock the initialization to set our components
        async def mock_initialize():
            manager._detector = mock_detector_instance
            manager._downloader = mock_downloader_instance
            manager._resume_validator = mock_resume_validator
            manager._state_manager = StateManager(temp_dir)

        return mock_initialize, mock_detector_instance, mock_downloader_instance, mock_resume_validator

    @pytest.fixture
    def download_config(self):
        """Create test download configuration."""
        return DownloadConfig(
            max_concurrent=2,
            max_retries=1,
            timeout=10,
            auto_merge=False,  # Disable merge for testing
            cleanup_segments=False
        )
    
    @pytest.fixture
    def mock_segments(self):
        """Create mock segments for testing."""
        return [
            SegmentInfo(
                url="http://example.com/segment1.ts",
                index=1,
                filename="segment_000001.ts",
                size=1024,
                downloaded=False
            ),
            SegmentInfo(
                url="http://example.com/segment2.ts",
                index=2,
                filename="segment_000002.ts",
                size=2048,
                downloaded=False
            ),
            SegmentInfo(
                url="http://example.com/segment3.ts",
                index=3,
                filename="segment_000003.ts",
                size=512,
                downloaded=False
            )
        ]
    
    @pytest.mark.asyncio
    async def test_fresh_download_creates_state(self, download_config, mock_segments):
        """Test that fresh download creates state file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = DownloadManager(download_config)
            
            # Mock detector to return segments
            with patch.object(manager, '_detector') as mock_detector:
                mock_detector_instance = AsyncMock()
                mock_detector_instance.detect_segments.return_value = mock_segments
                mock_detector.__aenter__.return_value = mock_detector_instance
                
                # Mock downloader
                with patch.object(manager, '_downloader') as mock_downloader:
                    mock_downloader_instance = AsyncMock()
                    # Simulate partial download (first segment fails)
                    download_results = mock_segments.copy()
                    download_results[0].downloaded = True
                    download_results[1].downloaded = True
                    download_results[2].downloaded = False
                    mock_downloader_instance.download_segments.return_value = download_results
                    mock_downloader.__aenter__.return_value = mock_downloader_instance
                    
                    # Mock other components
                    with patch.object(manager, '_progress_display'), \
                         patch.object(manager, '_merger', None):
                        
                        try:
                            await manager.download_hls(
                                url="http://example.com/segment1.ts",
                                output_dir=temp_dir,
                                output_filename="test.mp4"
                            )
                        except Exception:
                            pass  # Expected to fail due to failed segment
            
            # Check that state file was created
            state_manager = StateManager(temp_dir)
            assert state_manager.has_saved_state()
            
            # Check state content
            state = state_manager.load_state()
            assert state is not None
            assert state.url == "http://example.com/segment1.ts"
            # State should be created even if detection fails
            assert state.status == "failed"
    
    @pytest.mark.asyncio
    async def test_resume_existing_download(self, download_config, mock_segments):
        """Test resuming an existing download."""
        with tempfile.TemporaryDirectory() as temp_dir:
            segments_dir = Path(temp_dir) / "segments"
            segments_dir.mkdir(parents=True)

            # Create partial download state
            state_manager = StateManager(temp_dir)
            initial_state = state_manager.create_initial_state(
                url="http://example.com/segment{}.ts",
                output_dir=temp_dir,
                output_filename="test.mp4",
                config=download_config
            )
            
            # Set up segments with some already downloaded
            segments_with_status = mock_segments.copy()
            segments_with_status[0].downloaded = True
            segments_with_status[1].downloaded = True
            segments_with_status[2].downloaded = False
            
            state_manager.update_state_segments(initial_state, segments_with_status)
            state_manager.update_state_status(initial_state, "downloading")
            
            # Create files for downloaded segments
            (segments_dir / "segment_000001.ts").write_bytes(b"x" * 1024)
            (segments_dir / "segment_000002.ts").write_bytes(b"x" * 2048)
            
            # Resume download
            manager = DownloadManager(download_config)

            # Only the missing segment should be downloaded
            from copy import deepcopy
            remaining_segment = deepcopy(mock_segments[2])
            remaining_segment.downloaded = True

            # Set up mocked components
            mock_initialize, mock_detector_instance, mock_downloader_instance, mock_resume_validator = self._setup_mocked_components(
                manager, temp_dir, segments_with_status, [remaining_segment]
            )

            with patch.object(manager, '_initialize_components', side_effect=mock_initialize), \
                 patch.object(manager, '_progress_display'), \
                 patch.object(manager, '_merger', None), \
                 patch.object(manager, '_generate_results', return_value={
                     "success": True,
                     "segments_downloaded": 1,
                     "total_segments": 3,
                     "output_file": None
                 }):

                result = await manager.download_hls(
                    url="http://example.com/segment{}.ts",
                    output_dir=temp_dir,
                    output_filename="test.mp4"
                )
                
            # Verify detector was not called (segments loaded from state)
            mock_detector_instance.detect_segments.assert_not_called()

            # Verify only missing segment was downloaded
            mock_downloader_instance.download_segments.assert_called_once()
            call_args = mock_downloader_instance.download_segments.call_args
            segments_to_download = call_args[0][0]
            assert len(segments_to_download) == 1
            assert segments_to_download[0].index == 3
            
            # Verify result indicates resume
            assert result["resumed"] == True
            assert result["existing_segments"] == 2
            assert result["total_segments"] == 3
            
            # State file should be deleted on successful completion
            assert not state_manager.has_saved_state()
    
    @pytest.mark.asyncio
    async def test_resume_with_invalid_files(self, download_config, mock_segments):
        """Test resume when some existing files are invalid."""
        with tempfile.TemporaryDirectory() as temp_dir:
            segments_dir = Path(temp_dir) / "segments"
            segments_dir.mkdir(parents=True)

            # Create partial download state
            state_manager = StateManager(temp_dir)
            initial_state = state_manager.create_initial_state(
                url="http://example.com/segment{}.ts",
                output_dir=temp_dir,
                output_filename="test.mp4",
                config=download_config
            )
            
            # Set up segments as if all were downloaded
            segments_with_status = deepcopy(mock_segments)
            for segment in segments_with_status:
                segment.downloaded = True
            
            state_manager.update_state_segments(initial_state, segments_with_status)
            
            # Create files with wrong sizes (invalid)
            (segments_dir / "segment_000001.ts").write_bytes(b"x" * 500)  # Wrong size
            (segments_dir / "segment_000002.ts").write_bytes(b"x" * 2048)  # Correct size
            (segments_dir / "segment_000003.ts").write_bytes(b"")  # Empty file
            
            # Resume download
            manager = DownloadManager(download_config)

            # Invalid segments should be re-downloaded
            redownload_segments = [deepcopy(mock_segments[0]), deepcopy(mock_segments[2])]
            for segment in redownload_segments:
                segment.downloaded = True

            # Set up mocked components - simulate invalid files being detected
            valid_segments = [mock_segments[1]]  # Only segment 2 is valid
            invalid_segments = [mock_segments[0], mock_segments[2]]  # Segments 1 and 3 are invalid
            mock_initialize, mock_detector_instance, mock_downloader_instance, mock_resume_validator = self._setup_mocked_components(
                manager, temp_dir, segments_with_status, redownload_segments, valid_segments, invalid_segments
            )

            with patch.object(manager, '_initialize_components', side_effect=mock_initialize), \
                 patch.object(manager, '_progress_display'), \
                 patch.object(manager, '_merger', None), \
                 patch.object(manager, '_generate_results', return_value={
                     "success": True,
                     "segments_downloaded": 2,
                     "total_segments": 3,
                     "output_file": None
                 }):

                result = await manager.download_hls(
                    url="http://example.com/segment{}.ts",
                    output_dir=temp_dir,
                    output_filename="test.mp4"
                )

            # Verify invalid segments were re-downloaded
            mock_downloader_instance.download_segments.assert_called_once()
            call_args = mock_downloader_instance.download_segments.call_args
            segments_to_download = call_args[0][0]
            assert len(segments_to_download) == 2
            assert {s.index for s in segments_to_download} == {1, 3}
            
            # Note: File cleanup verification would require more complex mocking
            # The key test is that invalid segments were identified and re-downloaded
    
    @pytest.mark.asyncio
    async def test_force_restart_ignores_state(self, download_config, mock_segments):
        """Test that force restart ignores existing state."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create existing state
            state_manager = StateManager(temp_dir)
            initial_state = state_manager.create_initial_state(
                url="http://example.com/segment{}.ts",
                output_dir=temp_dir,
                output_filename="test.mp4",
                config=download_config
            )
            state_manager.save_state(initial_state)
            
            assert state_manager.has_saved_state()
            
            # Force restart
            manager = DownloadManager(download_config)

            # For force restart, all segments should be downloaded (start from fresh)
            fresh_segments = mock_segments.copy()
            for segment in fresh_segments:
                segment.downloaded = False  # Start fresh

            download_results = mock_segments.copy()
            for segment in download_results:
                segment.downloaded = True  # After download they should be complete

            # Set up mocked components - no resume, fresh detection
            mock_initialize, mock_detector_instance, mock_downloader_instance, mock_resume_validator = self._setup_mocked_components(
                manager, temp_dir, fresh_segments, download_results
            )

            with patch.object(manager, '_initialize_components', side_effect=mock_initialize), \
                 patch.object(manager, '_progress_display'), \
                 patch.object(manager, '_merger', None), \
                 patch.object(manager, '_generate_results', return_value={
                     "success": True,
                     "segments_downloaded": 3,
                     "total_segments": 3,
                     "output_file": None
                 }):

                result = await manager.download_hls(
                    url="http://example.com/segment{}.ts",
                    output_dir=temp_dir,
                    output_filename="test.mp4",
                    force_restart=True
                )

            # Verify detector was called (fresh detection)
            mock_detector_instance.detect_segments.assert_called_once()

            # Verify all segments were downloaded (no resume)
            mock_downloader_instance.download_segments.assert_called_once()
            call_args = mock_downloader_instance.download_segments.call_args
            segments_to_download = call_args[0][0]
            assert len(segments_to_download) == 3
            
            # Verify result indicates no resume
            assert result["resumed"] == False
    
    @pytest.mark.asyncio
    async def test_url_mismatch_starts_fresh(self, download_config, mock_segments):
        """Test that URL mismatch starts fresh download."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create existing state with different URL
            state_manager = StateManager(temp_dir)
            initial_state = state_manager.create_initial_state(
                url="http://different.com/segment{}.ts",  # Different URL
                output_dir=temp_dir,
                output_filename="test.mp4",
                config=download_config
            )
            state_manager.save_state(initial_state)
            
            # Try to download with different URL
            manager = DownloadManager(download_config)
            
            with patch.object(manager, '_detector') as mock_detector:
                mock_detector_instance = AsyncMock()
                mock_detector_instance.detect_segments.return_value = mock_segments
                mock_detector.__aenter__.return_value = mock_detector_instance
                
                with patch.object(manager, '_downloader') as mock_downloader:
                    mock_downloader_instance = AsyncMock()
                    download_results = mock_segments.copy()
                    for segment in download_results:
                        segment.downloaded = True
                    mock_downloader_instance.download_segments.return_value = download_results
                    mock_downloader.__aenter__.return_value = mock_downloader_instance
                    
                    with patch.object(manager, '_progress_display'), \
                         patch.object(manager, '_merger', None):
                        
                        result = await manager.download_hls(
                            url="http://example.com/segment{}.ts",  # Different URL
                            output_dir=temp_dir,
                            output_filename="test.mp4"
                        )
                
                # Verify fresh detection was performed
                mock_detector_instance.detect_segments.assert_called_once()
            
            # Verify result indicates no resume
            assert result["resumed"] == False
    
    @pytest.mark.asyncio
    async def test_state_updated_during_download(self, download_config, mock_segments):
        """Test that state is updated during download process."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = DownloadManager(download_config)
            
            # Track state updates
            state_updates = []
            original_save_state = StateManager.save_state
            
            def track_save_state(self, state):
                state_updates.append((state.status, len([s for s in state.segments if s.downloaded])))
                return original_save_state(self, state)
            
            with patch.object(StateManager, 'save_state', track_save_state):
                with patch.object(manager, '_detector') as mock_detector:
                    mock_detector_instance = AsyncMock()
                    mock_detector_instance.detect_segments.return_value = mock_segments
                    mock_detector.__aenter__.return_value = mock_detector_instance
                    
                    with patch.object(manager, '_downloader') as mock_downloader:
                        mock_downloader_instance = AsyncMock()
                        download_results = mock_segments.copy()
                        for segment in download_results:
                            segment.downloaded = True
                        mock_downloader_instance.download_segments.return_value = download_results
                        mock_downloader.__aenter__.return_value = mock_downloader_instance
                        
                        with patch.object(manager, '_progress_display'), \
                             patch.object(manager, '_merger', None):
                            
                            await manager.download_hls(
                                url="http://example.com/segment{}.ts",
                                output_dir=temp_dir,
                                output_filename="test.mp4"
                            )
            
            # Verify state was updated through the process
            assert len(state_updates) >= 3  # At least: detecting, downloading, completed
            
            # Check status progression
            statuses = [update[0] for update in state_updates]
            assert "detecting" in statuses
            assert "downloading" in statuses
            assert "completed" in statuses
    
    def test_has_resumable_download(self, download_config):
        """Test checking for resumable download."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = DownloadManager(download_config)
            
            # Initially no resumable download
            assert not manager.has_resumable_download(temp_dir)
            
            # Create state file
            state_manager = StateManager(temp_dir)
            initial_state = state_manager.create_initial_state(
                url="http://example.com/segment{}.ts",
                output_dir=temp_dir,
                output_filename="test.mp4",
                config=download_config
            )
            state_manager.save_state(initial_state)
            
            # Now should have resumable download
            assert manager.has_resumable_download(temp_dir)
    
    def test_get_resume_info(self, download_config, mock_segments):
        """Test getting resume information."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = DownloadManager(download_config)
            
            # Initially no resume info
            info = manager.get_resume_info(temp_dir)
            assert info is None
            
            # Create state with progress
            state_manager = StateManager(temp_dir)
            initial_state = state_manager.create_initial_state(
                url="http://example.com/segment{}.ts",
                output_dir=temp_dir,
                output_filename="test.mp4",
                config=download_config
            )
            
            # Update with segments and progress
            state_manager.update_state_segments(initial_state, mock_segments)
            initial_state.stats.downloaded_segments = 2
            initial_state.stats.failed_segments = 1
            initial_state.status = "downloading"
            state_manager.save_state(initial_state)
            
            # Get resume info
            info = manager.get_resume_info(temp_dir)
            
            assert info is not None
            assert info["url"] == "http://example.com/segment{}.ts"
            assert info["status"] == "downloading"
            assert info["total_segments"] == 3
            assert info["downloaded_segments"] == 2
            assert info["failed_segments"] == 1
    
    @pytest.mark.asyncio
    async def test_resume_download_convenience_method(self, download_config, mock_segments):
        """Test the resume_download convenience method."""
        with tempfile.TemporaryDirectory() as temp_dir:
            segments_dir = Path(temp_dir) / "segments"
            segments_dir.mkdir(parents=True)
            
            # Create existing state
            state_manager = StateManager(temp_dir)
            initial_state = state_manager.create_initial_state(
                url="http://example.com/segment{}.ts",
                output_dir=temp_dir,
                output_filename="test.mp4",
                config=download_config
            )
            
            segments_with_status = mock_segments.copy()
            segments_with_status[0].downloaded = True
            state_manager.update_state_segments(initial_state, segments_with_status)
            
            # Create file for downloaded segment
            (segments_dir / "segment_000001.ts").write_bytes(b"x" * 1024)
            
            manager = DownloadManager(download_config)
            
            with patch.object(manager, '_detector') as mock_detector:
                mock_detector_instance = AsyncMock()
                mock_detector.__aenter__.return_value = mock_detector_instance
                
                with patch.object(manager, '_downloader') as mock_downloader:
                    mock_downloader_instance = AsyncMock()
                    remaining_segments = mock_segments[1:].copy()
                    for segment in remaining_segments:
                        segment.downloaded = True
                    mock_downloader_instance.download_segments.return_value = remaining_segments
                    mock_downloader.__aenter__.return_value = mock_downloader_instance
                    
                    with patch.object(manager, '_progress_display'), \
                         patch.object(manager, '_merger', None):
                        
                        result = await manager.resume_download(
                            url="http://example.com/segment{}.ts",
                            output_dir=temp_dir,
                            output_filename="test.mp4"
                        )
            
            # Should behave same as download_hls with resume
            assert result["resumed"] == True
            assert result["existing_segments"] == 1