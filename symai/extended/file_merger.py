import os
from typing import List, Optional

from .. import Expression, FileReader, Indexer, Symbol


class FileMerger(Expression):
    """
    Class to merge contents of multiple files into one, specified by their file endings and root path.
    Files specified in the exclude list will not be included.
    """
    def __init__(self, file_endings: List[str] = ['.py', '.md', '.txt', '.sh', '.pdf', '.json', '.yaml'],
                       file_excludes: List[str] = ['__init__.py', '__pycache__', 'LICENSE', 'requirements.txt', 'environment.yaml', '.git']):
        super().__init__()
        self.file_endings = file_endings
        self.file_excludes = file_excludes
        self.reader = FileReader()

    def forward(self, root_path: str, **kwargs) -> Symbol:
        """
        Method to find, read, merge and return contents of files in the form of a Symbol starting from the root_path.

        The method recursively searches files with specified endings from the root path, excluding specific file names.
        Then, it reads all found files using the FileReader, merges them into one file (merged_file), and returns the
        merged file as a Symbol.
        """
        merged_file = ""

        # Implement recursive file search
        for root, dirs, files in os.walk(root_path):
            for file in files:
                file_path = os.path.join(root, file)
                # Exclude files with the specified names in the path
                if any(exclude in file_path for exclude in self.file_excludes):
                    continue

                # Look only for files with the specified endings
                if file.endswith(tuple(self.file_endings)):
                    # Read in the file using the FileReader
                    file_content = self.reader(file_path, **kwargs).value

                    # Append start and end markers for each file
                    file_content = f"# ----[FILE_START] {file_path}\n" + \
                                   file_content + \
                                   f"\n# ----[FILE_END] {file_path}\n"

                    # Merge the file contents
                    merged_file += file_content

        # Return the merged file as a Symbol
        return self._to_symbol(merged_file)