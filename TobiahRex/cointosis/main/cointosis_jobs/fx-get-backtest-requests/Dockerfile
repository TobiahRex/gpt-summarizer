# syntax=docker/dockerfile:1

FROM python:3.8-slim-buster
RUN apt update; apt-get -y install curl
WORKDIR src
ADD requirements.txt .
RUN pip install -r requirements.txt
ADD . .
CMD bash "start.sh"