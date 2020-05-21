unpack_json_col <- function(df, col, prefix = "") {
  new_cols <- purrr::map(df[[col]], ~ as_safe_tibble_row(jsonlite::fromJSON(.))) %>%
    bind_rows() %>%
    map(simplify_column) %>%
    as_tibble()
  names(new_cols) <- paste(prefix, names(new_cols), sep = "")
  df[[col]] <- NULL
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
  if (all(map_lgl(x, ~ length(.) %in% 0:1))) {
    for (i in seq_along(x)) {
      if (is.null(x[[i]])) x[[i]] <- NA
    }
    return(unlist(x))
  } else {
    return(x)
  }
}

get_node_answers <- function(node, trial) {
  node_df <- node %>% select(node_id = id)
  trial_df <- trial %>%
    transmute(trial_id = id,
              node_id = origin_id,
              answer = answer)
 inner_join(node_df, trial_df, by = "node_id") %>%
   group_by(node_id) %>%
   summarise(num_answers = length(answer),
             answers = list(answer))
}
