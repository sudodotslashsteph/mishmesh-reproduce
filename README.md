# mishmesh reproduction files

Download or clone the experiments, recorded results, provenance, and tests from
the [mishmesh reproduction page](https://mishmesh.net/reproduce/) as one package.
The Python programs use only the standard library. Python 3.12 is the tested
baseline; no package installation or network access is needed to run them.

## Get the complete package

```sh
git clone https://github.com/sudodotslashsteph/mishmesh-reproduce.git
cd mishmesh-reproduce
```

Without Git, use **Code → Download ZIP** on this repository, extract the archive,
and open a terminal in the extracted folder. Keep the directory layout intact.

## Run the checks

```sh
python3 -m unittest discover -s tests -v
```

This runs 17 checks: nine for Rule 30 and eight for self-caused silence. If you
have Make installed, `make test` runs the same suite. On Windows, use `py -3`
instead of `python3` if that is how Python is installed.

## Reproduce the recorded results

Run these commands from the repository root:

```sh
python3 experiments/rule30-flanks/reproduce.py
python3 scripts/reproduce.py
```

The first command emits the bounded Rule 30 report as JSON. The second runs a
temporary copy of the preserved self-caused-silence model, sends its JSON result
to stdout, and sends its readable summary to stderr. Neither command replaces
the committed results. To save fresh outputs for comparison:

```sh
mkdir -p artifacts
python3 experiments/rule30-flanks/reproduce.py --output artifacts/rule30-results.json
python3 scripts/reproduce.py > artifacts/self-caused-silence-results.json
```

The tests compare regenerated results with the recorded fixtures. Read the
experiment notes for the exact scope and interpretation:

| Experiment | Included material |
| --- | --- |
| [Rule 30 flanks](experiments/rule30-flanks/README.md) | Bounded checker, complete right-flank cycles through depth 39, recorded report, and regression tests |
| [Self-caused silence](experiments/self-caused-silence/README.md) | Preserved model and recorded output, temporary-directory runner, and analytical and regression checks |

**The billion-step Rule 30 left-flank simulation is not included or verified by
these tests.** Its source and run logs were absent from the supplied materials.
These checks also do not establish real-world failure probabilities or
independent human review of the scientific claims.

## Run the pinned container

The Dockerfile pins Python 3.12.14 by image digest and runs the tests as an
unprivileged user:

```sh
docker build -t mishmesh-reproduce-tests .
docker run --rm --network none --read-only \
  --tmpfs /tmp:rw,noexec,nosuid,size=64m mishmesh-reproduce-tests
```

The build may need network access to download the base image. The test container
runs without networking. With Make installed, `make docker-test` performs both
commands. GitHub Actions runs the Python suite using the same pinned Python image.

## Attribution and provenance

The experiment READMEs and `provenance.json` files retain the supplied credits,
source references, and evidence limits. The self-caused-silence upstream files
remain unchanged, and the Rule 30 package identifies the report it checks and the
separate checker implementation. SHA-256 records identify supplied files; they
are not signatures or proof of authorship.

This repository is a standalone reproduction package. Its initial experiment
files, Python tests, runner, Dockerfile, and Docker ignore rules match the
website's downloadable files.
The root Makefile is adapted for this standalone Python package; no Node.js
installation is required. The root README, Git ignore rules, and CI workflow
provide the repository entry point.
