#!/usr/bin/env python
# -*- coding:utf-8 -*-

import os
import sys
import re
import platform
import socket
import struct
import fcntl
import getopt


base_path = os.path.dirname(os.path.abspath(__file__))


def get_ip_address(ifname):
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

def get_version():
    os_type= None
    os_version = None
    arch_bit = platform.architecture()[0]
    arch = 'unknown'
    if arch_bit == '32bit':
        arch = 'x32'
    if arch_bit == '64bit':
        arch = 'x64'
    platform_str = platform.platform()
    if 'centos-7' in platform_str:
        os_type = 'centos'
        os_version = 7
    elif 'Ubuntu-16' in platform_str:
        os_type = 'ubuntu'
        os_version = 16 
    #todo more system version support
    return (os_type, os_version, arch)

def print_log(msg, t='info'):
    if t == 'info':
        print('\033[32m{0}\033[0m'.format(msg))
    elif t == 'error':
        print('\033[31m{0}\033[0m'.format(msg))
    elif t == 'warn':
        print('\033[33m{0}\033[0m'.format(msg))
    else:
        print(msg)         

def install_linux(ifname, salt_master):
    if os.geteuid() != 0:
        print_log('This script must be run as root. Aborting.', 'error')
        return False
    version_info = get_version()
    if version_info[0] == 'ubuntu':
        return install_ubuntu(version_info, ifname=ifname, salt_master=salt_master)
    elif version_info[0] == 'centos':
        return install_centos(version_info, ifname=ifname, salt_master=salt_master)
    else:
        print_log('system info: {0} ,does not support this system yet'.format(str(version_info)), 'error')
        return False
   
def install_ubuntu(version_info, ifname, salt_master):
    if version_info[1] != 16:
        print_log('Only support ubuntu 16 now...', 'error')
        return False
    if not os.path.exists('/tmp/hids_install'):
        os.makedirs('/tmp/hids_install')
    system_packages_path = os.path.join(base_path, version_info[0], str(version_info[1]), version_info[2])
    deb_packages_file = os.path.join(system_packages_path, 'deb.packages.tar.gz')
    if os.path.exists(deb_packages_file):
        res = step_exec('tar -xzf {0} -C {1}'.format(deb_packages_file, '/tmp/hids_install/'), '1.extract deb packages') \
              and step_exec('echo "deb file:///tmp/hids_install/ deb/" > /etc/apt/sources.list.d/hids.list', '2.adding apt-get local source') \
              and step_exec('apt-get install -y --allow-unauthenticated salt-minion python-pip', '3. install salt-minion and pip') 
        if not res:
            print_log('install deb packages failed', 'error')
            return False
    else:
        print_log('deb package not found', 'error')
        return False
    wheel_path = os.path.join(system_packages_path, 'wheels/*')
    res = step_exec('pip install {0}'.format(wheel_path), '4. install python modules')
    if not res:
        return False
    # config salt-minion
    ip_addr = get_ip_address(ifname)
    copy_tmp_file_cmd = '/bin/cp {0}/etc/minion {0}/etc/tmp_minion'.format(base_path, base_path) 
    minion_id_config_cmd = 'sed -i "s/#id:/id: {0}/g" {1}/etc/tmp_minion'.format(ip_addr, base_path)
    minion_master_config_cmd = 'sed -i "s/master: salt-master/master: {0}/g" {1}/etc/tmp_minion'.format(salt_master, base_path)
    cp_minion_cmd = '/bin/cp {0}/etc/tmp_minion /etc/salt/minion'.format(base_path)
    res = step_exec(copy_tmp_file_cmd, '5. gen config template file') \
          and step_exec(minion_id_config_cmd, '6. config salt minion id') \
          and step_exec(minion_master_config_cmd, '7. config salt minion master ip') \
          and step_exec(cp_minion_cmd, '8. copy salt minion config to /etc/salt/') \
          and step_exec('service salt-minion start', '9. start salt-minion') \
          and step_exec('service salt-minion status', '10. check salt-minion status')
    if res:
        print_log('ubuntu install success', 'info')
        return True
    else:
        print_log('ubuntu install failed', 'error')
        return False

def install_centos(version_info, ifname, salt_master):
    
    if version_info[1] != 7:
        print_log('Only support centos7 now...', 'error')
        return False
    
    rpm_install_cmd = 'yum localinstall -y {0}/centos/el{1}/{2}/rpm/*'.format(base_path, version_info[1], version_info[2])
    wheel_install_cmd = 'pip install {0}/centos/el{1}/{2}/wheels/*.*'.format(base_path, version_info[1], version_info[2])  
    
    # install rpm and wheels
    step_exec(rpm_install_cmd, info='1. install rpm pachages')
    step_exec(wheel_install_cmd, info='2. install python modules') 
 
    # config salt-minion
    ip_addr = get_ip_address(ifname)
    copy_tmp_file_cmd = '/bin/cp {0}/etc/minion {0}/etc/tmp_minion'.format(base_path, base_path)
    minion_id_config_cmd = 'sed -i "s/#id:/id: {0}/g" {1}/etc/tmp_minion'.format(ip_addr, base_path)
    minion_master_config_cmd = 'sed -i "s/master: salt-master/master: {0}/g" {1}/etc/tmp_minion'.format(salt_master, base_path)
    cp_minion_cmd = '/bin/cp {0}/etc/tmp_minion /etc/salt/minion'.format(base_path)
    res = step_exec(copy_tmp_file_cmd, '3. gen config template file') \
          and step_exec(minion_id_config_cmd, '4. config salt minion id') \
          and step_exec(minion_master_config_cmd, '5. config salt minion master ip') \
          and step_exec(cp_minion_cmd, '6. copy salt minion config to /etc/salt/') 
    if res:
        if version_info[1] >= 7:
            res = step_exec('systemctl enable salt-minion', '7. make salt-minion auto start') \
                  and step_exec('systemctl start salt-minion', '8. start salt-minion service') \
                  and step_exec('systemctl status salt-minion', '9. check salt-minion service status')
        else:
            res = step_exec('service salt-minion start', '7. start salt-minion service') \
                  and step_exec('service salt-minion status', '8. check salt-minion service status')
    else:
        print_log('config salt-minion failed', 'error')
    return res


def help():
    print_log('The script is to offline install fleet-hids-agent.')
    print_log('Only support on centos7 and ubuntu16, other verison will coming soon.')
    print_log('[*] -h or --help for help')
    print_log('[*] -i or --ifname to config hids network interface')
    print_log('[*] -m or --salt-master to config salt master ipaddr')

def main(argv):
    IFNAME = None
    SALT_MASTER = None
    try:
        opts, args = getopt.getopt(argv, "-h-i:-m:", ["help", "ifname=", "salt-master="])
        for opt_name, opt_value in opts:
            if opt_name in ('-h', '--help'):
                help()
                exit(0)
            if opt_name in ('-i', '--ifname'):
                IFNAME = opt_value
            if opt_name in ('-m', '--salt-master'):
                SALT_MASTER = opt_value
    except getopt.GetoptError, err:
        help()
        exit(-1)
    if IFNAME and SALT_MASTER: 
        res = install_linux(ifname=IFNAME, salt_master=SALT_MASTER)
        code = 0 if res else -1
        exit(code)
    else:
        print_log('require params', 'error')
        help()
        exit(-1)

if __name__ == '__main__':
    main(sys.argv[1:])
    #print(get_version())
    
