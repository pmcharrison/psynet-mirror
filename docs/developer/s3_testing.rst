S3 testing strategies
=====================

PsyNet has several ways to test code that normally talks to S3. Choose the
smallest strategy that exercises the behavior you need.

Filesystem-backed mock in the current process
---------------------------------------------

Use ``artifact_storage_s3_test_root`` when the code under test runs in the same
pytest process. This fixture monkeypatches PsyNet's S3 helper functions to use
the lightweight filesystem-backed mock in ``psynet.test_helpers.mock_s3``.

This strategy is fast and isolated. It is appropriate for unit and integration
tests that need S3-style upload, listing, metadata, download, copy, delete, or
export behavior.

Filesystem-backed mock in subprocesses
--------------------------------------

Use ``subprocess_mock_s3_root`` when the code under test starts a child process,
for example via ``psynet prepare``. This fixture sets ``PSYNET_MOCK_S3_ROOT``,
which makes PsyNet's S3 helper functions construct filesystem-backed mock S3
clients inside subprocesses too.

Tests using this strategy should assert durable evidence that the mock was used,
for example that files were written under ``subprocess_mock_s3_root``.

Limitations of the filesystem-backed mock
-----------------------------------------

The filesystem-backed mock does not provide a public HTTP endpoint. It can
verify storage operations and exports, but it cannot verify that generated
``https://s3.amazonaws.com/...`` URLs are reachable by browsers or other HTTP
clients.

If a test needs to prove public URL reachability, use a more realistic HTTP
emulator or a carefully isolated real-S3 integration test.

S3-compatible HTTP endpoints
----------------------------

Set ``PSYNET_S3_ENDPOINT_URL`` to route boto3 clients and AWS CLI transfer
commands to an S3-compatible endpoint such as Moto, LocalStack, or MinIO.
This is useful when a test needs a service process rather than an in-memory or
filesystem-only mock.

Note that this setting changes the S3 API endpoint used for storage operations.
It does not by itself change PsyNet's generated public S3 URLs, which may still
use the canonical ``https://s3.amazonaws.com/...`` form. Do not rely on this
strategy alone for browser-level public URL tests unless URL generation and HTTP
serving are also configured for the emulator.

Real S3 integration tests
-------------------------

Real S3 should be rare in automated tests. If it is necessary, use a unique
bucket prefix per test run, avoid deleting shared prefixes, and clean up only the
objects created by that test. Shared real-S3 prefixes can cause flakes when CI
pipelines run concurrently.
