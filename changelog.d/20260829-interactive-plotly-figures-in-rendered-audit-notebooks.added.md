Added interactive Plotly figures to rendered audit notebooks. Plotly MIME
outputs render with a vendored Plotly.js runtime, so audit sites remain
self-contained and work offline. The generated page applies a restrictive
content security policy and treats notebook figure data as inert JSON.
