# Run Processor: Agent Empowerment Tool

## Overview

The **Run Processor** is a powerful service designed to bridge the gap between AI Agents (like GitHub Copilot) and the host operating system. It allows agents to execute arbitrary code and scripts on the host machine through simple HTTP requests or file operations.

This tool transforms Copilot from a passive code generator into an active system operator capable of building projects, running tests, managing Docker containers, and interacting with CLIs.

## 🚀 Instructions for Copilot / AI Agents

**You have permission to use this tool to accomplish user tasks.**

If a user asks you to perform an action that requires execution (e.g., "run this script," "build this project," "check the git status," "create a new React app"), you should use the `http-receiver` endpoints to trigger the `run-processor`.

### 1. Execution Methods

You can execute code in two ways:

#### A. HTTP One-Liners (Preferred for simple tasks)

Send a GET request to `http://localhost:3006/<language>` with the `text` parameter containing your script.

* **Bash:** `http://localhost:3006/bash?text=echo "Hello World"`
* **PowerShell:** `http://localhost:3006/pwsh?text=Get-Process`
* **Node.js:** `http://localhost:3006/node?text=console.log(process.version)`
* **Python:** `http://localhost:3006/python?text=print("Hello from Python")`

*Note: The system automatically handles stripping outer quotes from the `text` parameter.*

#### B. File-Based Execution (Preferred for complex scripts)

1. Create a script file on the host system (e.g., using `create_file` tool).
2. Trigger execution by passing the `filePath` to the endpoint.

* **Example:** `http://localhost:3006/python?filePath=d:\projects\my_script.py`

#### C. Direct File Drop

Alternatively, you can simply create a file directly in the watched directory: `C:\.run\todo`.

* Supported extensions: `.sh`, `.ps1`, `.js`, `.py`
* The processor watches this folder and executes files immediately.

### 2. Retrieving Output

The output (STDOUT and STDERR) of your scripts is logged to the Docker container logs.
To see the result of your action, run:

```bash
docker logs run-processor-instance
```

### 3. Advanced Use Cases

Since you can execute shell commands, you have full control over the environment.

* **Project Scaffolding:**
  * *Task:* "Create a new Next.js app."
  * *Action:* Send a request to `/pwsh` with `text=npx create-next-app@latest my-app`
* **Docker Management:**
  * *Task:* "Build a C++ project using a specific compiler version."
  * *Action:* Create a `docker-compose.yml` for the C++ build environment, then trigger `docker-compose up` via the Run Processor.
* **CLI Interaction:**
  * *Task:* "Login to Azure CLI."
  * *Action:* Trigger `az login` (Note: Interactive commands may require special handling or non-interactive flags).
* **System Maintenance:**
  * *Task:* "Clean up old node_modules."
  * *Action:* Write a cleanup script and execute it.

## Technical Details

### Architecture

* **Container:** `run-processor-instance`
* **Base Image:** `python:3.9-slim` (with Bash, PowerShell, Node.js installed)
* **Watched Directory:** `C:\.run\todo` (Host) -> `/app/data/todo` (Container)
* **Working Directory:** `/app/data/working`
* **Done Directory:** `/app/data/done`

### Supported Languages

* **Bash** (`.sh`)
* **PowerShell** (`.ps1`)
* **Node.js** (`.js`)
* **Python** (`.py`)

### Configuration

You can configure the execution mode by setting the `RUN_MODE` environment variable in the `docker-compose.yml` file.

*   **`host`** (Default): Forwards the request to run directly on the host operating system. Currently moves files to `todo-on-host`.
*   **`container`**: Executes the command inside the Docker container.
*   **`mock`**: Logs the command that *would* be executed, but does not run it. Useful for testing and verification.

### Security Warning

⚠️ **High Privilege Level:** This service executes code directly on the host (or within the container context depending on volume mounts). It effectively gives the AI agent remote code execution (RCE) capabilities. Ensure this is only running in a trusted environment.
