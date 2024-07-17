import os
import subprocess


class DumpWidgets:
    @staticmethod
    def generate_hex_dump(file_path):
        if not os.path.isfile(file_path):
            return f"Error: File '{file_path}' does not exist"

        try:
            command = f"hexyl {file_path} 2>&1 | ./terminal-to-html-3.14.0-linux-amd64 -preview"
            result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if result.returncode != 0:
                return f"Error: {result.stderr}"
            return result.stdout
        except Exception as e:
            return str(e)
