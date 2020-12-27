#!/usr/bin/python
# this is a very simple tool to provide communications and control of the Arduino
# which handles lights and RTC, this script essentially acts as a basic hwclock command
# to interface with the Arduino and syncronize the time in the event either NTP or Date get out of sync

import os
import sys
import subprocess
import serial
from datetime import datetime,timedelta
# for debugging
from pprint import pprint

path = "/dev/ttyS0"
ttyspeed=9600

run = True

state_file = "/tmp/rtctimesync.state"
read_time_fmt = "%Y-%m-%d %H:%M:%S"
write_time_fmt= '%Y-%m-%dT%H:%M:%S'




if len(sys.argv) < 2:
	print("error: must provide option for commands")
	sys.exit(1)

##
## presume we're good
##
if str(sys.argv[1]).lower() == "sync":
	with serial.Serial(path,ttyspeed,timeout=5) as ser:
		ser.write(b'GET')
		tries=10
		while tries>1:
			line = ser.readline()   # read a '\n' terminated line
			if "G:" in line:
				print("found! date %s"%str(line))
				break
			else:
				tries-=1
		# now that we have the date we need to split on it
		line_str_split = str(line).strip().split("G:")
		dt_str = line_str_split[1]
		rtc_time = datetime.strptime(dt_str, read_time_fmt)
		state_file_time = rtc_time
		if os.path.exists(state_file):
			try:
				state_time = open(state_file,'r').read()
				state_file_time = datetime.strptime(str(state_time).strip(),read_time_fmt)
			except Exception as e:
				print("error took place on read", e)
		else:
			try:
				state_time = open(state_file,'w+')
				state_time.write(dt_str)
				state_time.write("\n")
				state_time.close()
			except Exception as e:
				print("error took place on write", e)
		# check whether we're greater then a 2 hour delta away from RTC greater
		current_time = datetime.now() # date.today()
		if (rtc_time > current_time) and (abs(current_time-rtc_time)>timedelta(hours=1)):
			print("warning: internal clock appears to be incorrectly set, syncing to rtc")
			ex_code = subprocess.call(['busybox','date','-u','-s',"'%s'%"%dt_str])
		elif (state_file_time > rtc_time and (abs(state_file_time-rtc_time)>timedelta(hours=1)) or (rtc_time < current_time and (abs(current_time-rtc_time)>timedelta(hours=1)))):
			print("warning: rtc clock seems to be incorrectly set, syncing from internal time")
			# determine which to pick
			new_time_str = current_time.strftime(write_time_fmt)
			if state_file_time > current_time:
				# we pick the state file
				new_time_str = state_file_time.strftime(write_time_fmt)
			ser.write("SET!%s"%new_time_str)
			try:
				state_time = open(state_file,'w+')
				state_time.write(current_time.strftime(read_time_fmt))
				state_time.write("\n")
				state_time.close()
			except Exception as e:
				print("error took place on write", e)
		else:
			print("time does not need sync, ready")
		ser.close() # yay
elif str(sys.argv[1]).lower() == "temp":
	with serial.Serial(path,ttyspeed,timeout=5) as ser:
		ser.write(b'TEMP')
		tries=10
		while tries>1:
			line = ser.readline()   # read a '\n' terminated line
			if "TEMP:" in line:
				print("found! temp is: %s"%str(line))
				break
			else:
				tries-=1
		ser.close()
