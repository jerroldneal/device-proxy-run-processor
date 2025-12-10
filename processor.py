import time
import os
import shutil
import subprocess
import json
import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import threading
from concurrent.futures import ThreadPoolExecutor

# Configuration
# Use local data directory relative to this script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Allow configuration via environment variable, default to local 'data' folder
DATA_DIR = os.environ.get('RUN_PROCESSOR_ROOT', os.path.join(BASE_DIR, "data"))
RUN_MODE = os.environ.get('RUN_MODE', 'host') # 'host' or 'container'

TODO_DIR = os.path.join(DATA_DIR, "todo")
WORKING_DIR = os.path.join(DATA_DIR, "working")
DONE_DIR = os.path.join(DATA_DIR, "done")
SCRIPTS_DIR = os.path.join(DATA_DIR, "scripts")

# Host directories (for forwarding)
TODO_HOST_DIR = os.path.join(DATA_DIR, "todo-on-host")
WORKING_HOST_DIR = os.path.join(DATA_DIR, "working-on-host")

# Concurrency
MAX_WORKERS = 5
active_tasks = set() # Track filenames currently being processed
active_tasks_lock = threading.Lock()

# Event to wake up the main loop
fs_event = threading.Event()

class QueueHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory:
            fs_event.set()

    def on_moved(self, event):
        if not event.is_directory:
            fs_event.set()

def execute_script(script_path, language):
    print(f"Executing: {script_path} ({language})")

    cmd = []
    if language == 'powershell' or script_path.endswith('.ps1'):
        cmd = ['pwsh', script_path]
    elif language == 'bash' or script_path.endswith('.sh'):
        cmd = ['bash', script_path]
    elif language == 'python' or script_path.endswith('.py'):
        cmd = ['python', script_path]
    elif language == 'node' or script_path.endswith('.js'):
        cmd = ['node', script_path]
    else:
        return {
            "success": False,
            "stdout": "",
            "stderr": f"Unsupported language/extension: {language} / {script_path}",
            "exit_code": -1
        }

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode
        }
    except Exception as e:
        return {
            "success": False,
            "stdout": "",
            "stderr": str(e),
            "exit_code": -1
        }

def safe_move(src, dst, retries=5, delay=1.0):
    for i in range(retries):
        try:
            shutil.move(src, dst)
            return True
        except (PermissionError, OSError) as e:
            if i < retries - 1:
                print(f"Move failed (attempt {i+1}/{retries}): {e}. Retrying in {delay}s...")
                time.sleep(delay)
            else:
                print(f"Move failed permanently: {e}")
                return False
    return False

def process_manifest(filename):
    with active_tasks_lock:
        if filename in active_tasks:
            return
        active_tasks.add(filename)

    try:
        _process_manifest_logic(filename)
    finally:
        with active_tasks_lock:
            active_tasks.remove(filename)

def _process_manifest_logic(filename):
    working_path = os.path.join(WORKING_DIR, filename)

    if not os.path.exists(working_path):
        print(f"Manifest not found: {working_path}")
        return

    try:
        with open(working_path, 'r') as f:
            manifest = json.load(f)

        if not isinstance(manifest, dict):
            raise ValueError("Manifest must be a JSON object")

    except Exception as e:
        print(f"Failed to load manifest {filename}: {e}")
        # Move to done (failed)
        dst_path = os.path.join(DONE_DIR, filename)

        # Handle collision in DONE
        if os.path.exists(dst_path):
            base, ext = os.path.splitext(filename)
            dst_path = os.path.join(DONE_DIR, f"{base}_err_{int(time.time())}{ext}")

        if not safe_move(working_path, dst_path):
            print(f"CRITICAL: Could not move bad manifest {filename} to DONE. Renaming to .bad")
            try:
                os.rename(working_path, working_path + ".bad")
            except Exception as rename_err:
                print(f"CRITICAL: Could not rename bad manifest {filename}: {rename_err}")
        return

    print(f"Processing Task: {manifest.get('id', 'unknown')} - {manifest.get('goal', 'no goal')}")

    # Resolve Script Path
    script_ref = manifest.get('script_ref')
    # script_ref is relative to DATA_DIR (e.g. "scripts/foo.ps1")
    script_path = os.path.join(DATA_DIR, script_ref)

    if not os.path.exists(script_path):
        print(f"Script not found: {script_path}")
        result = {
            "success": False,
            "stdout": "",
            "stderr": f"Script file not found: {script_ref}",
            "exit_code": -1
        }
    else:
        # Execute
        result = execute_script(script_path, manifest.get('language'))

    # Update History
    history_entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "attempt": manifest.get('attempt_count', 0) + 1,
        "script_used": script_ref,
        "exit_code": result['exit_code'],
        "stdout": result['stdout'],
        "stderr": result['stderr'],
        "verification_failed": False # Placeholder for future logic
    }

    manifest.setdefault('history', []).append(history_entry)
    manifest['attempt_count'] = manifest.get('attempt_count', 0) + 1

    if result['success']:
        manifest['status'] = "COMPLETED"
        # Save and Move to DONE
        with open(working_path, 'w') as f:
            json.dump(manifest, f, indent=2)
        safe_move(working_path, os.path.join(DONE_DIR, filename))
        print(f"Task {manifest['id']} COMPLETED.")
    else:
        max_retries = manifest.get('max_retries', 0)
        current_attempts = manifest.get('attempt_count', 0)

        if current_attempts < max_retries:
            manifest['status'] = "RETRYING"
            print(f"Task {manifest['id']} FAILED (Attempt {current_attempts}/{max_retries}). Retrying...")
            # Save and Keep in WORKING
            with open(working_path, 'w') as f:
                json.dump(manifest, f, indent=2)
            # Optional: Sleep to prevent tight loop if it's the only file
            time.sleep(2)
        else:
            manifest['status'] = "FAILED"
            print(f"Task {manifest['id']} FAILED (Max retries reached). Moving to DONE.")
            with open(working_path, 'w') as f:
                json.dump(manifest, f, indent=2)
            safe_move(working_path, os.path.join(DONE_DIR, filename))
def get_all_working_files(directory):
    try:
        return [f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f)) and f.endswith('.json')]
    except Exception:
        return []

def get_oldest_json_file(directory):
    try:
        files = [f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f)) and f.endswith('.json')]
        if not files:
            return None
        files.sort(key=lambda x: os.path.getmtime(os.path.join(directory, x)))
        return files[0]
    except Exception:
        return None

def main():
    print(f"Starting Run Processor V2 (Concurrent Mode)...")
    print(f"Data Directory: {DATA_DIR}")

    # Ensure directories exist
    os.makedirs(TODO_DIR, exist_ok=True)
    os.makedirs(WORKING_DIR, exist_ok=True)
    os.makedirs(DONE_DIR, exist_ok=True)
    os.makedirs(SCRIPTS_DIR, exist_ok=True)

    if RUN_MODE == 'host':
        os.makedirs(TODO_HOST_DIR, exist_ok=True)
        os.makedirs(WORKING_HOST_DIR, exist_ok=True)

    # Setup Watchdog
    event_handler = QueueHandler()
    observer = Observer()
    observer.schedule(event_handler, TODO_DIR, recursive=False)
    observer.start()
    print(f"Monitoring {TODO_DIR}...")
    print(f"Run Mode: {RUN_MODE}")

    executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)

    try:
        while True:
            # 1. Check WORKING first (Crash recovery & Active tasks)
            # Only process working files if we are in container mode (or if we want to resume local tasks)
            # If in host mode, we shouldn't have files in WORKING usually, unless we are processing them locally.
            # But let's assume we might have some.
            working_files = get_all_working_files(WORKING_DIR)
            for working_file in working_files:
                with active_tasks_lock:
                    if working_file not in active_tasks:
                        print(f"Submitting existing file in WORKING: {working_file}")
                        executor.submit(process_manifest, working_file)

            # 2. Check TODO
            todo_file = get_oldest_json_file(TODO_DIR)
            if todo_file:
                print(f"Picking up {todo_file}...")
                src = os.path.join(TODO_DIR, todo_file)

                if RUN_MODE == 'host':
                    # Forward to Host
                    dst = os.path.join(TODO_HOST_DIR, todo_file)
                    print(f"Forwarding {todo_file} to Host ({dst})...")
                    if safe_move(src, dst):
                        continue
                    else:
                        print(f"Failed to move {todo_file} to TODO_HOST after retries.")
                        time.sleep(1)
                else:
                    # Process Locally (Container)
                    dst = os.path.join(WORKING_DIR, todo_file)
                    if safe_move(src, dst):
                        # Loop will catch it in WORKING next iteration
                        continue
                    else:
                        print(f"Failed to move {todo_file} to WORKING after retries.")
                        time.sleep(1)

            # 3. Wait for event or timeout
            fs_event.wait(timeout=1.0)
            fs_event.clear()

    except KeyboardInterrupt:
        print("Stopping...")
        observer.stop()
        executor.shutdown(wait=False)
    observer.join()

if __name__ == "__main__":
    main()
