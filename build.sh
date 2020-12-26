#!/bin/bash -x
# set this....
MIPSGCCPATH="" # path to MIPS compiler

#INSTALLOPTIONAL="1"
#case "$PATH" in
#	*mips*)

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


# Add NEw LUCI
#    new_tab.lua had to be placed in:
#    /usr/lib/lua/luci/controller/myapp
#    cbi_tab.lua had to be placed in:
#    /usr/lib/lua/luci/model/cbi/myapp-mymodule
#    cbi_file can be put in the same place as mentioned:
#    /etc/config
#    view_tab.htm had to be placed in:
#    /usr/lib/lua/luci/view/myapp-mymodule
# https://openwrt.org/docs/guide-developer/luci?s[]=cbi
# REMOVE - rm -rf /var/luci* to reset and /etc/init.d/uhttpd restart
# http://www.electronicsfaq.com/2018/01/adding-new-elements-to-openwrts-luci-on.html
# https://github.com/openwrt/packages/issues/1784
# https://github.com/openwrt/packages/commit/73244f09ecf65e1722cfa10529f6c966f5fa8575
# https://stackoverflow.com/questions/20399331/error-importing-hashlib-with-python-2-7-but-not-with-2-6
# https://github.com/python/cpython/pull/12708/files

# setting are available at
#$(uci show atm_setup.config.balance)
# atm_setup.config=atm
# atm_setup.config.enabled='0'
# atm_setup.config.balance='10000'
# atm_setup.config.fee='10'
