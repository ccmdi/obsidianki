"""Test AnkiAPI functionality"""
import pytest
import requests
from unittest.mock import Mock, patch, MagicMock
from obsidianki.api.anki import AnkiAPI, ANKI_CUSTOM_MODEL_NAME


class TestAnkiAPIBasics:
    """Test basic AnkiAPI functionality"""

    def test_init_default_url(self):
        """Test AnkiAPI initialization with default URL"""
        anki = AnkiAPI()
        assert anki.url == "http://127.0.0.1:8765"
        assert anki.base_url == "http://127.0.0.1:8765"

    def test_init_custom_url(self):
        """Test AnkiAPI initialization with custom URL"""
        custom_url = "http://localhost:9999"
        anki = AnkiAPI(url=custom_url)
        assert anki.url == custom_url
        assert anki.base_url == custom_url


class TestAnkiAPIRequest:
    """Test _request method and error handling"""

    @patch('requests.post')
    def test_request_success(self, mock_post):
        """Test successful request"""
        mock_response = Mock()
        mock_response.json.return_value = {"result": ["Deck1", "Deck2"], "error": None}
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        anki = AnkiAPI()
        result = anki._request("deckNames")

        assert result == ["Deck1", "Deck2"]
        mock_post.assert_called_once()

    @patch('requests.post')
    def test_request_http_error(self, mock_post):
        """Test request with HTTP error"""
        mock_post.side_effect = requests.exceptions.HTTPError("Connection failed")

        anki = AnkiAPI()
        with pytest.raises(requests.exceptions.HTTPError):
            anki._request("deckNames")

    @patch('requests.post')
    def test_request_anki_error(self, mock_post):
        """Test request with AnkiConnect error"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "result": None,
            "error": "model was not found: NonExistent"
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        anki = AnkiAPI()
        with pytest.raises(Exception, match="AnkiConnect error"):
            anki._request("modelNames")

    @patch('requests.post')
    def test_request_duplicate_note_warning(self, mock_post, capsys):
        """Test that duplicate note errors are handled gracefully"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "result": None,
            "error": "cannot create note because it is a duplicate"
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        anki = AnkiAPI()
        result = anki._request("addNote", {"note": {}})

        # Should return empty list for duplicates
        assert result == []


class TestAnkiAPIDeckOperations:
    """Test deck-related operations"""

    @patch('requests.post')
    def test_ensure_deck_exists_already_exists(self, mock_post):
        """Test ensure_deck_exists when deck already exists"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "result": ["Default", "TestDeck"],
            "error": None
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        anki = AnkiAPI()
        anki.ensure_deck_exists("TestDeck")

        # Should only call deckNames
        assert mock_post.call_count == 1

    @patch('requests.post')
    def test_ensure_deck_exists_creates_new(self, mock_post):
        """Test ensure_deck_exists creates new deck"""
        responses = [
            # deckNames call
            {"result": ["Default"], "error": None},
            # addNote call
            {"result": 12345, "error": None},
            # findCards call
            {"result": [67890], "error": None},
            # changeDeck call
            {"result": None, "error": None},
            # deleteNotes call
            {"result": None, "error": None}
        ]

        mock_response = Mock()
        mock_response.json.side_effect = responses
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        anki = AnkiAPI()
        anki.ensure_deck_exists("NewDeck")

        # Should call multiple actions
        assert mock_post.call_count == 5


class TestAnkiAPICardOperations:
    """Test card-related operations"""

    @patch('requests.post')
    def test_add_flashcard(self, mock_post):
        """Test adding a single flashcard"""
        mock_response = Mock()
        mock_response.json.return_value = {"result": 12345, "error": None}
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        anki = AnkiAPI()
        note_id = anki._request("addNote", {
            "note": {
                "deckName": "Test",
                "modelName": "Basic",
                "fields": {"Front": "Q", "Back": "A"},
                "tags": ["test"]
            }
        })

        assert note_id == 12345

    @patch('requests.post')
    def test_find_cards(self, mock_post):
        """Test finding cards by query"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "result": [123, 456, 789],
            "error": None
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        anki = AnkiAPI()
        card_ids = anki._request("findCards", {"query": "deck:Test"})

        assert card_ids == [123, 456, 789]
        assert len(card_ids) == 3

    @patch('requests.post')
    def test_get_cards_info(self, mock_post):
        """Test getting card information"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "result": [
                {"cardId": 123, "fields": {"Front": {"value": "Q1"}}},
                {"cardId": 456, "fields": {"Front": {"value": "Q2"}}}
            ],
            "error": None
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        anki = AnkiAPI()
        cards = anki._request("cardsInfo", {"cards": [123, 456]})

        assert len(cards) == 2
        assert cards[0]["cardId"] == 123


class TestAnkiAPIModelOperations:
    """Test model-related operations"""

    @patch('requests.post')
    def test_get_model_names(self, mock_post):
        """Test getting model names"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "result": ["Basic", "Cloze", ANKI_CUSTOM_MODEL_NAME],
            "error": None
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        anki = AnkiAPI()
        models = anki._request("modelNames")

        assert "Basic" in models
        assert ANKI_CUSTOM_MODEL_NAME in models

    @patch('requests.post')
    def test_create_model(self, mock_post):
        """Test creating a new model"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "result": {"id": 123456789},
            "error": None
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        anki = AnkiAPI()
        result = anki._request("createModel", {
            "modelName": "CustomModel",
            "inOrderFields": ["Front", "Back"],
            "cardTemplates": []
        })

        assert result["id"] == 123456789


class TestAnkiAPIConnectionTest:
    """Test connection testing"""

    @patch('requests.post')
    def test_connection_success(self, mock_post):
        """Test successful connection"""
        mock_response = Mock()
        mock_response.json.return_value = {"result": 6, "error": None}
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        anki = AnkiAPI()
        # Simulate test_connection by checking version
        version = anki._request("version")
        assert version >= 6

    @patch('requests.post')
    def test_connection_failure(self, mock_post):
        """Test connection failure"""
        mock_post.side_effect = requests.exceptions.ConnectionError()

        anki = AnkiAPI()
        with pytest.raises(requests.exceptions.ConnectionError):
            anki._request("version")


class TestAnkiAPIEdgeCases:
    """Test edge cases and error conditions"""

    @patch('requests.post')
    def test_empty_deck_list(self, mock_post):
        """Test handling empty deck list"""
        mock_response = Mock()
        mock_response.json.return_value = {"result": [], "error": None}
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        anki = AnkiAPI()
        decks = anki._request("deckNames")
        assert decks == []

    @patch('requests.post')
    def test_null_result(self, mock_post):
        """Test handling null result"""
        mock_response = Mock()
        mock_response.json.return_value = {"result": None, "error": None}
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        anki = AnkiAPI()
        result = anki._request("someAction")
        assert result is None

    @patch('requests.post')
    def test_request_with_complex_params(self, mock_post):
        """Test request with complex nested parameters"""
        mock_response = Mock()
        mock_response.json.return_value = {"result": True, "error": None}
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        anki = AnkiAPI()
        result = anki._request("addNote", {
            "note": {
                "deckName": "Test::Subdeck",
                "modelName": "Basic",
                "fields": {
                    "Front": "Complex <b>HTML</b> content",
                    "Back": "Answer with\nmultiple\nlines"
                },
                "tags": ["tag1", "tag2", "tag3"],
                "options": {"allowDuplicate": False}
            }
        })

        assert result is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
