all:
	@echo Nothing to do

.PHONY: lint
lint:
	MYPYPATH=stubs mypy --config-file mypy.conf irc.py

.PHONY: test
test: lint

.PHONY: install
install:
	#Install slackclient
	install -d $${DESTDIR:-/}/usr/share/localslackirc/slackclient/
	install -m644 slackclient/exceptions.py $${DESTDIR:-/}/usr/share/localslackirc/slackclient/
	install -m644 slackclient/client.py $${DESTDIR:-/}/usr/share/localslackirc/slackclient/
	install -m644 slackclient/__init__.py $${DESTDIR:-/}/usr/share/localslackirc/slackclient/
	# Install files from the root dir
	install -m644 diff.py $${DESTDIR:-/}/usr/share/localslackirc/
	install -m644 slack.py $${DESTDIR:-/}/usr/share/localslackirc/
	install -m644 rocket.py $${DESTDIR:-/}/usr/share/localslackirc/
	install irc.py $${DESTDIR:-/}/usr/share/localslackirc/
	# Install command
	install -d $${DESTDIR:-/}/usr/bin/
	ln -s ../share/localslackirc/irc.py $${DESTDIR:-/}/usr/bin/localslackirc
	# install extras
	install -m644 -D CHANGELOG $${DESTDIR:-/}/usr/share/doc/localslackirc/CHANGELOG
	install -m644 -D README.md $${DESTDIR:-/}/usr/share/doc/localslackirc/README.md
	install -m644 -D man/localslackirc.1 $${DESTDIR:-/}/usr/share/man/man1/localslackirc.1

.PHONY: dist
dist:
	cd ..; tar -czvvf localslackirc.tar.gz \
		localslackirc/irc.py \
		localslackirc/diff.py \
		localslackirc/slack.py \
		localslackirc/rocket.py \
		localslackirc/slackclient/__init__.py \
		localslackirc/slackclient/client.py \
		localslackirc/slackclient/exceptions.py \
		localslackirc/Makefile \
		localslackirc/CHANGELOG \
		localslackirc/LICENSE \
		localslackirc/README.md \
		localslackirc/requirements.txt \
		localslackirc/docker/Dockerfile \
		localslackirc/man \
		localslackirc/mypy.conf \
		localslackirc/stubs/
	mv ../localslackirc.tar.gz localslackirc_`head -1 CHANGELOG`.orig.tar.gz
	gpg --detach-sign -a *.orig.tar.gz

deb-pkg: dist
	mv localslackirc_`head -1 CHANGELOG`.orig.tar.gz* /tmp
	cd /tmp; tar -xf localslackirc*.orig.tar.gz
	cp -r debian /tmp/localslackirc/
	cd /tmp/localslackirc/; dpkg-buildpackage
	install -d deb-pkg
	mv /tmp/localslackirc_* deb-pkg
	$(RM) -r /tmp/localslackirc

.PHONY: clean
clean:
	$(RM) -r deb-pkg
