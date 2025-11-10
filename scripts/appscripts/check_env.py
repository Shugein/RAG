# check_env.py
"""Check what's loaded from .env file"""
import os
from dotenv import load_dotenv

print("Current working directory:", os.getcwd())
print()

# Try to find .env file
env_paths = [
    ".env",
    "../.env",
    "../../.env"
]

for path in env_paths:
    if os.path.exists(path):
        print(f"Found .env at: {path}")
        abs_path = os.path.abspath(path)
        print(f"Absolute path: {abs_path}")

        # Read file content
        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            print("\nAPI_KEY related lines:")
            for i, line in enumerate(lines, 1):
                if 'API_KEY' in line:
                    print(f"  Line {i}: {line.rstrip()}")
        break

print("\n" + "="*60)
print("Loading .env...")
load_dotenv()

print("\nEnvironment variables:")
print(f"API_KEY_2: {os.getenv('API_KEY_2')}")
print(f"OPENAI_API_KEY: {os.getenv('OPENAI_API_KEY')}")
