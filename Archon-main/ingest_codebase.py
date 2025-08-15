import os
import requests
import time

ARCHON_API_URL = "http://localhost:8181/api/documents/upload"
SYNERGESIS_CODE_DIR = "c:\\Users\\Lenovo\\Desktop\\BigSyn\\Syn"

ALLOWED_EXTENSIONS = ['.py', '.md', '.txt']
EXCLUDED_DIRS = ['.git', '.venv', '__pycache__', '.pytest_cache', 'conversations', 'venv']
EXCLUDED_FILES = ['requirements.txt']

def ingest_codebase(session):
    print(f"Starting ingestion from {SYNERGESIS_CODE_DIR}...")
    file_count = 0
    for root, dirs, files in os.walk(SYNERGESIS_CODE_DIR):
        # Modify dirs in-place to skip excluded directories
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]

        for file in files:
            if file in EXCLUDED_FILES:
                continue

            if any(file.endswith(ext) for ext in ALLOWED_EXTENSIONS):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'rb') as f:
                        file_content = f.read()
                        if not file_content.strip():
                            print(f"Skipping empty file: {file_path}")
                            continue

                        relative_path = os.path.relpath(file_path, SYNERGESIS_CODE_DIR)
                        tags = ['synergesis_codebase'] + relative_path.split(os.sep)
                        payload = {
                            'file': (os.path.basename(file_path), open(file_path, 'rb'), 'application/octet-stream'),
                            'tags': (None, ','.join(tags)),
                            'knowledge_type': (None, 'technical')
                        }
                        
                        print(f"Uploading {file_path}...")
                        response = session.post(ARCHON_API_URL, files=payload)
                        
                        if response.status_code == 200:
                            print(f"  -> Success: {file_path}")
                            file_count += 1
                        else:
                            print(f"  -> Failed: {file_path} | Status: {response.status_code} | Response: {response.text[:100]}")
                        
                        time.sleep(0.1) # Avoid overwhelming the server

                except Exception as e:
                    print(f"Could not process file {file_path}: {e}")

    print(f"\nIngestion complete. Uploaded {file_count} files.")

def main():
    with requests.Session() as session:
        ingest_codebase(session)

if __name__ == "__main__":
    main()
