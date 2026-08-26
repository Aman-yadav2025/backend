import json
import os
import urllib.request
import sys

def generate_markdown(openapi_schema):
    md_content = "# API Documentation\n\n"
    md_content += "This document is auto-generated from the FastAPI OpenAPI schema.\n\n"

    paths = openapi_schema.get("paths", {})
    
    # Group by tags
    tags_map = {}
    for path, methods in paths.items():
        for method, details in methods.items():
            tags = details.get("tags", ["default"])
            for tag in tags:
                if tag not in tags_map:
                    tags_map[tag] = []
                tags_map[tag].append({
                    "path": path,
                    "method": method.upper(),
                    "details": details
                })
                
    for tag, endpoints in sorted(tags_map.items()):
        md_content += f"## {tag.capitalize()}\n\n"
        
        for ep in endpoints:
            path = ep["path"]
            method = ep["method"]
            details = ep["details"]
            
            summary = details.get("summary", "No summary provided")
            description = details.get("description", "")
            
            md_content += f"### {method} `{path}`\n"
            md_content += f"**Summary:** {summary}\n\n"
            
            if description:
                md_content += f"{description}\n\n"
                
            # Request Body
            request_body = details.get("requestBody")
            if request_body:
                md_content += "**Request Payload:**\n"
                content = request_body.get("content", {})
                for content_type, content_details in content.items():
                    schema = content_details.get("schema", {})
                    ref = schema.get("$ref")
                    if ref:
                        schema_name = ref.split("/")[-1]
                        md_content += f"- Content-Type: `{content_type}`\n"
                        md_content += f"- Schema: `{schema_name}`\n"
                    else:
                        md_content += f"- Content-Type: `{content_type}`\n"
                md_content += "\n"
                
            # Parameters
            parameters = details.get("parameters", [])
            if parameters:
                md_content += "**Parameters:**\n"
                for param in parameters:
                    name = param.get("name")
                    in_ = param.get("in")
                    required = param.get("required", False)
                    md_content += f"- `{name}` ({in_}) - Required: {required}\n"
                md_content += "\n"
                
            md_content += "---\n\n"
            
    return md_content

if __name__ == "__main__":
    try:
        url = "http://localhost:8000/openapi.json"
        print(f"Fetching OpenAPI schema from {url}...")
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as response:
            schema = json.loads(response.read().decode())
            
        md = generate_markdown(schema)
        
        out_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "api.md")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(md)
            
        print(f"✅ Successfully generated API documentation at {out_path}")
    except Exception as e:
        print(f"❌ Failed to fetch schema: {e}")
        print("Please ensure your FastAPI backend is running on http://localhost:8000")
