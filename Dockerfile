FROM python:3.7.16
COPY ./chatbot.py /
COPY ./heartbeat.py /
COPY ./docker.py /
COPY ./config.ini /
COPY ./docker_config.ini /
COPY ./redis.conf /
RUN pip install pip update
RUN pip install -r requirements.txt
# CMD [ "chatbot.py" ]
# ENTRYPOINT [ "python" ]