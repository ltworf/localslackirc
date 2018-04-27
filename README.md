localslackirc
=============

The idea of this project is to create a localhost IRC server that
functions as a gateway for one user of slack, that can connect
to it with whatever IRC client they prefer and keep using slack
from IRC even after they shut down their IRC gateway.


Obtaining token
===============

Instructions for chromium

* In your browser, go to "Inspect" (developer mode) on an empty page
* Select the "Network" tab.
* Select WS (WebSockets)
* Open your web slack client
* Copy the 'token' parameter from the WebSocket connection URL.
* Place the token inside '~/.localslackcattoken'

Instructions for firefox

* In your browser, open the Slack web client
* Press F12 to open the developer tools
* Refresh the page (F5)
* Select the 'Network' tab
* Select the 'WS' tab
* Copy the 'token' parameter from the WebSocket connection URL.
* Place the token inside '~/.localslackcattoken'

Requirements
============

* At least Python 3.6
* The modules `slackclient` and `typedload`. You can use pip3 to get them.

IRC Channel
===========

#localslackirc on oftc
