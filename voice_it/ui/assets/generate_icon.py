"""
Generate Voice IT icon files (ICO and PNG) from SVG source.
Run this script to regenerate icons after design changes.
"""

import io
from pathlib import Path

from PIL import Image
from reportlab.graphics import renderPM
from svglib.svglib import svg2rlg


def svg_to_png(svg_path: Path, size: int) -> Image.Image:
    """
    Convert SVG to PNG at specified size.

    Args:
        svg_path: Path to SVG file
        size: Output size in pixels

    Returns:
        PIL Image in RGBA mode
    """
    # Load SVG
    drawing = svg2rlg(str(svg_path))

    # Calculate scale factor
    scale = size / max(drawing.width, drawing.height)
    drawing.width = size
    drawing.height = size
    drawing.scale(scale, scale)

    # Render to PNG bytes
    png_bytes = renderPM.drawToString(drawing, fmt="PNG")

    # Convert to PIL Image
    img = Image.open(io.BytesIO(png_bytes))

    # Ensure RGBA mode
    if img.mode != "RGBA":
        img = img.convert("RGBA")

    return img


def save_ico_from_svg(svg_path: Path, ico_path: Path):
    """
    Convert SVG to ICO with multiple sizes.

    Args:
        svg_path: Path to source SVG
        ico_path: Path to output ICO
    """
    # Windows taskbar uses these sizes
    sizes = [256, 128, 64, 48, 32, 24, 16]
    icons = []

    for sz in sizes:
        print(f"  Rendering {sz}x{sz}...")
        icon = svg_to_png(svg_path, sz)
        icons.append(icon)

    # Save ICO with all sizes (largest first)
    icons[0].save(
        ico_path,
        format="ICO",
        append_images=icons[1:],
    )


def main():
    """Generate all icon files from SVG source."""
    # Paths
    assets_dir = Path(__file__).parent
    web_dir = assets_dir.parent / "web"

    # Source SVG (the detailed icon design)
    svg_path = web_dir / "favicon.svg"  # Using simpler favicon for taskbar

    if not svg_path.exists():
        print(f"Error: SVG not found at {svg_path}")
        return

    print(f"Converting: {svg_path}")

    # Generate ICO from SVG
    ico_path = assets_dir / "icon.ico"
    save_ico_from_svg(svg_path, ico_path)
    print(f"Created: {ico_path}")

    # Save high-res PNG
    png_path = assets_dir / "icon.png"
    icon_256 = svg_to_png(svg_path, 256)
    icon_256.save(png_path, "PNG")
    print(f"Created: {png_path}")

    # Save 64px PNG for tray
    tray_path = assets_dir / "tray_icon.png"
    tray_icon = svg_to_png(svg_path, 64)
    tray_icon.save(tray_path, "PNG")
    print(f"Created: {tray_path}")

    print("\nDone! Icons generated from SVG successfully.")


if __name__ == "__main__":
    main()
