FROM alpine:3.6
RUN apk add --no-cache python3 && \
    python3 -m ensurepip && \
    rm -r /usr/lib/python*/ensurepip && \
    pip3 install --upgrade pip setuptools && \
    if [ ! -e /usr/bin/pip ]; then ln -s pip3 /usr/bin/pip ; fi && \
    if [[ ! -e /usr/bin/python ]]; then ln -sf /usr/bin/python3 /usr/bin/python; fi && \
    rm -r /root/.cache
RUN apk --no-cache add ca-certificates && update-ca-certificates
RUN mkdir /localslackirc
RUN mkdir /localslackirc/slackclient
RUN addgroup -S localslackirc
RUN adduser -S localslackirc -G localslackirc
COPY requirements.txt /localslackirc
RUN python3 -m pip install -r /localslackirc/requirements.txt a
COPY *.py /localslackirc/
COPY slackclient/*.py /localslackirc/slackclient/
USER localslackirc
ENTRYPOINT echo ${SLACKTOKEN} > ~/.localslackirc && PYTHONPATH=/localslackirc python3 /localslackirc/irc.py -o -i "0.0.0.0"
