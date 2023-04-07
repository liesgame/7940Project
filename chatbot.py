from telegram import Update, Bot
from telegram.ext import Updater,MessageHandler,Filters, CommandHandler, CallbackContext
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
import redis
import openai

class chatbot():
  def __init__(self, config, ip,is_master):
    self.ip = ip
    self.is_master = is_master
    openai.api_key = (config["OPENAI"]["API_KEYS"])
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
    global redis1
    redis1 = redis.Redis(host=(config['REDIS']['HOST']), password=(config['REDIS']['PASSWORD']), port=(config['REDIS']['REDISPORT']))

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
          return
    
    if is_master:
      self.master()
    else:
      self.follow()
  def master(self,):
      # openai.api_key = (config["OPENAI"]["API_KEYS"])
      if not self.zk.exists(self.master_path):
        self.zk.create(self.master_path,bytes(self.ip, encoding = "utf8"),makepath=True)
      else:
         master_ip = self.zk.get(self.master_path)[0].decode()
         if master_ip != self.ip:
            logging.error("there is existed master node " + master_ip)
            return
      def node(update, context):
          commd = update.message.text.upper()
          logging.info("Update: "+str(update))
          logging.info("Context: "+str(context))
          if commd == 'LIST':
            node_list = self.zk.get_children(self.root)
            node_list.remove('master')
            master_ip = self.zk.get(self.master_path)[0].decode()
            node_list.appand(master_ip)
            update.message.reply_text(str(node_list))
          elif commd == 'MASTER':
             master_ip = self.zk.get(self.master_path)[0].decode()
             update.message.reply_text(str(master_ip))
          else:
             update.message.reply_text('Usage:/ node list or / node master')
          # self.send(id = update.effective_chat.id, message_content = update.message.text, method='echo')
      def echo(update, context):
          reply_message = update.message.text.upper()
          logging.info("Update: "+str(update))
          logging.info("Context: "+str(context))
          self.send(id = update.effective_chat.id, message_content = update.message.text, method='echo')
          # context.bot.send_message(chat_id = update.effective_chat.id, text = reply_message)
      def add(update: Update, context: CallbackContext) -> None:
          logging.info("Update: "+str(update))
          logging.info("Context: "+str(context))
          try:
             msg = context.args[0]
          except(IndexError, ValueError):
             update.message.reply_text('Usage:/ add <keyword>')
             return
          self.send(id = update.effective_chat.id, message_content = context.args[0], method='add')
      def chat(update: Update, context: CallbackContext):
          logging.info("Update: "+str(update))
          logging.info("Context: "+str(context))
          try:
             msg = context.args[0]
          except(IndexError, ValueError):
             update.message.reply_text('Usage:/ chat <string>')
             return
          self.send(id = update.effective_chat.id, message_content = " ".join(context.args), method='chat')
          # id = update.effective_chat.id
          # human_message = {"role":"user", "content": " ".join(context.args)}
          # global redis1
          # redis1.lpush(id, json.dumps(human_message))
          # chat_message = redis1.lrange(id, 0, 50)[::-1]
          # chat_message = [json.loads(i.decode()) for i in chat_message]
          # response =  openai.ChatCompletion.create(
          #     # engine="text-davinci-003",
          #     model = 'gpt-3.5-turbo',
          #     messages=chat_message,
          #     temperature=0.7,
          #     max_tokens=1000
          #     # top_p=1.0,
          #     # frequency_penalty=0.0,
          #     # presence_penalty=0.6
          #     # stop=["human:"]
          #   )
          # logging.info("chat: "+str(response))
          # bot_message = response['choices'][0]['message']['content'].strip()
          # update.message.reply_text(bot_message)
          # redis1.lpush(id, json.dumps({'role':'assistant','content':bot_message}))
      
      def hello(update: Update, context: CallbackContext) -> None:
          logging.info("Update: "+str(update))
          logging.info("Context: "+str(context))
          update.message.reply_text('Good day, '+ context.args[0] + '!')
      def help_command(update: Update, context: CallbackContext) -> None:
          logging.info("Update: "+str(update))
          logging.info("Context: "+str(context))
          update.message.reply_text('Helping you helping you')

      self.updater=Updater(token=(config['TELEGRAM']['ACCESS_TOKEN']),use_context= True)
      dispatcher=self.updater.dispatcher
      #You can set this logging module,so you will know when and why things do not work as expected
      #register a dispatcher to handle message: here we register an echo dispatcher   
      echo_handler=MessageHandler(Filters.text&(~Filters.command),echo)
      dispatcher.add_handler(CommandHandler("add", add))
      dispatcher.add_handler(CommandHandler("help", help_command))
      dispatcher.add_handler(CommandHandler("hello", hello))
      dispatcher.add_handler(CommandHandler("chat", chat))
      dispatcher.add_handler(CommandHandler("node", node))
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
        def return_chat(bot, id, return_message):
          human_message = {"role":"user", "content": return_message}
          global redis1
          redis1.lpush(id, json.dumps(human_message))
          chat_message = redis1.lrange(id, 0, 50)[::-1]
          chat_message = [json.loads(i.decode()) for i in chat_message]
          response =  openai.ChatCompletion.create(
              # engine="text-davinci-003",
              model = 'gpt-3.5-turbo',
              messages=chat_message,
              temperature=0.7,
              max_tokens=1000
              # top_p=1.0,
              # frequency_penalty=0.0,
              # presence_penalty=0.6
              # stop=["human:"]
            )
          logging.info("chat: "+str(response))
          bot_message = response['choices'][0]['message']['content'].strip()
          bot.send_message(chat_id=id, text =bot_message)
          redis1.lpush(id, json.dumps({'role':'assistant','content':bot_message}))

        def return_echo(bot, id, return_message):
           bot.send_message(chat_id=id, text=return_message)
        
        def return_add(bot, id, return_message):
          try:
              global redis1
              logging.info("redis incr "+ return_message)
              redis1.incr(return_message)
              bot.send_message(chat_id=id, text = 'You have said ' + return_message + ' for ' + redis1.get(return_message).decode('UTF-8') + ' times.')
          except (IndexError, ValueError):
              bot.send_message(chat_id=id, text = 'Usage:/ add <keyword>')
        ch.basic_ack(delivery_tag = method.delivery_tag)
        logging.info("receive message : " + body.decode())
        content_body = json.loads(str(body.decode()))
        if content_body['method'] == 'echo':
           return_echo(bot=bot, id =content_body['id'], return_message = content_body['message'])
        elif content_body['method'] == 'add':
           return_add(bot=bot, id =content_body['id'], return_message = content_body['message'])
        elif content_body['method'] == 'chat':
           return_chat(bot=bot, id =content_body['id'], return_message = content_body['message'])
      
      channel.basic_consume(result.method.queue,callback,auto_ack = False)
      channel.start_consuming()
  
  def send(self, id, message_content, method):
    zk = self.zk
    root = self.root
    key_list = zk.get_children(root)
    key_list.remove('master')
    if len(key_list) < 1:
      logging.info("ERROR: without any follower")
      return
    key = root + '/' +key_list[random.randint(0,len(key_list) - 1)]
    routing_key = self.zk.get(key)[0].decode()
    send_message_mq=json.dumps({'id': id, 'message' : message_content, 'method' : method}, ensure_ascii=False)
    logging.info("Send: "+str(routing_key) +' message: ' + str(send_message_mq))
    self.channel.basic_publish(exchange = config['RABBITMQ']['CHANNEL'],routing_key = routing_key,body = send_message_mq,properties=pika.BasicProperties(delivery_mode = 2))

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