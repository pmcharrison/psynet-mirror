Fixed post-commit ``/response`` render failures returning HTTP 503 busy, which could make a client retry look like a multi-tab conflict after ``page_uuid`` had already advanced.
