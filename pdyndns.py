#!/usr/bin/env python3 -u

import argparse
import json
import logging
import os
import re
import resource
import sys

import ipaddress

PDNS_PROTOCOL_VERSION = 3
PDNS_BITS = 0


def setup_logging(config):
    strlevel = config['loglevel'].upper()
    numlevel = getattr(logging, strlevel, logging.INFO)
    formatter = logging.Formatter('pdyndns.py %(levelname)s %(message)s')
    handler = logging.StreamHandler(stream=sys.stderr)
    handler.setFormatter(formatter)
    handler.setLevel(numlevel)
    logger = logging.getLogger()
    logger.setLevel(numlevel)
    logger.addHandler(handler)


def create_parser():
    desc = '''PEERING dynamic PowerDNS backend for RIPE Atlas'''
    parser = argparse.ArgumentParser(description=desc)
    parser.add_argument('--config',
                        dest='config',
                        action='store',
                        metavar='JSON',
                        type=str,
                        required=True,
                        help='File containing JSON configuration')
    return parser


def pdns_handshake(fdi, fdo):
    line = fdi.readline().strip()
    logging.debug('pdns_handshake [%s]', line)
    m = re.match(r'^HELO\t(\d+)', line)
    if not m:
        fdo.write('FAIL\n')
        raise RuntimeError('PowerDNS handshake failed')
    fdo.write('OK\tPEERING dynamic PowerDNS backend\n')
    logging.debug('pdns_handshake OK')
    return int(m.group(1))


class RoundRobinFileHandlerSet(object):
    def __init__(self, config):
        self.handlers = dict()
        for cfg in config['handlers']:
            self.handlers[cfg['qname']] = RoundRobinFileHandler(cfg['qname'],
                                                                cfg['qtype'],
                                                                cfg['file'])

    def handle(self, query):
        _q, qname, _qclass, _qtype, _qid, _ip, _localip, _edns = \
                query.split('\t')
        if qname in self.handlers:
            return self.handlers[qname].handle(query)
        return [tuple()]

    def close(self):
        for _name, handler in self.handlers.items():
            handler.close()


class RoundRobinFileHandler(object):
    def __init__(self, qname, qtype, fn):
        stat = os.stat(fn)
        self.fdstat = (stat.st_mtime, stat.st_ino)
        self.fd = open(fn, 'r')
        self.fn = fn
        self.qname = str(qname)
        self.qtype = str(qtype)

    def handle(self, query):
        logging.debug('RoundRobinFileHandler query [%s]', query)
        _q, qname, qclass, qtype, qid, _ip, _localip, _edns = query.split('\t')
        r = tuple()
        if (qtype == self.qtype or qtype == 'ANY') and qname == self.qname:
            data = self._readline().strip()
            assert ipaddress.ip_address(data)
            r = ('DATA', PDNS_BITS, 1, qname, qclass, self.qtype, 0, qid, data)
        logging.debug('RoundRobinFileHandler response [%s]',
                      '\t'.join(str(field) for field in r))
        return [r]

    def close(self):
        self.fd.close()

    def _readline(self):
        stat = os.stat(self.fn)
        if self.fdstat != (stat.st_mtime, stat.st_ino):
            logging.info('File %s changed, reloading', self.fn)
            self.fd.close()
            self.fd = open(self.fn, 'r')
        line = self.fd.readline()
        if not line:
            self.fd.seek(0)
            line = self.fd.readline()
        return line


class DomainHandler(object):
    def __init__(self, domain, soa, nameservers, ttl):
        self.domain = str(domain)
        self.soa = str(soa)
        self.nameservers = list(str(ns) for ns in nameservers)
        self.ttl = int(ttl)
        # https://doc.powerdns.com/md/authoritative/backend-pipe/
        # PowerDNS ABI v3 fields:
        self.bits = PDNS_BITS
        self.auth = 1

    def handle(self, query):
        def mkentry(etype, data):
            return ('DATA', PDNS_BITS, 1, qname, qclass, etype, self.ttl,
                    qid, data)
        logging.debug('DomainHandler [%s]', query)
        _q, qname, qclass, qtype, qid, _ip, _localip, _edns = query.split('\t')
        r = list()
        if (qtype == 'SOA' or qtype == 'ANY') and qname == self.domain:
            r.append(mkentry('SOA', self.soa))
        if (qtype == 'NS' or qtype == 'ANY') and qname == self.domain:
            r.extend(mkentry('NS', ns) for ns in self.nameservers)
        return r


def process_query(line, handlers, fdo):
    line = line.strip()
    for handler in handlers:
        for reply in handler.handle(line):
            if reply:
                fdo.write('\t'.join(str(f) for f in reply) + '\n')
    fdo.write('END\n')


def create_handlers(config):
    handlers = list()
    handlers.append(RoundRobinFileHandlerSet(config))
    handlers.append(DomainHandler(config['domain'],
                                  config['soa'],
                                  config['nameservers'],
                                  config['ttl']))
    return handlers


def main():
    resource.setrlimit(resource.RLIMIT_AS, (1 << 26, 1 << 26))
    parser = create_parser()
    args = parser.parse_args()
    with open(args.config) as fd:
        config = json.load(fd)

    setup_logging(config)
    handlers = create_handlers(config)

    try:
        abi = pdns_handshake(sys.stdin, sys.stdout)
    except RuntimeError as e:
        logging.exception(e)
    logging.info('PowerDNS PIPE protocol version %d', abi)
    if abi != PDNS_PROTOCOL_VERSION:
        logging.error('Unsupported PowerDNS protocol version [%d]', abi)
        sys.stdout.write('FAIL\n')
        sys.exit(1)

    for line in sys.stdin:
        process_query(line, handlers, sys.stdout)

    sys.stdout.write('FAIL\n')
    sys.exit(0)


if __name__ == '__main__':
    sys.exit(main())
