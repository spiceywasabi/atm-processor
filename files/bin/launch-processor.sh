#!/bin/sh

vol=$(block info|grep -i atm)
mdir="/mnt/atm"

touch /tmp/launchstart
if [ ! -z "$vol" ]; then
	mnt_pnt=$(echo "$vol"|sed -e "s/:.*//g")
	logger "atm processor found mount point at '$mnt_pnt'"
	# just in case
	umount $mnt_pnt > /dev/null
	mkdir -p "$mdir"
	mount $mnt_pnt $mdir
	if [ $? -eq 0 ]; then
		if [ -f "$mdir/atm-runner.sh" ]; then
			touch /tmp/launchhandoff
			logger "handing off atm processor"
			$mdir/atm-runner.sh
		fi
	else
		echo "mount failed"
	fi

fi
