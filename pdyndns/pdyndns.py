#!/usr/bin/python3

from __future__ import annotations

import argparse
import dataclasses
import ipaddress
import json
import logging
import os
import pathlib
import re
import resource
import sys
from collections import defaultdict
from typing import Optional, TextIO, Union

PDNS_PROTOCOL_VERSION = 3
PDNS_REGULAR_QUERY_STR = "Q"
PDNS_BITS = 0
PDNS_AUTHORITATIVE = 1

QUERY_LOG_FILE = "/etc/powerdns/backend/volume/queries.log"

IPAddress = Union[ipaddress.IPv4Address, ipaddress.IPv6Address]
IPNetwork = Union[ipaddress.IPv4Network, ipaddress.IPv6Network]


# https://doc.powerdns.com/md/authoritative/backend-pipe/
# PowerDNS ABI v3 fields:


@dataclasses.dataclass
class Query:
    qname: str  # the FQDN being asked for
    qname_orig: str  # the FQDN being asked for with 0x20 bit randomization
    qclass: str  # should be always IN
    qtype: str  # the type of query, like A, AAAA, and SOA
    qid: str  # the ID of the query, for caching and AXFR queries (unused)
    remote_ip: IPAddress  # the IP address of the resolver
    local_ip: IPAddress  # the local IP where we got the request (unused)
    edns_subnet: IPNetwork
    line: str  # The query line as received from PowerDNS

    @staticmethod
    def from_powerdns_query(line: str) -> Query:
        line = line.strip()
        (
            q,
            qname,
            qclass,
            qtype,
            qid,
            remote_ip,
            local_ip,
            edns_subnet,
        ) = line.split("\t")
        assert q == PDNS_REGULAR_QUERY_STR
        qname_lower = qname.lower()  # lowercase to fix 0x20 bit randomization
        rmt_v4addr = ipaddress.ip_address(remote_ip)
        loc_v4addr = ipaddress.ip_address(local_ip)
        edns_v4net = ipaddress.ip_network(edns_subnet)
        return Query(
            qname_lower,
            qname,
            qclass,
            qtype,
            qid,
            rmt_v4addr,
            loc_v4addr,
            edns_v4net,
            line,
        )

    def __str__(self) -> str:
        return self.line


@dataclasses.dataclass
class Response:
    query: Query
    qname: str
    rtype: str
    ttl: int
    answer: str

    def __str__(self):
        return "\t".join(
            str(f)
            for f in (
                "DATA",
                PDNS_BITS,
                PDNS_AUTHORITATIVE,
                self.qname,  # we may answer SOA and NS with different qname
                self.query.qclass,
                self.rtype,  # we may answer SOA, NS, A, AAAA for ANY queries
                self.ttl,
                self.query.qid,
                self.answer,
            )
        )


class DomainHandler:
    def __init__(self, config) -> None:
        self.domain: str = str(config["domain"])
        self.soa: str = str(config["soa"])
        self.nameservers: list[str] = list(str(ns) for ns in config["nameservers"])
        self.ttl: int = int(config["ttl"])

    def handle(self, query: Query) -> list[Response]:
        logging.debug("DomainHandler handling: %s", query)
        if not query.qname.endswith(self.domain):
            return []
        r: list[Response] = []
        if query.qtype in ("SOA", "ANY"):
            response = Response(query, self.domain, "SOA", self.ttl, self.soa)
            r.append(response)
        if query.qtype in ("NS", "ANY"):
            for ns in self.nameservers:
                response = Response(query, self.domain, "NS", self.ttl, ns)
                r.append(response)
        return r


class TargetIterator:
    def __init__(self, qtype: str, fn: str):
        self.qtype: str = qtype
        self.fn: pathlib.Path = pathlib.Path(fn)
        self.fdstat: tuple[float, int] = (0.0, 0)
        self.targets: list[IPAddress] = []
        self.idx: int = -1
        self.check_file()

    def check_file(self) -> None:
        if not self.fn.is_file():
            logging.error("Path %s is not a file", self.fn)
            return

        stat = os.stat(self.fn)

        if self.fdstat == (stat.st_mtime, stat.st_ino):
            return

        if stat.st_size == 0:
            logging.error("File %s is empty", self.fn)
            return

        logging.info("File %s changed, reloading", self.fn)
        logging.info("Current file: mtime=%f, ino=%d.", stat.st_mtime, stat.st_ino)
        self.fdstat = (stat.st_mtime, stat.st_ino)
        targets = []
        fd = open(self.fn, "r", encoding="utf8")
        for line in fd:
            line = line.strip()
            if not line:
                logging.warning("Empty line in %s", self.fn)
                continue
            try:
                addr = ipaddress.ip_address(line)
            except ValueError:
                logging.error("Malformed IP address in %s: %s", self.fn, line)
                continue
            if self.qtype == "A" and addr.version != 4:
                logging.error("Non IPv4 address in A handler %s: %s", self.fn, addr)
                continue
            if self.qtype == "AAAA" and addr.version != 6:
                logging.error("Non IPv6 address in AAAA handler %s: %s", self.fn, addr)
                continue
            targets.append(addr)
        fd.close()

        logging.info("Loaded %d targets from %s", len(targets), self.fn)
        if not targets:
            logging.error("No valid targets in %s, aborting", self.fn)
            return

        self.idx = -1
        self.targets = targets

    def __next__(self) -> Optional[IPAddress]:
        self.check_file()
        if len(self.targets) == 0:
            return None
        self.idx = (self.idx + 1) % len(self.targets)
        logging.debug("Advancing index for %s to %d", self.fn, self.idx)
        return self.targets[self.idx]


class NameHandler:
    def __init__(self, spec) -> None:
        self.qname: str = spec["qname"]
        self.qtype: str = spec["qtype"]
        self.targetit: TargetIterator = TargetIterator(self.qtype, spec["file"])

    def handle(self, query: Query) -> list[Response]:
        logging.debug("NameHandler handling: %s", query.line)
        assert self.qname == query.qname
        if query.qtype not in (self.qtype, "ANY"):
            return []

        addr = next(self.targetit)
        if addr is None:
            return []
        response = Response(query, query.qname_orig, self.qtype, 0, str(addr))
        return [response]


class HandlerSet:
    def __init__(self, config) -> None:
        self.domain: str = config["domain"]
        self.domain_handler = DomainHandler(config)
        qname2handlers: dict[str, list[NameHandler]] = defaultdict(list)
        for spec in config["handlers"]:
            qname = spec["qname"]
            if qname == self.domain or not qname.endswith(self.domain):
                logging.error("Skipping entry for invalid FQDN %s", qname)
                continue
            qname2handlers[qname].append(NameHandler(spec))
        self.qname2handlers: dict[str, list[NameHandler]] = dict(qname2handlers)

    def handle(self, query: Query) -> list[Response]:
        if not query.qname.endswith(self.domain):
            return []
        r: list[Response] = self.domain_handler.handle(query)
        for handler in self.qname2handlers.get(query.qname, []):
            r.extend(handler.handle(query))
        return r


def setup_logging(config: dict) -> None:
    loglevel = getattr(logging, config["loglevel"].upper(), logging.INFO)
    formatter = logging.Formatter("pdyndns %(levelname)s %(message)s")
    # Need to log to stderr because stdout is used to communicate with PowerDNS:
    shandler = logging.StreamHandler(stream=sys.stderr)
    shandler.setFormatter(formatter)
    shandler.setLevel(loglevel)
    logger = logging.getLogger()
    logger.setLevel(loglevel)
    logger.addHandler(shandler)


def create_parser() -> argparse.ArgumentParser:
    desc = """PEERING dynamic PowerDNS backend for RIPE Atlas"""
    parser = argparse.ArgumentParser(description=desc)
    parser.add_argument(
        "--config",
        dest="config",
        action="store",
        metavar="JSON",
        type=pathlib.Path,
        required=True,
        help="File containing JSON configuration",
    )
    return parser


def pdns_handshake(fdi: TextIO, fdo: TextIO, abi: int, startup_error: bool) -> bool:
    line = fdi.readline().strip()
    logging.info("pdns_handshake received: %s", line)
    m = re.match(r"^HELO\t(\d+)", line)
    if not m:
        logging.critical("Error parsing PowerDNS handshake")
        fdo.write("FAIL\n")
        fdo.flush()
        return False

    abi = int(m.group(1))
    if abi != PDNS_PROTOCOL_VERSION:
        logging.critical("Unsupported PowerDNS protocol version [%d]", abi)
        fdo.write("FAIL\n")
        fdo.flush()
        return False

    if startup_error:
        logging.critical("Failing handshake due to startup error")
        fdo.write("LOG\tpdyndns encountered a startup error\n")
        fdo.write("FAIL\n")
        fdo.flush()
        return False

    fdo.write("OK\tPEERING dynamic PowerDNS backend\n")
    fdo.flush()
    logging.info("pdns_handshake OK")
    return True


def process_query(line: str, hset: HandlerSet, fdo: TextIO) -> None:
    query = Query.from_powerdns_query(line)
    for response in hset.handle(query):
        if response is None:
            continue
        logging.debug("Sending: %s", response)
        fdo.write(str(response) + "\n")


def main():
    resource.setrlimit(resource.RLIMIT_AS, (1 << 26, 1 << 26))

    config = None
    hset = None
    startup_error = False
    try:
        parser = create_parser()
        args = parser.parse_args()
        with open(args.config, "r", encoding="utf8") as fd:
            config = json.load(fd)
        setup_logging(config)
        hset = HandlerSet(config)
    except Exception as e:
        sys.stderr.write(f"{e}\n")
        startup_error = True

    if not pdns_handshake(sys.stdin, sys.stdout, PDNS_PROTOCOL_VERSION, startup_error):
        # Following PowerDNS docs: "Suggested behaviour is to try and
        # read a further line, and wait to be terminated"
        sys.stdin.readline()
        sys.exit(1)

    assert config is not None
    assert hset is not None

    logging.info("PowerDNS PIPE protocol version %d", PDNS_PROTOCOL_VERSION)
    for line in sys.stdin:
        if not line.startswith(PDNS_REGULAR_QUERY_STR):
            logging.warning("Skipping unknown query type: %s", line.strip())
            sys.stdout.write("FAIL\n")
            sys.stdout.flush()
            continue
        logging.debug("Received: %s", line.strip())
        try:
            process_query(line, hset, sys.stdout)
            sys.stdout.write("END\n")
        except Exception as e:
            logging.exception(e)
            sys.stdout.write(f"LOG\t{e}\n")
            sys.stdout.write("FAIL\n")
        sys.stdout.flush()


if __name__ == "__main__":
    sys.exit(main())
