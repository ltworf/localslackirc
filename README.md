localslackirc
=============

The idea of this project is to create a localhost IRC server that
functions as a gateway for one user of slack, that can connect
to it with whatever IRC client they prefer and keep using slack
from IRC even after they shut down their IRC gateway.


Obtaining token
===============

Instructions for chromium, probably similar for other browsers.

* In your browser, go to "Inspect" (developer mode) on an empty page
* Select the "Network" tab.
* Select WS (WebSockets)
* Open your web slack client
* Copy the 'token' parameter from the WebSocket connection URL.

Now you can use localslackirc.

Contributors
============

Salvo 'LtWorf' Tomaselli <tiposchi@tiscali.it>
Joel Rosdahl (for the IRC server)
