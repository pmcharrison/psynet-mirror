chain_app <- function(data,
                      display_trial,
                      display_responses) {
  shinyApp(chain_app_ui(display_trial,
                        display_responses),
           chain_app_server(data,
                            display_trial,
                            display_responses))
}

chain_app_ui <- function(display_trial,
                         display_responses) {
  fluidPage(
    theme = shinythemes::shinytheme("cerulean"),
    fluidRow(
      column(6, chain_app_select_trial_ui()),
      column(6, chain_app_display_trial_and_responses_ui(display_trial,
                                                         display_responses))
    ))
}

chain_app_select_trial_ui <- function() {
  div(
    h2("Select chain"),
    DT::dataTableOutput("dt_select_chain"),

    h2("Select trial"),
    DT::dataTableOutput("dt_select_trial")
  )
}

chain_app_display_trial_and_responses_ui <- function(display_trial,
                                                     display_responses) {
  div(
    h2("Trial"),
    display_trial$ui,

    h2("Responses"),
    display_responses$ui
  )
}

chain_app_server <- function(data, display_trial, display_responses) {
  function(input, output) {
    browser()
    data$network %>%
      arrange(network_id) %>%
      select(network_id,
             phase,
             full,
             definition,
             starts_with("n_")) %>%
      unpack_list_col("definition") %>%
      View()

    data
    browser()
    # output$dt_select_chain <-
  }
}
