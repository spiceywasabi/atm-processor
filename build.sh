#!/bin/bash -x
# set this....
selected_packages+="-ppp -ppp-mod-pppoe -kmod-ppp -kmod-pppoe -kmod-pppox gpioctl-sysfs kmod-leds-gpio kmod-usb-acm -firewall -ip6tables -kmod-nf-conntrack6 -kmod-ip6tables -kmod-ipv6 -odhcp6c "
selected_packages+="screen python-light python-logging python-multiprocessing python-pyserial nano lsof logd kmod-gpio-button-hotplug e2fsprogs htop kmod-sdhci kmod-mt76-core kmod-mt76-usb htop serialconsole setserial coreutils-stty "
selected_packages+="kmod-fs-ext4 block-mount kmod-usb-storage kmod-usb-storage kmod-usb-storage-extras kmod-rt2800-usb kmod-sdhci-mt7620 block-mount kmod-fs-vfat kmod-nls-cp437 kmod-nls-utf8 kmod-nls-iso8859-1 "
selected_packages+="luci luci-compat luci-ssl python-pip "
#xinetd muninlite
#luci-ssl xinetd muninlite libopenssl "

# add ourselve to the build.
tar -czvf ./files/.build.tgz build.sh files/

make clean
make image PROFILE="gl-mt300a" PACKAGES="$selected_packages" FILES=files/

 ## REPORT SIZE
echo "Final size of image is..."
du -h  ./bin/targets/ramips/mt7620/

# setting are available at
#$(uci show atm_setup.config.balance)
# atm_setup.config=atm
# atm_setup.config.enabled='0'
# atm_setup.config.balance='10000'
# atm_setup.config.fee='10'
