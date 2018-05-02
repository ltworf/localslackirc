localslackirc
=============

The goal of this project is to keep using slack via IRC
after slack cloes their official IRC gateway.

localslackirc creates a localhost IRC server that
functions as a gateway for a single slack user.  You
connect with whatever IRC client you prefer or a
bouncer such as ZNC.


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

Get a slack token from https://api.slack.com/docs/oauth-test-tokens

Requirements
============

* At least Python 3.6
* The modules indicated in `requirements.txt`

IRC Channel
===========

#localslackirc on oftc
