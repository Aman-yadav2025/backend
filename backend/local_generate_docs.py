import sys
import os
import json

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Temporarily override REDIS_URL to memory so the script doesn't crash
# if the local Python environment doesn't have the `redis` library installed!
os.environ["REDIS_URL"] = "memory://"

from app.main import app
from scripts.generate_api_docs import generate_markdown

try:
    schema = app.openapi()
    md = generate_markdown(schema)
    out_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), "api.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(md)
    print("✅ Successfully generated API documentation locally.")
except Exception as e:
    print(f"❌ Failed to generate schema: {e}")
    import traceback
    traceback.print_exc()
