# Wrap h264 in mkv container with appropriate fps, then delete original file
ffmpeg -r 15 -i {path} -vcodec copy {mkvpath} >/dev/null 2>&1
rm -rf {path}