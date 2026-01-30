"""
Tests for Slack tool.

Covers:
- _SlackClient methods (post_message, list_channels, etc.)
- Error handling (API errors, timeout, network errors)
- Credential retrieval (CredentialStoreAdapter vs env var)
- All 7 MCP tool functions
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastmcp import FastMCP

from aden_tools.tools.slack_tool.slack_tool import (
    SLACK_API_BASE,
    _SlackClient,
    register_tools,
)


# --- _SlackClient tests ---


class TestSlackClient:
    def setup_method(self):
        self.client = _SlackClient("xoxb-test-token")

    def test_headers(self):
        headers = self.client._headers
        assert headers["Authorization"] == "Bearer xoxb-test-token"
        assert "application/json" in headers["Content-Type"]

    def test_handle_response_success(self):
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"ok": True, "channel": "C123"}
        result = self.client._handle_response(response)
        assert result["success"] is True
        assert result["channel"] == "C123"

    def test_handle_response_api_error(self):
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"ok": False, "error": "channel_not_found"}
        result = self.client._handle_response(response)
        assert "error" in result
        assert "channel_not_found" in result["error"]

    def test_handle_response_http_error(self):
        response = MagicMock()
        response.status_code = 500
        result = self.client._handle_response(response)
        assert "error" in result
        assert "500" in result["error"]

    @patch("aden_tools.tools.slack_tool.slack_tool.httpx.post")
    def test_post_message(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "channel": "C123",
            "ts": "1234567890.123456",
        }
        mock_post.return_value = mock_response

        result = self.client.post_message("C123", "Hello, world!")

        mock_post.assert_called_once_with(
            f"{SLACK_API_BASE}/chat.postMessage",
            headers=self.client._headers,
            json={"channel": "C123", "text": "Hello, world!"},
            timeout=30.0,
        )
        assert result["success"] is True
        assert result["ts"] == "1234567890.123456"

    @patch("aden_tools.tools.slack_tool.slack_tool.httpx.post")
    def test_post_message_with_thread(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True, "ts": "1234567890.123456"}
        mock_post.return_value = mock_response

        self.client.post_message("C123", "Reply", thread_ts="1234567890.000000")

        call_json = mock_post.call_args.kwargs["json"]
        assert call_json["thread_ts"] == "1234567890.000000"

    @patch("aden_tools.tools.slack_tool.slack_tool.httpx.get")
    def test_list_channels(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "channels": [
                {"id": "C123", "name": "general"},
                {"id": "C456", "name": "random"},
            ],
        }
        mock_get.return_value = mock_response

        result = self.client.list_channels(limit=50)

        mock_get.assert_called_once()
        assert result["success"] is True
        assert len(result["channels"]) == 2

    @patch("aden_tools.tools.slack_tool.slack_tool.httpx.get")
    def test_list_channels_limit_capped(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True, "channels": []}
        mock_get.return_value = mock_response

        self.client.list_channels(limit=2000)

        call_params = mock_get.call_args.kwargs["params"]
        assert call_params["limit"] == 1000

    @patch("aden_tools.tools.slack_tool.slack_tool.httpx.get")
    def test_get_channel_history(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "messages": [
                {"ts": "1234567890.123456", "text": "Hello", "user": "U123"},
            ],
        }
        mock_get.return_value = mock_response

        result = self.client.get_channel_history("C123", limit=20)

        mock_get.assert_called_once()
        assert result["success"] is True
        assert len(result["messages"]) == 1

    @patch("aden_tools.tools.slack_tool.slack_tool.httpx.get")
    def test_list_users(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "members": [
                {"id": "U123", "name": "alice", "real_name": "Alice Smith"},
                {"id": "U456", "name": "bob", "real_name": "Bob Jones"},
            ],
        }
        mock_get.return_value = mock_response

        result = self.client.list_users(limit=100)

        assert result["success"] is True
        assert len(result["members"]) == 2

    @patch("aden_tools.tools.slack_tool.slack_tool.httpx.get")
    def test_get_user_info(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "user": {
                "id": "U123",
                "name": "alice",
                "real_name": "Alice Smith",
                "profile": {"email": "alice@example.com"},
            },
        }
        mock_get.return_value = mock_response

        result = self.client.get_user_info("U123")

        mock_get.assert_called_once()
        assert result["success"] is True
        assert result["user"]["id"] == "U123"

    @patch("aden_tools.tools.slack_tool.slack_tool.httpx.post")
    def test_add_reaction(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True}
        mock_post.return_value = mock_response

        result = self.client.add_reaction("C123", "1234567890.123456", "thumbsup")

        mock_post.assert_called_once_with(
            f"{SLACK_API_BASE}/reactions.add",
            headers=self.client._headers,
            json={
                "channel": "C123",
                "timestamp": "1234567890.123456",
                "name": "thumbsup",
            },
            timeout=30.0,
        )
        assert result["success"] is True

    @patch("aden_tools.tools.slack_tool.slack_tool.httpx.get")
    def test_get_channel_info(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "channel": {
                "id": "C123",
                "name": "general",
                "is_private": False,
                "num_members": 50,
            },
        }
        mock_get.return_value = mock_response

        result = self.client.get_channel_info("C123")

        assert result["success"] is True
        assert result["channel"]["name"] == "general"


# --- Credential retrieval tests ---


class TestCredentialRetrieval:
    @pytest.fixture
    def mcp(self):
        return FastMCP("test-server")

    def test_no_credentials_returns_error(self, mcp):
        """When no credentials are configured, tools return helpful error."""
        with patch.dict("os.environ", {}, clear=True):
            with patch("os.getenv", return_value=None):
                register_tools(mcp, credentials=None)
                send_message = mcp._tool_manager._tools["slack_send_message"].fn

                result = send_message(channel="C123", text="test")

                assert "error" in result
                assert "not configured" in result["error"]
                assert "help" in result

    def test_env_var_token(self, mcp):
        """Token from SLACK_BOT_TOKEN env var is used."""
        with patch("os.getenv", return_value="xoxb-env-token"):
            with patch(
                "aden_tools.tools.slack_tool.slack_tool.httpx.post"
            ) as mock_post:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {"ok": True, "ts": "123"}
                mock_post.return_value = mock_response

                register_tools(mcp, credentials=None)
                send_message = mcp._tool_manager._tools["slack_send_message"].fn

                send_message(channel="C123", text="test")

                # Verify token was used in header
                call_headers = mock_post.call_args.kwargs["headers"]
                assert call_headers["Authorization"] == "Bearer xoxb-env-token"

    def test_credential_store_token(self, mcp):
        """Token from CredentialStoreAdapter is preferred."""
        mock_credentials = MagicMock()
        mock_credentials.get.return_value = "xoxb-store-token"

        with patch("aden_tools.tools.slack_tool.slack_tool.httpx.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"ok": True, "ts": "123"}
            mock_post.return_value = mock_response

            register_tools(mcp, credentials=mock_credentials)
            send_message = mcp._tool_manager._tools["slack_send_message"].fn

            send_message(channel="C123", text="test")

            mock_credentials.get.assert_called_with("slack")
            call_headers = mock_post.call_args.kwargs["headers"]
            assert call_headers["Authorization"] == "Bearer xoxb-store-token"


# --- MCP Tool function tests ---


class TestSlackSendMessage:
    @pytest.fixture
    def mcp(self):
        return FastMCP("test-server")

    @patch("aden_tools.tools.slack_tool.slack_tool.httpx.post")
    def test_send_message_success(self, mock_post, mcp):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "channel": "C123",
            "ts": "1234567890.123456",
        }
        mock_post.return_value = mock_response

        with patch("os.getenv", return_value="xoxb-test"):
            register_tools(mcp, credentials=None)
            send_message = mcp._tool_manager._tools["slack_send_message"].fn

            result = send_message(channel="C123", text="Hello!")

            assert result["success"] is True
            assert result["ts"] == "1234567890.123456"

    @patch("aden_tools.tools.slack_tool.slack_tool.httpx.post")
    def test_send_message_timeout(self, mock_post, mcp):
        mock_post.side_effect = httpx.TimeoutException("Timeout")

        with patch("os.getenv", return_value="xoxb-test"):
            register_tools(mcp, credentials=None)
            send_message = mcp._tool_manager._tools["slack_send_message"].fn

            result = send_message(channel="C123", text="Hello!")

            assert "error" in result
            assert "timed out" in result["error"]

    @patch("aden_tools.tools.slack_tool.slack_tool.httpx.post")
    def test_send_message_network_error(self, mock_post, mcp):
        mock_post.side_effect = httpx.RequestError("Network error")

        with patch("os.getenv", return_value="xoxb-test"):
            register_tools(mcp, credentials=None)
            send_message = mcp._tool_manager._tools["slack_send_message"].fn

            result = send_message(channel="C123", text="Hello!")

            assert "error" in result
            assert "Network error" in result["error"]


class TestSlackListChannels:
    @pytest.fixture
    def mcp(self):
        return FastMCP("test-server")

    @patch("aden_tools.tools.slack_tool.slack_tool.httpx.get")
    def test_list_channels_success(self, mock_get, mcp):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "channels": [
                {
                    "id": "C123",
                    "name": "general",
                    "is_private": False,
                    "num_members": 50,
                    "topic": {"value": "General discussion"},
                    "purpose": {"value": "Team chat"},
                },
            ],
        }
        mock_get.return_value = mock_response

        with patch("os.getenv", return_value="xoxb-test"):
            register_tools(mcp, credentials=None)
            list_channels = mcp._tool_manager._tools["slack_list_channels"].fn

            result = list_channels(limit=100)

            assert result["success"] is True
            assert result["count"] == 1
            assert result["channels"][0]["name"] == "general"


class TestSlackGetChannelHistory:
    @pytest.fixture
    def mcp(self):
        return FastMCP("test-server")

    @patch("aden_tools.tools.slack_tool.slack_tool.httpx.get")
    def test_get_history_success(self, mock_get, mcp):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "messages": [
                {
                    "ts": "1234567890.123456",
                    "user": "U123",
                    "text": "Hello everyone!",
                    "type": "message",
                },
            ],
        }
        mock_get.return_value = mock_response

        with patch("os.getenv", return_value="xoxb-test"):
            register_tools(mcp, credentials=None)
            get_history = mcp._tool_manager._tools["slack_get_channel_history"].fn

            result = get_history(channel="C123", limit=20)

            assert result["success"] is True
            assert result["count"] == 1
            assert result["messages"][0]["text"] == "Hello everyone!"


class TestSlackListUsers:
    @pytest.fixture
    def mcp(self):
        return FastMCP("test-server")

    @patch("aden_tools.tools.slack_tool.slack_tool.httpx.get")
    def test_list_users_success(self, mock_get, mcp):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "members": [
                {
                    "id": "U123",
                    "name": "alice",
                    "real_name": "Alice Smith",
                    "deleted": False,
                    "is_bot": False,
                    "is_admin": True,
                    "profile": {
                        "display_name": "alice.smith",
                        "email": "alice@example.com",
                    },
                },
                {
                    "id": "U456",
                    "name": "deleted_user",
                    "deleted": True,
                },
            ],
        }
        mock_get.return_value = mock_response

        with patch("os.getenv", return_value="xoxb-test"):
            register_tools(mcp, credentials=None)
            list_users = mcp._tool_manager._tools["slack_list_users"].fn

            result = list_users(limit=100)

            assert result["success"] is True
            # Deleted user should be filtered out
            assert result["count"] == 1
            assert result["users"][0]["name"] == "alice"


class TestSlackGetUserInfo:
    @pytest.fixture
    def mcp(self):
        return FastMCP("test-server")

    @patch("aden_tools.tools.slack_tool.slack_tool.httpx.get")
    def test_get_user_info_success(self, mock_get, mcp):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "user": {
                "id": "U123",
                "name": "alice",
                "real_name": "Alice Smith",
                "is_admin": True,
                "is_bot": False,
                "tz": "America/New_York",
                "profile": {
                    "display_name": "alice.smith",
                    "email": "alice@example.com",
                    "title": "Engineer",
                    "phone": "+1234567890",
                },
            },
        }
        mock_get.return_value = mock_response

        with patch("os.getenv", return_value="xoxb-test"):
            register_tools(mcp, credentials=None)
            get_user = mcp._tool_manager._tools["slack_get_user_info"].fn

            result = get_user(user_id="U123")

            assert result["success"] is True
            assert result["user"]["email"] == "alice@example.com"
            assert result["user"]["title"] == "Engineer"


class TestSlackAddReaction:
    @pytest.fixture
    def mcp(self):
        return FastMCP("test-server")

    @patch("aden_tools.tools.slack_tool.slack_tool.httpx.post")
    def test_add_reaction_success(self, mock_post, mcp):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True}
        mock_post.return_value = mock_response

        with patch("os.getenv", return_value="xoxb-test"):
            register_tools(mcp, credentials=None)
            add_reaction = mcp._tool_manager._tools["slack_add_reaction"].fn

            result = add_reaction(
                channel="C123",
                timestamp="1234567890.123456",
                emoji="thumbsup",
            )

            assert result["success"] is True


class TestSlackGetChannelInfo:
    @pytest.fixture
    def mcp(self):
        return FastMCP("test-server")

    @patch("aden_tools.tools.slack_tool.slack_tool.httpx.get")
    def test_get_channel_info_success(self, mock_get, mcp):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "channel": {
                "id": "C123",
                "name": "general",
                "is_private": False,
                "is_archived": False,
                "num_members": 50,
                "topic": {"value": "General discussion"},
                "purpose": {"value": "Team chat"},
                "created": 1234567890,
                "creator": "U123",
            },
        }
        mock_get.return_value = mock_response

        with patch("os.getenv", return_value="xoxb-test"):
            register_tools(mcp, credentials=None)
            get_channel = mcp._tool_manager._tools["slack_get_channel_info"].fn

            result = get_channel(channel="C123")

            assert result["success"] is True
            assert result["channel"]["name"] == "general"
            assert result["channel"]["num_members"] == 50
