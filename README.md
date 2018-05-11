localslackirc
=============

The idea of this project is to create a localhost IRC server that
functions as a gateway for one user of slack, that can connect
to it with whatever IRC client they prefer or a bouncer like
ZNC and keep using slack from IRC even after they shut down
their IRC gateway.


Options to Obtain token
===============

1) Instructions for chromium

* In your browser, go to "Inspect" (developer mode) on an empty page
* Select the "Network" tab.
* Select WS (WebSockets)
* Open your web slack client
* Copy the 'token' parameter from the WebSocket connection URL.

2) Instructions for firefox

* In your browser, open the Slack web client
* Press F12 to open the developer tools
* Refresh the page (F5)
* Select the 'Network' tab
* Select the 'WS' tab
* Copy the 'token' parameter from the WebSocket connection URL.

3) Get a slack token from https://api.slack.com/docs/oauth-test-tokens


Using Token
===========

* Place the token inside '~/.localslackirc'
* NOTE: do not include "token="


Warning
===========

* A token provides access to your private data and that of your team. Keep all tokens to yourself, protect them as you would a password and do not share them with others!


Requirements
============

* At least Python 3.6
* The modules indicated in `requirements.txt`

* NOTE: websocket doesnt work in Ubuntu. websocket-client must be used instead.
```
Uninstall websocket and websocket-client (if installed), then install 'only' websocket-client:

pip3 uninstall websocket
pip3 uninstall websocket-client
pip3 install websocket-client
```


Using localslackirc
===========

* Start localslackirc - you should see a connection message sililar to the this:
```
{'ok': True, 'url': 'wss://cerberus-xxxx.lb.slack-msgs.com/websocket/jhvbT8578765JHBfrewgsdy7', 'team': {'id': 'ZZZ789012', 'name': 'Some Team', 'domain': 'someteam'}, 'self': {'id': 'XXX123456', 'name': 'hack5190'}}
```

* Now point your irc client to localslackirc (127.0.0.1:9007) - login to localslackirc using use your Slack username - after your connected, list the channels in your irc client and select the ones you want to join. 

IRC Channel
===========

#localslackirc on oftc
