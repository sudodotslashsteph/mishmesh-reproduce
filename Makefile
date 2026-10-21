PYTHON ?= python3
IMAGE ?= mishmesh-reproduce-tests

.PHONY: test test-experiments reproduce reproduce-rule30 reproduce-silence docker-build docker-test

test: test-experiments

test-experiments:
	$(PYTHON) -m unittest discover -s tests -v

reproduce: reproduce-rule30 reproduce-silence

reproduce-rule30:
	$(PYTHON) experiments/rule30-flanks/reproduce.py

reproduce-silence:
	$(PYTHON) scripts/reproduce.py

docker-build:
	docker build -t $(IMAGE) .

docker-test: docker-build
	docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m $(IMAGE)
