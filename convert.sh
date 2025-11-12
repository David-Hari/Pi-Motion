#!/bin/bash

# Wrap h264 in mkv container with appropriate fps, then delete original file
input="$1"
output="$2"
frame_rate="$3"

ffmpeg -r "$frame_rate" -i "$input" -vcodec copy "$output" >/dev/null 2>&1
rm -rf "$input"