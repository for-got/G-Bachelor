#!/bin/sh
sudo kill -9 `pidof python3`
sudo nohup python3 /home/pi/graduation/app.py>>/home/pi/graduation/log.log 2>&1 &
