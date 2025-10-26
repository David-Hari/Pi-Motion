
To create the service:

> sudo mv pimotion.service /lib/systemd/system/
> sudo chmod 644 /lib/systemd/system/pimotion.service
> sudo systemctl daemon-reload
> sudo systemctl enable pimotion.service


To create the cron jobs:

> crontab -e
# Monitor temperature
*/10 * * * * /home/pi/temperature.sh

# Cleanup video directory
#0 * * * * /home/pi/cleanup.sh 