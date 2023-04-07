from telegram import Update, Bot
from telegram.ext import Updater,MessageHandler,Filters
import configparser
import logging
from kazoo.client import KazooClient, DataWatch
import pika
import time
import json
import random
import argparse
from os import system
import sys
import socket

class chatbot():
  def __init__(self, config, ip,is_master):
    self.ip = ip
    self.is_master = is_master
    file_handler = logging.FileHandler(str(ip)+'.log', mode= 'a', encoding="utf-8")
    console_handler = logging.StreamHandler(sys.stdout)
    logging.basicConfig(format='%(asctime)s-%(name)s-%(levelname)s-%(message)s',level=logging.INFO, handlers=[file_handler,console_handler])
    self.zkhost = config['ZOOKEEPER']['HOST']
    self.config = config
    self.updater = None 
    self.root = config['ZOOKEEPER']['ROOT']
    self.master_path = config['ZOOKEEPER']['MASTERPATH']
    self.zk = KazooClient(hosts=self.zkhost)   
    self.zk.start()
    self.rabbitmq()

    @self.zk.DataWatch(path=self.master_path)
    def _data_change(data,stat,event = None):
      if not event:
          return
      if event.type=='CREATED':
          logging.info(data.decode())
          master_ip = data.decode()
          if master_ip == self.ip:
              if not self.is_master:
                commend = 'python chatbot.py --is_master 1 --ip '+str(self.ip)
                logging.info(commend) 
                ok = system(commend)
                logging.info(ok)
          if master_ip != self.ip:
              if self.is_master:
                commend = 'python chatbot.py --ip '+str(self.ip)
                logging.info(commend) 
                ok = system(commend)
                logging.info(ok)
          logging.info(stat)
          logging.info(event)
          # self.updater.stop()
          # self.updater = None 
          # self.master()
          return
    
    if is_master:
      self.master()
    else:
      self.follow()
  def master(self,):
      if not self.zk.exists(self.master_path):
        self.zk.create(self.master_path,bytes(self.ip, encoding = "utf8"),makepath=True)
      else:
         master_ip = self.zk.get(self.master_path)[0].decode()
         if master_ip != self.ip:
            logging.error("there is existed master node " + master_ip)
            return
      def echo(update, context):
          reply_message = update.message.text.upper()
          logging.info("Update: "+str(update))
          logging.info("Update: "+str(type(update)))
          self.send(update)
          # context.bot.send_message(chat_id = update.effective_chat.id, text = reply_message)

      self.updater=Updater(token=(config['TELEGRAM']['ACCESS_TOKEN']),use_context= True)
      dispatcher=self.updater.dispatcher
      #You can set this logging module,so you will know when and why things do not work as expected
      #register a dispatcher to handle message: here we register an echo dispatcher   
      echo_handler=MessageHandler(Filters.text&(~Filters.command),echo)
      dispatcher.add_handler(echo_handler)
      
      # TO start the bot
      self.updater.start_polling()
      self.updater.idle()
      # self.updater.stop()
  def follow(self, ):

    zk = self.zk
    key = self.root + '/' + self.ip
    if self.zk.exists(self.master_path):
         master_ip = self.zk.get(self.master_path)[0].decode()
         if master_ip == self.ip:
            logging.error("it is master node " + master_ip)
            return
    if not zk.exists(key):
        logging.info('create node '+ self.ip + ' in zookeeper '+key)
        zk.create(key,bytes(self.ip, encoding = "utf8"),makepath=True)
    zk.set(key,bytes(self.ip, encoding = "utf8"))
    routing_key = self.ip
    if not zk.exists(key):
      zk.create(key,bytes(routing_key, encoding = "utf8"),makepath=True)
    zk.set(key, bytes(routing_key, encoding = "utf8"))
    bot = Bot(token=config['TELEGRAM']['ACCESS_TOKEN'])
    self.receive(bot=bot, routing_key =routing_key )
  
  
  def receive(self, bot, routing_key):
      channel = self.channel
      logging.info("routing_key in rabbitmq is " + routing_key)
      result = channel.queue_declare('',exclusive=True)
      channel.queue_bind(exchange = config['RABBITMQ']['CHANNEL'],queue = result.method.queue,routing_key=routing_key)
      def callback(ch, method, properties, body):
        ch.basic_ack(delivery_tag = method.delivery_tag)
        logging.info("receive message : " + body.decode())
        content_body = json.loads(str(body.decode()))
        bot.send_message(chat_id=content_body['id'], text=content_body['message'])
      
      channel.basic_consume(result.method.queue,callback,auto_ack = False)
      channel.start_consuming()
  
  def send(self, update):
    zk = self.zk
    root = self.root
    key_list = zk.get_children(root)
    key_list.remove('master')
    if len(key_list) < 1:
      logging.info("ERROR: without any follower")
      return
    key = root + '/' +key_list[random.randint(0,len(key_list) - 1)]
    routing_key = self.zk.get(key)[0].decode()
    message=json.dumps({'id': update.effective_chat.id, 'message' : update.message.text}, ensure_ascii=False)
    logging.info("Send: "+str(routing_key) +' message: ' + str(message))
    self.channel.basic_publish(exchange = config['RABBITMQ']['CHANNEL'],routing_key = routing_key,body = message,properties=pika.BasicProperties(delivery_mode = 2))

  def rabbitmq(self,):
    credentials = pika.PlainCredentials(config['RABBITMQ']['NAME'], config['RABBITMQ']['PASSWORD'])  # mq用户名和密码
    connection = pika.BlockingConnection(pika.ConnectionParameters(host = config['RABBITMQ']['HOST'],port = config['RABBITMQ']['PORT'],virtual_host = '/',credentials = credentials,  heartbeat = 0))
    self.channel =connection.channel()
    self.channel.exchange_declare(exchange = config['RABBITMQ']['CHANNEL'], durable = True, exchange_type='direct')
if __name__ == '__main__':
    parser = argparse.ArgumentParser()


    parser.add_argument("--config", type=str, default='docker_config.ini',help="configuration")
    parser.add_argument("--ip", type=str, default='127.0.0.1',help="ip")
    parser.add_argument("--is_master", type=bool, default=False,help="is master")

    args = parser.parse_args()
    config = configparser.ConfigParser()
    config.read(args.config)
    ip = args.ip
    is_master = args.is_master
    a = chatbot(config= config, ip = ip, is_master = is_master)