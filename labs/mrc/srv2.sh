#!/bin/sh
for f in /proc/sys/net/ipv6/conf/*/disable_ipv6; do echo 0 > $f; done
for f in /proc/sys/net/ipv4/conf/*/rp_filter; do echo 0 > $f; done
sysctl -qw net.ipv4.ip_forward=1 net.ipv6.conf.all.forwarding=1 net.ipv6.conf.all.seg6_enabled=1
sysctl -qw net.ipv4.fib_multipath_hash_policy=1 net.ipv6.fib_multipath_hash_policy=1
sysctl -qw net.ipv6.conf.all.keep_addr_on_down=1
ip -6 addr add fc00::2/128 dev lo
ip sr tunsrc set fc00::2
ip link add sr0 type dummy
ip link set sr0 up
ip -6 route add fcbb:bb00:e002::/48 encap seg6local action End.DT6 table 255 dev sr0
ip -6 addr add fd00:e2:0::2/64 dev eth1 nodad
ip -6 route add fcbb:bb00:b00::/48 via fd00:e2:0::1 dev eth1
ip -6 addr add fd00:e2:1::2/64 dev eth2 nodad
ip -6 route add fcbb:bb00:b01::/48 via fd00:e2:1::1 dev eth2
ip -6 addr add fd00:e2:2::2/64 dev eth3 nodad
ip -6 route add fcbb:bb00:b02::/48 via fd00:e2:2::1 dev eth3
ip -6 addr add fd00:e2:3::2/64 dev eth4 nodad
ip -6 route add fcbb:bb00:b03::/48 via fd00:e2:3::1 dev eth4
ip -6 addr add fd00:e2:4::2/64 dev eth5 nodad
ip -6 route add fcbb:bb00:b04::/48 via fd00:e2:4::1 dev eth5
ip -6 addr add fd00:e2:5::2/64 dev eth6 nodad
ip -6 route add fcbb:bb00:b05::/48 via fd00:e2:5::1 dev eth6
ip -6 addr add fd00:e2:6::2/64 dev eth7 nodad
ip -6 route add fcbb:bb00:b06::/48 via fd00:e2:6::1 dev eth7
ip -6 addr add fd00:e2:7::2/64 dev eth8 nodad
ip -6 route add fcbb:bb00:b07::/48 via fd00:e2:7::1 dev eth8
ip -6 route add fc00::1/128 encap seg6 mode encap.red segs fcbb:bb00:b00:c00:a00:e001:: dev eth1 src fc00::2 table 100
ip -6 rule add fwmark 100 lookup 100
ip -6 route add fc00::1/128 encap seg6 mode encap.red segs fcbb:bb00:b00:d00:a00:e001:: dev eth1 src fc00::2 table 101
ip -6 rule add fwmark 101 lookup 101
ip -6 route add fc00::1/128 encap seg6 mode encap.red segs fcbb:bb00:b01:c01:a01:e001:: dev eth2 src fc00::2 table 102
ip -6 rule add fwmark 102 lookup 102
ip -6 route add fc00::1/128 encap seg6 mode encap.red segs fcbb:bb00:b01:d01:a01:e001:: dev eth2 src fc00::2 table 103
ip -6 rule add fwmark 103 lookup 103
ip -6 route add fc00::1/128 encap seg6 mode encap.red segs fcbb:bb00:b02:c02:a02:e001:: dev eth3 src fc00::2 table 104
ip -6 rule add fwmark 104 lookup 104
ip -6 route add fc00::1/128 encap seg6 mode encap.red segs fcbb:bb00:b02:d02:a02:e001:: dev eth3 src fc00::2 table 105
ip -6 rule add fwmark 105 lookup 105
ip -6 route add fc00::1/128 encap seg6 mode encap.red segs fcbb:bb00:b03:c03:a03:e001:: dev eth4 src fc00::2 table 106
ip -6 rule add fwmark 106 lookup 106
ip -6 route add fc00::1/128 encap seg6 mode encap.red segs fcbb:bb00:b03:d03:a03:e001:: dev eth4 src fc00::2 table 107
ip -6 rule add fwmark 107 lookup 107
ip -6 route add fc00::1/128 encap seg6 mode encap.red segs fcbb:bb00:b04:c04:a04:e001:: dev eth5 src fc00::2 table 108
ip -6 rule add fwmark 108 lookup 108
ip -6 route add fc00::1/128 encap seg6 mode encap.red segs fcbb:bb00:b04:d04:a04:e001:: dev eth5 src fc00::2 table 109
ip -6 rule add fwmark 109 lookup 109
ip -6 route add fc00::1/128 encap seg6 mode encap.red segs fcbb:bb00:b05:c05:a05:e001:: dev eth6 src fc00::2 table 110
ip -6 rule add fwmark 110 lookup 110
ip -6 route add fc00::1/128 encap seg6 mode encap.red segs fcbb:bb00:b05:d05:a05:e001:: dev eth6 src fc00::2 table 111
ip -6 rule add fwmark 111 lookup 111
ip -6 route add fc00::1/128 encap seg6 mode encap.red segs fcbb:bb00:b06:c06:a06:e001:: dev eth7 src fc00::2 table 112
ip -6 rule add fwmark 112 lookup 112
ip -6 route add fc00::1/128 encap seg6 mode encap.red segs fcbb:bb00:b06:d06:a06:e001:: dev eth7 src fc00::2 table 113
ip -6 rule add fwmark 113 lookup 113
ip -6 route add fc00::1/128 encap seg6 mode encap.red segs fcbb:bb00:b07:c07:a07:e001:: dev eth8 src fc00::2 table 114
ip -6 rule add fwmark 114 lookup 114
ip -6 route add fc00::1/128 encap seg6 mode encap.red segs fcbb:bb00:b07:d07:a07:e001:: dev eth8 src fc00::2 table 115
ip -6 rule add fwmark 115 lookup 115
ip -6 route add fc00::1/128 encap seg6 mode encap.red segs fcbb:bb00:b00:c00:a00:e001:: dev eth1 src fc00::2
