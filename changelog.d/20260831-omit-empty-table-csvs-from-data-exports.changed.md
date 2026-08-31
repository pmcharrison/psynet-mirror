Data exports no longer include empty table CSVs. An experiment that never used
chat, Lucid, or barriers therefore no longer has header-only files such as
`chat_message.csv` in `database/`. `manifest.json` still lists every table under
`table_row_counts`, with a count of `0` for the omitted files.
