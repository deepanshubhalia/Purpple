# Video dataset (CCTV clips)

Place retail CCTV videos here, or upload via the dashboard (**Cameras** tab) or API.

## Folder layout (batch / CLI)

```
data/clips/
  store_001/
    entry_cam_01.mp4
    floor_cam_01.mp4
    billing_cam_01.mp4
  store_002/
    ...
```

## Run analysis from terminal

```bash
cd backend
.venv/bin/python -m app.detect --input data/clips/ --output events.jsonl
```

## Upload via API

```bash
curl -X POST http://127.0.0.1:8001/detect/analyze \
  -F "file=@/path/to/your/video.mp4" \
  -F "store_id=store_001" \
  -F "camera_id=entry_cam_01" \
  -F "ingest=true"
```

Supported formats: `.mp4`, `.avi`, `.mov`, `.webm`, `.mkv` (max 200MB per file).
