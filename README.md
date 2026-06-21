# MCP Server Reddit
[![smithery badge](https://smithery.ai/badge/@Hawstein/mcp-server-reddit)](https://smithery.ai/server/@Hawstein/mcp-server-reddit)

A Model Context Protocol server providing access to Reddit public API for LLMs. This server enables LLMs to interact with Reddit's content, including browsing frontpage posts, accessing subreddit information, and reading post comments.

This server uses [redditwarp](https://github.com/Pyprohly/redditwarp) to interact with Reddit's public API and exposes the functionality through MCP protocol.

<a href="https://glama.ai/mcp/servers/4032xr14pu"><img width="380" height="200" src="https://glama.ai/mcp/servers/4032xr14pu/badge" alt="Server Reddit MCP server" /></a>

## Video Demo (Click to Watch)

A demo in Clinde 👇

[![MCP Server Reddit - Clinde](https://img.youtube.com/vi/1Gdx1jWFbCM/maxresdefault.jpg)](https://youtu.be/1Gdx1jWFbCM)


## Available Tools

- `get_frontpage_posts` - Get hot posts from Reddit frontpage
  - Optional arguments:
    - `limit` (integer): Number of posts to return (default: 10, range: 1-100)

- `get_subreddit_info` - Get information about a subreddit
  - Required arguments:
    - `subreddit_name` (string): Name of the subreddit (e.g. 'Python', 'news')

- `get_subreddit_hot_posts` - Get hot posts from a specific subreddit
  - Required arguments:
    - `subreddit_name` (string): Name of the subreddit (e.g. 'Python', 'news')
  - Optional arguments:
    - `limit` (integer): Number of posts to return (default: 10, range: 1-100)

- `get_subreddit_new_posts` - Get new posts from a specific subreddit
  - Required arguments:
    - `subreddit_name` (string): Name of the subreddit (e.g. 'Python', 'news')
  - Optional arguments:
    - `limit` (integer): Number of posts to return (default: 10, range: 1-100)

- `get_subreddit_top_posts` - Get top posts from a specific subreddit
  - Required arguments:
    - `subreddit_name` (string): Name of the subreddit (e.g. 'Python', 'news')
  - Optional arguments:
    - `limit` (integer): Number of posts to return (default: 10, range: 1-100)
    - `time` (string): Time filter for top posts (default: '', options: 'hour', 'day', 'week', 'month', 'year', 'all')

- `get_subreddit_rising_posts` - Get rising posts from a specific subreddit
  - Required arguments:
    - `subreddit_name` (string): Name of the subreddit (e.g. 'Python', 'news')
  - Optional arguments:
    - `limit` (integer): Number of posts to return (default: 10, range: 1-100)

- `search_reddit_posts` - Search posts across Reddit
  - Required arguments:
    - `query` (string): Search query
  - Optional arguments:
    - `limit` (integer): Number of posts to return (default: 25, range: 1-100)
    - `sort` (string): Sort order (default: 'relevance', options: 'relevance', 'hot', 'top', 'new', 'comments')
    - `time` (string): Time filter (default: 'all', options: 'all', 'hour', 'day', 'week', 'month', 'year')

- `search_subreddit_posts` - Search posts in a specific subreddit
  - Required arguments:
    - `subreddit_name` (string): Name of the subreddit (e.g. 'Python', 'news')
    - `query` (string): Search query
  - Optional arguments:
    - `limit` (integer): Number of posts to return (default: 25, range: 1-100)
    - `sort` (string): Sort order (default: 'relevance', options: 'relevance', 'hot', 'top', 'new', 'comments')
    - `time` (string): Time filter (default: 'all', options: 'all', 'hour', 'day', 'week', 'month', 'year')

- `search_subreddits` - Search subreddits by name or description
  - Required arguments:
    - `query` (string): Search query
  - Optional arguments:
    - `limit` (integer): Number of subreddits to return (default: 25, range: 1-100)

- `search_post_comments` - Search fetched comments from a Reddit post ID or URL
  - Required arguments:
    - `post_id` (string): Post ID, `t3_` fullname, or Reddit comments URL
    - `query` (string): Comment search query
  - Optional arguments:
    - `result_limit` (integer): Maximum matching comments to return (default: 25, range: 1-100)
    - `comment_limit` (integer): Number of comments to fetch before local matching (default: 500, range: 1-500)
    - `depth` (integer): Maximum comment-tree depth (default: 10, range: 1-10)
    - `sort` (string): Comment sort (default: 'confidence', options: 'confidence', 'top', 'new', 'controversial', 'old', 'random', 'qa', 'live')
    - `match_mode` (string): Local matching mode (default: 'any_terms', options: 'any_terms', 'all_terms', 'phrase')
    - `expand_more` (boolean): Expand Reddit "load more comments" branches (default: true)
    - `max_more_batches` (integer): Maximum more-comments batches to expand (default: 10, range: 0-25)

- `search_reddit_url_comments` - Search comments from a batch of Reddit post URLs or IDs
  - Required arguments:
    - `post_urls` (array): Reddit post URLs, IDs, or `t3_` fullnames from a search engine
    - `query` (string): Comment search query
  - Optional arguments:
    - `result_limit` (integer): Maximum matching comments to return across all posts (default: 25, range: 1-100)
    - `comment_limit` (integer): Number of comments to fetch per post before local matching (default: 500, range: 1-500)
    - `depth` (integer): Maximum comment-tree depth (default: 10, range: 1-10)
    - `sort` (string): Comment sort (default: 'confidence', options: 'confidence', 'top', 'new', 'controversial', 'old', 'random', 'qa', 'live')
    - `match_mode` (string): Local matching mode (default: 'any_terms', options: 'any_terms', 'all_terms', 'phrase')
    - `expand_more` (boolean): Expand Reddit "load more comments" branches (default: true)
    - `max_more_batches_per_post` (integer): Maximum more-comments batches to expand per post (default: 10, range: 0-25)

- `search_reddit_discussions` - Search posts, then search comments from those candidate posts
  - Required arguments:
    - `query` (string): Search query
  - Optional arguments:
    - `subreddit_name` (string): Optional subreddit to restrict the post search
    - `post_limit` (integer): Number of candidate posts to inspect (default: 10, range: 1-50)
    - `result_limit` (integer): Maximum matching comments to return (default: 25, range: 1-100)
    - `post_sort` (string): Post search sort (default: 'relevance', options: 'relevance', 'hot', 'top', 'new', 'comments')
    - `post_time` (string): Post search time filter (default: 'all', options: 'all', 'hour', 'day', 'week', 'month', 'year')
    - `comment_limit` (integer): Number of comments to fetch per post before local matching (default: 500, range: 1-500)
    - `comment_depth` (integer): Maximum comment-tree depth (default: 10, range: 1-10)
    - `comment_sort` (string): Comment sort (default: 'confidence', options: 'confidence', 'top', 'new', 'controversial', 'old', 'random', 'qa', 'live')
    - `match_mode` (string): Local matching mode (default: 'any_terms', options: 'any_terms', 'all_terms', 'phrase')
    - `expand_more` (boolean): Expand Reddit "load more comments" branches (default: true)
    - `max_more_batches_per_post` (integer): Maximum more-comments batches to expand per post (default: 5, range: 0-25)

- `get_post_content` - Get detailed content of a specific post
  - Required arguments:
    - `post_id` (string): Post ID, `t3_` fullname, or Reddit comments URL
  - Optional arguments:
    - `comment_limit` (integer): Number of top-level comments to return (default: 10, range: 1-500)
    - `comment_depth` (integer): Maximum depth of comment tree (default: 3, range: 1-10)
    - `comment_sort` (string): Comment sort (default: 'top', options: 'confidence', 'top', 'new', 'controversial', 'old', 'random', 'qa', 'live')
    - `expand_more` (boolean): Expand Reddit "load more comments" branches (default: false)
    - `max_more_batches` (integer): Maximum more-comments batches to expand (default: 0, range: 0-25)

- `get_post_comments` - Get comments from a post
  - Required arguments:
    - `post_id` (string): Post ID, `t3_` fullname, or Reddit comments URL
  - Optional arguments:
    - `limit` (integer): Number of comments to return (default: 10, range: 1-500)
    - `depth` (integer): Maximum depth of comment tree (default: 3, range: 1-10)
    - `sort` (string): Comment sort (default: 'top', options: 'confidence', 'top', 'new', 'controversial', 'old', 'random', 'qa', 'live')
    - `expand_more` (boolean): Expand Reddit "load more comments" branches (default: false)
    - `max_more_batches` (integer): Maximum more-comments batches to expand (default: 0, range: 0-25)


## Installation

### Using [Clinde](https://clinde.ai/) (recommended)

The easiest way to use MCP Server Reddit is through the Clinde desktop app. Simply download and install Clinde, then:

1. Open the Clinde app
2. Navigate to the Servers page
3. Find mcp-server-reddit and click Install

That's it! No technical knowledge required - Clinde handles all the installation and configuration for you seamlessly.

### Using uv (recommended)

When using [`uv`](https://docs.astral.sh/uv/) no specific installation is needed. We will
use [`uvx`](https://docs.astral.sh/uv/guides/tools/) to directly run *mcp-server-reddit*.

### Using PIP

Alternatively you can install `mcp-server-reddit` via pip:

```bash
pip install mcp-server-reddit
```

After installation, you can run it as a script using:

```bash
python -m mcp_server_reddit
```

### Installing via Smithery

To install MCP Server Reddit for Claude Desktop automatically via [Smithery](https://smithery.ai/server/@Hawstein/mcp-server-reddit):

```bash
npx -y @smithery/cli install @Hawstein/mcp-server-reddit --client claude
```

## Configuration

### User-Agent

Set `REDDIT_USER_AGENT` to override the default User-Agent.

### Search Engine Handoff

Reddit's public API searches submissions, not the full comment corpus. For comment-first discovery, use a web-search MCP or search engine with queries like `site:reddit.com/r/<subreddit>/comments <terms>`, then pass the returned Reddit URLs to `search_reddit_url_comments`. This server will normalize `www.reddit.com`, `old.reddit.com`, `t3_` fullnames, and raw post IDs, then fetch and locally search expanded comments through Reddit's API.

### Configure for Claude.app

Add to your Claude settings:

<details>
<summary>Using uvx</summary>

```json
"mcpServers": {
  "reddit": {
    "command": "uvx",
    "args": ["mcp-server-reddit"]
  }
}
```
</details>

<details>
<summary>Using pip installation</summary>

```json
"mcpServers": {
  "reddit": {
    "command": "python",
    "args": ["-m", "mcp_server_reddit"]
  }
}
```
</details>

### Configure for Zed

Add to your Zed settings.json:

<details>
<summary>Using uvx</summary>

```json
"context_servers": [
  "mcp-server-reddit": {
    "command": "uvx",
    "args": ["mcp-server-reddit"]
  }
],
```
</details>

<details>
<summary>Using pip installation</summary>

```json
"context_servers": {
  "mcp-server-reddit": {
    "command": "python",
    "args": ["-m", "mcp_server_reddit"]
  }
},
```
</details>

## Examples of Questions

- "What are the current hot posts on Reddit's frontpage?" (get_frontpage_posts)
- "Tell me about the r/ClaudeAI subreddit" (get_subreddit_info)
- "What are the hot posts in the r/ClaudeAI subreddit?" (get_subreddit_hot_posts)
- "Show me the newest posts from r/ClaudeAI" (get_subreddit_new_posts)
- "What are the top posts of all time in r/ClaudeAI?" (get_subreddit_top_posts)
- "What posts are trending in r/ClaudeAI right now?" (get_subreddit_rising_posts)
- "Search Reddit for posts about people switching away from product X." (search_reddit_posts)
- "Search r/SaaS for anecdotes about churn after pricing changes." (search_subreddit_posts)
- "Find comments in this Reddit thread mentioning battery degradation: [post_url]" (search_post_comments)
- "Search these Reddit URLs from web search for comments about refunds: [post_urls]" (search_reddit_url_comments)
- "Search Reddit discussions for comments about people regretting a purchase." (search_reddit_discussions)
- "Get the full content and comments of this Reddit post: [post_url]" (get_post_content)
- "Summarize the comments on this Reddit post: [post_url]" (get_post_comments)

## Debugging

You can use the MCP inspector to debug the server. For uvx installations:

```bash
npx @modelcontextprotocol/inspector uvx mcp-server-reddit
```

Or if you've installed the package in a specific directory or are developing on it:

```bash
cd path/to/mcp_server_reddit
npx @modelcontextprotocol/inspector uv run mcp-server-reddit
```

## License

mcp-server-reddit is licensed under the MIT License. This means you are free to use, modify, and distribute the software, subject to the terms and conditions of the MIT License. For more details, please see the LICENSE file in the project repository.
