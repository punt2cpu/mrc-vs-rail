FROM quay.io/frrouting/frr:10.7.1
RUN apk add --no-cache iproute2 nftables tcpdump python3 iputils procps
# vtysh complains on every call without these two files
RUN echo "service integrated-vtysh-config" > /etc/frr/vtysh.conf && : > /etc/frr/frr.conf
