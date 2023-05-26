import logging
from io import StringIO
from unittest import TestCase

import pdyndns


class TestPowerDNSHandshake(TestCase):
    def setUp(self):
        logging.getLogger().setLevel(logging.CRITICAL + 1)

    def test_handshake(self):
        instr = "HELO\t3\n"
        outstr = "OK\tPEERING dynamic PowerDNS backend\n"
        fdin = StringIO(instr)
        fdout = StringIO()
        retval = pdyndns.pdns_handshake(fdin, fdout, 3, False)
        self.assertEqual(fdout.getvalue(), outstr)
        self.assertEqual(retval, True)

    def test_handshake_unsupported_abi(self):
        instr = "HELO\t1\n"
        outstr = "FAIL\n"
        fdin = StringIO(instr)
        fdout = StringIO()
        retval = pdyndns.pdns_handshake(fdin, fdout, 3, False)
        self.assertEqual(fdout.getvalue(), outstr)
        self.assertEqual(retval, False)

    def test_handshake_fail(self):
        instr = "ERRORHELO\t1\n"
        outstr = "FAIL\n"
        fdin = StringIO(instr)
        fdout = StringIO()
        retval = pdyndns.pdns_handshake(fdin, fdout, 3, False)
        self.assertEqual(fdout.getvalue(), outstr)
        self.assertEqual(retval, False)

    def test_handshake_startup_error(self):
        instr = "HELO\t3\n"
        outstr = "LOG\tpdyndns encountered a startup error\nFAIL\n"
        fdin = StringIO(instr)
        fdout = StringIO()
        retval = pdyndns.pdns_handshake(fdin, fdout, 3, True)
        self.assertEqual(fdout.getvalue(), outstr)
        self.assertEqual(retval, False)
