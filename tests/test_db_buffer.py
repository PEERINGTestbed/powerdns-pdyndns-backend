import json
import time
import pymongo
import datetime
import ipaddress
import bson.json_util as bson
from unittest import TestCase

from compass import data_buffer


class TestIPRoundRobin(TestCase):
    def test_ip_address_validation(self):
        self.assertRaises(ValueError, data_buffer.IPRoundRobin, list())
        self.assertRaises(ValueError, data_buffer.IPRoundRobin, ['123'])
        self.assertRaises(ValueError, data_buffer.IPRoundRobin, ['abc'])

    def test_ip_address_iteration(self):
        ipaddrs = ['150.164.0.0', '150.164.0.1', '150.164.0.2', '150.164.0.0', '150.164.0.1']
        rr = data_buffer.IPRoundRobin(ipaddrs[:len(set(ipaddrs))])
        for ipaddr in ipaddrs:
            self.assertEqual(ipaddr, rr.next())

    def test_ip_network_validation(self):
        self.assertRaises(ValueError, data_buffer.IPRoundRobin, list())
        self.assertRaises(ValueError, data_buffer.IPRoundRobin, '150.164.0.0')
        self.assertRaises(ValueError, data_buffer.IPRoundRobin, 'abc')

    def test_ip_network_iteration(self):
        net = '150.164.0.0/16'
        rr = data_buffer.IPRoundRobin([net])
        for i in range(3):
            for ipaddr in ipaddress.ip_network(net):
                self.assertEqual(ipaddr.exploded, rr.next())


class TestLiteHandlerBuffer(TestCase):
    def test_lite_round_robin_integration(self):
        f = open('tests/data/db-ipaddrs-handler.bson')
        ipaddrs_handler = bson.loads(f.read())
        f.close()

        f = open('tests/data/db-ipnet-handler.bson')
        ipnet_handler = bson.loads(f.read())
        f.close()

        lite_buffer = data_buffer.LiteHandlerBuffer([ipaddrs_handler, ipnet_handler])

        for ipaddr in 3*ipaddrs_handler['ipaddrs']:
            self.assertEqual(lite_buffer[ipaddrs_handler['qname']].next(), ipaddr)

        for i in range(3):
            for ipaddr in ipaddress.ip_network(ipnet_handler['ipaddrs'][0]):
                self.assertEqual(lite_buffer[ipnet_handler['qname']].next(), ipaddr.exploded)


class TestDatabaseHandlerBuffer(TestCase):
    @classmethod
    def setUpClass(self):
        f = open('tests/data/db-ipaddrs-handler.bson')
        self.default_ipaddrs_handler = bson.loads(f.read())
        f.close()

        f = open('tests/data/db-ipnet-handler.bson')
        self.default_ipnet_handler = bson.loads(f.read())
        f.close()

        f = open('tests/config/db-config.json')
        db_config = json.loads(f.read())
        self.db_config = {
            'host': db_config['mongo_host'],
            'port': db_config['mongo_port'],
            'db_name': db_config['mongo_dbname']
        }
        f.close()

        self.mongo_client = pymongo.MongoClient(self.db_config['host'],
                                                self.db_config['port'])

    @classmethod
    def tearDownClass(self):
        self.mongo_client.close()

    def setUp(self):
        self.mongo_client.drop_database(self.db_config['db_name'])

    def get_db(self):
        return self.mongo_client[self.db_config['db_name']]

    def test_basic_ipaddr_round_robin_integration(self):
        db = self.get_db()
        db['handlers'].insert_one(self.default_ipaddrs_handler)
        db_buffer = data_buffer.DatabaseHandlerBuffer(**self.db_config)


        for ipaddr in 3*self.default_ipaddrs_handler['ipaddrs']:
            self.assertEqual(db_buffer[self.default_ipaddrs_handler['qname']].next(), ipaddr)

    def test_basic_ipnet_round_robin_integration(self):
        db = self.get_db()
        db['handlers'].insert_one(self.default_ipnet_handler)
        db_buffer = data_buffer.DatabaseHandlerBuffer(**self.db_config)


        for i in range(3):
            for ipaddr in ipaddress.ip_network(self.default_ipnet_handler['ipaddrs'][0]):
                self.assertEqual(db_buffer[self.default_ipnet_handler['qname']].next(),
                                 ipaddr.exploded)

    def test_live_update_during_iteration(self):
        handler = dict(**self.default_ipaddrs_handler)
        handler['ipaddrs'] = ['150.164.0.0', '150.164.0.1']
        db = self.get_db()
        db['handlers'].insert_one(handler)
        db_buffer = data_buffer.DatabaseHandlerBuffer(**self.db_config)

        self.assertEqual(db_buffer[self.default_ipaddrs_handler['qname']].next(),
                         handler['ipaddrs'][0])

        new_ipaddrs = ['150.164.255.255', '150.164.255.254']
        db.handlers.update_one(
            {'qname': handler['qname']},
            {'$set': {'ipaddrs': new_ipaddrs, '_updated': datetime.datetime.utcnow()}}
        )

        time.sleep(3)

        for ipaddr in 3*new_ipaddrs:
            self.assertEqual(db_buffer[handler['qname']].next(), ipaddr)

    def test_live_handler_set_modifications(self):
        def compare_buffer_and_db(db, db_buffer):
            self.assertEqual(sorted(db_buffer.handlers),
                             sorted([i['qname'] for i in db.handlers.find({})]))

        base_handler = {
            k: v
            for k, v in self.default_ipaddrs_handler.items() if k != 'qname' and k != '_id'
        }
        handlers = [
            dict(**base_handler, qname='hitlist%d.compass.winet.dcc.ufmg.br' % i)
            for i in range(3)
        ]

        db = self.get_db()
        db['handlers'].insert_many(handlers[:-1])
        db_buffer = data_buffer.DatabaseHandlerBuffer(**self.db_config)
        compare_buffer_and_db(db, db_buffer)

        db['handlers'].delete_one({'qname': 'hitlist0.compass.winet.dcc.ufmg.br'})
        time.sleep(3)
        compare_buffer_and_db(db, db_buffer)

        db['handlers'].insert_one(handlers[-1])
        time.sleep(3)
        compare_buffer_and_db(db, db_buffer)



import unittest
if __name__ == '__main__':
    unittest.main()
