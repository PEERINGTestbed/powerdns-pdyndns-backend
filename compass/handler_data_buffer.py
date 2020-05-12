import ipaddress
import collections

IP_ADDRESS = 0
IP_NETWORK = 1

class IPRoundRobin():
    def __init__(self, targets):
        if isinstance(targets, list):
            # TODO verify max target len
            if not len(targets):
                raise ValueError('IP address list should not be empty.')
            curr_ipver = None
            for t in targets:
                try:
                    ipaddr = ipaddress.ip_address(t)
                    if curr_ipver is None:
                        curr_ipver = ipaddr.version
                    elif curr_ipver != ipaddr.version:
                        raise ValueError('Only addresses from same versions can be set.')

                except ValueError:
                    raise ValueError('''Target list contains invalid entries (only IP
                                     addresses are accepted).''')
            self.version = curr_ipver
            self.type = IP_ADDRESS
            self.content = collections.deque(targets)

        elif isinstance(targets, str):
            try:
                if not '/' in targets:
                    raise ValueError
                ip_net = ipaddress.ip_network(targets)
            except ValueError:
                raise ValueError('Invalid IP network specified.')
            self.version = ip_net.version
            self.type = IP_NETWORK
            self.network = ip_net
            self.content = ip_net.__iter__()

        else:
            raise ValueError('''targets argument should be a list of IP addresses or an IP
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





if __name__ == '__main__':
    print('aloha!')
