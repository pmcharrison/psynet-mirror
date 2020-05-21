unpack_json_col <- function(df, col, prefix = "") {
  df[[col]] <- map(df[[col]], jsonlite::fromJSON)
  unpack_list_col(df, col, prefix)
}

unpack_list_col <- function(df, col, prefix = "", keep_original = FALSE) {
  new_cols <-
    map(df[[col]], as_safe_tibble_row) %>%
    bind_rows() %>%
    map(simplify_column) %>%
    as_tibble()
  names(new_cols) <- paste(prefix, names(new_cols), sep = "") %>% gsub("^_", "", .)
  if (!keep_original) df[[col]] <- NULL
  bind_cols(df, new_cols)
}

as_safe_tibble_row <- function(x) {
  map(x, list) %>%
    as_tibble_row()
}

label_properties <- function(df, spec) {
  missing_properties <- setdiff(paste("property", 1:5, sep = ""), names(spec))
  cols_to_keep <- setdiff(names(df), missing_properties)
  df <- df[cols_to_keep]
  names(df) <- plyr::mapvalues(names(df), from = names(spec), to = spec)
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

get_node_metadata <- function(trial, node, network) {
  node_df <- node %>% select(node_id, network_id)

  trial_df <-
    trial %>%
    filter(!is_repeat_trial) %>%
    transmute(node_id = origin_id, answer = answer)

  network_df <-
    network %>%
    select(network_id, phase, definition) %>%
    unpack_list_col("definition", prefix = "network_")

  answers_df <-
    node_df %>%
    inner_join(trial_df, by = "node_id") %>%
    group_by(node_id) %>%
    summarise(num_answers_excl_repeats = length(answer),
              answers_excl_repeats = list(answer))

  stopifnot(!anyDuplicated(answers_df$node_id))

  node_df %>%
    inner_join(network_df, by = "network_id") %>%
    inner_join(answers_df, by = "node_id")
}

get_trial_metadata <- function(trial, node, network) {
  trial_df <- trial %>% select(trial_id, network_id, node_id = origin_id)

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
    left_join(network_df, by = "network_id")
}
