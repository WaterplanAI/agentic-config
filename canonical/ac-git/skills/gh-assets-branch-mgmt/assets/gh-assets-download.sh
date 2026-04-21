#!/usr/bin/env bash
#
# gh-assets-download.sh - Download videos from GitHub assets branch
#
# Usage: gh-assets-download.sh <context> [options]
#
# Options:
#   --all          Download all videos (default: latest only)
#   --list         List videos without downloading
#   --no-open      Don't open video after download
#   --output <dir> Download directory (default: /tmp)
#
# Examples:
#   gh-assets-download.sh pr-42              # Download & open latest video
#   gh-assets-download.sh pr-42 --all        # Download all videos
#   gh-assets-download.sh pr-42 --list       # List available videos
#
set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${GREEN}+${NC} $1"; }
log_warn() { echo -e "${YELLOW}!${NC} $1"; }
log_error() { echo -e "${RED}x${NC} $1" >&2; }
log_step() { echo -e "${BLUE}>${NC} $1"; }

usage() {
    echo "Usage: $0 <context> [options]"
    echo ""
    echo "Options:"
    echo "  --all          Download all videos (default: latest only)"
    echo "  --list         List videos without downloading"
    echo "  --no-open      Don't open video after download"
    echo "  --output <dir> Download directory (default: /tmp)"
    echo "  --repo <owner/repo>  Repository (default: current repo)"
    echo ""
    echo "Examples:"
    echo "  $0 pr-42              # Download & open latest video"
    echo "  $0 pr-42 --all        # Download all videos"
    echo "  $0 pr-42 --list       # List available videos"
    exit 1
}

# Parse arguments
CONTEXT=""
DOWNLOAD_ALL="false"
LIST_ONLY="false"
OPEN_VIDEO="true"
OUTPUT_DIR="/tmp"
REPO=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --all)
            DOWNLOAD_ALL="true"
            shift
            ;;
        --list)
            LIST_ONLY="true"
            shift
            ;;
        --no-open)
            OPEN_VIDEO="false"
            shift
            ;;
        --output)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --repo)
            REPO="$2"
            shift 2
            ;;
        -h|--help)
            usage
            ;;
        *)
            if [[ -z "$CONTEXT" ]]; then
                CONTEXT="$1"
            else
                log_error "Unknown argument: $1"
                usage
            fi
            shift
            ;;
    esac
done

# Validate context
[[ -z "$CONTEXT" ]] && usage

# Get repo if not specified
if [[ -z "$REPO" ]]; then
    REPO=$(gh repo view --json nameWithOwner -q '.nameWithOwner' 2>/dev/null || echo "")
    if [[ -z "$REPO" ]]; then
        log_error "Could not determine repository. Use --repo <owner/repo>"
        exit 1
    fi
fi

echo "=== GitHub Assets Download ==="
echo "Repository: $REPO"
echo "Context:    $CONTEXT"
echo ""

# List files in the context directory on assets branch
log_step "Fetching file list..."
FILES_JSON=$(gh api "repos/$REPO/contents/$CONTEXT?ref=assets" 2>/dev/null || echo "[]")

if [[ "$FILES_JSON" == "[]" ]] || [[ "$FILES_JSON" == *"Not Found"* ]]; then
    log_error "No files found in context: $CONTEXT"
    exit 1
fi

# Filter for video files (MP4)
VIDEOS=$(echo "$FILES_JSON" | jq -r '.[] | select(.name | test("\\.(mp4|MP4)$")) | .name' 2>/dev/null || echo "")

if [[ -z "$VIDEOS" ]]; then
    log_warn "No video files (.mp4) found in context: $CONTEXT"
    echo ""
    echo "Available files:"
    echo "$FILES_JSON" | jq -r '.[].name' 2>/dev/null || echo "  (none)"
    exit 0
fi

# Convert to array
mapfile -t VIDEO_ARRAY <<< "$VIDEOS"
VIDEO_COUNT=${#VIDEO_ARRAY[@]}

echo "Found $VIDEO_COUNT video(s):"
for v in "${VIDEO_ARRAY[@]}"; do
    echo "  - $v"
done
echo ""

# List only mode
if [[ "$LIST_ONLY" == "true" ]]; then
    exit 0
fi

# Determine which videos to download
if [[ "$DOWNLOAD_ALL" == "true" ]]; then
    DOWNLOAD_LIST=("${VIDEO_ARRAY[@]}")
else
    # Get latest (last in alphabetical order, which works for timestamped names)
    LATEST="${VIDEO_ARRAY[-1]}"
    DOWNLOAD_LIST=("$LATEST")
    log_step "Downloading latest: $LATEST"
fi

# Download videos
DOWNLOADED=()
for video in "${DOWNLOAD_LIST[@]}"; do
    output_path="$OUTPUT_DIR/$video"
    log_step "Downloading $video..."

    if gh api "repos/$REPO/contents/$CONTEXT/$video?ref=assets" --jq '.content' 2>/dev/null | base64 -d > "$output_path"; then
        log_info "Downloaded: $output_path"
        DOWNLOADED+=("$output_path")
    else
        # Try raw download method
        if gh api "repos/$REPO/contents/$CONTEXT/$video?ref=assets" -H "Accept: application/vnd.github.raw" > "$output_path" 2>/dev/null; then
            log_info "Downloaded: $output_path"
            DOWNLOADED+=("$output_path")
        else
            log_error "Failed to download: $video"
        fi
    fi
done

# Open video(s) if requested
if [[ "$OPEN_VIDEO" == "true" ]] && [[ ${#DOWNLOADED[@]} -gt 0 ]]; then
    echo ""
    for path in "${DOWNLOADED[@]}"; do
        log_step "Opening: $path"
        open "$path" 2>/dev/null || xdg-open "$path" 2>/dev/null || log_warn "Could not open video"
    done
fi

echo ""
log_info "Done. Downloaded ${#DOWNLOADED[@]} video(s) to $OUTPUT_DIR"
