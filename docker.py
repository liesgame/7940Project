import configparser
import logging
import pika
import json
import argparse
from os import system
import sys

class chatbot():
  def __init__(self, config, ip):
    file_handler = logging.FileHandler('docker.log', mode= 'a', encoding="utf-8")
    console_handler = logging.StreamHandler(sys.stdout)
    logging.basicConfig(format='%(asctime)s-%(name)s-%(levelname)s-%(message)s',level=logging.INFO, handlers=[file_handler,console_handler])
    self.config = config
    self.ip = ip
    self.rabbitmq()
    self.follow()
  def follow(self, ):
    routing_key = self.ip
    self.receive(routing_key =routing_key )
  
  
  def receive(self, routing_key):
      channel = self.channel
      logging.info("routing_key in rabbitmq is " + routing_key)
      result = channel.queue_declare('',exclusive=True)
      channel.queue_bind(exchange = config['RABBITMQ']['CHANNEL'],queue = result.method.queue,routing_key=routing_key)
      def callback(ch, method, properties, body):

        def return_add(return_message):
            logging.info('Create a new node ' + return_message)
            ok = system('docker run --name '+ return_message +' --net 7940 liesgame/chatbot python chatbot.py --config docker_config.ini --ip '+return_message)
            logging.info(ok)
        
        def return_delete(return_message):
            logging.info('delete node ' + return_message)
            ok = system('docker kill '+ return_message)
            logging.info(ok)  
    
        ch.basic_ack(delivery_tag = method.delivery_tag)
        logging.info("receive message : " + body.decode())
        content_body = json.loads(str(body.decode()))
        if content_body['method'] == 'add':
           return_add(return_message = content_body['message'])

        if content_body['method'] == 'delete':
           return_delete(return_message = content_body['message'])
      
      channel.basic_consume(result.method.queue,callback,auto_ack = False)
      channel.start_consuming()

  def rabbitmq(self,):
    credentials = pika.PlainCredentials(config['RABBITMQ']['NAME'], config['RABBITMQ']['PASSWORD'])  # mq用户名和密码
    connection = pika.BlockingConnection(pika.ConnectionParameters(host = '127.0.0.1',port = config['RABBITMQ']['PORT'],virtual_host = '/',credentials = credentials,  heartbeat = 0))
    self.channel =connection.channel()
    self.channel.exchange_declare(exchange = config['RABBITMQ']['CHANNEL'], durable = True, exchange_type='direct')
if __name__ == '__main__':
    parser = argparse.ArgumentParser()


    parser.add_argument("--config", type=str, default='docker_config.ini',help="configuration")
    parser.add_argument("--ip", type=str, default='docker',help="ip")

    args = parser.parse_args()
    config = configparser.ConfigParser()
    config.read(args.config)
    ip = args.ip
    a = chatbot(config= config, ip = ip)