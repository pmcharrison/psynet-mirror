Participant navigation no longer loads module-state and barrier relationships
until the current request actually uses them, and loads experiment variables
with their configuration row instead of issuing a second query.
