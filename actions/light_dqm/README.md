# Light DQM skeleton + Grafana push

Status: **work in progress / not yet functional end-to-end.** This is a
restructuring of `light_dqm.py` plus a first pass at pushing metrics to
Grafana. It's ready for a look, not for cutting the nearline pipeline over
to it yet.

## What this is

`light_dqm.py` does two things in one script: it computes and
plots DQM quantities from a light-readout file, and it has no path to
Grafana at all. This folder now also has a lighter skeleton version of the
same script, restructured so the "take in a file → build a PDF" scaffolding
is separate from the actual physics/plotting functions, plus a new module
that pushes summary metrics to the InfluxDB instance behind our Grafana
dashboards.

None of the DQM math itself is new — every processing/plotting function is
meant to be copied over verbatim from `light_dqm.py`. This is a
reorganization, not a rewrite.

## New/changed files

| File | What it does |
|---|---|
| `light_dqm_skeleton.py` | The restructured main script. Handles CLI args, per-file metadata (the block `light_dqm.py` has at lines ~1217-1325), calls out to the processing functions, builds the merged PDF report, and (new) builds a `metrics` dict and optionally pushes it to Grafana. |
| `light_dqm_funcs.py` | Where the actual processing/plotting functions live, ported one at a time from `light_dqm.py`. See status below — most are still stubs. |
| `grafana_metrics.py` | New. `push_metrics(metrics, tags, measurement)` — sends a metrics dict to InfluxDB, following the pattern in [rvizarreta/2x2_SlowControlsDisplay's wiki](https://github.com/rvizarreta/2x2_SlowControlsDisplay/wiki/Send-to-Influx-DB-with-Python). |
| `../light_dqm_skeleton.sh` | Bash wrapper, parallel to `light_dqm.sh`, calling `light_dqm_skeleton.py` instead. Turns on `--push_grafana` when `ARCUBE_NEARLINE_PUSH_GRAFANA=1`. |
| `../../config/templates/grafana_config.template.yaml` | Template for InfluxDB connection settings (URL/PORT/NAME/PINGIP), same pattern as `FW_config.template.yaml` / `my_launchpad.template.yaml`. |
| `../../config/grafana_config.yaml` | Real connection settings, gitignored (not in this PR) — copy the template and fill in real values, same as the other two config files. |

## What's actually ported vs. still a stub

In `light_dqm_funcs.py`, only `get_ptps()` and `adc16_to_voltage()` are
fully ported (used as the worked example for the rest). Everything else
`light_dqm_skeleton.py` imports is still a `NotImplementedError` stub:

`get_waveform_info`, `get_max_value_mask`, `tag_large_events`,
`get_fprompt_estimate`, `get_noise_spectra`, `check_flatline`,
`check_baseline`, `plot_sum_waveform`, `plot_fprompt_rates`,
`plot_fprompt_occurrences`, `plot_noises`, `plot_baselines`,
`plot_flatline_mask`, `plot_baseline_mask`, `plot_noise_spectra_epcb`,
`save_as_json`, `read_from_json`, `placeholder_pdf`.

Until these are copied over from `light_dqm.py`, running the skeleton will
produce a PDF, but every plot in it will be a placeholder page saying that
plot failed - the import itself currently fails as a whole (Python's
`from module import (a, b, c, ...)` is all-or-nothing), so even the two
finished functions aren't actually being used yet.

## Metrics currently pushed to Grafana

`run_processing()` in `light_dqm_skeleton.py` builds a `metrics` dict as it
goes: `beam_trigger_rate_hz`, `self_trigger_rate_hz`, `min_dead_time_us`,
`file_length_s`, `n_events`, `hv_instability_rate_adc*_hz`,
`hv_instability_rate_max_hz`, `mean_noise_adc_counts`,
`mean_baseline_adc_counts`, `frac_channels_flatlined`,
`frac_channels_baseline_deviating`. Several of these depend on the
still-stubbed functions above, so the real values won't show up until
those are ported.

## Running it

```bash
ARCUBE_NEARLINE_PUSH_GRAFANA=1 ./light_dqm_skeleton.sh /path/to/some_run.FLOW.hdf5
```

Set `ARCUBE_NEARLINE_PUSH_GRAFANA=0` (or leave it unset) to skip the
Grafana push and just build the PDF/JSON output.


## Not done yet

- Port the remaining functions into `light_dqm_funcs.py`.
- Test `grafana_metrics.py` against the real InfluxDB instance.
- End-to-end test against a real `.FLOW.hdf5` file, comparing output
  against `light_dqm.py`'s.

