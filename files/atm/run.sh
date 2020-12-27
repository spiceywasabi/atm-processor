#!/bin/sh
cd /atm
#old path:  /mnt/atm/processor/
screem -dmS serialprocessor ./serial-processor.sh
while true; do
	logger "starting atm processor"
	python atm-processor.py
	sleep 1
done
