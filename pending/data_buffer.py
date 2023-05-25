import time
import pymongo
import _thread
import ipaddress
import collections

IP_ADDRESS = 0
IP_NETWORK = 1

class IPRoundRobin():
    def __init__(self, targets):
        def parse_ipaddrs(self, ipaddrs):
            curr_qtype = None
            for t in ipaddrs:
                try:
                    ipaddr = ipaddress.ip_address(t)
                    if curr_qtype is None:
                        curr_qtype = ipaddr.version
                    elif curr_qtype != ipaddr.version:
                        raise ValueError('Only addresses from same versions can be set.')

                except ValueError as exp:
                    raise ValueError('''Target list contains invalid entries (only IP
                                     addresses are accepted).''')
            self.qtype = curr_qtype
            self.type = IP_ADDRESS
            self.content = collections.deque(ipaddrs)

        def parse_ipnet(self, ipnet):
            try:
                if not '/' in ipnet:
                    raise ValueError
                ip_net = ipaddress.ip_network(ipnet)
            except ValueError:
                raise ValueError('Invalid IP network specified.')
            self.qtype = ip_net.version
            self.type = IP_NETWORK
            self.network = ip_net
            self.content = ip_net.__iter__()

        if isinstance(targets, list):
            # TODO verify max target len
            if not len(targets):
                raise ValueError('IP address list should not be empty.')
            elif len(targets) == 1:
                if '/' in targets[0]:
                    parse_ipnet(self, targets[0])
                else:
                    parse_ipaddrs(self, targets)

            else:
                parse_ipaddrs(self, targets)

        elif isinstance(targets, str):
            parse_ipnet(self, targets)

        else:
            raise ValueError('''Targets argument should be a list of IP addresses or an IP
                             netowrk.''')

    def next(self):
        if self.type == IP_ADDRESS:
            curr_ipaddr = self.content.popleft()
            self.content.append(curr_ipaddr)
            return curr_ipaddr

        elif self.type == IP_NETWORK:
            try:
                curr_ipaddr = self.content.__next__()
            except StopIteration:
                self.content = self.network.__iter__()
                curr_ipaddr = self.content.__next__()
            return curr_ipaddr.exploded

class LiteHandlerBuffer():
    def set_handler(self, qname, hitlist=None):
        if hitlist is None:
            handler = self.db.handlers.find_one({'qname': qname})
            hitlist = handler.get('ipaddrs')
        self.handlers[qname] = IPRoundRobin(hitlist)

    def remove_handler(self, qname):
        del self.handlers[qname]


    def __init__(self, handlers):
        self.handlers = dict()
        for handler in handlers:
            self.set_handler(handler['qname'], handler['ipaddrs'])

        if not self.handlers:
            exit('Error: no handlers were found.')

    def __getitem__(self, qname):
        return self.handlers[qname]


class DatabaseHandlerBuffer(LiteHandlerBuffer):
    def __init__(self, host, port, db_name):
        try:
            mongo_client = pymongo.MongoClient(host, port)
            self.db = mongo_client[db_name]
            handlers = list(self.db.handlers.find({}))
        except pymongo.ConnectionFailure as e:
            print('Unable to establish database connection:')
            print(e)
            exit()

        super().__init__(handlers)
        self.handler2update = {h['qname']: h['_updated'] for h in handlers}
        _thread.start_new_thread(self.update_sentinel, ())

    def update_sentinel(self):
        while True:
            time.sleep(1)
            db_handler2update = {
                h['qname']: h['_updated']
                for h in list(self.db.handlers.find({}, {'qname': 1, '_updated': 1}))
            }

            pending_additions = list()
            pending_removals = list()
            for qname in set(list(db_handler2update.keys()) + \
                    list(self.handler2update.keys())):
                if qname in db_handler2update and qname not in self.handler2update:
                    pending_additions.append(qname)
                    continue
                elif qname not in db_handler2update and qname in self.handler2update:
                    pending_removals.append(qname)
                    continue

                if db_handler2update[qname] > self.handler2update[qname]:
                    self.set_handler(qname)

            for qname in pending_removals:
                self.remove_handler(qname)
                del self.handler2update[qname]

            for qname in pending_additions:
                self.set_handler(qname)
                self.handler2update[qname] = db_handler2update[qname]





if __name__ == '__main__':
    print('aloha!')
