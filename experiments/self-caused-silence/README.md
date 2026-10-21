# Self-caused silence

AI-authored experiment by **Claude (Anthropic)**, dated October 12, 2026.
The upstream run note records the model as `claude-opus-5-5`; that identifier is
preserved as reported. Astra (OpenAI) added this reproduction package and tests.

The model asks what happens when a monitor blocks its own response channel, then
counts the resulting silence as evidence. Part A enumerates a finite toy universe;
Part B computes probabilities in an invented model using dynamic programming.
These are not measured real-world failure rates.

From the repository root:

```sh
python3 -m unittest discover -s tests -v
python3 scripts/reproduce.py > /tmp/self-caused-silence-results.json
```

Python 3.12 is the container and CI baseline. No third-party Python packages or
network connections are needed to run the experiment or tests. The reproduction
runner uses a temporary copy because the original script writes beside itself.
Its JSON goes to stdout and its readable summary goes to stderr.

The tests compare the full recorded result, check the analytical threshold-erasure
formula, retain broken-policy negative controls, and check reserved-channel
behavior for independent and bursty absences. They do not establish a general
theorem or independently reimplement the model. The upstream Monte Carlo and
plotting scripts are outside this small package.

`upstream/` contains byte-for-byte copies of the source and recorded result.
See [provenance.json](provenance.json) for the original repository, commit, source
paths, SHA-256 digests, and author credit. Preserve those files when extending the
experiment; add a new version beside them and document the differences.
