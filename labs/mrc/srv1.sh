#!/bin/sh
for f in /proc/sys/net/ipv6/conf/*/disable_ipv6; do echo 0 > $f; done
for f in /proc/sys/net/ipv4/conf/*/rp_filter; do echo 0 > $f; done
sysctl -qw net.ipv4.ip_forward=1 net.ipv6.conf.all.forwarding=1 net.ipv6.conf.all.seg6_enabled=1
sysctl -qw net.ipv4.fib_multipath_hash_policy=1 net.ipv6.fib_multipath_hash_policy=1
sysctl -qw net.ipv6.conf.all.keep_addr_on_down=1
ip -6 addr add fc00::1/128 dev lo
ip sr tunsrc set fc00::1
ip link add sr0 type dummy
ip link set sr0 up
ip -6 route add fcbb:bb00:e001::/48 encap seg6local action End.DT6 table 255 dev sr0
ip -6 addr add fd00:e1:0::2/64 dev eth1 nodad
ip -6 route add fcbb:bb00:a00::/48 via fd00:e1:0::1 dev eth1
ip -6 addr add fd00:e1:1::2/64 dev eth2 nodad
ip -6 route add fcbb:bb00:a01::/48 via fd00:e1:1::1 dev eth2
ip -6 addr add fd00:e1:2::2/64 dev eth3 nodad
ip -6 route add fcbb:bb00:a02::/48 via fd00:e1:2::1 dev eth3
ip -6 addr add fd00:e1:3::2/64 dev eth4 nodad
ip -6 route add fcbb:bb00:a03::/48 via fd00:e1:3::1 dev eth4
ip -6 addr add fd00:e1:4::2/64 dev eth5 nodad
ip -6 route add fcbb:bb00:a04::/48 via fd00:e1:4::1 dev eth5
ip -6 addr add fd00:e1:5::2/64 dev eth6 nodad
ip -6 route add fcbb:bb00:a05::/48 via fd00:e1:5::1 dev eth6
ip -6 addr add fd00:e1:6::2/64 dev eth7 nodad
ip -6 route add fcbb:bb00:a06::/48 via fd00:e1:6::1 dev eth7
ip -6 addr add fd00:e1:7::2/64 dev eth8 nodad
ip -6 route add fcbb:bb00:a07::/48 via fd00:e1:7::1 dev eth8
ip -6 route add fc00::2/128 encap seg6 mode encap.red segs fcbb:bb00:a00:c00:b00:e002:: dev eth1 src fc00::1 table 100
ip -6 rule add fwmark 100 lookup 100
ip -6 route add fc00::2/128 encap seg6 mode encap.red segs fcbb:bb00:a00:d00:b00:e002:: dev eth1 src fc00::1 table 101
ip -6 rule add fwmark 101 lookup 101
ip -6 route add fc00::2/128 encap seg6 mode encap.red segs fcbb:bb00:a01:c01:b01:e002:: dev eth2 src fc00::1 table 102
ip -6 rule add fwmark 102 lookup 102
ip -6 route add fc00::2/128 encap seg6 mode encap.red segs fcbb:bb00:a01:d01:b01:e002:: dev eth2 src fc00::1 table 103
ip -6 rule add fwmark 103 lookup 103
ip -6 route add fc00::2/128 encap seg6 mode encap.red segs fcbb:bb00:a02:c02:b02:e002:: dev eth3 src fc00::1 table 104
ip -6 rule add fwmark 104 lookup 104
ip -6 route add fc00::2/128 encap seg6 mode encap.red segs fcbb:bb00:a02:d02:b02:e002:: dev eth3 src fc00::1 table 105
ip -6 rule add fwmark 105 lookup 105
ip -6 route add fc00::2/128 encap seg6 mode encap.red segs fcbb:bb00:a03:c03:b03:e002:: dev eth4 src fc00::1 table 106
ip -6 rule add fwmark 106 lookup 106
ip -6 route add fc00::2/128 encap seg6 mode encap.red segs fcbb:bb00:a03:d03:b03:e002:: dev eth4 src fc00::1 table 107
ip -6 rule add fwmark 107 lookup 107
ip -6 route add fc00::2/128 encap seg6 mode encap.red segs fcbb:bb00:a04:c04:b04:e002:: dev eth5 src fc00::1 table 108
ip -6 rule add fwmark 108 lookup 108
ip -6 route add fc00::2/128 encap seg6 mode encap.red segs fcbb:bb00:a04:d04:b04:e002:: dev eth5 src fc00::1 table 109
ip -6 rule add fwmark 109 lookup 109
ip -6 route add fc00::2/128 encap seg6 mode encap.red segs fcbb:bb00:a05:c05:b05:e002:: dev eth6 src fc00::1 table 110
ip -6 rule add fwmark 110 lookup 110
ip -6 route add fc00::2/128 encap seg6 mode encap.red segs fcbb:bb00:a05:d05:b05:e002:: dev eth6 src fc00::1 table 111
ip -6 rule add fwmark 111 lookup 111
ip -6 route add fc00::2/128 encap seg6 mode encap.red segs fcbb:bb00:a06:c06:b06:e002:: dev eth7 src fc00::1 table 112
ip -6 rule add fwmark 112 lookup 112
ip -6 route add fc00::2/128 encap seg6 mode encap.red segs fcbb:bb00:a06:d06:b06:e002:: dev eth7 src fc00::1 table 113
ip -6 rule add fwmark 113 lookup 113
ip -6 route add fc00::2/128 encap seg6 mode encap.red segs fcbb:bb00:a07:c07:b07:e002:: dev eth8 src fc00::1 table 114
ip -6 rule add fwmark 114 lookup 114
ip -6 route add fc00::2/128 encap seg6 mode encap.red segs fcbb:bb00:a07:d07:b07:e002:: dev eth8 src fc00::1 table 115
ip -6 rule add fwmark 115 lookup 115
ip -6 route add fc00::2/128 encap seg6 mode encap.red segs fcbb:bb00:a00:c00:b00:e002:: dev eth1 src fc00::1
