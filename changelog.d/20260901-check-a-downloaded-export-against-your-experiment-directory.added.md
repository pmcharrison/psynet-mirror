Exports from deployments that are too old to answer the project-identity
preflight are now checked against the identity recorded in the downloaded
`manifest.json` before the export is published, so an archive from the wrong
experiment cannot replace a good `exports/latest`.
