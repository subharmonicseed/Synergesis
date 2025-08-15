import requests
import json

ARCHON_SERVER_URL = "http://localhost:8181"

def get_todo_tasks():
    try:
        response = requests.get(f"{ARCHON_SERVER_URL}/api/tasks?status=todo")
        response.raise_for_status()  # Raise an exception for bad status codes
        tasks = response.json()
        if tasks:
            print(json.dumps(tasks, indent=2))
        else:
            print("No tasks found in 'todo' state.")
    except requests.exceptions.RequestException as e:
        print(f"Error fetching tasks: {e}")

if __name__ == "__main__":
    get_todo_tasks()
