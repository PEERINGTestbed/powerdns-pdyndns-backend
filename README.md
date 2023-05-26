# Dynamic PowerDNS backend

This repository implements a PowerDNS pipe backend to provide dynamic replies to DNS queries.  Replies are taken round-robin from a predefined list read from a text file.  We use this backend to steer RIPE Atlas traceroute measurements toward PEERING prefixes according to experiment requirements.

## Usage

This module communicates with PowerDNS using PowerDNS's [pipe backend][pdns-backend] protocol version 3.  The tool receives a single configuration file as parameter, and exchanges information with PowerDNS through standard input and output.  The configuration file is JSON and can be validated using `utils/validate.py` to check it follows the schema in `data/config-schema.json` [JSON schema][json-schema].

[pdns-backend]: https://doc.powerdns.com/md/authoritative/backend-pipe/
[json-schema]: http://json-schema.org/

## Backend configuration

The configuration file specifies the DNS domain the backend is responsible for, and information required to answer `SOA` and `NS` DNS queries:

``` {.json}
{
  "domain": "atlas.peering.ee.columbia.edu",
  "soa": "atlas.peering.ee.columbia.edu noc.peering.ee.columbia.edu 20230525 7200 3600 7200 120",
  "nameservers": [
    "ns1.peering.ee.columbia.edu",
  ],
  "ttl": 3600,
  "...": "..."
}
```

The `domain` parameter specifies what domain the backend is responsible for.  The `soa` parameter specifies zone-specific timers and configuration, and is used verbatim in replies for DNS `SOA` queries. The `nameserver` parameter specifies a list of name servers for the zone, used in replies for `NS` queries.  The time-to-live parameter (`ttl`) specifies the period for which replies to `SOA` and `NS` queries should be cached.  Normally, the third field in the `soa` parameter (`20230525`, the [serial number][dns-serial-number]) needs to be updated whenever a zone is updated.  Although updating the serial number when the dynamic addresses are reconfigured is not essential (because replies have a time-to-live of zero to prevent caching), the serial number needs to be updated if the `soa` or `nameservers` parameters are updated.

[dns-serial-number]: https://doc.powerdns.com/md/types/

Each dynamic host name within `domain` is handled by a handler that reads the list of IP addresses from a text file.  The handler replies to queries with IP addresses in the text file in round-robin order.  Each handler has three parameters:

``` {.json}
{
  "...": "...",
  "handlers": [
    {
      "qname": "target1.atlas.peering.ee.columbia.edu",
      "qtype": "A",
      "file": "/etc/powerdns/backend/volume/target1-v4.txt",
    },
    {
      "qname": "target1.atlas.peering.ee.columbia.edu",
      "qtype": "AAAA",
      "file": "/etc/powerdns/backend/volume/target1-v6.txt"
    },
    "..."
  ]
}
```

Parameter `qname` specifies the fully-qualified domain name that should be answered with IP addresses within `file`.  The `qtype` field specified whether IP addresses in `file` are IPv4 addresses (`qtype = A`) or IPv6 addresses (`qtype = AAAA`).

## Launching the container

As `pdyndns.py` does not have any external dependencies, one can use PowerDNS's official container image, and mount all required configuration, data, and code on the container.  This is how the integration tests are implemented, and example of such a configuration can be seen on `tests/test-pdns.sh` and `tests/data/docker-compose.yml`.

## Setting up the parent DNS server

We also need to configure the authoritative name server for the parent domain (`peering.ee.columbia.edu` in our case) to forward all requests for `atlas.peering.ee.columbia.edu` to the machine running the dynamic backend.

If using BIND and if the dynamic backend server is `ns1.peering.ee.columbia.edu`, this can be achieved by adding the following to the zone database (equivalent entries can be added to PowerDNS to achieve the same effect):

```bind
ns1                             A           35.196.250.129
atlas.peering.ee.columbia.edu.  NS          ns1.peering.ee.columbia.edu.
```

This should go within the zone starting with (something similar to):

```bind
@       IN      SOA     peering.ee.columbia.edu. sundog.ee.columbia.edu. (
```

## Testing pdyndns.py

We have a test suite for `pdyndns.py`.  You can run it by launching `python3 -m unittest tests/*.py`.  We also have a [tox][python-tox] script that checks for formatting and performs some linting.

[python-tox]: https://pypi.python.org/pypi/tox

## Troubleshooting and notes

* PowerDNS stores serial numbers in 32-bit signed integers.
* `docker compose` considers volume source paths relative to the `docker-compose.yml` file.

## Acknowledgements

Precursors and early implementations for this code include [RIPE Atlas][ripe-atlas]'s [atlas-dyndns][atlas-dyndns], Emile Aben's [Scapy DNS Ninja][dns-ninja] and [Zeerover DNS][zeerover-dns].

[ripe-atlas]: https://atlas.ripe.net
[atlas-dyndns]: https://github.com/RIPE-NCC/atlas-dyndns
[dns-ninja]: https://github.com/emileaben/scapy-dns-ninja
[zeerover-dns]: https://github.com/USC-NSL/RIPE2015HackAThon
