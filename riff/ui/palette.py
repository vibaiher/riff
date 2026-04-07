"""Shared color palette for the RIFF TUI."""

YOU_COLOR = "#b388ff"
YOU_BORDER = "#7c4dff"
YOU_BG = "#0e0a17"

RIFF_COLOR = "#69f0ae"
RIFF_BORDER = "#00bfa5"
RIFF_BG = "#090f0d"

LABEL_DIM = "#555555"
META_KEY = "#444444"
META_VAL = "#666666"
BAR_EMPTY = "#1e1e1e"
SEP_COLOR = "#2a2a2a"

REFRESH_RATE = 20

NOTE_COLORS: dict[str, str] = {
    "C": "#ff6b6b",
    "C#": "#ff9f43",
    "D": "#ffd32a",
    "D#": "#0be881",
    "E": "#0fbcf9",
    "F": "#48dbfb",
    "F#": "#f368e0",
    "G": "#ff9ff3",
    "G#": "#54a0ff",
    "A": "#a29bfe",
    "A#": "#00d2d3",
    "B": "#fd79a8",
    "—": LABEL_DIM,
}

LOGO = (
    "██████╗ ██╗███████╗███████╗\n"
    "██╔══██╗██║██╔════╝██╔════╝\n"
    "██████╔╝██║█████╗  █████╗  \n"
    "██╔══██╗██║██╔══╝  ██╔══╝  \n"
    "██║  ██║██║██║     ██║     \n"
    "╚═╝  ╚═╝╚═╝╚═╝     ╚═╝  v0.1"
)


def note_color(note: str) -> str:
    return NOTE_COLORS.get(note, "#aaaaaa")
