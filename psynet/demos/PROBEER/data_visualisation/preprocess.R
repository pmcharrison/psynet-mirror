# Title     : TODO
# Objective : TODO
# Created by: pol.van-rijn
# Created on: 04.05.20
df = read.csv('psynet/demos/PROBEER/data_visualisation/sample_data.csv', sep = ";")
c = 0
full_df = NULL
for (r in as.character(df$contents)) {
  c = c + 1
  row = jsonlite::fromJSON(r)
  if ("vector" %in% names(row)) {
    row$network_id = df$network_id[c]
    row$type = df$type[c]
    row$id = df$id[c]
    pp = 0
    for (i in row$vector) {
      pp = pp + 1
      row[paste0("p", pp)] = i
    }
    row[['vector']] = NULL
    full_df = rbind(full_df, data.frame(row))
  }
}
library(dplyr)
new_df = NULL
for (net_id in as.numeric((unique(full_df$network_id)))) {
  filt_df = filter(full_df, network_id == net_id)
  if (nrow(filt_df) > 1) {
    p_matrix = as.matrix(filt_df[, 6:10])

    num_rows = nrow(filt_df)

    initialized = c()
    changed = c()

    for (i in 1:(num_rows - 1)) {
      bool_idx = abs(p_matrix[i,] - p_matrix[i + 1,]) > 0
      if (length(which(bool_idx)) != 2) {
        stop('This may not happen')
      }
      selected_vals = p_matrix[i + 1, bool_idx]
      changed = c(changed, selected_vals[[1]])
      initialized = c(initialized, selected_vals[[2]])
    }

    changed_row = c()
    for (i in 1:num_rows) {
      changed_row = c(changed_row, paste0("p", 1 + filt_df[i, 'active_index']))
    }

    col_idx = filt_df[1, "active_index"] + 1
    filt_df$initialized = c(p_matrix[1, col_idx], initialized)
    filt_df$changed = c(changed, 0)
    filt_df$changed_row = changed_row
    new_df = rbind(new_df, filt_df)
  }
}

write.csv(new_df, 'psynet/demos/PROBEER/data_visualisation/preprocessed_data.csv', row.names = F)
