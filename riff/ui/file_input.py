from __future__ import annotations

import glob
import os


def complete_path(partial: str) -> list[str]:
    expanded = os.path.expanduser(partial)
    matches = glob.glob(expanded + "*")
    results = []
    for m in matches:
        if os.path.isdir(m) and not m.endswith("/"):
            results.append(m + "/")
        else:
            results.append(m)
    return sorted(results)


class InputBuffer:
    def __init__(self) -> None:
        self.text = ""

    def append(self, ch: str) -> None:
        self.text += ch

    def backspace(self) -> None:
        self.text = self.text[:-1]

    def clear(self) -> None:
        self.text = ""

    def tab_complete(self) -> None:
        matches = complete_path(self.text)
        if not matches:
            return
        if len(matches) == 1:
            self.text = matches[0]
        else:
            prefix = os.path.commonprefix(matches)
            if prefix:
                self.text = prefix
