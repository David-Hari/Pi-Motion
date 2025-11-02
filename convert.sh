# Example, use file name passed to script
ffmpeg -f rawvideo -pixel_format gray -video_size 1920x1080 -framerate 15 -i /mnt/video/1762042287.avi -vf format=yuv420p -c:v h264_v4l2m2m -b:v 2M /mnt/video/output.mp4
rm -rf /mnt/video/1762042287.avi