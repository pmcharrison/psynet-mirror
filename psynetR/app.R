display_node <-
  list(
    ui = p("Node display")
  )

display_responses <-
  list(
    ui = p("Responses display")
  )


path <- "/Users/peter.harrison/Dropbox/Academic/projects/jacoby-nori/cap/ganspace-gsp"

if (FALSE) {
  data <- import_gsp(
    path,
    label = "gansexp1",
    # label = "gsbcolor",
    # label = "mcmcpcol",
    node_type = "custom_node",
    trial_type = "custom_trial",
    network_type = "custom_network"
  )
  saveRDS(data, "tmp.rds")
}
data <- readRDS("tmp.rds")

runApp(chain_app(data, display_trial, display_responses))
