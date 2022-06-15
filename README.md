localslackirc
=============

The idea of this project is to create a localhost IRC server that functions as
a gateway for one user of slack, that can connect to it with whatever IRC
client they prefer or a bouncer like ZNC and keep using slack from IRC even
after they shut down their IRC gateway.

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

Obtain a token from slack
-------------------------

* Retrieve a slack token from https://api.slack.com/docs/oauth-test-tokens

Alternatively if this method fails you can get one from Slack's web client

1) Instructions for Chromium and Firefox

* In your browser, login to slack and then open the web console.
* Run this javascript code: `q=JSON.parse(localStorage.localConfig_v2)["teams"]; q[Object.keys(q)[0]]["token"]`
* Copy the result, without quotes.
* **Note**: If you are signed in to multiple teams this will not work, run in a private window for the team you want to set up.

Obtain a Slack cookie
---------------------

This step is only needed if your token starts with `xoxc-`. This option is available since release 1.7.

* Run this javascript code:

```js
q=JSON.parse(localStorage.localConfig_v2)["teams"];
var authToken=q[Object.keys(q)[0]]["token"];


// setup request
var formData = new FormData();
formData.append('token', authToken);

// make request
(async () => {
  const rawResponse = await fetch('/api/emoji.list', {
    method: 'POST',
    body: formData
  });

  const emojisApi = await rawResponse.json();

  // dump to console
})();
```

* In the network tab inspect the request for "emoji.list".
* From that request, copy the "Cookie" header.
* The values in the field look like `key1=value1; key2=value2; key3=value3;`
* Get the string `d=XXXXXX;` (where XXX is the secret) and that is your cookie value. It is important to copy the `d=` part and the final `;`.
* Save the string in its own file (different than the token file).


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
