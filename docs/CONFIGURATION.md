# Configuration

The mock demo builds its own fictional profile, resume, and job in memory. It does
not load `data/profile.json`, `data/settings.json`, or a personal resume. Temporary
demo documents are removed when the demo exits normally.

Private files for the retained experimental workflow:

- `data/profile.json`: contact details, education, experience, and optional answers.
- `data/settings.json`: limits, scoring weights, test hosts, and optional Ollama.
- `data/applications.db`: local workflow records.
- `resumes/`: private PDFs.
- `outputs/`: generated documents.

`examples/profile.example.json` contains fictional data. Do not publish a copy of
your private profile in its place.

The integration workflow requires `--authorized-testing` and interactive confirmation.
Remote autofill additionally requires exact hostnames in private settings, for example:

```json
{
  "authorized_test_hosts": ["your-authorized-test-host.example"],
  "use_ollama": false,
  "request_delay_seconds": 1.0,
  "max_display": 15,
  "community_read_limit": 45
}
```

List only test hosts you control or have explicit permission to automate. This
flag is not permission to automate real job submissions. No wildcards are supported;
external redirects and unlisted resources are blocked by the automation context.

`.env.example` contains a loopback service address and a model-name placeholder.
Ollama is optional; set the model name only if enabling a locally installed model.
Profiles may be included in prompts sent to that local process.

`IA_DATA_DIR`, `IA_OUTPUT_DIR`, and `IA_RESUME_DIR` can override private data paths.
Keep overridden folders private too. The tests set temporary paths automatically.
