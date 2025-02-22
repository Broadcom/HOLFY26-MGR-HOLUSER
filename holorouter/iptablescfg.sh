#!/bin/sh

# DEFAULT HOL FIREWALL RULESET
# version 22-February 2025

# clear any existing rules
iptables --flush
ip6tables --flush

# EXAMPLE allow SSH: do not use as-is. Too open!
#iptables -A FORWARD -s 192.168.110.0/24 -p TCP --dport 22 -j ACCEPT

# allow ssh on the Manager
iptables -A FORWARD -p tcp -d 10.1.0.4 --dport 22 -j ACCEPT
iptables -A FORWARD -p tcp -s 10.1.0.4 --sport 22 -j ACCEPT

# DNAT/SNAT ssh on the Manager over external port 5480
iptables -A PREROUTING -t nat -d 192.168.100.2 -p tcp --dport 5480 -j DNAT --to-d 10.1.0.4:22
iptables -A POSTROUTING -t nat -p tcp -d 10.1.0.4 --dport 22 -j SNAT --to-source 192.168.100.2:5480

# for VLP Agent open access on the Manager VM 
iptables -A FORWARD -p tcp -s 10.1.0.4 -d 0.0.0.0/0 -j ACCEPT
iptables -A FORWARD -p tcp -d 10.1.0.4 -j ACCEPT

# allow ssh on the Main Console
iptables -A FORWARD -p tcp -d 10.1.0.2 --dport 22 -j ACCEPT
iptables -A FORWARD -p tcp -s 10.1.0.2 --sport 22 -j ACCEPT

# DNAT/SNAT port forward ssh to the Main Console
iptables -A PREROUTING -t nat -p tcp -d 192.168.100.2 --dport 22 -j DNAT --to 10.1.0.2:22
iptables -A POSTROUTING -t nat -p tcp -d 10.1.0.2 --dport 22 -j SNAT --to-source 192.168.100.2

# allow 5901 on the Main Console
iptables -A FORWARD -p tcp -d 10.1.0.2 --dport 5901 -j ACCEPT
iptables -A FORWARD -p tcp -s 10.1.0.2 --sport 5901 -j ACCEPT

# DNAT/SNAT port forward screen sharing over 5901 to the Main Console
iptables -A PREROUTING -t nat -p tcp -d 192.168.100.2 --dport 5901 -j DNAT --to 10.1.0.2:5901
iptables -A POSTROUTING -t nat -p tcp -d 10.1.0.2 --dport 5901 -j SNAT --to-source 192.168.100.2

# allow RDP 3389 on the Main Console
iptables -A FORWARD -p tcp -d 10.1.0.2 --dport 3389 -j ACCEPT
iptables -A FORWARD -p tcp -s 10.1.0.2 --sport 3389 -j ACCEPT

# DNAT/SNAT port forward 3389 for RDP to the Main Console
iptables -A PREROUTING -t nat -p tcp -d 192.168.100.2 --dport 3389 -j DNAT --to 10.1.0.2:3389
iptables -A POSTROUTING -t nat -p tcp -d 10.1.0.2 --dport 3389 -j SNAT --to-source 192.168.100.2

iptables -A INPUT -p tcp --sport 3128 -m state --state NEW,ESTABLISHED -j ACCEPT
iptables -A OUTPUT -p tcp --dport 3128 -m state --state ESTABLISHED -j ACCEPT

# allow access to and from Google DNS
iptables -A FORWARD -p UDP -d 8.8.8.8 --dport 53 -j ACCEPT
iptables -A FORWARD -p UDP -s 8.8.8.8 --sport 53 -j ACCEPT
iptables -A FORWARD -p UDP -d 8.8.4.4 --dport 53 -j ACCEPT
iptables -A FORWARD -p UDP -s 8.8.4.4 --sport 53 -j ACCEPT

# allow ping everywhere
iptables -A FORWARD -p icmp --icmp-type 8 -s 0/0 -d 0/0 -m state --state NEW,ESTABLISHED,RELATED -j ACCEPT
iptables -A FORWARD -p icmp --icmp-type 0 -s 0/0 -d 0/0 -m state --state ESTABLISHED,RELATED -j ACCEPT

# allow IPs inside the vPod, only on private networks TBD
#iptables -A FORWARD -s 192.168.0.0/16 -d 192.168.0.0/16 -j ACCEPT
#iptables -A FORWARD -s 192.168.0.0/16 -d 172.16.0.0/12  -j ACCEPT
#iptables -A FORWARD -s 192.168.0.0/16 -d 10.0.0.0/8     -j ACCEPT
#iptables -A FORWARD -s 172.16.0.0/12 -d 192.168.0.0/16  -j ACCEPT
#iptables -A FORWARD -s 172.16.0.0/12 -d 172.16.0.0/12   -j ACCEPT
#iptables -A FORWARD -s 172.16.0.0/12 -d 10.0.0.0/8      -j ACCEPT
#iptables -A FORWARD -s 10.0.0.0/8 -d 192.168.0.0/16     -j ACCEPT
#iptables -A FORWARD -s 10.0.0.0/8 -d 172.16.0.0/12      -j ACCEPT
#iptables -A FORWARD -s 10.0.0.0/8 -d 10.0.0.0/8         -j ACCEPT

### LAB-SPECIFIC RULES

# (add your rules here)

### END RULES

#set the default policy on FORWARD to DROP (deny all)
iptables -P FORWARD DROP

# indicate that iptables has run
> ~holuser/firewall
