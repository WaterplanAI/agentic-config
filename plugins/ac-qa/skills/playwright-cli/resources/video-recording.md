# Video Recording

Record browser sessions as video files for evidence and documentation.

## Recording Commands

```bash
# Start recording
playwright-cli video-start

# Perform actions...
playwright-cli click "Submit"
playwright-cli snapshot

# Stop recording (saves video file)
playwright-cli video-stop
```

## Configuration

Set video resolution in `playwright-cli.json`:

```json
{
  "saveVideo": {
    "width": 1920,
    "height": 1080
  },
  "outputDir": "./outputs/e2e"
}
```

## Notes

- Videos are saved when `video-stop` is called
- Output directory defaults to current working directory unless configured
- Video format depends on playwright-cli version (typically WebM or MP4)
