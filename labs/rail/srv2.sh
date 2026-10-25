#!/bin/sh
for f in /proc/sys/net/ipv6/conf/*/disable_ipv6; do echo 0 > $f; done
for f in /proc/sys/net/ipv4/conf/*/rp_filter; do echo 0 > $f; done
sysctl -qw net.ipv4.ip_forward=1 net.ipv6.conf.all.forwarding=1 net.ipv6.conf.all.seg6_enabled=1
sysctl -qw net.ipv4.fib_multipath_hash_policy=1 net.ipv6.fib_multipath_hash_policy=1
sysctl -qw net.ipv6.conf.all.keep_addr_on_down=1
ip addr add 10.0.2.1/31 dev eth1
ip route add 10.0.0.0/16 via 10.0.2.0 dev eth1
ip addr add 10.1.2.1/31 dev eth2
ip route add 10.1.0.0/16 via 10.1.2.0 dev eth2
ip addr add 10.2.2.1/31 dev eth3
ip route add 10.2.0.0/16 via 10.2.2.0 dev eth3
ip addr add 10.3.2.1/31 dev eth4
ip route add 10.3.0.0/16 via 10.3.2.0 dev eth4
ip addr add 10.4.2.1/31 dev eth5
ip route add 10.4.0.0/16 via 10.4.2.0 dev eth5
ip addr add 10.5.2.1/31 dev eth6
ip route add 10.5.0.0/16 via 10.5.2.0 dev eth6
ip addr add 10.6.2.1/31 dev eth7
ip route add 10.6.0.0/16 via 10.6.2.0 dev eth7
ip addr add 10.7.2.1/31 dev eth8
ip route add 10.7.0.0/16 via 10.7.2.0 dev eth8
