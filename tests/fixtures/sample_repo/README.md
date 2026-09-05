# sample_repo

A tiny, deterministic fixture repository used by Lumora's integration tests.

It is checked into git as ordinary files (never cloned at test time) so the
ingestion pipeline can be exercised end to end with no network access.
