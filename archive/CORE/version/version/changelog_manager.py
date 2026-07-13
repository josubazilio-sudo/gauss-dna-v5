from datetime import datetime, timezone
from typing import List


class ChangelogEntry:
    def __init__(self, version: str, change_type: str, description: str):
        self.version = version
        self.change_type = change_type
        self.description = description
        self.timestamp = datetime.now(timezone.utc)


class ChangelogManager:
    def __init__(self):
        self._entries: List[ChangelogEntry] = []

    def add_entry(self, version: str, change_type: str, description: str) -> None:
        entry = ChangelogEntry(version, change_type, description)
        self._entries.append(entry)

    def generate(self) -> str:
        lines = ["# Changelog\n"]
        for entry in self._entries:
            date = entry.timestamp.strftime("%Y-%m-%d")
            lines.append(f"## [{entry.version}] - {date}")
            lines.append(f"- [{entry.change_type}] {entry.description}\n")
        return "\n".join(lines)
