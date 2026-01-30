"""
Slack Tool - Send messages and interact with Slack workspaces.

Supports:
- Bot tokens (SLACK_BOT_TOKEN / xoxb-...)
- OAuth tokens via the credential store

API Reference: https://api.slack.com/methods
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

import httpx
from fastmcp import FastMCP

if TYPE_CHECKING:
    from aden_tools.credentials import CredentialStoreAdapter

SLACK_API_BASE = "https://slack.com/api"


class _SlackClient:
    """Internal client wrapping Slack Web API calls."""

    def __init__(self, bot_token: str):
        self._token = bot_token

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json; charset=utf-8",
        }

    def _handle_response(self, response: httpx.Response) -> dict[str, Any]:
        """Handle Slack API response format."""
        if response.status_code != 200:
            return {"error": f"HTTP error: {response.status_code}"}

        data = response.json()

        # Slack API returns {"ok": false, "error": "..."} on failure
        if not data.get("ok"):
            error = data.get("error", "Unknown Slack API error")
            return {"error": f"Slack API error: {error}"}

        return {"success": True, **data}

    def post_message(
        self,
        channel: str,
        text: str,
        thread_ts: str | None = None,
    ) -> dict[str, Any]:
        """Post a message to a channel."""
        body: dict[str, Any] = {
            "channel": channel,
            "text": text,
        }
        if thread_ts:
            body["thread_ts"] = thread_ts

        response = httpx.post(
            f"{SLACK_API_BASE}/chat.postMessage",
            headers=self._headers,
            json=body,
            timeout=30.0,
        )
        return self._handle_response(response)

    def list_channels(
        self,
        limit: int = 100,
        exclude_archived: bool = True,
    ) -> dict[str, Any]:
        """List channels in the workspace."""
        params = {
            "limit": min(limit, 1000),
            "exclude_archived": str(exclude_archived).lower(),
            "types": "public_channel,private_channel",
        }

        response = httpx.get(
            f"{SLACK_API_BASE}/conversations.list",
            headers=self._headers,
            params=params,
            timeout=30.0,
        )
        return self._handle_response(response)

    def get_channel_history(
        self,
        channel: str,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Get message history from a channel."""
        params = {
            "channel": channel,
            "limit": min(limit, 100),
        }

        response = httpx.get(
            f"{SLACK_API_BASE}/conversations.history",
            headers=self._headers,
            params=params,
            timeout=30.0,
        )
        return self._handle_response(response)

    def list_users(
        self,
        limit: int = 100,
    ) -> dict[str, Any]:
        """List users in the workspace."""
        params = {
            "limit": min(limit, 1000),
        }

        response = httpx.get(
            f"{SLACK_API_BASE}/users.list",
            headers=self._headers,
            params=params,
            timeout=30.0,
        )
        return self._handle_response(response)

    def get_user_info(
        self,
        user_id: str,
    ) -> dict[str, Any]:
        """Get information about a user."""
        params = {
            "user": user_id,
        }

        response = httpx.get(
            f"{SLACK_API_BASE}/users.info",
            headers=self._headers,
            params=params,
            timeout=30.0,
        )
        return self._handle_response(response)

    def add_reaction(
        self,
        channel: str,
        timestamp: str,
        name: str,
    ) -> dict[str, Any]:
        """Add a reaction emoji to a message."""
        body = {
            "channel": channel,
            "timestamp": timestamp,
            "name": name,  # emoji name without colons, e.g., "thumbsup"
        }

        response = httpx.post(
            f"{SLACK_API_BASE}/reactions.add",
            headers=self._headers,
            json=body,
            timeout=30.0,
        )
        return self._handle_response(response)

    def get_channel_info(
        self,
        channel: str,
    ) -> dict[str, Any]:
        """Get information about a channel."""
        params = {
            "channel": channel,
        }

        response = httpx.get(
            f"{SLACK_API_BASE}/conversations.info",
            headers=self._headers,
            params=params,
            timeout=30.0,
        )
        return self._handle_response(response)


def register_tools(
    mcp: FastMCP,
    credentials: CredentialStoreAdapter | None = None,
) -> None:
    """Register Slack tools with the MCP server."""

    def _get_token() -> str | None:
        """Get Slack bot token from credential manager or environment."""
        if credentials is not None:
            token = credentials.get("slack")
            if token is not None and not isinstance(token, str):
                raise TypeError(
                    f"Expected string from credentials.get('slack'), got {type(token).__name__}"
                )
            return token
        return os.getenv("SLACK_BOT_TOKEN")

    def _get_client() -> _SlackClient | dict[str, str]:
        """Get a Slack client, or return an error dict if no credentials."""
        token = _get_token()
        if not token:
            return {
                "error": "Slack credentials not configured",
                "help": (
                    "Set SLACK_BOT_TOKEN environment variable "
                    "or configure via credential store. "
                    "Get a token at https://api.slack.com/apps"
                ),
            }
        return _SlackClient(token)

    # --- Messages ---

    @mcp.tool()
    def slack_send_message(
        channel: str,
        text: str,
        thread_ts: str | None = None,
    ) -> dict:
        """
        Send a message to a Slack channel.

        Args:
            channel: Channel ID (e.g., "C01234567") or name (e.g., "#general")
            text: Message text (supports Slack markdown)
            thread_ts: Optional thread timestamp to reply in a thread

        Returns:
            Dict with message details or error
        """
        client = _get_client()
        if isinstance(client, dict):
            return client
        try:
            return client.post_message(channel, text, thread_ts)
        except httpx.TimeoutException:
            return {"error": "Request timed out"}
        except httpx.RequestError as e:
            return {"error": f"Network error: {e}"}

    @mcp.tool()
    def slack_list_channels(
        limit: int = 100,
        exclude_archived: bool = True,
    ) -> dict:
        """
        List channels in the Slack workspace.

        Args:
            limit: Maximum number of channels to return (1-1000, default 100)
            exclude_archived: Whether to exclude archived channels (default True)

        Returns:
            Dict with list of channels or error
        """
        client = _get_client()
        if isinstance(client, dict):
            return client
        try:
            result = client.list_channels(limit, exclude_archived)
            if result.get("success") and "channels" in result:
                # Simplify channel data for easier consumption
                channels = [
                    {
                        "id": ch.get("id"),
                        "name": ch.get("name"),
                        "is_private": ch.get("is_private", False),
                        "num_members": ch.get("num_members", 0),
                        "topic": ch.get("topic", {}).get("value", ""),
                        "purpose": ch.get("purpose", {}).get("value", ""),
                    }
                    for ch in result.get("channels", [])
                ]
                return {"success": True, "channels": channels, "count": len(channels)}
            return result
        except httpx.TimeoutException:
            return {"error": "Request timed out"}
        except httpx.RequestError as e:
            return {"error": f"Network error: {e}"}

    @mcp.tool()
    def slack_get_channel_history(
        channel: str,
        limit: int = 20,
    ) -> dict:
        """
        Get recent messages from a Slack channel.

        Args:
            channel: Channel ID (e.g., "C01234567")
            limit: Maximum number of messages to return (1-100, default 20)

        Returns:
            Dict with list of messages or error
        """
        client = _get_client()
        if isinstance(client, dict):
            return client
        try:
            result = client.get_channel_history(channel, limit)
            if result.get("success") and "messages" in result:
                # Simplify message data
                messages = [
                    {
                        "ts": msg.get("ts"),
                        "user": msg.get("user"),
                        "text": msg.get("text"),
                        "type": msg.get("type"),
                        "thread_ts": msg.get("thread_ts"),
                        "reply_count": msg.get("reply_count", 0),
                    }
                    for msg in result.get("messages", [])
                ]
                return {"success": True, "messages": messages, "count": len(messages)}
            return result
        except httpx.TimeoutException:
            return {"error": "Request timed out"}
        except httpx.RequestError as e:
            return {"error": f"Network error: {e}"}

    @mcp.tool()
    def slack_list_users(
        limit: int = 100,
    ) -> dict:
        """
        List users in the Slack workspace.

        Args:
            limit: Maximum number of users to return (1-1000, default 100)

        Returns:
            Dict with list of users or error
        """
        client = _get_client()
        if isinstance(client, dict):
            return client
        try:
            result = client.list_users(limit)
            if result.get("success") and "members" in result:
                # Simplify user data, exclude bots and deleted users
                users = [
                    {
                        "id": user.get("id"),
                        "name": user.get("name"),
                        "real_name": user.get("real_name", ""),
                        "display_name": user.get("profile", {}).get("display_name", ""),
                        "email": user.get("profile", {}).get("email", ""),
                        "is_admin": user.get("is_admin", False),
                        "is_bot": user.get("is_bot", False),
                    }
                    for user in result.get("members", [])
                    if not user.get("deleted", False)
                ]
                return {"success": True, "users": users, "count": len(users)}
            return result
        except httpx.TimeoutException:
            return {"error": "Request timed out"}
        except httpx.RequestError as e:
            return {"error": f"Network error: {e}"}

    @mcp.tool()
    def slack_get_user_info(
        user_id: str,
    ) -> dict:
        """
        Get information about a Slack user.

        Args:
            user_id: The Slack user ID (e.g., "U01234567")

        Returns:
            Dict with user information or error
        """
        client = _get_client()
        if isinstance(client, dict):
            return client
        try:
            result = client.get_user_info(user_id)
            if result.get("success") and "user" in result:
                user = result["user"]
                return {
                    "success": True,
                    "user": {
                        "id": user.get("id"),
                        "name": user.get("name"),
                        "real_name": user.get("real_name", ""),
                        "display_name": user.get("profile", {}).get("display_name", ""),
                        "email": user.get("profile", {}).get("email", ""),
                        "title": user.get("profile", {}).get("title", ""),
                        "phone": user.get("profile", {}).get("phone", ""),
                        "is_admin": user.get("is_admin", False),
                        "is_bot": user.get("is_bot", False),
                        "tz": user.get("tz", ""),
                    },
                }
            return result
        except httpx.TimeoutException:
            return {"error": "Request timed out"}
        except httpx.RequestError as e:
            return {"error": f"Network error: {e}"}

    @mcp.tool()
    def slack_add_reaction(
        channel: str,
        timestamp: str,
        emoji: str,
    ) -> dict:
        """
        Add a reaction emoji to a message.

        Args:
            channel: Channel ID where the message is (e.g., "C01234567")
            timestamp: Message timestamp (e.g., "1234567890.123456")
            emoji: Emoji name without colons (e.g., "thumbsup", "heart", "rocket")

        Returns:
            Dict with success status or error
        """
        client = _get_client()
        if isinstance(client, dict):
            return client
        try:
            return client.add_reaction(channel, timestamp, emoji)
        except httpx.TimeoutException:
            return {"error": "Request timed out"}
        except httpx.RequestError as e:
            return {"error": f"Network error: {e}"}

    @mcp.tool()
    def slack_get_channel_info(
        channel: str,
    ) -> dict:
        """
        Get information about a Slack channel.

        Args:
            channel: Channel ID (e.g., "C01234567")

        Returns:
            Dict with channel information or error
        """
        client = _get_client()
        if isinstance(client, dict):
            return client
        try:
            result = client.get_channel_info(channel)
            if result.get("success") and "channel" in result:
                ch = result["channel"]
                return {
                    "success": True,
                    "channel": {
                        "id": ch.get("id"),
                        "name": ch.get("name"),
                        "is_private": ch.get("is_private", False),
                        "is_archived": ch.get("is_archived", False),
                        "num_members": ch.get("num_members", 0),
                        "topic": ch.get("topic", {}).get("value", ""),
                        "purpose": ch.get("purpose", {}).get("value", ""),
                        "created": ch.get("created"),
                        "creator": ch.get("creator"),
                    },
                }
            return result
        except httpx.TimeoutException:
            return {"error": "Request timed out"}
        except httpx.RequestError as e:
            return {"error": f"Network error: {e}"}
