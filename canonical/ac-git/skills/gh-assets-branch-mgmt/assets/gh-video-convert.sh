#!/usr/bin/env bash
#
# gh-video-convert.sh - Convert videos to optimized H.264 MP4 for GitHub
#
# Usage: gh-video-convert.sh <input> [options]
#
# Options:
#   --preset <name>    Compression preset (pr-small, pr-medium, pr-large, demo)
#   --max-size <mb>    Target file size in MB (overrides preset)
#   --output <path>    Custom output path (default: input_converted.mp4)
#   --speed <factor>   Playback speed multiplier (default: 8 = 8x faster)
#   --gif              Also generate GIF from output MP4
#   --gif-only         Generate only GIF, remove MP4 after
#   --gif-fps <n>      GIF frame rate (default: 10)
#   --gif-width <px>   GIF max width (default: 720)
#
# Presets:
#   pr-small   - Target ~8MB, 720p, CRF 28 (GitHub free plan safe)
#   pr-medium  - Target ~25MB, 720p, CRF 24
#   pr-large   - Target ~50MB, 1080p, CRF 23
#   demo       - High quality, 1080p, CRF 20
#
# Requirements:
#   - ffmpeg with libx264 encoder
#   - ffprobe (comes with ffmpeg)
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
    echo "Usage: $0 <input> [options]"
    echo ""
    echo "Options:"
    echo "  --preset <name>    Compression preset (pr-small, pr-medium, pr-large, demo)"
    echo "  --max-size <mb>    Target file size in MB (enables two-pass encoding)"
    echo "  --output <path>    Custom output path"
    echo "  --speed <factor>   Playback speed multiplier (default: 8 = 8x faster)"
    echo "                     Use --speed 1 for original speed"
    echo "  --gif              Also generate GIF from output MP4"
    echo "  --gif-only         Generate only GIF, remove MP4 after"
    echo "  --gif-fps <n>      GIF frame rate (default: 10)"
    echo "  --gif-width <px>   GIF max width (default: 720)"
    echo ""
    echo "Presets:"
    echo "  pr-small   - ~8MB, 720p, CRF 28 (GitHub free plan)"
    echo "  pr-medium  - ~25MB, 720p, CRF 24"
    echo "  pr-large   - ~50MB, 1080p, CRF 23"
    echo "  demo       - High quality, 1080p, CRF 20"
    echo ""
    echo "Notes:"
    echo "  - Audio is dropped when speed > 1 (avoids chipmunk effect)"
    echo "  - GIF is generated FROM the output MP4 (not input)"
    exit 1
}

# Check dependencies
check_deps() {
    if ! command -v ffmpeg &>/dev/null; then
        log_error "ffmpeg not found. Install with: brew install ffmpeg"
        exit 1
    fi
    if ! command -v ffprobe &>/dev/null; then
        log_error "ffprobe not found. Install with: brew install ffmpeg"
        exit 1
    fi
}

# Get video duration in seconds
get_duration() {
    ffprobe -v error -show_entries format=duration -of csv=p=0 "$1" 2>/dev/null | cut -d'.' -f1
}

# Get video resolution
get_resolution() {
    ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0 "$1" 2>/dev/null
}

# Generate GIF from video using two-pass palette optimization
# Args: input_mp4, output_gif, fps, width
generate_gif_from_video() {
    local input_mp4="$1"
    local output_gif="$2"
    local fps="$3"
    local width="$4"

    log_step "Generating GIF from MP4 (${width}px, ${fps}fps)..."

    # Two-pass palette generation for optimal quality
    # GIF is created FROM the already-processed MP4 (not raw input)
    ffmpeg -y -i "$input_mp4" \
        -vf "fps=$fps,scale=$width:-1:flags=lanczos,split[s0][s1];[s0]palettegen=stats_mode=diff[p];[s1][p]paletteuse=dither=bayer:bayer_scale=5" \
        "$output_gif" 2>/dev/null
}

# Preset configurations: CRF, MAX_WIDTH, MAX_HEIGHT, TARGET_MB
declare -A PRESETS=(
    ["pr-small"]="28 1280 720 8"
    ["pr-medium"]="24 1280 720 25"
    ["pr-large"]="23 1920 1080 50"
    ["demo"]="20 1920 1080 80"
)

# Parse arguments
INPUT=""
PRESET="pr-small"
MAX_SIZE_MB=""
OUTPUT=""
SPEED="8"  # Default 8x speed
GENERATE_GIF="false"
GIF_ONLY="false"
GIF_FPS="10"
GIF_WIDTH="720"

while [[ $# -gt 0 ]]; do
    case $1 in
        --preset)
            PRESET="$2"
            shift 2
            ;;
        --max-size)
            MAX_SIZE_MB="$2"
            shift 2
            ;;
        --output)
            OUTPUT="$2"
            shift 2
            ;;
        --speed|-s)
            SPEED="$2"
            shift 2
            ;;
        --gif)
            GENERATE_GIF="true"
            shift
            ;;
        --gif-only)
            GENERATE_GIF="true"
            GIF_ONLY="true"
            shift
            ;;
        --gif-fps)
            GIF_FPS="$2"
            shift 2
            ;;
        --gif-width)
            GIF_WIDTH="$2"
            shift 2
            ;;
        -h|--help)
            usage
            ;;
        *)
            if [[ -z "$INPUT" ]]; then
                INPUT="$1"
            else
                log_error "Unknown argument: $1"
                usage
            fi
            shift
            ;;
    esac
done

# Validate input
[[ -z "$INPUT" ]] && usage
[[ ! -f "$INPUT" ]] && { log_error "Input file not found: $INPUT"; exit 1; }

# Validate preset
if [[ ! -v "PRESETS[$PRESET]" ]]; then
    log_error "Unknown preset: $PRESET"
    echo "Available presets: ${!PRESETS[*]}"
    exit 1
fi

# Validate speed
if ! [[ "$SPEED" =~ ^[0-9]+\.?[0-9]*$ ]] || [[ $(echo "$SPEED <= 0" | bc -l) -eq 1 ]]; then
    log_error "Invalid speed: $SPEED (must be positive number)"
    exit 1
fi

check_deps

# Parse preset
read -r CRF MAX_W MAX_H TARGET_MB <<< "${PRESETS[$PRESET]}"

# Override target size if specified
[[ -n "$MAX_SIZE_MB" ]] && TARGET_MB="$MAX_SIZE_MB"

# Set output path
if [[ -z "$OUTPUT" ]]; then
    OUTPUT="${INPUT%.*}_converted.mp4"
fi

echo "=== Video Conversion ==="
echo "Input:    $INPUT"
echo "Output:   $OUTPUT"
echo "Preset:   $PRESET (CRF=$CRF, ${MAX_W}x${MAX_H}, target=${TARGET_MB}MB)"
echo "Speed:    ${SPEED}x"
[[ "$GENERATE_GIF" == "true" ]] && echo "GIF:      ${GIF_WIDTH}px, ${GIF_FPS}fps"
echo ""

# Get source info
DURATION=$(get_duration "$INPUT")
RESOLUTION=$(get_resolution "$INPUT")
SRC_W=$(echo "$RESOLUTION" | cut -d',' -f1)
SRC_H=$(echo "$RESOLUTION" | cut -d',' -f2)

# Calculate output duration based on speed
OUTPUT_DURATION=$(echo "scale=0; $DURATION / $SPEED" | bc)

# Guard against division by zero for short videos with high speed
[[ $OUTPUT_DURATION -lt 1 ]] && OUTPUT_DURATION=1

log_step "Source: ${SRC_W}x${SRC_H}, ${DURATION}s -> ${OUTPUT_DURATION}s at ${SPEED}x"

# Calculate if we need to scale
SCALE_W=$MAX_W
SCALE_H=$MAX_H
if [[ $SRC_W -le $MAX_W && $SRC_H -le $MAX_H ]]; then
    # Don't upscale - use source resolution
    SCALE_W=$SRC_W
    SCALE_H=$SRC_H
    log_info "No scaling needed (source within limits)"
else
    log_step "Scaling to max ${MAX_W}x${MAX_H}"
fi

# Build video filter chain
# 1. Scale (maintain aspect ratio, ensure even dimensions for h264)
# 2. Speed up with setpts (PTS/SPEED = faster playback)
SCALE_FILTER="scale='min($SCALE_W,iw)':'min($SCALE_H,ih)':force_original_aspect_ratio=decrease,pad=ceil(iw/2)*2:ceil(ih/2)*2"

# Add speed filter if speed != 1
if [[ $(echo "$SPEED != 1" | bc -l) -eq 1 ]]; then
    VIDEO_FILTER="${SCALE_FILTER},setpts=PTS/$SPEED"
    AUDIO_OPTS="-an"  # Drop audio when sped up (avoids chipmunk effect)
    log_step "Speed ${SPEED}x enabled (audio will be dropped)"
else
    VIDEO_FILTER="$SCALE_FILTER"
    AUDIO_OPTS="-c:a aac -b:a 128k"
fi

# Calculate if two-pass is needed (large files or explicit size target)
INPUT_SIZE_MB=$(du -m "$INPUT" | cut -f1)
USE_TWO_PASS=false

if [[ -n "$MAX_SIZE_MB" ]] || [[ $INPUT_SIZE_MB -gt $((TARGET_MB * 2)) ]]; then
    USE_TWO_PASS=true
fi

# Create temp directory for two-pass logs
TEMP_DIR=$(mktemp -d)
trap 'rm -rf "$TEMP_DIR"' EXIT

if $USE_TWO_PASS; then
    log_step "Using two-pass encoding for size target (${TARGET_MB}MB)"

    # Calculate target bitrate (kbps)
    # Formula: (target_size_kb * 8) / output_duration - audio_bitrate
    # Use OUTPUT_DURATION since video will be shorter after speedup
    TARGET_SIZE_KB=$((TARGET_MB * 1024))
    AUDIO_BITRATE=128
    # Only subtract audio bitrate if we're keeping audio
    if [[ "$AUDIO_OPTS" == "-an" ]]; then
        VIDEO_BITRATE=$(( TARGET_SIZE_KB * 8 / OUTPUT_DURATION ))
    else
        VIDEO_BITRATE=$(( (TARGET_SIZE_KB * 8 / OUTPUT_DURATION) - AUDIO_BITRATE ))
    fi

    # Ensure minimum bitrate
    [[ $VIDEO_BITRATE -lt 200 ]] && VIDEO_BITRATE=200

    log_step "Target video bitrate: ${VIDEO_BITRATE}kbps"

    # Pass 1
    log_step "Pass 1/2: Analyzing..."
    ffmpeg -y -i "$INPUT" \
        -c:v libx264 -b:v "${VIDEO_BITRATE}k" -preset slow \
        -vf "$VIDEO_FILTER" \
        -pass 1 -passlogfile "$TEMP_DIR/ffmpeg2pass" \
        -an -f null /dev/null 2>/dev/null

    # Pass 2
    log_step "Pass 2/2: Encoding..."
    # shellcheck disable=SC2086
    ffmpeg -y -i "$INPUT" \
        -c:v libx264 -b:v "${VIDEO_BITRATE}k" -preset slow \
        -vf "$VIDEO_FILTER" \
        -pass 2 -passlogfile "$TEMP_DIR/ffmpeg2pass" \
        $AUDIO_OPTS \
        -movflags +faststart \
        "$OUTPUT" 2>/dev/null
else
    # Single-pass CRF encoding
    log_step "Single-pass CRF encoding (CRF=$CRF)"
    # shellcheck disable=SC2086
    ffmpeg -y -i "$INPUT" \
        -c:v libx264 -preset slow -crf "$CRF" \
        -vf "$VIDEO_FILTER" \
        $AUDIO_OPTS \
        -movflags +faststart \
        "$OUTPUT" 2>/dev/null
fi

# Verify output
if [[ ! -f "$OUTPUT" ]]; then
    log_error "Conversion failed - output not created"
    exit 1
fi

OUTPUT_SIZE_MB=$(du -m "$OUTPUT" | cut -f1)
OUTPUT_RES=$(get_resolution "$OUTPUT")
ACTUAL_OUTPUT_DURATION=$(get_duration "$OUTPUT")

echo ""
log_info "Conversion complete"
echo "  Output size: ${OUTPUT_SIZE_MB}MB (was ${INPUT_SIZE_MB}MB)"
echo "  Duration:    ${ACTUAL_OUTPUT_DURATION}s (was ${DURATION}s, ${SPEED}x speed)"
echo "  Resolution:  $OUTPUT_RES"
echo "  File:        $OUTPUT"

# Warn if still over GitHub limit
if [[ $OUTPUT_SIZE_MB -gt 100 ]]; then
    log_warn "Output exceeds GitHub 100MB limit. Try --max-size 90"
elif [[ $OUTPUT_SIZE_MB -gt 10 ]]; then
    log_warn "Output exceeds GitHub free plan 10MB limit. Paid plan required or try --preset pr-small"
fi

# Generate GIF from output MP4 if requested
if [[ "$GENERATE_GIF" == "true" ]]; then
    GIF_OUTPUT="${OUTPUT%.*}.gif"

    echo ""
    echo "=== GIF Generation ==="
    generate_gif_from_video "$OUTPUT" "$GIF_OUTPUT" "$GIF_FPS" "$GIF_WIDTH"

    if [[ -f "$GIF_OUTPUT" ]]; then
        GIF_SIZE_KB=$(du -k "$GIF_OUTPUT" | cut -f1)
        GIF_SIZE_MB=$((GIF_SIZE_KB / 1024))

        log_info "GIF generated"
        echo "  GIF size:    ${GIF_SIZE_MB}MB (${GIF_SIZE_KB}KB)"
        echo "  GIF file:    $GIF_OUTPUT"

        if [[ $GIF_SIZE_KB -gt 10240 ]]; then
            log_warn "GIF exceeds 10MB - may not embed on GitHub free plan"
            log_warn "Try: --gif-width 320 or --gif-fps 8"
        fi

        # Remove MP4 if --gif-only mode
        if [[ "$GIF_ONLY" == "true" ]]; then
            rm -f "$OUTPUT"
            log_info "Removed MP4 (--gif-only mode)"
        fi
    else
        log_error "GIF generation failed"
        exit 1
    fi
fi

exit 0
