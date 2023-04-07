import schedule
import time
import socket
import configparser
from kazoo.client import KazooClient, DataWatch
import logging
import argparse
from ping3 import ping, verbose_ping

if __name__ == '__main__':
    parser = argparse.ArgumentParser()


    parser.add_argument("--config", type=str, default='docker_config.ini',help="configuration")
    args = parser.parse_args()

    config = configparser.ConfigParser()
    config.read(args.config)
    zk = KazooClient(hosts=config['ZOOKEEPER']['HOST'])   
    zk.start()   
    master_path = config['ZOOKEEPER']['MASTERPATH']
    root = config['ZOOKEEPER']['ROOT']
    logging.basicConfig(format='%(asctime)s-%(name)s-%(levelname)s-%(message)s',level=logging.INFO)
    @zk.DataWatch(path=master_path)
    def _data_change(data,stat,event = None):
        if not event:
            return
        if event.type=='DELETED':
            cont = zk.get_children(root)
            if len(cont) < 1:
               logging.info('master delete, zookeeper is empty')
               return
            key = cont[0]
            key = root + '/' + key
            ip = zk.get(key)[0]
            zk.delete(key,recursive=True)
            logging.info('master move to ' + str(ip))
            zk.create(master_path,ip,makepath=True)
            return
    def check_ip(ip):
      alive = ping(ip, timeout = 0.1)
      if alive:
         return True
      else:
         return False
    def heatbeat():
        if (not zk.exists(root)) or (not zk.exists(master_path)):
          logging.info('ERROR without master')
          return
        zk_list = zk.get_children(root)
        for i in zk_list:
            key = root + '/' + i
            ip = zk.get(key)[0].decode()
            is_alive = check_ip(ip)
            if not is_alive:
                logging.info('lass '+ip)
                zk.delete(key,recursive=True)
    schedule.every(1).seconds.do(heatbeat)
    while True:
      schedule.run_pending()