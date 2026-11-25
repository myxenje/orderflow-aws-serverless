from unittest.mock import patch
from src.functions.coletor.handler import lambda_handler


@patch("src.functions.coletor.handler.publish_pending_events")
def test_lambda_handler_success(mock_publish):
    mock_publish.return_value = 5

    response = lambda_handler({}, None)

    assert response["statusCode"] == 200
    assert response["body"]["published_count"] == 5
    mock_publish.assert_called_once()


@patch("src.functions.coletor.handler.publish_pending_events")
def test_lambda_handler_error(mock_publish):
    mock_publish.side_effect = Exception("Erro de publicação")

    try:
        lambda_handler({}, None)
        assert False, "Era esperado que a exceção fosse propagada."
    except Exception as error:
        assert str(error) == "Erro de publicação"

    mock_publish.assert_called_once()