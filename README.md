Dynamic PowerDNS backend
========================

[![PyPI](https://img.shields.io/pypi/v/pdyndns.svg)](https://pypi.org/project/pdyndns/)
[![Python](https://img.shields.io/pypi/pyversions/pdyndns.svg)](https://pypi.org/project/pdyndns/)

This repository implements a PowerDNS pipe backend to provide
dynamic replies to DNS queries.  Replies are taken round-robin from
a predefined list read from a text file.  We use this backend to
steer RIPE Atlas traceroute measurements toward PEERING prefixes
according to experiment requirements.

Usage
=====

This module communicates with PowerDNS using PowerDNS's [pipe
backend][1] protocol version 3.  The tool receives a single
configuration file as parameter, and exchanges information with
PowerDNS through standard input and output.  The configuration file
is in JSON format and is validated by the `config-schema.json` [JSON
schema][2].

 [1]: https://doc.powerdns.com/md/authoritative/backend-pipe/
 [2]: http://json-schema.org/

Backend configuration
---------------------

The configuration file specifies the DNS domain the backend is
responsible for, and information required to answer `SOA` and `NS`
DNS queries:

``` {.json}
{
  "domain": "atlas.peering.usc.edu",
  "soa": "atlas.peering.usc.edu noc.peering.usc.edu 20170723 7200 3600 7200 120",
  "nameservers": [
    "peering-atlas-ns.vms.uscnsl.net",
    "peering-atlas-ns.peering-vms.usc.edu"
  ],
  "ttl": 3600,
  "...": "..."
}
```

The `domain` parameter specifies what domain the backend is
responsible for.  The `soa` parameter specifies zone-specific timers
and configuration, and is used verbatim in replies for DNS `SOA`
queries.  The `nameserver` parameter specifies a list of name
servers for the zone, used in replies for `NS` queries.  The
time-to-live parameter (`ttl`) specifies the period for which
replies to `SOA` and `NS` queries should be cached.  Normally, the
third field in the `soa` parameter (`20170723`, the [serial
number][3]) needs to be updated whenever a zone is updated.
Although updating the serial number when the dynamic addresses are
reconfigured is not essential (because replies have a time-to-live
of zero to prevent caching), the serial number needs to be updated
if the `soa` or `nameservers` parameters are updated.

 [3]: https://doc.powerdns.com/md/types/

Each dynamic host name within `domain` is handled by a handler that
reads the list of IP addresses from a text file.  The handler
replies to queries with IP addresses in the text file in round-robin
order.  Each handler has three parameters:

``` {.json}
{
  "...": "...",
  "handlers": [
    {
      "qname": "target1.atlas.peering.usc.edu",
      "qtype": "A",
      "file": "data/peering-v4.txt",
    },
    {
      "qname": "target2.atlas.peering.usc.edu",
      "qtype": "AAAA",
      "file": "data/peering-v6.txt"
    },
    "..."
  ]
}
```

Parameter `qname` specifies the fully-qualified domain name that
should be answered with IP addresses within `file`.  The `qtype`
field specified whether IP addresses in `file` are IPv4 addresses
(`qtype = A`) or IPv6 addresses (`qtype = AAAA`).

Setting up the parent DNS server
--------------------------------

We also need to configure the authoritative name server for the
parent domain (`peering.usc.edu` in our case) to forward all
requests for `atlas.peering.usc.edu` to the machine running the
dynamic backend.

If using BIND and if the dynamic backend server is
`peering-atlas-ns.vms.uscnsl.net`, this can be achieved by adding
the following to the zone database (equivalent entries can be added
to PowerDNS to achieve the same effect):

```
atlas.peering.usc.edu.  NS          peering-atlas-ns.vms.uscnsl.net.
```

Testing pdyndns.py
==================

We have a test suite for `pdyndns.py`.  You can run it by installing
[nose][10] and running `nosetests`.  Note that we require nose for
Python 3.  We also have a [tox][11] script that checks for formatting
and performs some linting.

 [10]: http://nose.readthedocs.io/en/latest/
 [11]: https://pypi.python.org/pypi/tox

Acknowledgements
================

Precursors and early implementations for this code include [RIPE
Atlas][8]'s [atlas-dyndns][5], Emile Aben's [Scapy DNS Ninja][6] and
[Zeerover DNS][7].

 [8]: https://atlas.ripe.net
 [5]: https://github.com/RIPE-NCC/atlas-dyndns
 [6]: https://github.com/emileaben/scapy-dns-ninja
 [7]: https://github.com/USC-NSL/RIPE2015HackAThon
