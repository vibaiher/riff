"""ASCII waveform renderers for the rich panels.

render_bars()        — single-row ▁▂▃▄▅▆▇█ bar chart (absolute amplitude)
render_oscilloscope() — multi-row oscilloscope using signed samples
"""

from __future__ import annotations

import numpy as np

# Unicode block characters: index 0 = empty, 8 = full block
BARS = " ▁▂▃▄▅▆▇█"

# Braille-dot character used for low-amplitude oscilloscope points
_DOT = "·"

# Vertical bar character for the equalizer-style waveform
_VBAR = "█"


def render_vbars(
    data: list[float],
    n_bars: int = 28,
    height: int = 6,
) -> str:
    """
    Render amplitude data as vertical equalizer bars (multi-row, fills bottom-up).

    This matches the waveform style in the mockup: thin vertical columns of
    varying height, with one-character gaps between bars.

    Args:
        data:   Non-negative floats (absolute amplitude per bin).
        n_bars: Number of vertical bars to render.
        height: Number of rows (terminal lines) the waveform occupies.

    Returns:
        A multi-line string with *height* rows.
        Each row is  n_bars + (n_bars - 1)  characters wide.

    Example (height=4, n_bars=8):
        ``       █           ``
        ``   █   █   █   █   ``
        `` █ █ █ █ █ █ █ █   ``
        `` █ █ █ █ █ █ █ █   ``
    """
    n_cols = n_bars * 2 - 1  # bars + gaps
    empty = " " * n_cols

    if not data:
        return "\n".join([empty] * (height - 1) + ["─" * n_cols])

    # Resize data to n_bars values by taking peak per segment
    n = len(data)
    bars: list[float] = []
    for i in range(n_bars):
        lo = int(i * n / n_bars)
        hi = int((i + 1) * n / n_bars)
        hi = max(hi, lo + 1)
        bars.append(max(data[lo:hi]))

    MIN_PEAK = 0.05  # minimum amplitude reference (~-26 dBFS)
    peak = max(bars)
    if peak < 1e-7:
        return "\n".join([empty] * (height - 1) + ["─" * n_cols])

    # Normalize 0..1, using a minimum reference to avoid inflating quiet signals
    norm_ref = max(peak, MIN_PEAK)
    bars = [b / norm_ref for b in bars]
    bars = [min(b, 1.0) for b in bars]

    # Build grid top-to-bottom.  Row 0 = top (highest amplitude),
    # row height-1 = bottom (always filled if amp > 0).
    rows: list[str] = []
    for r in range(height):
        # Threshold: bar must exceed this fraction to appear in this row
        threshold = (height - 1 - r) / height
        row_chars: list[str] = []
        for b, amp in enumerate(bars):
            if b > 0:
                row_chars.append(" ")  # gap between bars
            row_chars.append(_VBAR if amp >= threshold else " ")
        rows.append("".join(row_chars))

    return "\n".join(rows)


def render_bars(data: list[float], width: int = 48) -> str:
    """
    Render amplitude values as a single-row bar waveform.

    Args:
        data:   Non-negative floats (absolute amplitude per bin).
                Pass the list from AppState.waveform.
        width:  Number of characters in the result.

    Returns:
        A string of exactly *width* unicode block characters, e.g.
        ``▁▁▂▃▄▅▆▇█▇▆▅▄▃▂▁▂▃▄▅▄▃``

    When *data* is empty or all-zero, returns a row of ``─`` characters.
    """
    if not data:
        return "─" * width

    # Resize to target width by taking peak per segment
    n = len(data)
    if n != width:
        resampled: list[float] = []
        for i in range(width):
            lo = int(i * n / width)
            hi = int((i + 1) * n / width)
            hi = max(hi, lo + 1)
            resampled.append(max(data[lo:hi]))
        data = resampled

    peak = max(data)
    if peak < 1e-7:
        return "─" * width

    n_levels = len(BARS) - 1  # 8
    return "".join(BARS[min(n_levels, int(v / peak * n_levels))] for v in data)


def render_oscilloscope(
    data: list[float],
    width: int = 48,
    height: int = 5,
) -> str:
    """
    Render signed audio samples as a multi-row oscilloscope.

    Args:
        data:   Signed float samples in [-1.0, +1.0].
        width:  Number of columns.
        height: Number of rows (must be odd for a clean center line).

    Returns:
        A multi-line string with *height* rows of *width* characters.
        Row 0 = +1.0, center row = 0.0, last row = -1.0.
    """
    center = height // 2
    empty_row = " " * width
    center_line = "─" * width

    if not data:
        rows = [empty_row] * height
        rows[center] = center_line
        return "\n".join(rows)

    peak = max(abs(v) for v in data)
    if peak < 1e-7:
        rows = [empty_row] * height
        rows[center] = center_line
        return "\n".join(rows)

    norm = [max(-1.0, min(1.0, v / peak)) for v in data]

    # Resample to target width using linear interpolation
    indices = np.linspace(0, len(norm) - 1, width)
    samples = [norm[int(i)] for i in indices]

    # Build character grid
    grid = [[" "] * width for _ in range(height)]
    for col in range(width):
        grid[center][col] = "─"  # baseline

    for col, val in enumerate(samples):
        # Map +1.0 → row 0 (top), -1.0 → row height-1 (bottom)
        row = int(round((1.0 - val) / 2.0 * (height - 1)))
        row = max(0, min(height - 1, row))

        # Character intensity reflects amplitude
        intensity = abs(val)
        if intensity > 0.7:
            char = "█"
        elif intensity > 0.45:
            char = "▓"
        elif intensity > 0.2:
            char = "░"
        else:
            char = _DOT

        grid[row][col] = char

    return "\n".join("".join(row) for row in grid)
