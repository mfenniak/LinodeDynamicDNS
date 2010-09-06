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
#   6 - IP address could not be found on interface
#   7 - Multiple IP addresses found on interface

from __future__ import with_statement

import sys
import linode.api
import getopt
import netifaces

opts, args = getopt.getopt(sys.argv[1:], "", ["force", "superforce", "api-key=", "iface=", "root=", "name=", "help", "ipv6"])
force = superforce = display_help = ipv6 = False
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
    elif o == "--ipv6":
        ipv6 = True

if linode_api_key == None or network_iface == None or domain_root == None or domain_name == None or display_help:
    print "usage: %s --api-key=... --iface=... --root=... --name=... [--force] [--superforce] [--ipv6]" % sys.argv[0]
    print "api-key: Linode API key"
    print "iface:   Network interface (eg. eth0)"
    print "root:    Domain root (eg. example.com)"
    print "name:    Domain entry (eg. myserver, to update myserver.example.com)"
    print "force:   Skip local not-modified check"
    print "superforce: Skip remote not-modified check"
    print "ipv6:    Update AAAA record with an IPv6 address"
    sys.exit(5)

api = linode.api.Api(linode_api_key)

def get_ip_address(ifname):
    address_family_name = "AF_INET"
    if ipv6:
        address_family_name = "AF_INET6"
    addresses = netifaces.ifaddresses(ifname).get(getattr(netifaces, address_family_name))
    if ipv6:
        addresses = [x for x in addresses if not x.get("addr", "").startswith("fe80:")]
    if addresses == None or len(addresses) == 0:
        print "Could not find an %s address for interface %s" % (address_family_name, ifname)
        sys.exit(6)
    elif len(addresses) > 1:
        print "Found multiple %s addresses for interface %s" % (address_family_name, ifname)
        sys.exit(7)
    return addresses[0]["addr"]

ip_addr = get_ip_address(network_iface)
prev_fname = "prev_ipaddr"
if ipv6:
    prev_fname = "prev_ip6addr"
if not force:
    with open(prev_fname, "r") as f:
        prev = f.readline()
        if prev == ip_addr:
            sys.exit(4)
with open(prev_fname, "w") as f:
    f.write(ip_addr)

domain_id = None
for domain in api.domain_list():
    if domain["DOMAIN"] == domain_root:
        domain_id = domain["DOMAINID"]
        break
if domain_id == None:
    print "Failed to find domain %s" % (domain_root)
    sys.exit(1)

resource_type = "A"
if ipv6:
    resource_type = "AAAA"
resource_id = None
for resource in api.domain_resource_list(domainid=domain_id):
    if resource["NAME"] == domain_name and resource["TYPE"] == resource_type:
        resource_id = resource["RESOURCEID"]
        if resource["TARGET"] == ip_addr and not superforce:
            sys.exit(3)
        break
if resource_id == None:
    print "Failed to find resource %s w/ type %s in domain %s" % (domain_name, resource_type, domain_root)
    sys.exit(2)

api.domain_resource_update(domainid=domain_id, resourceid=resource_id, target=ip_addr)

