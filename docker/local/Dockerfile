FROM python:3.7-slim-buster

LABEL maintainer="Jesse Egbosionu <j3bsie@gmail.com>"
WORKDIR /tudo-api
USER root

RUN apt-get update
RUN apt-get install -y netcat supervisor 

ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
RUN pip install --upgrade pip

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

COPY . .

CMD [ "supervisord", "-c", "supervisor.tudo.conf" ]
