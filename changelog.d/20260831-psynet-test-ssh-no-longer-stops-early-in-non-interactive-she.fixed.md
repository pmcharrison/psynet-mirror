`psynet test ssh` and `psynet performance-test ssh` no longer stop early when
run without an interactive terminal, for example from a script or an editor's
integrated shell. They previously watched local standard input so that you could
quit by pressing `q`, which made them exit immediately on end-of-file and report
that no participants had run. They now also fail with a non-zero exit code when
the remote command fails.
