#!/usr/bin/python2.5
#
# update.py (the worst name for a python script ever) updates a Linode DNS
# entry to match the IP address of a network interface.  update.py is smart
# enough to not bother contacting Linode if the IP address hasn't changed,
# and also smart enough to not update the DNS entry if the address is already
# correct.  Both of those behaviors can be overridden.
#
# Args:
#   --force         Ignore previous IP address stored in prev_ipaddr file
#
#   --superforce    Ignores both prev_ipaddr and the current value in the
#                   Linode DNS manager, and saves the new value regardless.
#
# Exit codes:
#   0 - address updated successfully
#   1 - domain could not be found
#   2 - resource in domain could not be found
#   3 - IP address has not changed compared to Linode's DNS
#   4 - IP address has not changed compared to prev_ipaddr file
#   5 - Help output

from __future__ import with_statement

import socket
import struct
import fcntl
import sys
import linode.api
import getopt

opts, args = getopt.getopt(sys.argv[1:], "", ["force", "superforce", "api-key=", "iface=", "root=", "name=", "help"])
force = superforce = display_help = False
linode_api_key = network_iface = domain_root = domain_name = None
for o, a in opts:
    if o == "--force":
        force = True
    elif o == "--superforce":
        force = superforce = True
    elif o == "--api-key":
        linode_api_key = a
    elif o == "--iface":
        network_iface = a
    elif o == "--root":
        domain_root = a
    elif o == "--name":
        domain_name = a
    elif o == "--help":
        display_help = True

if linode_api_key == None or network_iface == None or domain_root == None or domain_name == None or display_help:
    print "usage: %s --api-key=... --iface=... --root=... --name=... [--force] [--superforce]" % sys.argv[0]
    print "api-key: Linode API key"
    print "iface:   Network interface (eg. eth0)"
    print "root:    Domain root (eg. example.com)"
    print "name:    Domain entry (eg. myserver, to update myserver.example.com)"
    print "force:   Skip local not-modified check"
    print "superforce: Skip remote not-modified check"
    sys.exit(5)

api = linode.api.Api(linode_api_key)

def get_ip_address(ifname):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    return socket.inet_ntoa(fcntl.ioctl(
        s.fileno(),
        0x8915,  # SIOCGIFADDR
        struct.pack('256s', ifname[:15])
    )[20:24])

ip_addr = get_ip_address(network_iface)
if not force:
    with open("prev_ipaddr", "r") as f:
        prev = f.readline()
        if prev == ip_addr:
            sys.exit(4)
with open("prev_ipaddr", "w") as f:
    f.write(ip_addr)

domain_id = None
for domain in api.domain_list():
    if domain["DOMAIN"] == domain_root:
        domain_id = domain["DOMAINID"]
        break
if domain_id == None:
    print "Failed to find domain %s" % (domain_root)
    sys.exit(1)

resource_id = None
for resource in api.domain_resource_list(domainid=domain_id):
    if resource["NAME"] == domain_name:
        resource_id = resource["RESOURCEID"]
        if resource["TARGET"] == ip_addr and not superforce:
            sys.exit(3)
        break
if resource_id == None:
    print "Failed to find resource %s in domain %s" % (domain_name, domain_root)
    sys.exit(2)

api.domain_resource_update(domainid=domain_id, resourceid=resource_id, target=ip_addr)

