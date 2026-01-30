# Slack Tool

Send messages and interact with Slack workspaces within the Aden agent framework.

## Installation

The Slack tool uses `httpx` which is already included in the base dependencies. No additional installation required.

## Setup

You need a Slack Bot Token to use this tool.

### Getting a Slack Bot Token

1. Go to https://api.slack.com/apps
2. Create a new app or select an existing one
3. Navigate to "OAuth & Permissions"
4. Add the following Bot Token Scopes:
   - `channels:read` - View basic information about public channels
   - `channels:history` - View messages in public channels
   - `chat:write` - Send messages
   - `reactions:write` - Add reactions to messages
   - `users:read` - View people in the workspace
   - `groups:read` - View basic information about private channels (optional)
   - `groups:history` - View messages in private channels (optional)
5. Install the app to your workspace
6. Copy the "Bot User OAuth Token" (starts with `xoxb-`)

### Configuration

Set the token as an environment variable:

```bash
export SLACK_BOT_TOKEN=xoxb-your-token-here
```

Or configure via the credential store (recommended for production).

## Available Functions

### `slack_send_message`

Send a message to a Slack channel.

**Parameters:**
- `channel` (str): Channel ID (e.g., "C01234567") or name (e.g., "#general")
- `text` (str): Message text (supports Slack markdown)
- `thread_ts` (str, optional): Thread timestamp to reply in a thread

**Returns:**
```python
{
    "success": True,
    "channel": "C01234567",
    "ts": "1234567890.123456",
    "message": {...}
}
```

**Example:**
```python
# Send a message to a channel
result = slack_send_message(
    channel="#general",
    text="Hello team! :wave:"
)

# Reply in a thread
result = slack_send_message(
    channel="C01234567",
    text="This is a reply",
    thread_ts="1234567890.123456"
)
```

### `slack_list_channels`

List channels in the Slack workspace.

**Parameters:**
- `limit` (int, optional): Maximum number of channels (1-1000, default 100)
- `exclude_archived` (bool, optional): Exclude archived channels (default True)

**Returns:**
```python
{
    "success": True,
    "channels": [
        {
            "id": "C01234567",
            "name": "general",
            "is_private": False,
            "num_members": 50,
            "topic": "General discussion",
            "purpose": "Team chat"
        }
    ],
    "count": 1
}
```

**Example:**
```python
result = slack_list_channels(limit=50, exclude_archived=True)
for channel in result["channels"]:
    print(f"#{channel['name']} - {channel['num_members']} members")
```

### `slack_get_channel_history`

Get recent messages from a channel.

**Parameters:**
- `channel` (str): Channel ID (e.g., "C01234567")
- `limit` (int, optional): Maximum messages to return (1-100, default 20)

**Returns:**
```python
{
    "success": True,
    "messages": [
        {
            "ts": "1234567890.123456",
            "user": "U01234567",
            "text": "Hello everyone!",
            "type": "message",
            "thread_ts": None,
            "reply_count": 0
        }
    ],
    "count": 1
}
```

**Example:**
```python
result = slack_get_channel_history(channel="C01234567", limit=10)
for msg in result["messages"]:
    print(f"{msg['user']}: {msg['text']}")
```

### `slack_list_users`

List users in the Slack workspace.

**Parameters:**
- `limit` (int, optional): Maximum users to return (1-1000, default 100)

**Returns:**
```python
{
    "success": True,
    "users": [
        {
            "id": "U01234567",
            "name": "alice",
            "real_name": "Alice Smith",
            "display_name": "alice.smith",
            "email": "alice@example.com",
            "is_admin": False,
            "is_bot": False
        }
    ],
    "count": 1
}
```

**Example:**
```python
result = slack_list_users(limit=100)
admins = [u for u in result["users"] if u["is_admin"]]
print(f"Found {len(admins)} admins")
```

### `slack_get_user_info`

Get information about a specific user.

**Parameters:**
- `user_id` (str): Slack user ID (e.g., "U01234567")

**Returns:**
```python
{
    "success": True,
    "user": {
        "id": "U01234567",
        "name": "alice",
        "real_name": "Alice Smith",
        "display_name": "alice.smith",
        "email": "alice@example.com",
        "title": "Engineer",
        "phone": "+1234567890",
        "is_admin": False,
        "is_bot": False,
        "tz": "America/New_York"
    }
}
```

**Example:**
```python
result = slack_get_user_info(user_id="U01234567")
print(f"{result['user']['real_name']} - {result['user']['title']}")
```

### `slack_add_reaction`

Add a reaction emoji to a message.

**Parameters:**
- `channel` (str): Channel ID where the message is
- `timestamp` (str): Message timestamp
- `emoji` (str): Emoji name without colons (e.g., "thumbsup", "heart")

**Returns:**
```python
{
    "success": True
}
```

**Example:**
```python
result = slack_add_reaction(
    channel="C01234567",
    timestamp="1234567890.123456",
    emoji="thumbsup"
)
```

### `slack_get_channel_info`

Get detailed information about a channel.

**Parameters:**
- `channel` (str): Channel ID (e.g., "C01234567")

**Returns:**
```python
{
    "success": True,
    "channel": {
        "id": "C01234567",
        "name": "general",
        "is_private": False,
        "is_archived": False,
        "num_members": 50,
        "topic": "General discussion",
        "purpose": "Team chat",
        "created": 1234567890,
        "creator": "U01234567"
    }
}
```

**Example:**
```python
result = slack_get_channel_info(channel="C01234567")
print(f"Channel: #{result['channel']['name']}")
print(f"Members: {result['channel']['num_members']}")
```

## Error Handling

All functions return a dict with an `error` key if something goes wrong:

```python
{
    "error": "Slack API error: channel_not_found",
    "help": "Set SLACK_BOT_TOKEN environment variable..."
}
```

Common errors:
- `not configured` - No bot token provided
- `channel_not_found` - Channel ID doesn't exist
- `invalid_auth` - Token is invalid or expired
- `missing_scope` - Bot lacks required permissions
- `rate_limited` - Too many requests (Slack has rate limits)

## Security

- Bot tokens are never logged or exposed
- All API calls use HTTPS
- Tokens are retrieved from secure credential store or environment variables

## Use Cases

### Team Notifications
```python
# Notify team of deployment
slack_send_message(
    channel="#deployments",
    text="🚀 Production deployment successful! Version 2.1.0"
)
```

### Daily Standup Bot
```python
# Get channel history and summarize
messages = slack_get_channel_history(channel="C123", limit=50)
# Process and summarize...
slack_send_message(channel="#standup", text="Daily summary: ...")
```

### User Onboarding
```python
# Welcome new users
users = slack_list_users(limit=100)
for user in users["users"]:
    if user["is_new"]:  # Custom logic
        slack_send_message(
            channel=user["id"],  # DM
            text=f"Welcome to the team, {user['real_name']}! 👋"
        )
```

## Rate Limits

Slack enforces rate limits on API calls:
- Tier 1: 1+ request per minute
- Tier 2: 20+ requests per minute
- Tier 3: 50+ requests per minute
- Tier 4: 100+ requests per minute

The tool handles rate limit errors gracefully with appropriate error messages.
