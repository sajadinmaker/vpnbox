APP := vpnbox
VERSION := $(shell sed -n 's/^APP_VERSION = "\(.*\)"/\1/p' vpnbox.py)

.PHONY: help test check dist clean

help:
	@echo "vpnbox $(VERSION) — targets: test | check | dist | clean"

test:
	python3 -m unittest discover -s . -p "test_*.py" -v

check:
	python3 -m compileall -q vpnbox.py test_vpnbox.py
	bash -n install.sh
	bash -n uninstall.sh

dist:
	rm -rf dist
	mkdir -p dist/$(APP)-$(VERSION)
	cp vpnbox.py README.md CHANGELOG.md LICENSE install.sh uninstall.sh dist/$(APP)-$(VERSION)/
	tar -czf dist/$(APP)-$(VERSION).tar.gz -C dist $(APP)-$(VERSION)
	rm -rf dist/$(APP)-$(VERSION)
	cd dist && sha256sum $(APP)-$(VERSION).tar.gz > SHA256SUMS
	@echo "built dist/$(APP)-$(VERSION).tar.gz"

clean:
	rm -rf __pycache__ dist pkg
