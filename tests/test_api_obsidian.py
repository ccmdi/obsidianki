"""Test ObsidianAPI functionality"""
import pytest
import os
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from obsidianki.api.obsidian import ObsidianAPI
from obsidianki.cli.models import Note


class TestObsidianAPIInit:
    """Test ObsidianAPI initialization"""

    def test_init_with_api_key(self):
        """Test initialization with valid API key"""
        with patch.dict(os.environ, {'OBSIDIAN_API_KEY': 'test_key'}):
            api = ObsidianAPI()
            assert api.api_key == 'test_key'
            assert api.base_url == "https://127.0.0.1:27124"
            assert 'Authorization' in api.headers

    def test_init_without_api_key(self):
        """Test initialization fails without API key"""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="OBSIDIAN_API_KEY not found"):
                ObsidianAPI()


class TestObsidianAPIJsonLogicFilters:
    """Test JsonLogic filter building"""

    @patch('obsidianki.cli.config.CONFIG', None)
    def test_build_folder_filter_none(self):
        """Test building folder filter with no folders"""
        with patch.dict(os.environ, {'OBSIDIAN_API_KEY': 'test'}):
            api = ObsidianAPI()
            result = api._build_folder_filter(None)
            assert result is None

    @patch('obsidianki.cli.config.CONFIG', None)
    def test_build_folder_filter_empty(self):
        """Test building folder filter with empty list"""
        with patch.dict(os.environ, {'OBSIDIAN_API_KEY': 'test'}):
            api = ObsidianAPI()
            result = api._build_folder_filter([])
            assert result is None

    @patch('obsidianki.cli.config.CONFIG', None)
    def test_build_folder_filter_single(self):
        """Test building folder filter with single folder"""
        with patch.dict(os.environ, {'OBSIDIAN_API_KEY': 'test'}):
            api = ObsidianAPI()
            result = api._build_folder_filter(['folder1'])
            assert result == {"glob": ["folder1/*", {"var": "path"}]}

    @patch('obsidianki.cli.config.CONFIG', None)
    def test_build_folder_filter_multiple(self):
        """Test building folder filter with multiple folders"""
        with patch.dict(os.environ, {'OBSIDIAN_API_KEY': 'test'}):
            api = ObsidianAPI()
            result = api._build_folder_filter(['folder1', 'folder2'])
            assert "or" in result
            assert len(result["or"]) == 2

    @patch('obsidianki.cli.config.CONFIG')
    def test_build_excluded_tags_filter(self, mock_config):
        """Test building excluded tags filter"""
        with patch.dict(os.environ, {'OBSIDIAN_API_KEY': 'test'}):
            mock_config.excluded_tags = ['private', 'draft']
            api = ObsidianAPI()
            result = api._build_excluded_tags_filter()
            assert "and" in result
            assert len(result["and"]) == 2

    @patch('obsidianki.cli.config.CONFIG')
    def test_build_excluded_tags_filter_empty(self, mock_config):
        """Test building excluded tags filter with no excluded tags"""
        with patch.dict(os.environ, {'OBSIDIAN_API_KEY': 'test'}):
            mock_config.excluded_tags = []
            api = ObsidianAPI()
            result = api._build_excluded_tags_filter()
            assert result is None

    @patch('obsidianki.cli.config.CONFIG', None)
    def test_combine_filters_empty(self):
        """Test combining filters with no conditions"""
        with patch.dict(os.environ, {'OBSIDIAN_API_KEY': 'test'}):
            api = ObsidianAPI()
            result = api._combine_filters()
            # Should return query that matches all (returns full object)
            assert result == {"var": ""}

    @patch('obsidianki.cli.config.CONFIG', None)
    def test_combine_filters_single(self):
        """Test combining single filter"""
        with patch.dict(os.environ, {'OBSIDIAN_API_KEY': 'test'}):
            api = ObsidianAPI()
            condition = {">": [{"var": "stat.size"}, 100]}
            result = api._combine_filters(condition)
            # Should wrap in if statement
            assert "if" in result
            assert result["if"][0] == condition

    @patch('obsidianki.cli.config.CONFIG', None)
    def test_combine_filters_multiple(self):
        """Test combining multiple filters"""
        with patch.dict(os.environ, {'OBSIDIAN_API_KEY': 'test'}):
            api = ObsidianAPI()
            cond1 = {">": [{"var": "stat.size"}, 100]}
            cond2 = {"<": [{"var": "stat.mtime"}, 1234567890]}
            result = api._combine_filters(cond1, cond2)
            # Should wrap in if with and
            assert "if" in result
            assert "and" in result["if"][0]


class TestObsidianAPISearch:
    """Test JsonLogic search"""

    @patch('obsidianki.api.obsidian.BaseAPI._make_request')
    def test_search_success(self, mock_request):
        """Test successful JsonLogic search"""
        with patch.dict(os.environ, {'OBSIDIAN_API_KEY': 'test'}):
            mock_response = Mock()
            mock_request.return_value = mock_response

            api = ObsidianAPI()

            with patch.object(api, '_parse_response') as mock_parse:
                mock_parse.return_value = [
                    {
                        "filename": "path/note1.md",
                        "result": {
                            "path": "path/note1.md",
                            "basename": "note1",
                            "stat": {"mtime": 1234567890, "size": 100},
                            "tags": ["tag1"]
                        }
                    }
                ]

                results = api.search({">": [{"var": "stat.size"}, 50]})
                assert len(results) == 1
                assert isinstance(results[0], Note)


class TestObsidianAPIGetOldNotes:
    """Test getting old notes"""

    @patch.object(ObsidianAPI, 'search')
    @patch('obsidianki.cli.config.CONFIG')
    def test_get_old_notes_basic(self, mock_config, mock_search):
        """Test getting old notes with basic parameters"""
        with patch.dict(os.environ, {'OBSIDIAN_API_KEY': 'test'}):
            mock_config.search_folders = []
            mock_config.excluded_tags = []
            mock_search.return_value = [
                Note(path="old.md", filename="Old", content="test", tags=[], size=100)
            ]

            api = ObsidianAPI()
            notes = api.get_old_notes(days=7, limit=10)

            assert len(notes) == 1
            mock_search.assert_called_once()

    @patch.object(ObsidianAPI, 'search')
    @patch('obsidianki.cli.config.CONFIG')
    def test_get_old_notes_with_limit(self, mock_config, mock_search):
        """Test getting old notes respects limit"""
        with patch.dict(os.environ, {'OBSIDIAN_API_KEY': 'test'}):
            mock_config.search_folders = []
            mock_config.excluded_tags = []
            mock_search.return_value = [
                Note(path=f"note{i}.md", filename=f"Note{i}", content="", tags=[], size=100)
                for i in range(20)
            ]

            api = ObsidianAPI()
            notes = api.get_old_notes(days=30, limit=5)

            assert len(notes) == 5


class TestObsidianAPIGetTaggedNotes:
    """Test getting tagged notes"""

    @patch.object(ObsidianAPI, 'search')
    @patch('obsidianki.cli.config.CONFIG')
    def test_get_tagged_notes_single_tag(self, mock_config, mock_search):
        """Test getting notes with single tag"""
        with patch.dict(os.environ, {'OBSIDIAN_API_KEY': 'test'}):
            mock_config.search_folders = []
            mock_config.excluded_tags = []
            mock_search.return_value = [
                Note(path="tagged.md", filename="Tagged", content="test",
                     tags=["important"], size=100)
            ]

            api = ObsidianAPI()
            notes = api.get_tagged_notes(["important"])

            assert len(notes) == 1
            mock_search.assert_called_once()

    @patch.object(ObsidianAPI, 'search')
    @patch('obsidianki.cli.config.CONFIG')
    def test_get_tagged_notes_multiple_tags(self, mock_config, mock_search):
        """Test getting notes with multiple tags"""
        with patch.dict(os.environ, {'OBSIDIAN_API_KEY': 'test'}):
            mock_config.search_folders = []
            mock_config.excluded_tags = []
            mock_search.return_value = []

            api = ObsidianAPI()
            api.get_tagged_notes(["tag1", "tag2", "tag3"])

            mock_search.assert_called_once()
            # Verify the query contains an 'or' for multiple tags
            call_args = mock_search.call_args[0][0]
            assert "if" in call_args


class TestObsidianAPIEdgeCases:
    """Test edge cases"""

    @patch.object(ObsidianAPI, 'search')
    @patch('obsidianki.cli.config.CONFIG')
    def test_get_old_notes_empty_result(self, mock_config, mock_search):
        """Test getting old notes with empty result"""
        with patch.dict(os.environ, {'OBSIDIAN_API_KEY': 'test'}):
            mock_config.search_folders = []
            mock_config.excluded_tags = []
            mock_search.return_value = []

            api = ObsidianAPI()
            notes = api.get_old_notes(days=365)

            assert notes == []
            assert len(notes) == 0

    @patch.object(ObsidianAPI, 'search')
    @patch('obsidianki.cli.config.CONFIG')
    def test_get_tagged_notes_empty_tags(self, mock_config, mock_search):
        """Test getting notes with empty tags list"""
        with patch.dict(os.environ, {'OBSIDIAN_API_KEY': 'test'}):
            mock_config.search_folders = []
            mock_config.excluded_tags = []
            mock_search.return_value = []

            api = ObsidianAPI()
            notes = api.get_tagged_notes([])

            mock_search.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
