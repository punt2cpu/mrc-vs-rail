FROM quay.io/frrouting/frr:10.7.1
RUN apk add --no-cache iproute2 nftables tcpdump python3 iputils procps
