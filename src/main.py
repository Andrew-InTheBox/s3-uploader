import os
import time
import boto3
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from boto3.s3.transfer import TransferConfig
from datetime import datetime

# Configuration
WATCH_DIR = r"C:\BlueIris\New"
BUCKET = "security-cam-backups"
PREFIX = "camera/"
MAX_RETRIES = 3
STABLE_CHECKS = 3  # Number of consecutive checks file must be stable
EXCLUDED_PREFIXES = ["xxx123xxx", "yyy123yyy"]  # Add prefixes to exclude from backup

# S3 client with multipart upload configuration
s3 = boto3.client("s3")
transfer_config = TransferConfig(
    multipart_threshold=1024 * 25,  # 25 MB
    max_concurrency=10,
    multipart_chunksize=1024 * 25,  # 25 MB
    use_threads=True
)


class UploadHandler(FileSystemEventHandler):
    def __init__(self):
        self.uploading = set()  # Track files currently being processed
    
    def on_created(self, event):
        if event.is_directory:
            return
        
        path = event.src_path
        filename = os.path.basename(path)
        
        # Check if file starts with an excluded prefix
        if any(filename.startswith(prefix) for prefix in EXCLUDED_PREFIXES):
            self._log(f"Skipping excluded file: {filename}")
            return
        
        # Check file extension
        if not path.lower().endswith((".dat", ".bvr", ".avi", ".mov", ".jpg", ".mp4")):
            return
        
        # Prevent duplicate processing
        if path in self.uploading:
            return
        
        self.uploading.add(path)
        
        try:
            self._wait_for_file_ready(path)
            self._upload_to_s3(path)
        except FileNotFoundError:
            self._log(f"File disappeared: {path}")
        except Exception as e:
            self._log(f"Unexpected error processing {path}: {e}")
        finally:
            self.uploading.discard(path)
    
    def _wait_for_file_ready(self, path, timeout=60):
        """Wait until file is completely written and unlocked."""
        self._log(f"Waiting for file to stabilize: {path}")
        
        last_size = -1
        stable_count = 0
        start_time = time.time()
        
        while stable_count < STABLE_CHECKS:
            # Check timeout
            if time.time() - start_time > timeout:
                raise TimeoutError(f"File did not stabilize within {timeout}s")
            
            try:
                # Check if file still exists
                if not os.path.exists(path):
                    raise FileNotFoundError(f"File no longer exists: {path}")
                
                # Get file size
                size = os.path.getsize(path)
                
                # Try to open file to ensure it's not locked
                with open(path, 'rb') as f:
                    # Read first byte to verify access
                    f.read(1)
                
                # Check if size is stable
                if size == last_size and size > 0:
                    stable_count += 1
                else:
                    stable_count = 0
                
                last_size = size
                time.sleep(0.5)
                
            except PermissionError:
                # File is locked, reset counter
                stable_count = 0
                last_size = -1
                time.sleep(1)
            except OSError as e:
                # Handle other OS errors
                self._log(f"OS error while checking {path}: {e}")
                stable_count = 0
                time.sleep(1)
        
        self._log(f"File ready ({last_size} bytes): {path}")
    
    def _upload_to_s3(self, path):
        """Upload file to S3 with retry logic."""
        # Build S3 key
        rel_path = os.path.relpath(path, WATCH_DIR)
        key = PREFIX + rel_path.replace("\\", "/")
        
        # Get file size for logging
        file_size = os.path.getsize(path)
        file_size_mb = file_size / (1024 * 1024)
        
        # Retry loop
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                self._log(f"Uploading {os.path.basename(path)} ({file_size_mb:.1f} MB) -> s3://{BUCKET}/{key} (attempt {attempt}/{MAX_RETRIES})")
                
                start_time = time.time()
                s3.upload_file(
                    path,
                    BUCKET,
                    key,
                    Config=transfer_config
                )
                elapsed = time.time() - start_time
                
                self._log(f"✓ Successfully uploaded {os.path.basename(path)} in {elapsed:.1f}s")
                return  # Success, exit retry loop
                
            except s3.exceptions.NoSuchBucket:
                self._log(f"✗ ERROR: Bucket '{BUCKET}' does not exist!")
                return  # Don't retry for this error
                
            except Exception as e:
                self._log(f"✗ Upload attempt {attempt} failed: {e}")
                
                if attempt < MAX_RETRIES:
                    wait_time = 2 ** attempt  # Exponential backoff
                    self._log(f"Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    self._log(f"✗ FAILED to upload {path} after {MAX_RETRIES} attempts")
    
    def _log(self, message):
        """Log message with timestamp."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {message}")


def main():
    # Verify watch directory exists
    if not os.path.exists(WATCH_DIR):
        print(f"ERROR: Watch directory does not exist: {WATCH_DIR}")
        return
    
    # Verify AWS credentials
    try:
        s3.head_bucket(Bucket=BUCKET)
        print(f"✓ Connected to S3 bucket: {BUCKET}")
    except s3.exceptions.NoSuchBucket:
        print(f"ERROR: S3 bucket '{BUCKET}' does not exist or you don't have access")
        return
    except Exception as e:
        print(f"ERROR: Could not connect to S3: {e}")
        print("Make sure AWS credentials are configured (aws configure)")
        return
    
    print(f"Monitoring directory: {WATCH_DIR}")
    print(f"Uploading to: s3://{BUCKET}/{PREFIX}")
    print(f"Press Ctrl+C to stop...\n")
    
    # Set up file system observer
    event_handler = UploadHandler()
    observer = Observer()
    observer.schedule(event_handler, WATCH_DIR, recursive=True)
    observer.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping monitor...")
        observer.stop()
    
    observer.join()
    print("Monitor stopped.")


if __name__ == "__main__":
    main()