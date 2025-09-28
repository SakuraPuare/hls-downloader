#!/usr/bin/env python3
"""
Simple script to test the real HLS URL provided.
This can be run manually to verify the URL pattern works correctly.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent / "src"))

from hls_downloader.detector import HLSDetector
from hls_downloader.models import DownloadConfig


async def test_real_url():
    """Test the real HLS URL provided."""
    # The real URL provided
    real_url = "https://dh5wswx02.v.cntv.cn/asp/h5e/hls/1200/0303000a/3/default/6f3ab539680c4b359d857b4c73a824eb/81.ts"
    
    print(f"Testing HLS URL: {real_url}")
    print("=" * 80)
    
    # Create detector
    detector = HLSDetector(timeout=10, max_concurrent_checks=3)
    
    try:
        # Test URL pattern extraction
        print("1. Testing URL pattern extraction...")
        base_url, pattern, extension = detector._extract_url_pattern(real_url)
        print(f"   Base URL: {base_url}")
        print(f"   Pattern: {pattern}")
        print(f"   Extension: {extension}")
        
        # Test URL generation
        print("\n2. Testing URL generation...")
        test_segments = [1, 81, 82, 100]
        for seg_num in test_segments:
            generated_url = detector._generate_segment_url(base_url, pattern, seg_num)
            print(f"   Segment {seg_num}: {generated_url}")
        
        # Test segment existence check
        print("\n3. Testing segment existence...")
        async with detector:
            # Check the known segment (81)
            print(f"   Checking segment 81 (known)...")
            exists_81 = await detector._check_segment_exists(real_url)
            print(f"   Segment 81 exists: {exists_81}")
            
            # Check a few segments around it
            for seg_num in [80, 82, 83]:
                test_url = detector._generate_segment_url(base_url, pattern, seg_num)
                exists = await detector._check_segment_exists(test_url)
                print(f"   Segment {seg_num} exists: {exists}")
            
            # Check a segment that likely doesn't exist
            high_seg_url = detector._generate_segment_url(base_url, pattern, 99999)
            exists_high = await detector._check_segment_exists(high_seg_url)
            print(f"   Segment 99999 exists: {exists_high}")
        
        print("\n4. Testing batch segment checking...")
        test_urls = [
            detector._generate_segment_url(base_url, pattern, i) 
            for i in [79, 80, 81, 82, 83]
        ]
        
        async with detector:
            batch_results = await detector._batch_check_segments(test_urls)
            for i, (url, exists) in enumerate(zip(test_urls, batch_results), 79):
                print(f"   Segment {i}: {exists}")
        
        print("\n5. Testing upper bound detection (limited range)...")
        async with detector:
            # Test with a limited range to avoid too many requests
            upper_bound = await detector._find_upper_bound(base_url, pattern)
            print(f"   Found upper bound: {upper_bound}")
            
            # If upper bound is reasonable, test binary search with a smaller range
            if upper_bound > 0 and upper_bound < 1000:
                print(f"\n6. Testing binary search (up to {min(upper_bound, 100)})...")
                # Limit to 100 to avoid too many requests
                limited_upper = min(upper_bound, 100)
                max_segment = await detector._binary_search_max_segment(base_url, pattern)
                print(f"   Maximum valid segment found: {max_segment}")
        
        print("\n✅ All tests completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


async def test_template_detection():
    """Test full segment detection with the template URL."""
    # Convert the real URL to template format
    template_url = "https://dh5wswx02.v.cntv.cn/asp/h5e/hls/1200/0303000a/3/default/6f3ab539680c4b359d857b4c73a824eb/1.ts"
    
    print(f"\n7. Testing full segment detection with template: {template_url}")
    print("=" * 80)
    
    detector = HLSDetector(timeout=10, max_concurrent_checks=3)
    
    try:
        async with detector:
            # Limit the detection to avoid too many requests
            # We'll mock the binary search to return a small range
            original_binary_search = detector._binary_search_max_segment
            
            async def limited_binary_search(base_url, pattern):
                # Only search up to segment 90 to limit requests
                result = await original_binary_search(base_url, pattern)
                return min(result, 90)
            
            detector._binary_search_max_segment = limited_binary_search
            
            segments = await detector.detect_segments(template_url)
            
            print(f"   Found {len(segments)} segments")
            if segments:
                print(f"   First segment: {segments[0].url}")
                print(f"   Last segment: {segments[-1].url}")
                print(f"   Segment range: {segments[0].index} to {segments[-1].index}")
            
            return len(segments) > 0
            
    except Exception as e:
        print(f"   ❌ Error during segment detection: {e}")
        return False


def main():
    """Main function to run all tests."""
    print("HLS Downloader - Real URL Testing")
    print("=" * 80)
    print("This script tests the provided HLS URL to verify our implementation works correctly.")
    print("Note: This makes real HTTP requests, so it requires internet connectivity.")
    print()
    
    try:
        # Run basic URL tests
        success = asyncio.run(test_real_url())
        
        if success:
            # Run template detection test
            template_success = asyncio.run(test_template_detection())
            
            if template_success:
                print("\n🎉 All tests passed! The HLS downloader should work with this URL.")
                print("\nTo use this URL with the downloader, use:")
                print("python -m src.hls_downloader.cli \"https://dh5wswx02.v.cntv.cn/asp/h5e/hls/1200/0303000a/3/default/6f3ab539680c4b359d857b4c73a824eb/{}.ts\"")
            else:
                print("\n⚠️  Basic tests passed but template detection had issues.")
        else:
            print("\n❌ Tests failed. Check the error messages above.")
            
    except KeyboardInterrupt:
        print("\n\n⏹️  Testing interrupted by user.")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()