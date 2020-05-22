unpack_json_col <- function(df, col, prefix = "", keep_original = FALSE) {
  df[[col]] <- map(df[[col]], jsonlite::fromJSON)
  unpack_list_col(df, col, prefix, keep_original)
}

unpack_list_col <- function(df, col, prefix = "", keep_original = FALSE) {
  new_cols <-
    map(df[[col]], as_safe_tibble_row) %>%
    bind_rows() %>%
    simplify_columns()
  names(new_cols) <- paste(prefix, names(new_cols), sep = "") %>% gsub("^_*", "", .)
  if (!keep_original) df[[col]] <- NULL
  bind_cols(df, new_cols)
}

simplify_columns <- function(df) {
  df %>%
    map(simplify_column) %>%
    as_tibble()
}
as_safe_tibble_row <- function(x) {
  map(x, list) %>%
    as_tibble_row()
}

label_properties <- function(df, spec) {
  properties_to_keep <- names(spec)
  properties_to_discard <- setdiff(paste("property", 1:5, sep = ""), names(spec))
  cols_to_keep <- setdiff(names(df), properties_to_discard)
  df <- df[cols_to_keep]
  for (i in seq_along(spec)) {
    original_name <- names(spec)[i]
    field_definition <- spec[[i]]
    df[[original_name]] <- field_definition$coerce(df[[original_name]])
    names(df) <- plyr::mapvalues(names(df), from = original_name, to = field_definition$name)
  }
  df
}

simplify_column <- function(x) {
  if (length(x) > 0 && all(map_lgl(x, ~ is.list(.) && !is.null(names(.))))) {
    return(x)
  }
  if (all(map_lgl(x, ~ length(.) %in% 0:1))) {
    for (i in seq_along(x)) {
      if (length(x[[i]]) == 0) x[[i]] <- NA
    }
    return(unlist(x, recursive = FALSE))
  }
  return(x)
}

warning("summarise_node_answers is currently a bit of a hack. PsyNet should be updated for ",
        "future experiments such that the trials used for seed generation ",
        "are stored explicitly.")

get_node_metadata <- function(trial, node, network) {
  node_df <- node %>%
    select(node_id, network_id, child_id) %>%
    left_join(node %>% select(child_id = node_id, child_creation_time = creation_time, child_seed = seed),
              by = "child_id")

  network_df <-
    network %>%
    select(network_id, phase, definition) %>%
    unpack_list_col("definition", prefix = "network_")

  trial_df <-
    trial %>%
    select(trial_id,
           node_id,
           answer,
           is_repeat_trial,
           trial_failed = failed,
           trial_time_of_death = time_of_death,
           trial_response_time = response_time)

  summarise_node_answers <- function(df) {
    node_id <- unique(df$node_id)
    child_id <- unique(df$child_id)
    stopifnot(length(node_id) == 1, length(child_id) == 1)
    if (is.na(child_id)) {
      answers_for_seed <- NULL
    } else {
      answers_for_seed <-
        df %>%
        filter(!is_repeat_trial &
                 trial_response_time <= child_creation_time &
                 (!trial_failed | trial_time_of_death > child_creation_time)) %>%
        pull(answer)
    }
    list(
      node_id = node_id,
      answers_for_seed = answers_for_seed,
      num_answers_for_seed = length(answers_for_seed)
    ) %>% as_safe_tibble_row()
  }

  answers_df <-
    node_df %>%
    inner_join(trial_df, by = "node_id") %>%
    group_by(node_id) %>%
    group_split() %>%
    map(summarise_node_answers) %>%
    bind_rows() %>%
    simplify_columns()

  stopifnot(!anyDuplicated(answers_df$node_id))

  node_df %>%
    left_join(network_df, by = "network_id") %>%
    left_join(answers_df, by = "node_id") %>%
    select(- network_id) %>%
    mutate(num_answers_for_seed = if_else(is.na(num_answers_for_seed),
                                          0L,
                                          num_answers_for_seed),
           answers_for_seed = map2(num_answers_for_seed,
                                   answers_for_seed,
                                   function(n, answers) if (n == 0) NULL else answers))
}

get_trial_metadata <- function(trial, node, network) {
  trial_df <- trial %>% select(trial_id, network_id, node_id)

  node_df <-
    node %>%
    select(node_id, phase, degree, definition) %>%
    unpack_list_col("definition", prefix = "node_")

  network_df <-
    network %>%
    select(network_id, definition) %>%
    unpack_list_col("definition", prefix = "network_")

  trial_df %>%
    left_join(node_df, by = "node_id") %>%
    left_join(network_df, by = "network_id") %>%
    select(- c(network_id, node_id))
}

add_response <- function(trial, response) {
  trial %>%
    left_join(response %>% select(response_id = id, response_time = creation_time),
              by = "response_id")
}
