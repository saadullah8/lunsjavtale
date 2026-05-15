import subprocess
import sys

def run_cmd(cmd):
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print(f"Error: {result.stderr}")

run_cmd(f"{sys.executable} manage.py makemigrations scm")
run_cmd(f"{sys.executable} manage.py migrate scm")
