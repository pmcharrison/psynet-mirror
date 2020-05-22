display_trial <-
  list(
    ui = p("Trial display")
  )

display_responses <-
  list(
    ui = p("Responses display")
  )


path <- "/Users/peter.harrison/Dropbox/Academic/projects/jacoby-nori/cap/ganspace-gsp"
data <- import_gsp(
  path,
  label = "gansexp1",
  # label = "gsbcolor",
  # label = "mcmcpcol",
  node_type = "custom_node",
  trial_type = "custom_trial",
  network_type = "custom_network"
)

runApp(chain_app(data, display_trial, display_responses))
