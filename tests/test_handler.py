import collections.abc
import ipaddress
import json
import logging
import pathlib
import shutil
import tempfile
import time
import typing
from io import StringIO
from unittest import TestCase

import pdyndns

SCHEMA = pathlib.Path("data/config-schema.json")
CONFIG_VALID_FP = pathlib.Path("tests/data/config-test.json")
Q_RMT_LOCAL_EDNS = "127.0.0.1\t127.0.0.1\t10.0.0.0/24"


def tabulate(entries: collections.abc.Iterable[typing.Any]):
    return "\t".join(str(e) for e in entries) + "\n"


def tabulatn(entries: collections.abc.Iterable[typing.Any]):
    return "\t".join(str(e) for e in entries)


class TestNameHandler(TestCase):
    def setUp(self):
        logging.getLogger().setLevel(logging.CRITICAL + 1)
        with open(CONFIG_VALID_FP, "r", encoding="utf8") as fd:
            self.config = json.load(fd)
        self.hs = pdyndns.HandlerSet(self.config)
        self.domain = self.config["domain"]
        self.soa = self.config["soa"]
        self.ttl = self.config["ttl"]

    def test_name_handler_any(self):
        for h in self.config["handlers"]:
            for name in (h["qname"], h["qname"].upper()):
                instr = tabulate(("Q", name, "IN", "ANY", "-1", Q_RMT_LOCAL_EDNS))
                outstr = tabulatn(("DATA", "0", "1", name, "IN", h["qtype"], "0", "-1"))
                fdout = StringIO()
                pdyndns.process_query(instr, self.hs, fdout)
                self.assertRegex(fdout.getvalue(), outstr)

    def test_handler_qtype(self):
        for h in self.config["handlers"]:
            for name in (h["qname"], h["qname"].upper()):
                instr = tabulate(("Q", name, "IN", h["qtype"], "-1", Q_RMT_LOCAL_EDNS))
                outstr = tabulatn(("DATA", "0", "1", name, "IN", h["qtype"], "0", "-1"))
                fdout = StringIO()
                pdyndns.process_query(instr, self.hs, fdout)
                self.assertRegex(fdout.getvalue(), outstr)

    def test_handler_a_aaaa(self):
        for h in self.config["handlers"]:
            for name in (h["qname"], h["qname"].upper()):
                for qtype in ("A", "AAAA"):
                    instr = tabulate(("Q", name, "IN", qtype, "-1", Q_RMT_LOCAL_EDNS))
                    outstr = tabulatn(("DATA", "0", "1", name, "IN", qtype, "0", "-1"))
                    fdout = StringIO()
                    pdyndns.process_query(instr, self.hs, fdout)
                    if h["qtype"] == qtype:
                        self.assertRegex(fdout.getvalue(), outstr)
                    else:
                        self.assertEqual(fdout.getvalue(), "")

    def test_handler_empty(self):
        for name in ("unknown.dyndns.example.net", "UnknowN.DyndnS.ExamplE.NeT"):
            instr = tabulate(("Q", name, "IN", "A", "-1", Q_RMT_LOCAL_EDNS))
            fdout = StringIO()
            pdyndns.process_query(instr, self.hs, fdout)
            self.assertEqual(fdout.getvalue(), "")
            instr = tabulate(("Q", name, "IN", "AAAA", "-1", Q_RMT_LOCAL_EDNS))
            fdout = StringIO()
            pdyndns.process_query(instr, self.hs, fdout)
            self.assertEqual(fdout.getvalue(), "")
            instr = tabulate(("Q", name, "IN", "ANY", "-1", Q_RMT_LOCAL_EDNS))
            outstr = tabulatn(("DATA", "0", "1", name, "IN", "A", "0", "-1"))
            fdout = StringIO()
            pdyndns.process_query(instr, self.hs, fdout)
            self.assertNotRegex(fdout.getvalue(), outstr)

    def test_name_handler_file_rewind(self):
        for h in self.config["handlers"]:
            name = h["qname"]
            fileit = pdyndns.TargetIterator(h["qtype"], h["file"])
            ips = set(fileit.targets)
            targets = set()
            for _ in range(len(ips)):
                instr = tabulate(("Q", name, "IN", h["qtype"], "-1", Q_RMT_LOCAL_EDNS))
                outstr = tabulatn(("DATA", "0", "1", name, "IN", h["qtype"], "0", "-1"))
                fdout = StringIO()
                pdyndns.process_query(instr, self.hs, fdout)
                self.assertRegex(fdout.getvalue(), outstr)
                outstr = outstr.strip()
                addrstr = fdout.getvalue().strip().split("\t")[-1]
                targets.add(ipaddress.ip_address(addrstr))
            self.assertSetEqual(ips, targets)

    def test_name_handler_rewind_on_file_change(self):
        with tempfile.NamedTemporaryFile() as fd:
            shutil.copy(self.config["handlers"][0]["file"], fd.name)
            time.sleep(0.1)

            # Create new NameHandler to reset index
            spec = dict(self.config["handlers"][0])
            spec["file"] = fd.name
            nh = pdyndns.NameHandler(spec)
            name = nh.qname

            instr = tabulate(("Q", name, "IN", nh.qtype, "-1", Q_RMT_LOCAL_EDNS))
            outstr = tabulate(
                ("DATA", "0", "1", name, "IN", "A", "0", "-1", "10.1.0.1")
            )
            fdout = StringIO()
            pdyndns.process_query(instr, nh, fdout)
            self.assertEqual(fdout.getvalue(), outstr)

            # Overwrite t1.txt with t2.txt
            shutil.copy(self.config["handlers"][1]["file"], fd.name)
            time.sleep(0.1)  # Sleeping to avoid race conditions when calling os.stat
            instr = tabulate(("Q", name, "IN", "A", "-1", Q_RMT_LOCAL_EDNS))
            outstr = tabulate(
                ("DATA", "0", "1", name, "IN", "A", "0", "-1", "10.2.0.1")
            )
            fdout = StringIO()
            pdyndns.process_query(instr, nh, fdout)
            self.assertEqual(fdout.getvalue(), outstr)

            # Overwrite t1.txt with t2.txt
            shutil.copy(self.config["handlers"][0]["file"], fd.name)
            instr = tabulate(("Q", name, "IN", nh.qtype, "-1", Q_RMT_LOCAL_EDNS))
            outstr = tabulate(
                ("DATA", "0", "1", name, "IN", "A", "0", "-1", "10.1.0.1")
            )
            fdout = StringIO()
            pdyndns.process_query(instr, nh, fdout)
            self.assertEqual(fdout.getvalue(), outstr)
