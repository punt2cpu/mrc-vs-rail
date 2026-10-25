#!/usr/bin/env bash
# ./lab.sh all [N]                           everything: install what's missing, both labs, all tests, N rounds (default 1)
# ./lab.sh setup                             only install what's missing + prepare the kernel
# ./lab.sh up rail|mrc
# ./lab.sh test rail|mrc spray|link|switch|flap|t0down
# ./lab.sh watch rail|mrc                    live view while a test runs (second terminal)
# ./lab.sh down rail|mrc
# ./lab.sh results                           every run, then median (min-max) per lab and test
# ./lab.sh summary                           only the median part
set -eu
cd "$(dirname "$0")"
cmd=${1:-} lab=${2:-} test=${3:-}
IMAGE=mrc-lab-node:latest

# use docker directly if this user may, otherwise through sudo (no docker group needed)
if docker info >/dev/null 2>&1; then D=docker; else D="sudo docker"; fi
dx()  { $D exec "clab-$lab-$1" sh -c "$2"; }
dxd() { $D exec -d "clab-$lab-$1" sh -c "$2"; }
note() { echo "$(date +%s.%N) $1" >> "$out/events.log"; echo "$(date +%T.%3N)  $1"; }
load() { lab=$1; source "labs/$lab/lab.env"; }

ensure() {
  if ! command -v docker >/dev/null || ! command -v containerlab >/dev/null; then
    echo "== installing docker and containerlab"
    curl -sL https://containerlab.dev/setup | sudo -E bash -s "all"
  fi
  if ! $D image inspect $IMAGE >/dev/null 2>&1; then
    echo "== building $IMAGE (pulls the FRR image)"
    $D build -t $IMAGE .
  fi
}

prepare_host() {  # kernel modules the tests use: netem (link test), nftables (switch test)
  if ! sudo modprobe sch_netem 2>/dev/null && [ -f /etc/debian_version ]; then
    sudo apt-get update -qq && sudo apt-get install -y -qq "linux-modules-extra-$(uname -r)" && sudo modprobe sch_netem
  fi
  sudo modprobe nf_tables 2>/dev/null || true
}

usid_ok() {  # SRv6 uSID (next-csid) in the kernel, tested with the image's iproute2
  $D run --rm --cap-add NET_ADMIN --sysctl net.ipv6.conf.all.disable_ipv6=0 --entrypoint sh $IMAGE -c \
    'ip link add sr0 type dummy && ip link set sr0 up &&
     ip -6 route add fcbb:bb00:100::/48 encap seg6local action End flavors next-csid dev sr0' >/dev/null 2>&1
}

make_ready() {  # uSID needs kernel 6.1+. On Ubuntu install the HWE kernel, that needs one reboot
  usid_ok && return 0
  echo "kernel $(uname -r) can't do SRv6 uSID"
  . /etc/os-release
  if [ "$ID" = ubuntu ]; then
    sudo apt-get update -qq && sudo apt-get install -y -qq "linux-generic-hwe-$VERSION_ID"
    echo "newer kernel installed - reboot and run ./lab.sh all again"
    exit 1
  fi
  return 1
}

up() {
  sudo containerlab deploy -t "labs/$lab/topo.clab.yml" --reconfigure
  echo "== waiting until srv1 reaches srv2"
  for t in $WAIT; do
    n=0
    until dx srv1 "ping -c1 -W1 $t" >/dev/null 2>&1; do
      n=$((n + 1))
      if [ $n -ge 90 ]; then echo "srv1 can't reach $t after 90 s, lab left up for debugging"; exit 1; fi
      sleep 1
    done
  done
  sleep 5   # let ECMP settle on all paths
}
down() { sudo containerlab destroy -t "labs/$lab/topo.clab.yml" --cleanup; }

counters() {
  for u in $UPLINKS; do
    echo "$u $(dx "${u%:*}" "cat /sys/class/net/${u#*:}/statistics/tx_packets")"
  done
}

restore() {
  set -- $LINK
  dx "$1" "tc qdisc del dev $2 root 2>/dev/null; ip link set $2 up; true" || true
  dx "$3" "tc qdisc del dev $4 root 2>/dev/null; ip link set $4 up; true" || true
  dx "$SWITCH" "nft delete table inet lab 2>/dev/null; true" || true
  dx "$T0" "for i in eth1 eth2 eth3; do ip link set \$i up; done" || true
}

run_test() {
  out=results/$(date +%m%d-%H%M%S)-$lab-$test
  mkdir -p "$out"
  echo "== $lab $test"
  trap restore EXIT
  dxd srv2 "exec python3 /tools/flows.py recv $RECV --out /tmp/recv.json --live /tmp/live.txt"
  sleep 1
  dxd srv1 "exec python3 /tools/flows.py send $SEND --out /tmp/send.json"
  note START
  sleep 3

  case $test in
    spray)
      counters > "$out/before.txt"
      sleep 10
      counters > "$out/after.txt"
      echo "packets on each pod A uplink in 10 s:"
      paste "$out/before.txt" "$out/after.txt" | awk '{printf "  %-14s %7d\n", $1, $4 - $2}' | tee "$out/spray.txt"
      ;;
    link)  # 100% loss both ways, link stays up
      set -- $LINK
      note INJECT
      dx "$1" "tc qdisc add dev $2 root netem loss 100%" &
      dx "$3" "tc qdisc add dev $4 root netem loss 100%" &
      wait
      sleep 10
      # what netem itself counted as dropped, to check the numbers against
      dx "$1" "tc -s qdisc show dev $2" > "$out/netem-a.txt"
      dx "$3" "tc -s qdisc show dev $4" > "$out/netem-b.txt"
      note RESTORE
      restore
      sleep 5
      ;;
    flap)  # link loses carrier for 2 s every 10 s, four times
      set -- $LINK
      note INJECT
      for flap in 1 2 3 4; do
        note "flap $flap down"
        dx "$1" "ip link set $2 down"
        sleep 2
        dx "$1" "ip link set $2 up"
        sleep 8
      done
      note RESTORE
      restore
      sleep 5
      ;;
    t0down)  # a whole tier-0 switch goes down: all its links lose carrier
      note INJECT
      dx "$T0" "for i in eth1 eth2 eth3; do ip link set \$i down; done"
      sleep 10
      note RESTORE
      restore
      sleep 5
      ;;
    switch)  # switch drops everything it forwards, control plane stays up
      note INJECT
      dx "$SWITCH" "nft add table inet lab && nft add chain inet lab labfwd '{ type filter hook forward priority 0; policy drop; }'"
      sleep 10
      note RESTORE
      restore
      sleep 5
      ;;
  esac

  dx srv1 "pkill -INT -f '[f]lows.py send'; true"
  sleep 1
  dx srv2 "pkill -INT -f '[f]lows.py recv'; true"
  sleep 1
  $D cp "clab-$lab-srv1:/tmp/send.json" "$out/"
  $D cp "clab-$lab-srv2:/tmp/recv.json" "$out/"
  $D cp "clab-$lab-srv2:/tmp/live.txt" "$out/timeline.txt"
  note END
  trap - EXIT
  python3 tools/summary.py "$out"
}

case $cmd in
  setup)
    ensure
    prepare_host
    if make_ready; then echo "kernel: ok"; else echo "no SRv6 uSID support here, only the rail lab will work"; fi
    ;;
  up)   ensure; prepare_host; load "$lab"; up ;;
  down) load "$lab"; down ;;
  test) load "$lab"; run_test ;;
  results) python3 tools/summary.py results/*/ ;;
  summary) python3 tools/summary.py --summary results/*/ ;;
  watch)   load "$lab"; dx srv2 "touch /tmp/live.txt; tail -n 0 -F /tmp/live.txt" ;;
  all)
    rounds=${2:-1}
    ensure
    prepare_host
    labs="rail mrc"
    make_ready || { echo "no SRv6 uSID support here, running the rail lab only"; labs=rail; }
    for round in $(seq "$rounds"); do
      for l in $labs; do
        echo "== round $round of $rounds: $l"
        load "$l"
        up
        for test in spray link switch flap t0down; do run_test; done
        down
      done
    done
    python3 tools/summary.py --summary results/*/
    ;;
  *) sed -n '2,9p' "$0" | cut -c3- ;;
esac
