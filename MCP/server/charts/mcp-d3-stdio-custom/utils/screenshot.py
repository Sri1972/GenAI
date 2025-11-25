"""
Screenshot utility for capturing chart HTML files as PNG images.
Uses Playwright for headless browser rendering.
"""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright
import logging

logger = logging.getLogger(__name__)


async def capture_html_as_png_async(html_path: str, output_png_path: str = None, 
                                     width: int = 1200, height: int = 800,
                                     wait_time: int = 2000) -> str:
    """
    Capture an HTML file as a PNG screenshot using Playwright.
    
    Args:
        html_path: Path to the HTML file to capture
        output_png_path: Path for output PNG (defaults to same name as HTML with .png extension)
        width: Viewport width in pixels
        height: Viewport height in pixels
        wait_time: Time to wait for chart rendering in milliseconds (default 2000ms)
        
    Returns:
        Path to the generated PNG file
        
    Raises:
        Exception if screenshot fails
    """
    html_path = Path(html_path).resolve()
    
    if not html_path.exists():
        raise FileNotFoundError(f"HTML file not found: {html_path}")
    
    # Determine output path
    if output_png_path is None:
        output_png_path = html_path.with_suffix('.png')
    else:
        output_png_path = Path(output_png_path).resolve()
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(viewport={'width': width, 'height': height})
            
            # Load the HTML file
            await page.goto(f'file:///{html_path.as_posix()}')
            
            # Wait for chart to render (D3/Chart.js animations)
            await page.wait_for_timeout(wait_time)
            
            # Take screenshot
            await page.screenshot(path=str(output_png_path), full_page=True)
            
            await browser.close()
            
        logger.info(f"Screenshot saved: {output_png_path}")
        return str(output_png_path)
        
    except Exception as e:
        logger.error(f"Failed to capture screenshot: {e}")
        raise


def capture_html_as_png(html_path: str, output_png_path: str = None,
                        width: int = 1200, height: int = 800,
                        wait_time: int = 2000) -> str:
    """
    Synchronous wrapper for capture_html_as_png_async.
    
    Args:
        html_path: Path to the HTML file to capture
        output_png_path: Path for output PNG (defaults to same name as HTML with .png extension)
        width: Viewport width in pixels
        height: Viewport height in pixels
        wait_time: Time to wait for chart rendering in milliseconds
        
    Returns:
        Path to the generated PNG file
    """
    return asyncio.run(capture_html_as_png_async(
        html_path, output_png_path, width, height, wait_time
    ))


async def capture_multiple_html_as_png_async(html_paths: list[str], 
                                              width: int = 1200, 
                                              height: int = 800,
                                              wait_time: int = 2000) -> list[str]:
    """
    Capture multiple HTML files as PNG screenshots concurrently.
    
    Args:
        html_paths: List of paths to HTML files
        width: Viewport width in pixels
        height: Viewport height in pixels
        wait_time: Time to wait for chart rendering in milliseconds
        
    Returns:
        List of paths to generated PNG files
    """
    tasks = [
        capture_html_as_png_async(html_path, None, width, height, wait_time)
        for html_path in html_paths
    ]
    return await asyncio.gather(*tasks, return_exceptions=True)


def capture_multiple_html_as_png(html_paths: list[str],
                                  width: int = 1200,
                                  height: int = 800,
                                  wait_time: int = 2000) -> list[str]:
    """
    Synchronous wrapper for capturing multiple HTML files as PNG screenshots.
    
    Args:
        html_paths: List of paths to HTML files
        width: Viewport width in pixels
        height: Viewport height in pixels
        wait_time: Time to wait for chart rendering in milliseconds
        
    Returns:
        List of paths to generated PNG files
    """
    return asyncio.run(capture_multiple_html_as_png_async(
        html_paths, width, height, wait_time
    ))


# Example usage:
if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python screenshot.py <html_file> [output_png]")
        sys.exit(1)
    
    html_file = sys.argv[1]
    output_png = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        png_path = capture_html_as_png(html_file, output_png)
        print(f"✓ Screenshot saved: {png_path}")
    except Exception as e:
        print(f"✗ Error: {e}")
        sys.exit(1)
