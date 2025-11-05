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


class TestObsidianAPIBuildFilters:
    """Test filter building"""

    def test_build_filters_no_filters(self):
        """Test building filters with no conditions"""
        with patch.dict(os.environ, {'OBSIDIAN_API_KEY': 'test'}):
            api = ObsidianAPI()
            result = api._build_filters(None)
            assert result == ""

    def test_build_filters_with_folders(self):
        """Test building filters with search folders"""
        with patch.dict(os.environ, {'OBSIDIAN_API_KEY': 'test'}):
            api = ObsidianAPI()
            result = api._build_filters(['folder1', 'folder2'])
            assert 'startswith(file.path, "folder1/")' in result
            assert 'startswith(file.path, "folder2/")' in result
            assert ' OR ' in result

    @patch('obsidianki.api.obsidian.CONFIG')
    def test_build_filters_with_excluded_tags(self, mock_config):
        """Test building filters with excluded tags"""
        with patch.dict(os.environ, {'OBSIDIAN_API_KEY': 'test'}):
            mock_config.excluded_tags = ['private', 'draft']
            api = ObsidianAPI()
            result = api._build_filters(None)
            assert '!contains(file.tags, "private")' in result
            assert '!contains(file.tags, "draft")' in result


class TestObsidianAPIBuildQuery:
    """Test DQL query building"""

    def test_build_base_query_default(self):
        """Test building base query with defaults"""
        with patch.dict(os.environ, {'OBSIDIAN_API_KEY': 'test'}):
            api = ObsidianAPI()
            query = api._build_base_query()
            assert 'TABLE' in query
            assert 'file.name' in query
            assert 'file.path' in query
            assert 'file.mtime' in query
            assert 'SORT file.mtime ASC' in query

    def test_build_base_query_custom_sort(self):
        """Test building query with custom sort"""
        with patch.dict(os.environ, {'OBSIDIAN_API_KEY': 'test'}):
            api = ObsidianAPI()
            query = api._build_base_query(
                extra_conditions='file.size > 100',
                sort_field='file.name',
                sort_order='DESC'
            )
            assert 'file.size > 100' in query
            assert 'SORT file.name DESC' in query


class TestObsidianAPIDQL:
    """Test DQL query execution"""

    @patch('obsidianki.api.obsidian.BaseAPI._make_request')
    def test_dql_success(self, mock_request):
        """Test successful DQL query"""
        with patch.dict(os.environ, {'OBSIDIAN_API_KEY': 'test'}):
            mock_response = Mock()
            mock_response.json.return_value = {
                "data": {
                    "values": [
                        ["Note 1", "path/note1.md", "2024-01-01", 100, ["tag1"]],
                        ["Note 2", "path/note2.md", "2024-01-02", 200, ["tag2"]]
                    ]
                }
            }
            mock_request.return_value = mock_response

            api = ObsidianAPI()

            # Mock the _parse_response to return list of dicts
            with patch.object(api, '_parse_response') as mock_parse:
                mock_parse.return_value = [
                    {
                        "filename": "Note 1",
                        "path": "path/note1.md",
                        "mtime": "2024-01-01",
                        "size": 100,
                        "tags": ["tag1"]
                    }
                ]

                results = api.dql("LIST FROM #test")
                assert len(results) == 1
                assert isinstance(results[0], Note)

    @patch('obsidianki.api.obsidian.BaseAPI._make_request')
    def test_dql_failure(self, mock_request):
        """Test DQL query failure"""
        with patch.dict(os.environ, {'OBSIDIAN_API_KEY': 'test'}):
            mock_request.side_effect = Exception("Connection failed")

            api = ObsidianAPI()
            with pytest.raises(Exception):
                api.dql("INVALID QUERY")


class TestObsidianAPIGetOldNotes:
    """Test getting old notes"""

    @patch.object(ObsidianAPI, 'dql')
    @patch('obsidianki.api.obsidian.CONFIG')
    def test_get_old_notes_basic(self, mock_config, mock_dql):
        """Test getting old notes with basic parameters"""
        with patch.dict(os.environ, {'OBSIDIAN_API_KEY': 'test'}):
            mock_config.search_folders = []
            mock_dql.return_value = [
                Note(path="old.md", filename="Old", content="test", tags=[], size=100)
            ]

            api = ObsidianAPI()
            notes = api.get_old_notes(days=7, limit=10)

            assert len(notes) == 1
            mock_dql.assert_called_once()

            # Check the query contains date filter
            call_args = mock_dql.call_args[0][0]
            assert 'file.mtime <' in call_args
            assert 'LIMIT 10' in call_args

    @patch.object(ObsidianAPI, 'dql')
    @patch('obsidianki.api.obsidian.CONFIG')
    def test_get_old_notes_no_limit(self, mock_config, mock_dql):
        """Test getting old notes without limit"""
        with patch.dict(os.environ, {'OBSIDIAN_API_KEY': 'test'}):
            mock_config.search_folders = []
            mock_dql.return_value = []

            api = ObsidianAPI()
            api.get_old_notes(days=30, limit=0)

            call_args = mock_dql.call_args[0][0]
            assert 'LIMIT' not in call_args


class TestObsidianAPIGetTaggedNotes:
    """Test getting tagged notes"""

    @patch.object(ObsidianAPI, 'dql')
    @patch('obsidianki.api.obsidian.CONFIG')
    def test_get_tagged_notes_single_tag(self, mock_config, mock_dql):
        """Test getting notes with single tag"""
        with patch.dict(os.environ, {'OBSIDIAN_API_KEY': 'test'}):
            mock_config.search_folders = []
            mock_dql.return_value = [
                Note(path="tagged.md", filename="Tagged", content="test",
                     tags=["important"], size=100)
            ]

            api = ObsidianAPI()
            notes = api.get_tagged_notes(["important"])

            assert len(notes) == 1
            call_args = mock_dql.call_args[0][0]
            assert 'contains(file.tags, "important")' in call_args

    @patch.object(ObsidianAPI, 'dql')
    @patch('obsidianki.api.obsidian.CONFIG')
    def test_get_tagged_notes_multiple_tags(self, mock_config, mock_dql):
        """Test getting notes with multiple tags"""
        with patch.dict(os.environ, {'OBSIDIAN_API_KEY': 'test'}):
            mock_config.search_folders = []
            mock_dql.return_value = []

            api = ObsidianAPI()
            api.get_tagged_notes(["tag1", "tag2", "tag3"])

            call_args = mock_dql.call_args[0][0]
            assert 'contains(file.tags, "tag1")' in call_args
            assert 'contains(file.tags, "tag2")' in call_args
            assert ' OR ' in call_args

    @patch.object(ObsidianAPI, 'dql')
    @patch('obsidianki.api.obsidian.CONFIG')
    def test_get_tagged_notes_exclude_recent(self, mock_config, mock_dql):
        """Test getting tagged notes excluding recent ones"""
        with patch.dict(os.environ, {'OBSIDIAN_API_KEY': 'test'}):
            mock_config.search_folders = []
            mock_dql.return_value = []

            api = ObsidianAPI()
            api.get_tagged_notes(["important"], exclude_recent_days=7)

            call_args = mock_dql.call_args[0][0]
            assert 'file.mtime <' in call_args


class TestObsidianAPIEdgeCases:
    """Test edge cases"""

    @patch('obsidianki.api.obsidian.CONFIG')
    def test_empty_search_folders(self, mock_config):
        """Test with empty search folders list"""
        with patch.dict(os.environ, {'OBSIDIAN_API_KEY': 'test'}):
            mock_config.excluded_tags = []
            api = ObsidianAPI()
            result = api._build_filters([])
            assert result == ""

    @patch.object(ObsidianAPI, 'dql')
    @patch('obsidianki.api.obsidian.CONFIG')
    def test_get_old_notes_empty_result(self, mock_config, mock_dql):
        """Test getting old notes with empty result"""
        with patch.dict(os.environ, {'OBSIDIAN_API_KEY': 'test'}):
            mock_config.search_folders = []
            mock_dql.return_value = []

            api = ObsidianAPI()
            notes = api.get_old_notes(days=365)

            assert notes == []
            assert len(notes) == 0

    @patch.object(ObsidianAPI, 'dql')
    @patch('obsidianki.api.obsidian.CONFIG')
    def test_get_tagged_notes_empty_tags(self, mock_config, mock_dql):
        """Test getting notes with empty tags list"""
        with patch.dict(os.environ, {'OBSIDIAN_API_KEY': 'test'}):
            mock_config.search_folders = []
            mock_dql.return_value = []

            api = ObsidianAPI()
            notes = api.get_tagged_notes([])

            # Should still make a query but with no tag conditions
            mock_dql.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
