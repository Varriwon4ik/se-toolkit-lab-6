#!/usr/bin/env python3
"""Simple script to seed database via HTTP API calls."""

import urllib.request
import urllib.error
import json
import os

API_BASE = os.environ.get("AGENT_API_BASE_URL", "http://localhost:42002")
LMS_API_KEY = os.environ.get("LMS_API_KEY", "my-secret-api-key")


def make_request(method, path, body=None):
    """Make HTTP request to the API."""
    url = f"{API_BASE}{path}"
    headers = {"Content-Type": "application/json"}
    if LMS_API_KEY:
        headers["Authorization"] = f"Bearer {LMS_API_KEY}"
    
    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return {"status_code": resp.status, "body": json.loads(resp.read().decode())}
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else ""
        return {"status_code": e.code, "body": error_body}
    except urllib.error.URLError as e:
        return {"status_code": 0, "body": f"Connection error: {e.reason}"}


def seed_items():
    """Create sample items via API."""
    print("Seeding items...")
    
    # Create labs
    labs = [
        {"type": "lab", "title": "lab-1", "description": "Python Basics"},
        {"type": "lab", "title": "lab-2", "description": "Data Structures"},
        {"type": "lab", "title": "lab-3", "description": "Functions"},
        {"type": "lab", "title": "lab-6", "description": "Software Engineering Toolkit"},
    ]
    
    lab_ids = []
    for lab in labs:
        result = make_request("POST", "/items/", lab)
        if result["status_code"] in (200, 201):
            item = result["body"]
            lab_ids.append(item["id"])
            print(f"  Created: {lab['title']} (id={item['id']})")
        else:
            print(f"  Skip {lab['title']}: {result}")
    
    # Create tasks for each lab
    tasks = [
        (lab_ids[0], "task-1-1", "Variables and Types"),
        (lab_ids[0], "task-1-2", "Control Flow"),
        (lab_ids[1], "task-2-1", "Lists and Tuples"),
        (lab_ids[1], "task-2-2", "Dictionaries"),
        (lab_ids[2], "task-3-1", "Defining Functions"),
        (lab_ids[2], "task-3-2", "Lambda Functions"),
        (lab_ids[3], "task-6-1", "Agent Setup"),
        (lab_ids[3], "task-6-2", "Documentation Agent"),
        (lab_ids[3], "task-6-3", "System Agent"),
    ]
    
    for parent_id, title, desc in tasks:
        task = {"type": "task", "parent_id": parent_id, "title": title, "description": desc}
        result = make_request("POST", "/items/", task)
        if result["status_code"] in (200, 201):
            print(f"  Created: {title}")
        else:
            print(f"  Skip {title}: {result}")


if __name__ == "__main__":
    # Check if database is empty
    result = make_request("GET", "/items/")
    if result["status_code"] == 200 and len(result["body"]) == 0:
        print("Database is empty. Seeding...")
        seed_items()
    else:
        print(f"Database already has {len(result['body'])} items. Skipping seed.")
    
    # Verify
    result = make_request("GET", "/items/")
    print(f"\nTotal items: {len(result.get('body', []))}")
