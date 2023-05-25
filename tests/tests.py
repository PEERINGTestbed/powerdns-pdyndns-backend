from io import StringIO
import json
import jsonschema
import shutil
import tempfile
from unittest import TestCase

import pdyndns

class TestPowerDNSPipe(TestCase):
    def setUp(self):
        with open('config-schema.json', 'r') as fd:
            self.schema = json.load(fd)
        with open('tests/pdyndns.json', 'r') as fd:
            self.config = json.load(fd)
        self.addrs = '127.0.0.1\t127.0.0.1\t10.0.0.0/8'

    def test_schema_check_correct(self):
        self.assertIsNone(jsonschema.validate(self.config, self.schema))

    def test_schema_check_incorrect(self):
        with self.assertRaises(jsonschema.ValidationError):
            with open('tests/data/config1.json', 'r') as fd:
                wrong1 = json.load(fd)
                jsonschema.validate(wrong1, self.schema)
        with self.assertRaises(jsonschema.ValidationError):
            with open('tests/data/config2.json', 'r') as fd:
                wrong2 = json.load(fd)
                jsonschema.validate(wrong2, self.schema)
        with self.assertRaises(jsonschema.ValidationError):
            with open('tests/data/config3.json', 'r') as fd:
                wrong3 = json.load(fd)
                jsonschema.validate(wrong3, self.schema)

    def test_handshake(self):
        instr = 'HELO\t3\n'
        outstr = 'OK\tPEERING dynamic PowerDNS backend\n'
        fdin = StringIO(instr)
        fdout = StringIO()
        abi = pdyndns.pdns_handshake(fdin, fdout)
        self.assertEqual(fdout.getvalue(), outstr)
        self.assertEqual(abi, 3)

    def test_handshake_unsupported_abi(self):
        instr = 'HELO\t1\n'
        outstr = 'OK\tPEERING dynamic PowerDNS backend\n'
        fdin = StringIO(instr)
        fdout = StringIO()
        abi = pdyndns.pdns_handshake(fdin, fdout)
        self.assertEqual(fdout.getvalue(), outstr)
        self.assertEqual(abi, 1)

    def test_handshake_fail(self):
        instr = 'ERRORHELO\t1\n'
        outstr = 'FAIL\n'
        fdin = StringIO(instr)
        fdout = StringIO()
        with self.assertRaises(RuntimeError):
            abi = pdyndns.pdns_handshake(fdin, fdout)
            self.assertEqual(fdout.getvalue(), outstr)
            self.assertEqual(abi, 1)

    def test_domain_handler(self):
        dh = pdyndns.DomainHandler(self.config['domain'],
                                  self.config['soa'],
                                  self.config['nameservers'],
                                  self.config['ttl'])

        instr = 'Q\t%s\tIN\tSOA\t-1\t%s\n' % (
                    self.config['domain'], self.addrs)
        outstr = 'DATA\t0\t1\t%s\tIN\tSOA\t%d\t-1\t%s\n' % (
                    self.config['domain'],
                    self.config['ttl'],
                    self.config['soa'])
        outstr += 'END\n'

        fdout = StringIO()
        pdyndns.process_query(instr, [dh], fdout)
        self.assertEqual(fdout.getvalue(), outstr)

        instr = 'Q\t%s\tIN\tANY\t-1\t%s\n' % (
                    self.config['domain'], self.addrs)
        outstr = 'DATA\t0\t1\t%s\tIN\tSOA\t%d\t-1\t%s\n' % (
                    self.config['domain'],
                    self.config['ttl'],
                    self.config['soa'])
        for ns in self.config['nameservers']:
            outstr += 'DATA\t0\t1\t%s\tIN\tNS\t%d\t-1\t%s\n' % (
                        self.config['domain'], self.config['ttl'], ns)
        outstr += 'END\n'
        fdout = StringIO()
        pdyndns.process_query(instr, [dh], fdout)
        self.assertEqual(fdout.getvalue(), outstr)

    def test_domain_handler_broken_query(self):
        dh = pdyndns.DomainHandler(self.config['domain'],
                                  self.config['soa'],
                                  self.config['nameservers'],
                                  self.config['ttl'])
        instr = '%s\tIN\tSOA\t-1\t%s\n' % (
                    self.config['domain'], self.addrs)
        outstr = 'END\n'
        fdout = StringIO()
        with self.assertRaises(ValueError):
            pdyndns.process_query(instr, [dh], fdout)
            self.assertEqual(fdout.getvalue(), outstr)

    def test_domain_handler_empty_response(self):
        dh = pdyndns.DomainHandler(self.config['domain'],
                                  self.config['soa'],
                                  self.config['nameservers'],
                                  self.config['ttl'])
        instr = 'Q\t%s\tIN\tA\t-1\t%s\n' % (self.config['domain'], self.addrs)
        outstr = 'END\n'
        fdout = StringIO()
        pdyndns.process_query(instr, [dh], fdout)
        self.assertEqual(fdout.getvalue(), outstr)

        instr = 'Q\t%s\tIN\tA\t-1\t%s\n' % (
                    't1.%s' % self.config['domain'], self.addrs)
        outstr = 'END\n'
        fdout = StringIO()
        pdyndns.process_query(instr, [dh], fdout)
        self.assertEqual(fdout.getvalue(), outstr)

    def test_rr(self):
        handlers = [pdyndns.RoundRobinFileHandler(h['qname'],
                                                 h['qtype'],
                                                 h['file'])
                    for h in self.config['handlers']]
        names = [h['qname'] for h in self.config['handlers']]
        names += ['unknown.dyndns.example.net']

        for name in names[0:2]:
            instr = 'Q\t%s\tIN\tANY\t-1\t%s\n' % (name, self.addrs)
            outstr = 'DATA\t0\t1\t%s\tIN\tA\t0\t-1\t' % name
            fdout = StringIO()
            pdyndns.process_query(instr, handlers, fdout)
            self.assertTrue(fdout.getvalue().startswith(outstr))
            self.assertTrue(fdout.getvalue().endswith('END\n'))

        for name in names[2:3]:
            instr = 'Q\t%s\tIN\tANY\t-1\t%s\n' % (name, self.addrs)
            outstr = 'DATA\t0\t1\t%s\tIN\tAAAA\t0\t-1\t' % name
            fdout = StringIO()
            pdyndns.process_query(instr, handlers, fdout)
            self.assertTrue(fdout.getvalue().startswith(outstr))
            self.assertTrue(fdout.getvalue().endswith('END\n'))

        for name in names[3:4]:
            instr = 'Q\t%s\tIN\tANY\t-1\t%s\n' % (name, self.addrs)
            fdout = StringIO()
            pdyndns.process_query(instr, handlers, fdout)
            self.assertEqual(fdout.getvalue(), 'END\n')

        for handler in handlers:
            handler.close()

    def test_rr_a_aaaa(self):
        handlers = [pdyndns.RoundRobinFileHandler(h['qname'],
                                                  h['qtype'],
                                                  h['file'])
                    for h in self.config['handlers']]
        names = [h['qname'] for h in self.config['handlers']]
        names += ['unknown.dyndns.example.net']

        for name in names[0:2]:
            instr = 'Q\t%s\tIN\tA\t-1\t%s\n' % (name, self.addrs)
            outstr = 'DATA\t0\t1\t%s\tIN\tA\t0\t-1\t' % name
            fdout = StringIO()
            pdyndns.process_query(instr, handlers, fdout)
            self.assertTrue(fdout.getvalue().startswith(outstr))
            self.assertTrue(fdout.getvalue().endswith('END\n'))
            instr = 'Q\t%s\tIN\tAAAA\t-1\t%s\n' % (name, self.addrs)
            fdout = StringIO()
            pdyndns.process_query(instr, handlers, fdout)
            self.assertEqual(fdout.getvalue(), 'END\n')

        for name in names[2:3]:
            instr = 'Q\t%s\tIN\tAAAA\t-1\t%s\n' % (name, self.addrs)
            outstr = 'DATA\t0\t1\t%s\tIN\tAAAA\t0\t-1\t' % name
            fdout = StringIO()
            pdyndns.process_query(instr, handlers, fdout)
            self.assertTrue(fdout.getvalue().startswith(outstr))
            self.assertTrue(fdout.getvalue().endswith('END\n'))
            instr = 'Q\t%s\tIN\tA\t-1\t%s\n' % (name, self.addrs)
            fdout = StringIO()
            pdyndns.process_query(instr, handlers, fdout)
            self.assertEqual(fdout.getvalue(), 'END\n')

        for name in names[3:4]:
            instr = 'Q\t%s\tIN\tA\t-1\t%s\n' % (name, self.addrs)
            fdout = StringIO()
            pdyndns.process_query(instr, handlers, fdout)
            self.assertEqual(fdout.getvalue(), 'END\n')

        for handler in handlers:
            handler.close()

    def test_rr_a_aaaa_upper(self):
        handlers = [pdyndns.RoundRobinFileHandler(h['qname'],
                                                  h['qtype'],
                                                  h['file'])
                    for h in self.config['handlers']]
        names = [h['qname'].upper() for h in self.config['handlers']]
        names += ['UnknowN.DyndnS.ExamplE.NeT']

        for name in names[0:2]:
            instr = 'Q\t%s\tIN\tA\t-1\t%s\n' % (name, self.addrs)
            outstr = 'DATA\t0\t1\t%s\tIN\tA\t0\t-1\t' % name
            fdout = StringIO()
            pdyndns.process_query(instr, handlers, fdout)
            self.assertTrue(fdout.getvalue().startswith(outstr))
            self.assertTrue(fdout.getvalue().endswith('END\n'))
            instr = 'Q\t%s\tIN\tAAAA\t-1\t%s\n' % (name, self.addrs)
            fdout = StringIO()
            pdyndns.process_query(instr, handlers, fdout)
            self.assertEqual(fdout.getvalue(), 'END\n')

        for name in names[2:3]:
            instr = 'Q\t%s\tIN\tAAAA\t-1\t%s\n' % (name, self.addrs)
            outstr = 'DATA\t0\t1\t%s\tIN\tAAAA\t0\t-1\t' % name
            fdout = StringIO()
            pdyndns.process_query(instr, handlers, fdout)
            self.assertTrue(fdout.getvalue().startswith(outstr))
            self.assertTrue(fdout.getvalue().endswith('END\n'))
            instr = 'Q\t%s\tIN\tA\t-1\t%s\n' % (name, self.addrs)
            fdout = StringIO()
            pdyndns.process_query(instr, handlers, fdout)
            self.assertEqual(fdout.getvalue(), 'END\n')

        for name in names[3:4]:
            instr = 'Q\t%s\tIN\tA\t-1\t%s\n' % (name, self.addrs)
            fdout = StringIO()
            pdyndns.process_query(instr, handlers, fdout)
            self.assertEqual(fdout.getvalue(), 'END\n')

        for handler in handlers:
            handler.close()

    def test_rr_rewind(self):
        handlers = [pdyndns.RoundRobinFileHandler(h['qname'],
                                                 h['qtype'],
                                                 h['file'])
                    for h in self.config['handlers']]
        names = [h['qname'] for h in self.config['handlers']]
        names += ['unknown.dyndns.example.net']

        for _ in range(64):
            for name in names[0:2]:
                instr = 'Q\t%s\tIN\tA\t-1\t%s\n' % (name, self.addrs)
                outstr = 'DATA\t0\t1\t%s\tIN\tA\t0\t-1\t' % name
                fdout = StringIO()
                pdyndns.process_query(instr, handlers, fdout)
                self.assertTrue(fdout.getvalue().startswith(outstr))
                self.assertTrue(fdout.getvalue().endswith('END\n'))
                instr = 'Q\t%s\tIN\tAAAA\t-1\t%s\n' % (name, self.addrs)
                fdout = StringIO()
                pdyndns.process_query(instr, handlers, fdout)
                self.assertEqual(fdout.getvalue(), 'END\n')

            for name in names[2:3]:
                instr = 'Q\t%s\tIN\tAAAA\t-1\t%s\n' % (name, self.addrs)
                outstr = 'DATA\t0\t1\t%s\tIN\tAAAA\t0\t-1\t' % name
                fdout = StringIO()
                pdyndns.process_query(instr, handlers, fdout)
                self.assertTrue(fdout.getvalue().startswith(outstr))
                self.assertTrue(fdout.getvalue().endswith('END\n'))
                instr = 'Q\t%s\tIN\tA\t-1\t%s\n' % (name, self.addrs)
                fdout = StringIO()
                pdyndns.process_query(instr, handlers, fdout)
                self.assertEqual(fdout.getvalue(), 'END\n')

            for name in names[3:4]:
                instr = 'Q\t%s\tIN\tA\t-1\t%s\n' % (name, self.addrs)
                fdout = StringIO()
                pdyndns.process_query(instr, handlers, fdout)
                self.assertEqual(fdout.getvalue(), 'END\n')

        for handler in handlers:
            handler.close()

    def test_rr_reload(self):
        h = self.config['handlers'][0]
        rr = pdyndns.RoundRobinFileHandler(h['qname'], h['qtype'], h['file'])

        instr = 'Q\t%s\tIN\tA\t-1\t%s\n' % (h['qname'], self.addrs)
        outstr = 'DATA\t0\t1\t%s\tIN\tA\t0\t-1\t10.0.0.1\n' % h['qname']
        outstr += 'END\n'
        fdout = StringIO()
        pdyndns.process_query(instr, [rr], fdout)
        self.assertEqual(fdout.getvalue(), outstr)

        with tempfile.NamedTemporaryFile() as fd:
            # Overwrite t1.txt with t2.txt
            shutil.copy(h['file'], fd.name)
            shutil.copy(self.config['handlers'][1]['file'], h['file'])
            instr = 'Q\t%s\tIN\tA\t-1\t%s\n' % (h['qname'], self.addrs)
            outstr = 'DATA\t0\t1\t%s\tIN\tA\t0\t-1\t10.1.0.1\n' % h['qname']
            outstr += 'END\n'
            fdout = StringIO()
            pdyndns.process_query(instr, [rr], fdout)
            self.assertEqual(fdout.getvalue(), outstr)
            # Restore
            shutil.copy(fd.name, h['file'])

        instr = 'Q\t%s\tIN\tA\t-1\t%s\n' % (h['qname'], self.addrs)
        outstr = 'DATA\t0\t1\t%s\tIN\tA\t0\t-1\t10.0.0.1\n' % h['qname']
        outstr += 'END\n'
        fdout = StringIO()
        pdyndns.process_query(instr, [rr], fdout)
        self.assertEqual(fdout.getvalue(), outstr)

        rr.close()

    def test_rrset(self):
        rrset = pdyndns.RoundRobinFileHandlerSet(self.config)
        handlers = [rrset]
        names = [h['qname'] for h in self.config['handlers']]
        names += ['unknown.dyndns.example.net']

        for name in names[0:2]:
            instr = 'Q\t%s\tIN\tANY\t-1\t%s\n' % (name, self.addrs)
            outstr = 'DATA\t0\t1\t%s\tIN\tA\t0\t-1\t' % name
            fdout = StringIO()
            pdyndns.process_query(instr, handlers, fdout)
            self.assertTrue(fdout.getvalue().startswith(outstr))
            self.assertTrue(fdout.getvalue().endswith('END\n'))

        for name in names[2:3]:
            instr = 'Q\t%s\tIN\tANY\t-1\t%s\n' % (name, self.addrs)
            outstr = 'DATA\t0\t1\t%s\tIN\tAAAA\t0\t-1\t' % name
            fdout = StringIO()
            pdyndns.process_query(instr, handlers, fdout)
            self.assertTrue(fdout.getvalue().startswith(outstr))
            self.assertTrue(fdout.getvalue().endswith('END\n'))

        for name in names[3:4]:
            instr = 'Q\t%s\tIN\tANY\t-1\t%s\n' % (name, self.addrs)
            fdout = StringIO()
            pdyndns.process_query(instr, handlers, fdout)
            self.assertEqual(fdout.getvalue(), 'END\n')

        for handler in handlers:
            handler.close()
