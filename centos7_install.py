#!/usr/bin/env python
# -*- coding:utf-8 -*-

import os
import sys
import re
import platform
import socket
import struct
import fcntl

IFNAME = 'enp0s3'
FLEET_PROXY = '10.230.164.23'
SYSLOG_PORT = 3514
base_path = os.path.dirname(os.path.abspath(__file__))


def get_ip_address(ifname=IFNAME): 
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) 
    return socket.inet_ntoa(fcntl.ioctl( 
        s.fileno(), 
        0x8915,  # SIOCGIFADDR 
        struct.pack('256s', ifname[:15]) 
    )[20:24]) 


def step_exec(cmd, info='', ignore_fail=False):
    result = False
    try:
        res = os.system(cmd)
        if res == 0:
            print('\033[32m{0} {1}\033[0m'.format(info, 'success'))
            result = True
        else:
            print('\033[31m{0} {1}\033[0m'.format(info, 'failed'))
    except Exception:
        print('\033[31m{0} {1}\033[0m'.format(info, 'failed'))

    return True if ignore_fail else  result


def install_hids():

    rpm_install_cmd = 'yum localinstall -y {0}/centos/el7/rpm/*'.format(base_path) 
    wheel_install_cmd = 'pip install {0}/centos/el7/wheels/*.*'.format(base_path)
    
    # install rpm and wheels
     
    step_exec(rpm_install_cmd, info='install rpm pachages')     
    step_exec(wheel_install_cmd, info='install python modules')

    # edit hosts

    step_exec('sed -i "/fleet-eu-data.zatech.com/d" /etc/hosts', info='delete if hosts has fleet-eu-data.zatech.com')   
    step_exec('sed -i "/salt-master/d"  /etc/hosts', info='delete if hosts has salt-master')   
 
    if not (step_exec('echo "{0}    fleet-eu-data.zatech.com" >> /etc/hosts'.format(FLEET_PROXY), info='edit hosts')
       and step_exec('echo "{0}    salt-master" >> /etc/hosts'.format(FLEET_PROXY), info='adding salt-master in /etc/hosts')):
       return False   
 
    # edit bashrc
    bashrc_1 = '''
export PROMPT_COMMAND='RETRN_VAL=$?;logger -p local1.info \"$(whoami) $SSH_CONNECTION $PWD [$$]: $(history 1 | sed \"s/^[ ]*[0-9]\+[ ]*//\" ) [$RETRN_VAL]\"'
    '''
    bashrc_2 = '''
typeset -r PROMPT_COMMAND
    '''

    step_exec('sed -i "/export PROMPT_COMMAND/d" /etc/bashrc', info='delete if bashrc has export PROMPT_COMMAND')    
    step_exec('sed -i "/typeset -r PROMPT_COMMAND/d" /etc/bashrc', info='delete if bashrc has typeset PROMPT_COMMAND') 

    with open('/etc/bashrc', 'a') as brc:
        brc.write(bashrc_1)
        brc.write(bashrc_2)

    # edit rsyslog

    if not step_exec('grep "@{0}:{1}" /etc/rsyslog.conf'.format(FLEET_PROXY, SYSLOG_PORT), info='rsyslog has collect log?' ):
       if not step_exec('echo "*.*    @{0}:{1}" >> /etc/rsyslog.conf'.format(FLEET_PROXY, SYSLOG_PORT), info='config rsyslog'):
           return False
   
    # config salt-minion
    ip_addr = get_ip_address()
    minion_cmd = 'sed -i "s/#id:/id: {0}/g" {1}/etc/minion'.format(ip_addr, base_path)
    if step_exec(minion_cmd, info='edit minion config'):
        cp_minion_cmd = '/bin/cp {0}/etc/minion /etc/salt/minion'.format(base_path) 
        if not step_exec(cp_minion_cmd, info='copy minion config'):
            return False
    else:
        return False 

    print('\033[32m{0}\033[0m'.format('Begin to enable and luanch service'))

    if not (step_exec('systemctl enable salt-minion', info='make salt-minion auto start')
       and step_exec('systemctl start  salt-minion', info='start salt-minion')
       and step_exec('systemctl restart rsyslog', info='restart rsyslog')):
       return False

if os.geteuid() != 0:
    print 'This script must be run as root. Aborting.'
    sys.exit(1)

if 'centos-7' not in platform.platform() or 'x86_64' != platform.machine() :
    print 'This script must be run in centos 7 and x86_64'
    sys.exit(1)

if __name__ == '__main__':
    if os.geteuid() != 0:
        print 'This script must be run as root. Aborting.'
        sys.exit(1)

    if 'centos-7' not in platform.platform() or 'x86_64' != platform.machine() :
        print 'This script must be run in centos 7 and x86_64'
        sys.exit(1)

    if install_hids():
        print 'Install success ...'
        sys.exit(0)
    else:
        print 'Install failed ..., contact us'
        sys.exit(1)
    

    
