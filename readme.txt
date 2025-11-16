
To create the service:

> sudo cp pimotion.service /lib/systemd/system/
> sudo chmod 644 /lib/systemd/system/pimotion.service
> sudo systemctl daemon-reload
> sudo systemctl enable pimotion.service


To create the cron job:

> crontab -e
0 * * * * /home/pi/cleanup.sh