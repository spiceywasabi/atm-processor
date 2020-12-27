#!/bin/sh
cd /atm
while true; do
	logger "starting new instance of serial processor"
	./fix-serial.sh
	./serial-processor.py /dev/ttyACM0
	sleep 4
done

