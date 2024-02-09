localslackirc
=============

The idea of this project is to create a localhost IRC server that functions as
a gateway for one user of slack, that can connect to it with whatever IRC
client they prefer or a bouncer like ZNC and keep using slack from IRC even
after they shut down their IRC gateway.

[![Donate to LtWorf](docs/donate.svg)](https://liberapay.com/ltworf/donate)

Why? Peace of mind!
-------------------

Using slack from IRC instead of web app offers several advantages:

* You do not see all the gifs other people post.
* You can silence @here notifications for selected users and channels where they
  are abused.
* You can `/ignore` users who bother you (can't do that on slack).
* Leaving channels on slack is hard, normally I get invited back continuously
  on the off topic channels. With *localslackirc* you can leave them on the IRC
  client without people knowing that you won't be reading any of that.
* IRC clients allow to customise notifications. For example I have set mine to
  just blink in the tray area and do no sounds or popups.
* Any IRC client is faster than the web ui slack has, and it will respect your
  colour and style settings.
* Power savings. Because that's a logical consequence of not doing something
  in the browser.

Running localslackirc
=====================

The preferred way is to have Debian Testing and install from the repository.
You can grab the latest .deb and sources from:
https://github.com/ltworf/localslackirc/releases

All the options are documented in the man page. Execute

```bash
man man/localslackirc.1
```

To read the page without installing localslackirc on the system.

There is a`localslackirc` binary but the preferred way is to run it
using systemd.

Systemd
-------

When installed from the .deb you will find a configuration template file in
`/etc/localslackirc.d/example`.

Create a copy of it in the same directory and edit the copy.

You can create several copies to use several slack workspaces.

Tell systemd to start localslackirc and make sure the ports do not collide.

`instancename` is the name of the file.

```bash
# To start the instance
sudo systemctl start localslackirc@instancename.service
# To start the instance at every boot
sudo systemctl enable localslackirc@instancename.service
```

Docker
------

Create a configuration file basing it on `localslackirc.d/example`

```bash
# Create the container
docker build -t localslackirc -f docker/Dockerfile .

# Run localslackirc
docker run -d -p 9007:9007 --name=mylocalslackirc --env-file configfile localslackirc
```

Sources
-------

### Requirements

* At least Python 3.10
* The modules indicated in `requirements.txt`

Check the manpage for the parameters.

```bash
./localslackirc
```

Obtain a token
==============

Before localslackirc can do anything useful, you need to obtain a token.

Your token should be placed inside the configuration file.

Use lsi-getconf
---------------

After logging in slack with firefox, run `lsi-getconf`.

This tool is experimental. If it fails to work you need to do it manually.

Obtain a token from the browser
-------------------------------

* Open firefox
* Open slack
* Login
* Open developer mode
* Go to "network" tab
* Click on "WS", that means websocket
* Select the connection, right click and copy value > copy with cURL.
  If there is no connection, refresh the page and it will appear.

It will be something like this:

```
curl 'wss://wss-primary.slack.com/?token=xoxc-1111111111-111111111111-1111111111111-11111111111111111&sync_desync=1&start_args=%3Fagent%3Dclient%26org_wide_aware%3Dtrue%26agent_version%111111111111%26eac_cache_ts%3Dtrue' \
  -H 'User-Agent: Mozilla/5.0' \
  -H 'Accept: */*' \
  -H 'Accept-Language: en-US,en;q=0.5' \
  -H 'Accept-Encoding: gzip, deflate, br' -H 'Sec-WebSocket-Version: 13' \
  -H 'Origin: https://app.slack.com' \
  -H 'Sec-WebSocket-Extensions: permessage-deflate' \
  -H 'Sec-WebSocket-Key: 111111111111111111111111' \
  -H 'DNT: 1' \
  -H 'Connection: keep-alive, Upgrade' \
  -H 'Cookie: b=1111111111111111; d=xoxd-1111111111111111111111111111111; tz=60; OptanonConsent=isGpcEnabled=0&datestamp=Wed+Feb+07+2024+15%3A37%3A16+GMT%2B0100+(Ora+standard+dell%E2%80%99Europa+centrale)&version=202211.1.0&isIABGlobal=false&hosts=&consentId=11111111-1111-1111-1111-111111111111&interactionCount=1&landingPath=NotLandingPage&groups=1%3A1%2C3%3A0%2C2%3A0%2C4%3A0&AwaitingReconsent=false; lc=1111111111; shown_download_ssb_modal=1; d-s=1111111111; x=11111111111111111111111111111111.1111111111' \
  -H 'Sec-Fetch-Dest: empty' \
  -H 'Sec-Fetch-Mode: websocket' \
  -H 'Sec-Fetch-Site: same-site' -H 'Pragma: no-cache' -H 'Cache-Control: no-cache' -H 'Upgrade: websocket'
```

The `token=` part of the URL (terminated by `&`) and the `Cookie:` header are the parts that are important.

The cookie header contains more than one cookie, we want the one starting with `d=`. The value for the cookie must include the initial `d=` and the final `;`.

So, for example (the real values will be longer):

```
TOKEN=xoxc-1111111
COOKIE="d=xoxd-1111111;"
```

Using localslackirc
===================

After installing localslackirc and obtaining the token, it is the time
to connect to localslackirc with the IRC client.

* Connect to the IRC server created by localslackirc (by default 127.0.0.1:9007)
* Use your Slack username as your nickname
* If you left autojoin on, your client will automatically join your slack channels.

## Sending files
You can use `/sendfile #destination filepath` to send files. Destination can be a channel or a user.

## Annoying people
You can use `/annoy user` to send typing notifications whenever the specified user sends a typing notification.

## Discussion threads
There is some support for discussion threads.
They are mapped as irc channels that get automatically joined when a message is received. The channel of origin is specified in the topic.
Until a thread has some activity you can't write to it.
They are only tested for channels, not private groups or chats.

## Reacting to messages
Since I don't feel like manually wasting time to do it, a very nice `/autoreact` command is available to automate reacting.

## Instructions for irssi

If you need to refresh your memory about connecting in general, this is a good guide: https://pthree.org/2010/02/02/irssis-channel-network-server-and-connect-what-it-means/

Here's a list of irssi commands to set up a network and a localhost server:

```
/network add -user <you> -realname "<your name>" -nick <your nick> <slackname>
/server add -auto -port 9007 -network <slackname> localhost
/save
```

Then, start localslackirc in your terminal if you haven't already. (Just type `./localslackirc`).

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

IRC Channel
===========

#localslackirc on oftc
