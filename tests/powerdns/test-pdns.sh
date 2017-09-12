#!/bin/bash
set -eu

if [[ $(id -u) -ne 0 ]] ; then
    echo "PowerDNS requires root"
    exit 1
fi

savedpwd=$(pwd)
cd ../../

tmpfn=$(mktemp)
pdns_server --config-dir=$(pwd)/tests/powerdns &>$savedpwd/powerdns.log &
cleanup () {
    rm -f $tmpfn
    rm -f $savedpwd/powerdns.log
    kill $!
    cd $savedpwd
}
trap cleanup EXIT

for file in tests/data/*.txt ; do
    while read line ; do
        host=$(basename --suffix .txt $file)
        dig +short @127.0.0.1 $host.dyndns.example.net ANY >> $tmpfn
    done < $file
    diff $file $tmpfn
    rm -f $tmpfn
done
