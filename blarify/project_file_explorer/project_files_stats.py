from blarify.project_file_explorer.project_files_iterator import ProjectFilesIterator
import os
from typing import Optional
from blarify.logger import Logger


class ProjectFileStats:
    def __init__(self, project_files_iterator: ProjectFilesIterator):
        self.project_files_iterator = project_files_iterator
        self.file_stats = []
        self._analize()

    def _analize(self):
        for folder in self.project_files_iterator:
            for file in folder.files:
                file_stats = self.get_file_stats(file.path)
                if file_stats:
                    self.file_stats.append(file_stats)

        self._sort_stats()

    def _sort_stats(self):
        self.file_stats.sort(key=lambda x: x["size"], reverse=True)

    def print(self, limit: Optional[int] = None):
        file_stats = self.file_stats
        if limit:
            file_stats = file_stats[:limit]

        Logger.log(f"Top {len(file_stats)} files by size:")
        Logger.log(f"Total files: {len(self.file_stats)}")
        for file_stat in file_stats:
            Logger.log(f"{file_stat['name']} - {file_stat['lines_count']} lines - {file_stat['size']} bytes")

    def get_file_stats(self, file_path: str):
        file_lines = self._read_file(file_path)
        if not file_lines:
            return None

        return {
            "name": os.path.basename(file_path),
            "lines_count": len(file_lines),
            "size": os.path.getsize(file_path),
        }

    def _read_file(self, file_path: str):
        try:
            with open(file_path, "r") as file:
                return file.readlines()
        except UnicodeDecodeError:
            # Logger.log(f"Error reading file {file_path}: {e}")
            return []
