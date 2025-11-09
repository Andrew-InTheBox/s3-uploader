import os, time, boto3
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

WATCH_DIR = r"C:\BlueIris\New"
BUCKET = "security-cam-backups"
PREFIX = "camera/"

s3 = boto3.client("s3")

class UploadHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory: return
        path = event.src_path
        if not path.lower().endswith((".mp4",".bvr",".avi",".mov",".jpg")):
            return
        # wait until file stops growing
        last = -1
        while True:
            try:
                size = os.path.getsize(path)
            except FileNotFoundError:
                return
            if size == last:
                break
            last = size
            time.sleep(0.5)
        key = PREFIX + os.path.relpath(path, WATCH_DIR).replace("\\", "/")
        print(f"Uploading {path} -> s3://{BUCKET}/{key}")
        s3.upload_file(path, BUCKET, key)

if __name__ == "__main__":
    event_handler = UploadHandler()
    observer = Observer()
    observer.schedule(event_handler, WATCH_DIR, recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
