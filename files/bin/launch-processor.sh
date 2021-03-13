#!/bin/sh

# try to identify if we have external sd card or similar with the partition labeled 'atm'
vol=$(block info|grep -i atm)
mdir="/atm"
touch /tmp/launchstart
if [ ! -z "$vol" ]; then
	mnt_pnt=$(echo "$vol"|sed -e "s/:.*//g")
	logger "atm processor found mount point at '$mnt_pnt'"
	# just in case
	umount $mnt_pnt > /dev/null
	mkdir -p "$mdir"
	mount $mnt_pnt $mdir
	if [ $? -eq 0 ]; then
		logger "atm processor has successfully  mounted storage card"
	else
		logger "atm processor could not mount external storage"
	fi
fi
# internal data can either be the embedded or external. so just check if our file exists
if [ -f "$mdir/atm-runner.sh" ]; then
		touch /tmp/launchhandoff
		logger "handing off atm processor"
		$mdir/atm-runner.sh
	fi
else
	echo "atm processor is unavailable, no storage is available with the code"
	logger "atm processor is unavailable, no storage is available with the code"
fi
