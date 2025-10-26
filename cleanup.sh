#!/bin/bash

video_dir="/mnt/video"

# Minimum free space in KB
min_free=$((4 * 1024 * 1024))

free_space=$(df "$video_dir" | awk 'NR==2 {print $4}')

# Max number to delete, to prevent infinite loop or script taking too long
max_count=20
count=0

# Delete oldest files until free space is above threshold
while [ "$free_space" -lt "$min_free" ] && [ "$count" -lt "$max_count" ]; do
	oldest_file=$(find "$video_dir" -type f -printf '%T+ %p\n' | sort | head -n 1 | cut -d' ' -f2-)
	[ -z "$oldest_file" ] && exit 0
	rm -f "$oldest_file"
	free_space=$(df "$video_dir" | awk 'NR==2 {print $4}')
	((count++))
done