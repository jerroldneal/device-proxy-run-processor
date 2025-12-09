import time
import os
import shutil
import subprocess
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import threading

# Configuration
DATA_DIR = "/app/data"
TODO_DIR = os.path.join(DATA_DIR, "todo")
TODO_ON_HOST_DIR = os.path.join(DATA_DIR, "todo-on-host")
WORKING_DIR = os.path.join(DATA_DIR, "working")
DONE_DIR = os.path.join(DATA_DIR, "done")

# Execution Mode: container (default), mock, host
RUN_MODE = os.environ.get("RUN_MODE", "host").lower()

# Event to wake up the main loop
fs_event = threading.Event()

class QueueHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory:
            fs_event.set()

    def on_moved(self, event):
        if not event.is_directory:
            fs_event.set()

def execute_file(file_path):
    print(f"Executing: {file_path}")
    ext = os.path.splitext(file_path)[1].lower()

    cmd = []
    if ext == '.sh':
        cmd = ['bash', file_path]
    elif ext == '.ps1':
        cmd = ['pwsh', file_path]
    elif ext == '.js':
        cmd = ['node', file_path]
    elif ext == '.py':
        cmd = ['python', file_path]
    else:
        print(f"Unsupported file type: {ext}")
        return

    if RUN_MODE == "mock":
        print(f"[MOCK] Would execute: {' '.join(cmd)}")
        return

    if RUN_MODE == "host":
        print(f"[HOST] Host execution not yet implemented. Would execute: {' '.join(cmd)}")
        # TODO: Implement host execution forwarding
        return

    try:
        # Execute the command
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False # Don't raise exception on non-zero exit code
        )

        print("--- STDOUT ---")
        print(result.stdout)
        print("--- STDERR ---")
        print(result.stderr)
        print(f"Exit Code: {result.returncode}")

    except Exception as e:
        print(f"Error executing {file_path}: {e}")

def process_working_item(filename):
    working_path = os.path.join(WORKING_DIR, filename)
    done_path = os.path.join(DONE_DIR, filename)

    try:
        if not os.path.exists(working_path):
            return

        execute_file(working_path)

        # Move to done
        if os.path.exists(working_path):
            shutil.move(working_path, done_path)
            print(f"Finished {filename}.")
        else:
            print(f"File {filename} no longer in working. Assuming cancelled.")

    except Exception as e:
        print(f"Error processing {filename}: {e}")

def get_oldest_file(directory):
    try:
        files = [f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))]
        if not files:
            return None
        files.sort(key=lambda x: os.path.getmtime(os.path.join(directory, x)))
        return files[0]
    except Exception:
        return None

def main():
    print(f"Starting Run Processor (Mode: {RUN_MODE})...")

    # Ensure directories exist
    os.makedirs(TODO_DIR, exist_ok=True)
    os.makedirs(TODO_ON_HOST_DIR, exist_ok=True)
    os.makedirs(WORKING_DIR, exist_ok=True)
    os.makedirs(DONE_DIR, exist_ok=True)

    # Setup Watchdog
    event_handler = QueueHandler()
    observer = Observer()
    observer.schedule(event_handler, TODO_DIR, recursive=False)
    observer.schedule(event_handler, WORKING_DIR, recursive=False)
    observer.start()
    print(f"Monitoring {TODO_DIR} and {WORKING_DIR} for changes...")

    try:
        while True:
            # 1. Check WORKING first (Priority)
            working_file = get_oldest_file(WORKING_DIR)
            if working_file:
                print(f"Found existing file in WORKING: {working_file}")
                process_working_item(working_file)
                continue

            # 2. Check TODO
            todo_file = get_oldest_file(TODO_DIR)
            if todo_file:
                if RUN_MODE == "host":
                    print(f"Moving {todo_file} to TODO_ON_HOST (Host Mode)...")
                    src = os.path.join(TODO_DIR, todo_file)
                    dst = os.path.join(TODO_ON_HOST_DIR, todo_file)
                    try:
                        shutil.move(src, dst)
                        continue
                    except Exception as e:
                        print(f"Error moving file to host todo: {e}")
                else:
                    print(f"Moving {todo_file} to WORKING...")
                    src = os.path.join(TODO_DIR, todo_file)
                    dst = os.path.join(WORKING_DIR, todo_file)
                    try:
                        shutil.move(src, dst)
                        continue
                    except Exception as e:
                        print(f"Error moving file: {e}")

            # 3. Wait for event or timeout
            fs_event.wait(timeout=1.0)
            fs_event.clear()

    except KeyboardInterrupt:
        print("Stopping...")
        observer.stop()

    observer.join()

if __name__ == "__main__":
    main()
