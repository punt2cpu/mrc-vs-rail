#!/bin/sh
for f in /proc/sys/net/ipv6/conf/*/disable_ipv6; do echo 0 > $f; done
for f in /proc/sys/net/ipv4/conf/*/rp_filter; do echo 0 > $f; done
sysctl -qw net.ipv4.ip_forward=1 net.ipv6.conf.all.forwarding=1 net.ipv6.conf.all.seg6_enabled=1
sysctl -qw net.ipv4.fib_multipath_hash_policy=1 net.ipv6.fib_multipath_hash_policy=1
sysctl -qw net.ipv6.conf.all.keep_addr_on_down=1
for d in zebra bgpd bfdd staticd; do
  until vtysh -c 'show daemons' 2>/dev/null | grep -qw $d; do sleep 0.5; done
done
vtysh -f /frr.conf
