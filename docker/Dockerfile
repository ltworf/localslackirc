FROM python:3.10-slim
RUN mkdir -p /localslackirc/slackclient
RUN adduser --group --system localslackirc
COPY requirements.txt /localslackirc
RUN python3 -m pip install -r /localslackirc/requirements.txt a
COPY *.py /localslackirc/
COPY localslackirc /localslackirc/
COPY slackclient/*.py /localslackirc/slackclient/
USER localslackirc
ENTRYPOINT PYTHONPATH=/localslackirc python3 /localslackirc/localslackirc -o -i "0.0.0.0"
