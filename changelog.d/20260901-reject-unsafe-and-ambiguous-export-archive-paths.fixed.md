Export archives now accept only exact ``database/<table>.csv`` or legacy
``data/<table>.csv`` members. Nested lookalikes, path traversal, duplicate
members, and mixed zip or extracted layouts are rejected. Downloaded zips are
streamed into the destination directory without allowing path traversal.
