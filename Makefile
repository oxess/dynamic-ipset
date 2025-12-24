.PHONY: all build install uninstall clean test lint format check help dev-install

PREFIX ?= /usr/local
SYSCONFDIR ?= /etc
SYSTEMD_UNIT_DIR ?= /lib/systemd/system
PYTHON ?= python3
DESTDIR ?=

all: build

help:
	@echo "Dynamic IPSet Makefile"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@echo "  build        Build the Python package"
	@echo "  install      Install to system (requires root)"
	@echo "  uninstall    Uninstall from system (requires root)"
	@echo "  dev-install  Install in development mode"
	@echo "  test         Run tests"
	@echo "  lint         Run linter (ruff)"
	@echo "  format       Format code (ruff)"
	@echo "  check        Run lint and tests"
	@echo "  clean        Clean build artifacts"
	@echo "  help         Show this help"

build:
	$(PYTHON) -m build

dev-install:
	$(PYTHON) -m pip install -e ".[dev]"

install:
	# Install Python package
	$(PYTHON) -m pip install .

	# Install CLI script
	install -D -m 755 bin/dynamic-ipset $(DESTDIR)$(PREFIX)/bin/dynamic-ipset

	# Install default config
	install -D -m 644 etc/dynamic-ipset/config $(DESTDIR)$(SYSCONFDIR)/dynamic-ipset/config
	install -d -m 755 $(DESTDIR)$(SYSCONFDIR)/dynamic-ipset/config.d

	# Install systemd templates
	install -D -m 644 systemd/dynamic-ipset@.service $(DESTDIR)$(SYSTEMD_UNIT_DIR)/dynamic-ipset@.service
	install -D -m 644 systemd/dynamic-ipset@.timer $(DESTDIR)$(SYSTEMD_UNIT_DIR)/dynamic-ipset@.timer

	@echo ""
	@echo "Installation complete!"
	@echo "Run 'systemctl daemon-reload' to load new systemd units."

uninstall:
	# Stop and disable all timers
	-systemctl stop 'dynamic-ipset-*.timer' 2>/dev/null || true
	-systemctl disable 'dynamic-ipset-*.timer' 2>/dev/null || true

	# Remove systemd units
	rm -f $(DESTDIR)$(SYSTEMD_UNIT_DIR)/dynamic-ipset@.service
	rm -f $(DESTDIR)$(SYSTEMD_UNIT_DIR)/dynamic-ipset@.timer
	rm -f $(DESTDIR)/etc/systemd/system/dynamic-ipset-*.service
	rm -f $(DESTDIR)/etc/systemd/system/dynamic-ipset-*.timer

	# Reload systemd
	-systemctl daemon-reload 2>/dev/null || true

	# Remove CLI script
	rm -f $(DESTDIR)$(PREFIX)/bin/dynamic-ipset

	# Remove config (keep config.d to preserve user data)
	rm -f $(DESTDIR)$(SYSCONFDIR)/dynamic-ipset/config

	# Uninstall Python package
	$(PYTHON) -m pip uninstall -y dynamic-ipset || true

	@echo ""
	@echo "Uninstall complete!"
	@echo "Note: Config files in $(SYSCONFDIR)/dynamic-ipset/config.d were preserved."

test:
	$(PYTHON) -m pytest tests/ -v --cov=dynamic_ipset --cov-report=term-missing

lint:
	$(PYTHON) -m ruff check .

format:
	$(PYTHON) -m ruff check --fix .
	$(PYTHON) -m ruff format .

check: lint test

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .ruff_cache/
	rm -rf .coverage
	rm -rf htmlcov/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
