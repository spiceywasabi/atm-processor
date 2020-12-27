#!/bin/sh
while true; do
	./fix-serial.sh
	./serial-processor.py /dev/ttyACM0
	sleep 4
done



