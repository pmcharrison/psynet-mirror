chain_app <- function(data,
                      display_node,
                      display_responses) {
  shinyApp(chain_app_ui(display_node,
                        display_responses),
           chain_app_server(data,
                            display_node,
                            display_responses))
}

chain_app_ui <- function(display_node,
                         display_responses) {
  navbarPage(
    "Chain visualisation",
    theme = shinythemes::shinytheme("cerulean"),
    tabPanel(
      "Select chain",
      DT::dataTableOutput("dt_select_chain")
    ),
    tabPanel(
      "Select node",
      chain_app_select_node_ui(display_node,
                               display_responses)
    )
  )
}

chain_app_select_node_ui <- function(display_node,
                                     display_responses) {
  fluidRow(
    column(
      6,
      h2("Select node"),
      DT::dataTableOutput("dt_select_node")
    ),
    column(
      6,

      h2("Node"),
      display_node$ui,

      h2("Responses"),
      display_responses$ui
  ))
}

chain_app_server <- function(data, display_node, display_responses) {
  function(input, output) {
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
                      selection = "single")
    })

    observe({
      state$network_id <-
        if (is.null(state$network_table)) {
          NULL
        } else if (length(input$dt_select_chain_rows_selected) != 1) {
          NULL
        } else {
          state$network_table %>%
            slice(input$dt_select_chain_rows_selected) %>%
            pull(network_id)
        }
      showNotification(glue("Selected network {state$network_id}."))
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
                   n_answers_for_seed)%>%
            unpack_list_col("definition")
        }
    })

    output$dt_select_node <- DT::renderDataTable({
      DT::datatable(state$node_table,
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

  }
}
