#!/usr/bin/env -S uv run
# /// script
# dependencies = [
#   "google-genai>=1.0",
#   "python-dotenv>=1.0",
#   "typer>=0.9",
#   "rich>=13.0",
# ]
# requires-python = ">=3.12"
# ///
"""Query videos using Google Gemini API with native video support."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Annotated

# Pricing per 1M tokens (gemini-2.5-flash-lite)
PRICING = {
    "gemini-2.5-flash-lite": {"input": 0.10, "output": 0.40},
    "gemini-2.5-flash": {"input": 0.15, "output": 0.60},
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    "default": {"input": 0.10, "output": 0.40},
}

import typer
from dotenv import load_dotenv
from google import genai
from rich.console import Console

# Load .env file from current directory or parent directories
load_dotenv()

app = typer.Typer(help="Query videos using Gemini API (native video upload).")
console = Console(stderr=True)


def get_mime_type(path: Path) -> str:
    """Get MIME type from file extension."""
    ext = path.suffix.lower()
    mime_types = {
        ".mp4": "video/mp4",
        ".webm": "video/webm",
        ".mov": "video/quicktime",
        ".avi": "video/x-msvideo",
        ".mpeg": "video/mpeg",
        ".mpg": "video/mpeg",
        ".wmv": "video/x-ms-wmv",
        ".3gp": "video/3gpp",
    }
    return mime_types.get(ext, "video/mp4")


@app.command()
def main(
    video_path: Annotated[Path, typer.Argument(help="Path to video file")],
    query: Annotated[str, typer.Argument(help="Query to ask about the video")],
    model: Annotated[str, typer.Option(help="Gemini model")] = "gemini-2.5-flash-lite",
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Query a video using Google Gemini API with native video upload."""
    # Check API key
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        console.print("[red]Error:[/red] GEMINI_API_KEY environment variable not set")
        raise typer.Exit(1)

    # Validate video exists
    if not video_path.exists():
        console.print(f"[red]Error:[/red] Video not found: {video_path}")
        raise typer.Exit(1)

    # Initialize client
    client = genai.Client(api_key=api_key)

    # Upload video
    console.print(f"[blue]Uploading video:[/blue] {video_path}")
    try:
        video_file = client.files.upload(file=str(video_path))
    except Exception as e:
        console.print(f"[red]Error uploading video:[/red] {e}")
        raise typer.Exit(1)

    # Wait for file to be processed
    console.print("[blue]Waiting for video processing...[/blue]")
    while video_file.state.name == "PROCESSING":
        time.sleep(2)
        video_file = client.files.get(name=video_file.name)

    if video_file.state.name != "ACTIVE":
        console.print(f"[red]Error:[/red] Video processing failed: {video_file.state.name}")
        raise typer.Exit(1)

    # Query model
    console.print(f"[blue]Querying {model}...[/blue]")
    start_time = time.time()
    try:
        response = client.models.generate_content(
            model=model,
            contents=[video_file, query],
        )
        response_text = response.text
    except Exception as e:
        console.print(f"[red]Error from API:[/red] {e}")
        raise typer.Exit(1)
    elapsed_time = time.time() - start_time

    # Extract token usage
    input_tokens = 0
    output_tokens = 0
    if response.usage_metadata:
        input_tokens = response.usage_metadata.prompt_token_count or 0
        output_tokens = response.usage_metadata.candidates_token_count or 0

    # Calculate cost
    pricing = PRICING.get(model, PRICING["default"])
    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    total_cost = input_cost + output_cost

    # Output result
    if json_output:
        result = {
            "video_path": str(video_path),
            "query": query,
            "model": model,
            "response": response_text,
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
            },
            "cost": {
                "input_cost_usd": round(input_cost, 6),
                "output_cost_usd": round(output_cost, 6),
                "total_cost_usd": round(total_cost, 6),
            },
            "time_seconds": round(elapsed_time, 2),
        }
        print(json.dumps(result, indent=2))
    else:
        print(response_text)
        console.print(f"\n[dim]Tokens: {input_tokens:,} in / {output_tokens:,} out | Cost: ${total_cost:.6f} | Time: {elapsed_time:.2f}s[/dim]")


if __name__ == "__main__":
    app()
