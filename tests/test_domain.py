import collections
import json
import logging
import pathlib
import typing
from io import StringIO
from unittest import TestCase

import pdyndns

SCHEMA = pathlib.Path("data/config-schema.json")
CONFIG_VALID_FP = pathlib.Path("tests/data/config-test.json")
Q_RMT_LOCAL_EDNS = "127.0.0.1\t127.0.0.1\t10.0.0.0/24"


def tabulate(entries: collections.abc.Iterable[typing.Any]):
    return "\t".join(str(e) for e in entries) + "\n"


class TestDomainHandler(TestCase):
    def setUp(self):
        logging.getLogger().setLevel(logging.CRITICAL + 1)
        with open(CONFIG_VALID_FP, "r", encoding="utf8") as fd:
            self.config = json.load(fd)
        self.dh = pdyndns.DomainHandler(self.config)
        self.domain = self.config["domain"]
        self.soa = self.config["soa"]
        self.ttl = self.config["ttl"]

    def test_domain_handler_soa(self):
        instr = tabulate(("Q", self.domain, "IN", "SOA", "-1", Q_RMT_LOCAL_EDNS))
        outstr = tabulate(
            ("DATA", "0", "1", self.domain, "IN", "SOA", self.ttl, "-1", self.soa)
        )
        fdout = StringIO()
        pdyndns.process_query(instr, self.dh, fdout)
        self.assertEqual(fdout.getvalue(), outstr)

    def test_domain_handler_ns(self):
        instr = tabulate(("Q", self.domain, "IN", "NS", "-1", Q_RMT_LOCAL_EDNS))
        outstr = ""
        for ns in self.config["nameservers"]:
            outstr += tabulate(("DATA", "0", "1", self.domain, "IN", "NS", self.ttl, "-1", ns))
        fdout = StringIO()
        pdyndns.process_query(instr, self.dh, fdout)
        self.assertEqual(fdout.getvalue(), outstr)

    def test_domain_handler_any(self):
        instr = tabulate(("Q", self.domain, "IN", "ANY", "-1", Q_RMT_LOCAL_EDNS))
        outstr = tabulate(
            ("DATA", "0", "1", self.domain, "IN", "SOA", self.ttl, "-1", self.soa)
        )
        for ns in self.config["nameservers"]:
            outstr += tabulate(("DATA", "0", "1", self.domain, "IN", "NS", self.ttl, "-1", ns))
        fdout = StringIO()
        pdyndns.process_query(instr, self.dh, fdout)
        self.assertEqual(fdout.getvalue(), outstr)

    def test_domain_handler_empty_response(self):
        instr = tabulate(("Q", self.domain, "IN", "A", "-1", Q_RMT_LOCAL_EDNS))
        fdout = StringIO()
        pdyndns.process_query(instr, self.dh, fdout)
        self.assertEqual(fdout.getvalue(), "")
