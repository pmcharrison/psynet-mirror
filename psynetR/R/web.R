chain_app <- function(data,
                      display_node,
                      display_responses,
                      display_network_summary,
                      format_node_df) {
  display <- list(
    node = display_node,
    responses = display_responses,
    network_summary = display_network_summary
  )
  shinyApp(chain_app_ui(display),
           chain_app_server(data, display, format_node_df))
}

chain_app_ui <- function(display) {
  navbarPage(
    "Chain visualisation",
    theme = shinythemes::shinytheme("cerulean"),
    tabPanel(
      "Select chain",
      DT::dataTableOutput("dt_select_chain"),
      tags$em("Select a chain to visualise, then click 'Select node' to explore this chain.")
    ),
    tabPanel(
      "Select node",
      chain_app_select_node_ui(display)
    ),
    useShinyjs()
  )
}

chain_app_select_node_ui <- function(display) {
  fluidRow(
    column(
      6,
      h2("Network"),
      display$network_summary$ui,

      h2("Select node"),
      DT::dataTableOutput("dt_select_node")
    ),
    column(
      6,

      h2("Node"),
      display$node$ui,

      h2("Responses"),
      display$responses$ui
  ))
}

chain_app_server <- function(data, display, format_node_df) {
  function(input, output, session, ...) {
    state <- reactiveValues(
      network_table = NULL,
      network_id = NULL,
      node_table = NULL,
      node_id = NULL
    )

    observe({
      state$network_table <-
        data$network %>%
        arrange(network_id) %>%
        select(network_id,
               phase,
               full,
               definition,
               starts_with("n_")) %>%
        unpack_list_col("definition")
    })

    output$dt_select_chain <- DT::renderDataTable({
        DT::datatable(state$network_table,
                      selection = "single",
                      extensions = c("FixedColumns"),
                      rownames = FALSE,
                      options = list(paging = FALSE,
                                     scrollX = TRUE,
                                     scrollY = 300,
                                     scrollCollapse = TRUE,
                                     fixedColumns = list(
                                       leftColumns = 1
                                     )))
    })

    observe({
      if (is.null(state$network_table)) {
        state$network_id <- NULL
      } else if (length(input$dt_select_chain_rows_selected) != 1) {
        state$network_id <- NULL
      } else {
        state$network_id <- state$network_table %>%
          slice(input$dt_select_chain_rows_selected) %>%
          pull(network_id)
        showNotification(glue("Selected network {state$network_id}."))
      }
    })

    observe({
      if (is.null(state$node_table)) {
        state$node_id <- NULL
      } else if (length(input$dt_select_node_rows_selected) != 1) {
        state$node_id <- NULL
      } else {
        state$node_id <-
          state$node_table %>%
          slice(input$dt_select_node_rows_selected) %>%
          pull(node_id)
        showNotification(glue("Selected node {state$node_id}."))
      }
    })

    observe({
      state$node_table <-
        if (is.null(state$network_id)) {
          NULL
        } else {
          data$node %>%
            filter(network_id == !!state$network_id) %>%
            arrange(node_id) %>%
            select(degree,
                   node_id,
                   definition,
                   n_answers_for_seed) %>%
            unpack_list_col("definition") %>%
            format_node_df()
        }
    })

    output$dt_select_node <- DT::renderDataTable({
      state$node_table %>%
        DT::datatable(
          selection = "single",
          extensions = c("FixedColumns"),
          rownames = FALSE,
          options = list(paging = FALSE,
                         scrollX = TRUE,
                         scrollY = 300,
                         scrollCollapse = TRUE,
                         fixedColumns = list(
                           leftColumns = 1
                         )))
    })

    observe({
      if (is.null(state$node_id)) {
        display$node$server$null(output = output)
      } else {
        display$node$server$main(input = input,
                                 output = output,
                                 session = session,
                                 data = data,
                                 node_id = state$node_id,
                                 node_data = data$node %>% filter(node_id == !!state$node_id) %>% row_to_list())
      }
    })

    observe({
      if (is.null(state$node_id)) {
        display$responses$server$null(output = output)
      } else {
        node_id <- state$node_id
        node_data <- data$node %>% filter(node_id == !!state$node_id) %>% row_to_list()
        display$responses$server$main(
          input = input,
          output = output,
          session = session,
          data = data,
          node_id = node_id,
          node_data = node_data
        )
      }
    })

    observe({
      if (is.null(state$network_id)) {
        display$network_summary$server$null(output = output)
      } else {
        network_id <- state$network_id
        network_data <- data$network %>% filter(network_id == !!state$network_id) %>% row_to_list()
        display$network_summary$server$main(
          input = input,
          output = output,
          session = session,
          data = data,
          network_id = network_id,
          network_data = network_data
        )
      }
    })

  }
}
