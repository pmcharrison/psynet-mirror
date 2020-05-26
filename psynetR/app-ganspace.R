library(ggpubr)
theme_set(theme_pubr())

# options(shiny.error = browser)

path <- "/Users/peter.harrison/Dropbox/Academic/projects/jacoby-nori/cap/ganspace-gsp"

SLIDER_RANGE <- 4

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


format_node_df <- function(df) {
  df$vector <- map(df$vector, function(x) {
    sprintf("%.2f", x) %>% paste(collapse = ", ")
  })
  df
}

display_node <-
  list(
    ui = tags$div(
      # includeHTML("video-slider.html")
      includeHTML(system.file("video-slider.html", package = "psynetR", mustWork = TRUE))
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

null_ggplot <- function() ggplot() + theme(axis.line = element_blank())

display_responses <-
  list(
    ui = tags$div(
      plotOutput("plot_responses", height = "250px")
    ),
    server = list(
      null = function(output, ...) {
        output$plot_responses <- renderPlot(null_ggplot())
      },
      main = function(output, node_data, ...) {
        answers_for_seed <- node_data$answers_for_seed

        if (length(answers_for_seed) == 0) {
          p <- null_ggplot()
        } else {
          p <- tibble(x = answers_for_seed) %>%
            ggplot(aes(x)) +
            scale_x_continuous(limits = c(- SLIDER_RANGE, SLIDER_RANGE))

          has_kernel <- length(answers_for_seed) > 1

          if (has_kernel) {
            suppressWarnings(bw <- bw.bcv(answers_for_seed))
            p <- p + geom_density(bw = bw)
          }

          has_summarised_answer <- !is.null(node_data$generated_seed)
          if (has_summarised_answer) {
            summarised_answer <- node_data$generated_seed$vector[1 + node_data$definition$active_index]
            p <- p +
              geom_vline(xintercept = summarised_answer, linetype = "dashed", colour = "red") +
              geom_vline(xintercept = mean(summarised_answer), linetype = "dotted", colour = "blue")
          }

          ylim <- if (has_kernel) layer_scales(p)$y$range$range else c(0, 1)

          p <- p +
            geom_dotplot(binwidth = 2 * SLIDER_RANGE / 30) +
            scale_y_continuous("Density", limits = ylim)

        }

        output$plot_responses <- renderPlot(p)
      }
    )
  )

display_network_summary <- list(

  ui = tags$div(uiOutput("network_summary")),

  server = list(
    null = function(output, ...) {
      output$network_summary <- renderUI(tags$p())
    },

    main = function(output, network_id, network_data, ...) {
      output$network_summary <- renderUI({
        tags$div(
          style = "font-size: 20px;",
          tags$p("Network: ", tags$strong(network_id)),
          tags$p("Target: ", tags$strong(network_data$definition$target))
        )
      })
    }

  )
)

runApp(chain_app(data, display_node, display_responses, display_network_summary, format_node_df))
