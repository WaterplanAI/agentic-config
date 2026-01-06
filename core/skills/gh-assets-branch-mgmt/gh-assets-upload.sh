#!/usr/bin/env bash
#
# gh-assets-upload.sh - Upload files to GitHub assets branch
#
# Usage: gh-assets-upload.sh <source-dir-or-glob> <context> [owner/repo]
#
# Examples:
#   gh-assets-upload.sh ./screenshots pr-42
#   gh-assets-upload.sh "./outputs/*.png" pr-42 owner/my-repo
#
# Requirements:
#   - gh CLI authenticated
#   - base64 command available
#   - ffmpeg (for video conversion)
#
set -euo pipefail

# Script directory for sibling tools
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

usage() {
    echo "Usage: $0 <source-dir-or-glob> <context> [owner/repo]"
    echo ""
    echo "Arguments:"
    echo "  source-dir-or-glob  Directory or glob pattern for files to upload"
    echo "  context             Context path (e.g., pr-42, review-123)"
    echo "  owner/repo          Optional. Defaults to current repo from gh"
    echo ""
    echo "Examples:"
    echo "  $0 ./screenshots pr-42"
    echo "  $0 './outputs/*.png' pr-42 owner/my-repo"
    exit 1
}

log_info() { echo -e "${GREEN}+${NC} $1"; }
log_warn() { echo -e "${YELLOW}!${NC} $1"; }
log_error() { echo -e "${RED}x${NC} $1" >&2; }

# Video detection
VIDEO_EXTENSIONS="mov|mp4|webm|avi|mkv|m4v|MOV|MP4|WEBM|AVI|MKV|M4V"
is_video() {
    [[ "$1" =~ \.($VIDEO_EXTENSIONS)$ ]]
}

# Get SHA of existing file (for updates)
get_file_sha() {
    local repo="$1"
    local path="$2"
    gh api "repos/$repo/contents/$path?ref=assets" --jq '.sha' 2>/dev/null || echo ""
}

# Track files to cleanup after upload
CLEANUP_FILES=()
cleanup() {
    for f in "${CLEANUP_FILES[@]}"; do
        [[ -f "$f" ]] && rm -f "$f"
    done
}
trap cleanup EXIT

# Validate arguments
[[ $# -lt 2 ]] && usage

SOURCE="$1"
CONTEXT="$2"
REPO="${3:-$(gh repo view --json nameWithOwner -q '.nameWithOwner' 2>/dev/null || echo "")}"

if [[ -z "$REPO" ]]; then
    log_error "Could not determine repository. Provide owner/repo as third argument."
    exit 1
fi

# Validate context format
if ! [[ "$CONTEXT" =~ ^[a-z0-9-]+$ ]]; then
    log_error "Invalid context format. Use lowercase letters, numbers, and hyphens only."
    exit 1
fi

echo "=== GitHub Assets Upload ==="
echo "Repository: $REPO"
echo "Context:    $CONTEXT"
echo "Source:     $SOURCE"
echo ""

# Collect files to upload
FILES=()
if [[ -d "$SOURCE" ]]; then
    # Source is a directory - get all files
    while IFS= read -r -d '' file; do
        FILES+=("$file")
    done < <(find "$SOURCE" -type f -print0)
elif [[ "$SOURCE" == *"*"* ]]; then
    # Source is a glob pattern
    for file in $SOURCE; do
        [[ -f "$file" ]] && FILES+=("$file")
    done
else
    # Source is a single file
    [[ -f "$SOURCE" ]] && FILES+=("$SOURCE")
fi

if [[ ${#FILES[@]} -eq 0 ]]; then
    log_error "No files found matching: $SOURCE"
    exit 1
fi

echo "Files to upload: ${#FILES[@]}"
echo ""

# Check if assets branch exists, create if not
echo "Checking assets branch..."
if ! gh api "repos/$REPO/branches/assets" --jq '.name' &>/dev/null; then
    log_warn "Assets branch not found. Creating..."

    EMPTY_TREE="4b825dc642cb6eb9a060e54bf8d69288fbee4904"
    COMMIT=$(gh api "repos/$REPO/git/commits" -X POST \
        -f message="chore: initialize assets branch" \
        -f tree="$EMPTY_TREE" \
        --jq '.sha')

    gh api "repos/$REPO/git/refs" -X POST \
        -f ref="refs/heads/assets" \
        -f sha="$COMMIT" >/dev/null

    log_info "Created assets branch"
else
    log_info "Assets branch exists"
fi

echo ""
echo "=== Uploading Files ==="

# Track results
UPLOADED=()
FAILED=()
URLS=()
VIDEO_URLS=()  # Track video MP4 URLs for download links

# Upload files sequentially (CRITICAL: not parallel)
for filepath in "${FILES[@]}"; do
    filename=$(basename "$filepath")
    upload_path="$filepath"

    # Convert video to GIF + MP4 if needed
    if is_video "$filepath"; then
        echo "Converting video: $filename..."
        converted_mp4="${filepath%.*}_converted.mp4"
        converted_gif="${filepath%.*}_converted.gif"
        mp4_filename="${filename%.*}_converted.mp4"
        gif_filename="${filename%.*}_converted.gif"

        # Generate MP4 + GIF (GIF created FROM MP4 for consistency)
        if "$SCRIPT_DIR/gh-video-convert.sh" "$filepath" --preset pr-small --gif --output "$converted_mp4"; then
            CLEANUP_FILES+=("$converted_mp4" "$converted_gif")

            # Upload MP4 first (for download link)
            if [[ -f "$converted_mp4" ]]; then
                echo -n "Uploading $mp4_filename... "
                mp4_content=$(base64 -i "$converted_mp4" 2>/dev/null || base64 "$converted_mp4")

                # Check if file exists (need SHA for update)
                existing_sha=$(get_file_sha "$REPO" "$CONTEXT/$mp4_filename")

                if [[ -n "$existing_sha" ]]; then
                    mp4_result=$(gh api "repos/$REPO/contents/$CONTEXT/$mp4_filename" -X PUT \
                        -f message="assets($CONTEXT): update $mp4_filename" \
                        -f content="$mp4_content" \
                        -f sha="$existing_sha" \
                        -f branch="assets" \
                        --jq '.content.sha' 2>&1) || true
                else
                    mp4_result=$(gh api "repos/$REPO/contents/$CONTEXT/$mp4_filename" -X PUT \
                        -f message="assets($CONTEXT): add $mp4_filename" \
                        -f content="$mp4_content" \
                        -f branch="assets" \
                        --jq '.content.sha' 2>&1) || true
                fi

                if [[ "$mp4_result" =~ ^[a-f0-9]{40}$ ]]; then
                    log_info "OK (sha: ${mp4_result:0:7})"
                    VIDEO_URLS+=("https://raw.githubusercontent.com/$REPO/assets/$CONTEXT/$mp4_filename")
                else
                    log_error "FAILED"
                    echo "  Error: $mp4_result" >&2
                fi
            fi

            # Upload GIF for embedding
            if [[ -f "$converted_gif" ]]; then
                upload_path="$converted_gif"
                filename="$gif_filename"
                log_info "Video converted to GIF for embedding"
            else
                log_warn "GIF generation failed, skipping GIF upload"
                continue
            fi
        else
            log_error "Video conversion failed, uploading original"
        fi
    fi

    echo -n "Uploading $filename... "

    # Base64 encode file content
    content=$(base64 -i "$upload_path" 2>/dev/null || base64 "$upload_path")

    # Check if file exists (need SHA for update)
    existing_sha=$(get_file_sha "$REPO" "$CONTEXT/$filename")

    # Upload via GitHub Contents API
    if [[ -n "$existing_sha" ]]; then
        result=$(gh api "repos/$REPO/contents/$CONTEXT/$filename" -X PUT \
            -f message="assets($CONTEXT): update $filename" \
            -f content="$content" \
            -f sha="$existing_sha" \
            -f branch="assets" \
            --jq '.content.sha' 2>&1) || true
    else
        result=$(gh api "repos/$REPO/contents/$CONTEXT/$filename" -X PUT \
            -f message="assets($CONTEXT): add $filename" \
            -f content="$content" \
            -f branch="assets" \
            --jq '.content.sha' 2>&1) || true
    fi

    if [[ "$result" =~ ^[a-f0-9]{40}$ ]]; then
        log_info "OK (sha: ${result:0:7})"
        UPLOADED+=("$filename")
        URLS+=("https://raw.githubusercontent.com/$REPO/assets/$CONTEXT/$filename")
    else
        log_error "FAILED"
        echo "  Error: $result" >&2
        FAILED+=("$filename")
    fi
done

echo ""
echo "=== Upload Summary ==="
echo "Uploaded: ${#UPLOADED[@]}/${#FILES[@]}"
[[ ${#FAILED[@]} -gt 0 ]] && echo "Failed:   ${#FAILED[@]} (${FAILED[*]})"

if [[ ${#URLS[@]} -gt 0 ]]; then
    echo ""
    echo "=== Embed URLs (works for both public and private repos) ==="
    for url in "${URLS[@]}"; do
        # Convert raw URL to blob URL with ?raw=true
        blob_url="${url/raw.githubusercontent.com/github.com}"
        blob_url="${blob_url/\/$REPO\//\/$REPO\/blob\/}?raw=true"
        echo "$blob_url"
    done

    echo ""
    echo "=== Markdown (copy-paste ready) ==="
    for url in "${URLS[@]}"; do
        filename=$(basename "$url")
        blob_url="${url/raw.githubusercontent.com/github.com}"
        blob_url="${blob_url/\/$REPO\//\/$REPO\/blob\/}?raw=true"
        echo "![${filename%.*}]($blob_url)"
    done
fi

# Output video download links if any videos were uploaded
if [[ ${#VIDEO_URLS[@]} -gt 0 ]]; then
    echo ""
    echo "=== Video Download Links ==="
    for url in "${VIDEO_URLS[@]}"; do
        blob_url="${url/raw.githubusercontent.com/github.com}"
        blob_url="${blob_url/\/$REPO\//\/$REPO\/blob\/}?raw=true"
        echo "[Download Recording]($blob_url)"
    done
fi

# Exit with error if any failed
[[ ${#FAILED[@]} -gt 0 ]] && exit 1
exit 0
