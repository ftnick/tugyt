import os

import pytest

import ytget.ytget as app


@pytest.mark.integration
def test_configured_url_can_be_processed_without_download():
    url = os.getenv("YTGET_INTEGRATION_URL")
    if not url:
        pytest.skip("set YTGET_INTEGRATION_URL to run integration tests")

    assert app.execute(url, "--quiet", "--skip-download") == 0
