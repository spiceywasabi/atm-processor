#!/bin/sh
screen -d -m /dev/ttyACM0 -S tmpfix
kill -9 $(ps|grep tmpfix|grep screen|cut -f 2 -d " ")
killall -9 python
echo -e "+++\r\nATH0\r\n" >> /dev/ttyACM0
echo Hung Up
sleep 1
echo -e "\r\nATH\r\nATS0=4\r\n\r\nAT\r\n" >> /dev/ttyACM0
exit 0
