# Camera Uploader

Overview
- Monitors a local directory (e.g., Blue Iris "New" folder) for new video/image files and uploads them to an S3 bucket.
- Uses watchdog to detect new files, waits until files are stable/unlocked, then uploads with boto3 using multipart transfer where appropriate.
- Handles retries with exponential backoff.

Key features
- Detects common camera file types (.dat, .bvr, .avi, .mov, .jpg, .mp4)
- Waits for files to be fully written and unlocked before uploading
- Multipart upload for large files (configurable)
- Retry logic with exponential backoff
- Simple timestamped console logging

Prerequisites
- Python 3.7+
- pip
- AWS account with an S3 bucket and credentials configured locally (see below)

Python dependencies
- boto3
- watchdog

Install dependencies
- Create a virtual environment (recommended)
  - python -m venv .venv
  - .venv\Scripts\activate  (Windows)
- Install packages:
  - pip install boto3 watchdog

AWS credentials
- Configure AWS credentials using the AWS CLI or environment variables:
  - aws configure
  - or set AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, and optionally AWS_SESSION_TOKEN and AWS_DEFAULT_REGION

Configuration (edit src/main.py)
- WATCH_DIR: Path to monitor (default in script: C:\BlueIris\New)
- BUCKET: Target S3 bucket name
- PREFIX: Prefix (folder) inside the bucket where files will be uploaded
- MAX_RETRIES: Number of upload attempts before giving up
- STABLE_CHECKS: Number of consecutive stable size checks before considering a file ready
- TransferConfig options (multipart threshold/chunk size, concurrency) are defined in the script

Running
- From project root:
  - python src\main.py
- The script will:
  - verify the watch directory exists
  - check access to the configured S3 bucket
  - start monitoring and upload created files

Behavior notes
- The handler waits until a file's size is stable for STABLE_CHECKS consecutive checks and attempts to open the file before uploading. Adjust STABLE_CHECKS and timeouts if files are large or writes are slow.
- Files temporarily locked by other processes will be retried until readable or timed out.
- Uploads use multipart transfer for files larger than the configured multipart_threshold.

Logging
- Simple console logging with timestamps. Example messages:
  - "Waiting for file to stabilize"
  - "File ready (X bytes)"
  - "Uploading ... attempt N"
  - "Successfully uploaded ..."
  - Errors and retry messages are printed to console.

Troubleshooting
- "Watch directory does not exist": ensure WATCH_DIR path is correct and accessible by the user running the script.
- "S3 bucket does not exist or you don't have access": verify the BUCKET name and that your AWS credentials have s3:ListBucket and s3:PutObject permissions.
- PermissionError while reading files: ensure the account running the script has read access to the camera output folder.
- If uploads fail often, increase MAX_RETRIES or check network stability.

Optional / Deployment tips
- Run as a Windows service (e.g., NSSM) or schedule a persistent process in the background.
- Consider sending logs to a file or central logging service for long-term monitoring.
- Add heuristics to delete or archive local files after successful upload (not implemented in the script).
- For high-volume environments, tune TransferConfig (multipart_chunksize, max_concurrency) and STABLE_CHECKS to balance throughput vs correctness.

## Windows Task Scheduler (task-scheduler)

Files
- Task XML (standalone import): `c:\camera-uploader\task-scheduler\task.xml`
- Optional startup script: `c:\camera-uploader\task-scheduler\start-cam-watcher.bat`

Note: task.xml is a complete, standalone Task Scheduler export. It can be imported directly into Task Scheduler and does not require the batch file unless the task XML's action explicitly references it. The batch file is provided as a simple, alternative way to start the watcher manually or to call from a task if you prefer to wrap execution in a script.

Importing the task (task.xml)
- Using schtasks (CMD):
  - schtasks /Create /XML "c:\camera-uploader\task-scheduler\task.xml" /TN "CameraWatcher"
- Using PowerShell:
  - Register-ScheduledTask -Xml (Get-Content 'c:\camera-uploader\task-scheduler\task.xml' -Raw) -TaskName "CameraWatcher"
- Using the GUI:
  - Open Task Scheduler → Action → Import Task… → select `task.xml`.

Using the batch script (start-cam-watcher.bat)
- The batch file is standalone; run it directly to start the watcher in the foreground:
  - c:\camera-uploader\task-scheduler\start-cam-watcher.bat
- If you want the scheduled task to run the batch instead of calling Python directly, ensure the task.xml's <Command> (or the imported task action) points to the batch file's absolute path.

Adjust before importing
- Open `task.xml` and confirm the Action's Command points to the intended executable/script:
  - either the venv python (e.g., `C:\camera-uploader\venv\Scripts\python.exe` with argument `C:\camera-uploader\src\main.py`)
  - or the batch file `C:\camera-uploader\task-scheduler\start-cam-watcher.bat`
- If you edit the XML, make sure paths are absolute and accessible by the account that will run the task.

Recommended task settings
- Run whether user is logged on or not (for startup)
- Run with highest privileges if needed
- Trigger at system startup or on user login, as desired

Test and manage the task
- Run immediately:
  - schtasks /Run /TN "CameraWatcher"  (or Start-ScheduledTask -TaskName "CameraWatcher")
- Query status:
  - schtasks /Query /TN "CameraWatcher" /V

Troubleshooting
- If the task fails on boot, check:
  - The task action path (batch vs python) is correct
  - Permissions and "Log on as a batch job" if required
  - Virtual environment paths are valid
  - Task history for error codes

License / Attribution
- This README is provided as documentation for the included script. Adjust and extend as needed for your environment.
