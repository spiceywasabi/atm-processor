#!/bin/sh -x 
# basically just another hand off but at least we don't need new firmware each time we need to make a change
# 1. call set seriall
# 2. launch 
cd /mnt/atm/processor
killall -9 screen
killall -9 screen
screen -wipe
./rtc-comms.py sync 
screen -dmS atmprocessor ./run.sh
screen -dmS serialprocessor ./serial-processor.sh
 