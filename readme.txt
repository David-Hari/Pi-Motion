
To create the service:

> sudo mv pimotion.service /lib/systemd/system/
> sudo chmod 644 /lib/systemd/system/pimotion.service
> sudo systemctl daemon-reload
> sudo systemctl enable pimotion.service
