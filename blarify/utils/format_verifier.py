class FormatVerifier:
    @staticmethod
    def is_path_uri(path: str) -> bool:
        return path.startswith("file://")
