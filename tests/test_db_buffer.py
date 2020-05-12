import ipaddress
from unittest import TestCase

#from .compass import IPRoundRobin

import sys
sys.path.append('..')
from compass.handler_data_buffer import IPRoundRobin

class TestIPRoundRobin(TestCase):
    def test_ip_address_validation(self):
        self.assertRaises(ValueError, IPRoundRobin, list())
        self.assertRaises(ValueError, IPRoundRobin, ['123'])
        self.assertRaises(ValueError, IPRoundRobin, ['abc'])

    def test_ip_address_iteration(self):
        ipaddrs = ['150.164.0.0', '150.164.0.1', '150.164.0.2', '150.164.0.0', '150.164.0.1']
        rr = IPRoundRobin(ipaddrs[:len(set(ipaddrs))])
        for ipaddr in ipaddrs:
            self.assertEqual(ipaddr, rr.next())

    def test_ip_network_validation(self):
        self.assertRaises(ValueError, IPRoundRobin, list())
        self.assertRaises(ValueError, IPRoundRobin, '150.164.0.0')
        self.assertRaises(ValueError, IPRoundRobin, 'abc')

    def test_ip_network_iteration(self):
        net = '150.164.0.0/16'
        rr = IPRoundRobin(net)
        for ipaddr in ipaddress.ip_network(net):
            self.assertEqual(ipaddr.exploded, rr.next())

import unittest
if __name__ == '__main__':
    unittest.main()

