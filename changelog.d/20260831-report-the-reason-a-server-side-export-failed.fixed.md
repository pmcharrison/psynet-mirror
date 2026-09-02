When the deployed experiment cannot build an export, `psynet export` now reports
why instead of only "Internal Server Error (500)". This most often happens with
`--assets all`, where PsyNet has to run your own asset-generating code to
materialize on-demand assets.
