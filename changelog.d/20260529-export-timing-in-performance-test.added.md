`psynet performance-test local` now runs `psynet export local` after each
bot-count stage and reports the duration. Use `--no-export` to skip. Export
time is included in `--json-output` results and tracked as a new
`track_export_time_s` metric in the ASV benchmark suite.
