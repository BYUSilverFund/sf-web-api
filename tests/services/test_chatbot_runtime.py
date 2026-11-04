import pytest

from app.services import chatbot


def test_bedrock_client_uses_configured_timeouts_and_standard_retries(
    monkeypatch, mocker
):
    monkeypatch.setenv("AWS_REGION", "us-west-2")
    monkeypatch.setattr(chatbot, "BEDROCK_CONNECT_TIMEOUT_SECONDS", 7)
    monkeypatch.setattr(chatbot, "BEDROCK_READ_TIMEOUT_SECONDS", 90)
    boto_client = mocker.patch.object(
        chatbot.boto3, "client", return_value=mocker.sentinel.client
    )

    assert chatbot._bedrock_client() is mocker.sentinel.client
    _, kwargs = boto_client.call_args
    assert kwargs["region_name"] == "us-west-2"
    assert kwargs["config"].connect_timeout == 7
    assert kwargs["config"].read_timeout == 90
    assert kwargs["config"].retries == {"max_attempts": 2, "mode": "standard"}


@pytest.mark.parametrize("value", ["0", "1201", "not-a-number"])
def test_bedrock_output_token_limit_rejects_invalid_values(monkeypatch, value):
    monkeypatch.setenv("BEDROCK_MAX_OUTPUT_TOKENS", value)

    with pytest.raises((RuntimeError, ValueError)):
        chatbot._bounded_positive_int_env("BEDROCK_MAX_OUTPUT_TOKENS", 1200, 1200)
