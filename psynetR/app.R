library(ggpubr)
theme_set(theme_pubr())

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

# Formatting data for the app
data$node$definition <- map(data$node$definition, function(x) {
  x$vector <- sprintf("%.2f", x$vector) %>% paste(collapse = ", ")
  x
})

display_node <-
  list(
    ui = tags$div(
      p("Node display"),
      includeHTML("video-slider.html")
    ),
    server = list(
      null = function(output, ...) {
        runjs("unload_video()");
      },
      main = function(output, node_data, ...) {
        'load_video("{node_data$url}")' %>% glue() %>% runjs()
      }
    )
  )

display_responses <-
  list(
    ui = p("Responses display")
  )

runApp(chain_app(data, display_node, display_responses))
