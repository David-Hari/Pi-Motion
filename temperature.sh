#!/bin/bash

logfile="/home/pi/temperature.csv"

# Write header if file doesn't exist
if [ ! -f "$logfile" ]; then
	echo "Time,CPU,GPU" >> "$logfile"
fi

timestamp=$(date +"%Y-%m-%d %H:%M:%S")

cpu_temp_raw=$(cat /sys/class/thermal/thermal_zone0/temp)
cpu_temp="$((cpu_temp_raw/1000))"
gpu_temp=$(vcgencmd measure_temp | grep -oE '[0-9.]+')

echo "$timestamp,$cpu_temp,$gpu_temp" >> "$logfile"