localslackirc
=============

The idea of this project is to create a localhost IRC server that
functions as a gateway for one user of slack, that can connect
to it with whatever IRC client they prefer or a bouncer like
ZNC and keep using slack from IRC even after they shut down
their IRC gateway.

Since at my workplace they waited for me to implement all this to decide to
switch to rocketchat, it now has support for doing the same thing with
rocketchat.


Options to Obtain token
===============

* Retrieve a slack token from https://api.slack.com/docs/oauth-test-tokens

Alternatively if this method fails you can get one from Slack's web client

1) Instructions for chromium

* In your browser, go to "Inspect" (developer mode) on an empty page
* Select the "Network" tab.
* Select WS (WebSockets)
* Open your web slack client
* Copy the 'token' parameter from the WebSocket connection URL. [Picture](https://raw.githubusercontent.com/inariksit/localslackirc/master/doc/token-instructions.png)


2) Instructions for firefox

* In your browser, open the Slack web client
* Press F12 to open the developer tools
* Refresh the page (F5)
* Select the 'Network' tab
* Select the 'WS' tab
* Copy the 'token' parameter from the WebSocket connection URL.



Using Token
===========

Your Slack token should be placed inside a file named `.localslackirc` inside your home directory.

Any location works, with the '-t' argument to the desired location. eg: ```python3 irc.py -t /home/me/slack/token.txt```

Using localslackirc
===================

* Start localslackirc by running `python3 irc.py` - you should see a connection message similar to the this:
```
{'ok': True, 'url': 'wss://cerberus-xxxx.lb.slack-msgs.com/websocket/jhvbT8578765JHBfrewgsdy7', 'team': {'id': 'ZZZ789012', 'name': 'Some Team', 'domain': 'someteam'}, 'self': {'id': 'XXX123456', 'name': 'your name'}}
```


* Now point your irc client to localslackirc (127.0.0.1:9007)
  * login to localslackirc using your Slack username
  * after your connected, list the channels in your irc client and select the ones you want to join.

## Automatically joining channels
To automatically connect to the Slack channels you are in open localslackirc with the -j argument
```python3 irc.py -j```

## Sending files
You can use `/sendfile #destination filepath` to send files. Destination can be a channel or a user.

## Instructions for irssi

If you need to refresh your memory about connecting in general, this is a good guide: https://pthree.org/2010/02/02/irssis-channel-network-server-and-connect-what-it-means/

Here's a list of irssi commands to set up a network and a localhost server:

```
/network add -user <you> -realname "<your name>" -nick <your nick> <slackname>
/server add -auto -port 9007 -network <slackname> localhost
/save
```

Then, start localslackirc in your terminal if you haven't already. (Just type `python3 irc.py`).

After localslackirc is running, and you have seen the connection
message seen above, you can just connect to the localhost IRC network
in irssi. Like this:

```
/connect <slackname>
```

And you should see the following message in your irssi:
```
22:15:35 [<slackname>] -!- Irssi: Looking up localhost
22:15:35 [<slackname>] -!- Irssi: Connecting to localhost [127.0.0.1] port 9007
22:15:35 [<slackname>] -!- Irssi: Connection to localhost established
22:15:36 [<slackname>] -!- Hi, welcome to IRC
22:15:36 [<slackname>] -!- Your host is serenity, running version miniircd-1.2.1
22:15:36 [<slackname>] -!- This server was created sometime
22:15:36 [<slackname>] -!- serenity miniircd-1.2.1 o o
22:15:36 [<slackname>] -!- There are 1 users and 0 services on 1 server
...
```

Requirements
============

* At least Python 3.6
* The modules indicated in `requirements.txt`


Using a docker container to run localslackirc
=============================================

Inside `docker` directory there is a dockerfile to generate a container that runs `localslackirc`.
In order to use it follow the instructions:

```
# docker build -t localslackirc -f docker/Dockerfile .

```

If everything went fine you should have a new container running localslackirc.

To start your new container:

```
docker run -d -p 9007:9007 --name=mylocalslackirc -e 'SLACKTOKEN=MYSLACKTOKEN' localslackirc
```


IRC Channel
===========

#localslackirc on oftc
