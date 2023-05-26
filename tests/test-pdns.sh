#!/bin/bash
set -eu

if [[ ! -f ../pdyndns/pdyndns.py ]] ; then
    echo "Execute this script from the 'tests' directory:"
    echo "cd tests ; ./test-pdns.sh"
    exit 1
fi

docker compose --file data/docker-compose.yml up --detach pdns

tmpfn=$(mktemp)
trap 'rm -f $tmpfn' EXIT

for file in data/*.txt ; do
    echo "testing $file"
    host=$(basename --suffix .txt "$file")
    for _ in $(seq "$(wc -l < "$file")") ; do
        echo "resolving $host.dyndns.example.net"
        dig @127.0.0.1 ANY "$host.atlas.peering.ee.columbia.edu" \
                | grep -Ee ". 0 IN" \
                | awk '{print $NF}' \
                >> "$tmpfn"
    done
    sort -o "$tmpfn" "$tmpfn"
    diff "$file" "$tmpfn"
    rm -f "$tmpfn"
done

docker compose --file data/docker-compose.yml stop pdns
