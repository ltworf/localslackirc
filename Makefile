all:
	@echo Nothing to do

.PHONY: lint
lint:
	mypy --config-file mypy.conf irc.py

.PHONY: test
test: lint

.PHONY: install
install:
	#Install slackclient
	install -d $${DESTDIR:-/}/usr/share/localslackirc/slackclient/
	install -m644 slackclient/slackrequest.py $${DESTDIR:-/}/usr/share/localslackirc/slackclient/
	install -m644 slackclient/server.py $${DESTDIR:-/}/usr/share/localslackirc/slackclient/
	install -m644 slackclient/exceptions.py $${DESTDIR:-/}/usr/share/localslackirc/slackclient/
	install -m644 slackclient/client.py $${DESTDIR:-/}/usr/share/localslackirc/slackclient/
	install -m644 slackclient/__init__.py $${DESTDIR:-/}/usr/share/localslackirc/slackclient/
	# Install files from the root dir
	install -m644 diff.py $${DESTDIR:-/}/usr/share/localslackirc/
	install -m644 slack.py $${DESTDIR:-/}/usr/share/localslackirc/
	install irc.py $${DESTDIR:-/}/usr/share/localslackirc/
	# Install command
	install -d $${DESTDIR:-/}/usr/bin/
	ln -s ../share/localslackirc/irc.py $${DESTDIR:-/}/usr/bin/localslackirc
	# install extras
	#TODO
