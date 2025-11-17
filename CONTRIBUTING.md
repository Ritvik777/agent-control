# Contributing to Agent Protect

Thanks for contributing! This document captures the conventions we expect from all contributors (humans and AI tools) to keep the repository consistent and easy to maintain.

## Testing conventions

- Write tests using Given/When/Then comments with colons. Use this exact casing and punctuation.
  - Required markers in every test function:
    - `# Given:` to describe preconditions/setup
    - `# When:` to describe the action under test
    - `# Then:` to describe the expected outcomes/assertions
- Keep tests small and focused. Prefer clear, explicit setup over hidden fixtures unless necessary.

Example (pytest):

```python
from fastapi.testclient import TestClient


def test_example(client: TestClient) -> None:
    # Given: a valid payload
    payload = {"x": 1}

    # When: submitting the request
    resp = client.post("/example", json=payload)

    # Then: the response is successful and matches expectations
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
```
