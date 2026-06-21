from enum import Enum
import json
import os
import re
from typing import Sequence
import redditwarp.SYNC
import redditwarp.models.subreddit
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent, ImageContent, EmbeddedResource
from mcp.shared.exceptions import McpError
from pydantic import BaseModel, Field

# Workaround for redditwarp bug: Reddit sometimes omits 'active_user_count'
# from subreddit JSON, causing KeyError in Subreddit.__init__.
if not getattr(redditwarp.models.subreddit.Subreddit.__init__, '_patched', False):
    _original_subreddit_init = redditwarp.models.subreddit.Subreddit.__init__

    def _patched_subreddit_init(self, d, *args, **kwargs):
        if 'active_user_count' not in d:
            d = dict(d)
            d['active_user_count'] = None
        _original_subreddit_init(self, d, *args, **kwargs)

    _patched_subreddit_init._patched = True
    redditwarp.models.subreddit.Subreddit.__init__ = _patched_subreddit_init


class PostType(str, Enum):
    LINK = "link"
    TEXT = "text"
    GALLERY = "gallery"
    UNKNOWN = "unknown"


class RedditTools(str, Enum):
    GET_FRONTPAGE_POSTS = "get_frontpage_posts"
    GET_SUBREDDIT_INFO = "get_subreddit_info"
    GET_SUBREDDIT_HOT_POSTS = "get_subreddit_hot_posts"
    GET_SUBREDDIT_NEW_POSTS = "get_subreddit_new_posts"
    GET_SUBREDDIT_TOP_POSTS = "get_subreddit_top_posts"
    GET_SUBREDDIT_RISING_POSTS = "get_subreddit_rising_posts"
    SEARCH_REDDIT_POSTS = "search_reddit_posts"
    SEARCH_SUBREDDIT_POSTS = "search_subreddit_posts"
    SEARCH_SUBREDDITS = "search_subreddits"
    SEARCH_POST_COMMENTS = "search_post_comments"
    SEARCH_REDDIT_DISCUSSIONS = "search_reddit_discussions"
    SEARCH_REDDIT_URL_COMMENTS = "search_reddit_url_comments"
    GET_POST_CONTENT = "get_post_content"
    GET_POST_COMMENTS = "get_post_comments"


class SubredditInfo(BaseModel):
    name: str
    subscriber_count: int
    description: str | None


class Post(BaseModel):
    id: str
    title: str
    author: str
    score: int
    subreddit: str
    url: str
    created_at: str
    comment_count: int
    post_type: PostType
    content: str | None


class SubredditSearchResult(BaseModel):
    name: str
    subscriber_count: int
    description: str | None
    url: str


class Comment(BaseModel):
    id: str
    author: str
    body: str
    score: int
    subreddit: str | None = None
    url: str | None = None
    created_at: str | None = None
    parent_id: str | None = None
    post_id: str | None = None
    depth: int = 0
    is_submitter: bool = False
    replies: list['Comment'] = Field(default_factory=list)


class Moderator(BaseModel):
    name: str


class PostDetail(BaseModel):
    post: Post
    comments: list[Comment]


class DiscussionCommentMatch(BaseModel):
    post: Post
    comment: Comment


REDDIT_POST_ID_RE = re.compile(r"(?:^|/)comments/([a-z0-9]+)(?:[/?#]|$)", re.IGNORECASE)


def _normalize_post_id(post_id_or_url: str) -> str:
    value = post_id_or_url.strip()
    if value.startswith("t3_"):
        return value[3:]

    match = REDDIT_POST_ID_RE.search(value)
    if match:
        return match.group(1)

    return value


def _build_reddit_client():
    client = redditwarp.SYNC.Client()
    user_agent = os.environ.get("REDDIT_USER_AGENT")
    if user_agent:
        client.set_user_agent(user_agent)

    return client


class RedditServer:
    def __init__(self):
        self.client = _build_reddit_client()

    def _get_post_type(self, submission) -> PostType:
        """Helper method to determine post type"""
        if isinstance(submission, redditwarp.models.submission_SYNC.LinkPost):
            return PostType.LINK
        elif isinstance(submission, redditwarp.models.submission_SYNC.TextPost):
            return PostType.TEXT
        elif isinstance(submission, redditwarp.models.submission_SYNC.GalleryPost):
            return PostType.GALLERY
        return PostType.UNKNOWN

    # The type can actually be determined by submission.post_hint
    # - self for text
    # - image for image
    # - hosted:video for video
    def _get_post_content(self, submission) -> str | None:
        """Helper method to extract post content based on type"""
        if isinstance(submission, redditwarp.models.submission_SYNC.LinkPost):
            return submission.permalink
        elif isinstance(submission, redditwarp.models.submission_SYNC.TextPost):
            return submission.body
        elif isinstance(submission, redditwarp.models.submission_SYNC.GalleryPost):
            return str(submission.gallery_link)
        return None

    def _build_post(self, submission) -> Post:
        """Helper method to build Post object from submission"""
        return Post(
            id=submission.id36,
            title=submission.title,
            author=submission.author_display_name or '[deleted]',
            score=submission.score,
            subreddit=submission.subreddit.name,
            url=submission.permalink,
            created_at=submission.created_at.astimezone().isoformat(),
            comment_count=submission.comment_count,
            post_type=self._get_post_type(submission),
            content=self._get_post_content(submission)
        )

    def _build_subreddit_search_result(self, subreddit) -> SubredditSearchResult:
        """Helper method to build SubredditSearchResult from subreddit search results"""
        return SubredditSearchResult(
            name=subreddit.name,
            subscriber_count=subreddit.subscriber_count,
            description=subreddit.public_description,
            url=f"https://www.reddit.com/r/{subreddit.name}/"
        )

    def get_frontpage_posts(self, limit: int = 10) -> list[Post]:
        """Get hot posts from Reddit frontpage"""
        posts = []
        for subm in self.client.p.front.pull.hot(limit):
            posts.append(self._build_post(subm))
        return posts

    def get_subreddit_info(self, subreddit_name: str) -> SubredditInfo:
        """Get information about a subreddit"""
        subr = self.client.p.subreddit.fetch_by_name(subreddit_name)
        return SubredditInfo(
            name=subr.name,
            subscriber_count=subr.subscriber_count,
            description=subr.public_description
        )

    def _expand_more_comments(
        self,
        more,
        depth: int,
        expand_more: bool,
        more_state: dict[str, int],
        current_depth: int,
    ) -> list[Comment]:
        if not expand_more or not more or depth <= 0 or more_state["remaining"] <= 0:
            return []

        more_state["remaining"] -= 1
        more_node = more(depth=depth)
        comments = []
        for child in more_node.children:
            child_comment = self._build_comment_tree(
                child,
                depth,
                expand_more,
                more_state,
                current_depth,
            )
            if child_comment:
                comments.append(child_comment)

        comments.extend(self._expand_more_comments(
            more_node.more,
            depth,
            expand_more,
            more_state,
            current_depth,
        ))
        return comments

    def _build_comment_tree(
        self,
        node,
        depth: int = 3,
        expand_more: bool = False,
        more_state: dict[str, int] | None = None,
        current_depth: int = 1,
    ) -> Comment | None:
        """Helper method to recursively build comment tree"""
        if depth <= 0 or not node:
            return None

        if more_state is None:
            more_state = {"remaining": 0}

        comment = node.value
        replies = []
        for child in node.children:
            child_comment = self._build_comment_tree(
                child,
                depth - 1,
                expand_more,
                more_state,
                current_depth + 1,
            )
            if child_comment:
                replies.append(child_comment)

        replies.extend(self._expand_more_comments(
            node.more,
            depth - 1,
            expand_more,
            more_state,
            current_depth + 1,
        ))

        return Comment(
            id=comment.id36,
            author=comment.author_display_name or '[deleted]',
            body=comment.body,
            score=comment.score,
            subreddit=comment.subreddit.name,
            url=comment.permalink,
            created_at=comment.created_at.astimezone().isoformat(),
            parent_id=comment.parent_comment_id36 or None,
            post_id=comment.submission.id36,
            depth=current_depth,
            is_submitter=comment.is_submitter,
            replies=replies
        )

    def _get_post_comments_with_post(
        self,
        post_id: str,
        limit: int = 10,
        depth: int = 3,
        sort: str = "top",
        expand_more: bool = False,
        max_more_batches: int = 0,
    ) -> tuple[Post, list[Comment]]:
        tree_node = self.client.p.comment_tree.fetch(
            _normalize_post_id(post_id),
            sort=sort,
            limit=limit,
            depth=depth,
        )
        post = self._build_post(tree_node.value)
        more_state = {"remaining": max(0, max_more_batches if expand_more else 0)}
        comments = []
        for node in tree_node.children:
            comment = self._build_comment_tree(node, depth, expand_more, more_state)
            if comment:
                comments.append(comment)

        comments.extend(self._expand_more_comments(
            tree_node.more,
            depth,
            expand_more,
            more_state,
            1,
        ))
        return post, comments

    def _flatten_comments(self, comments: list[Comment]) -> list[Comment]:
        flattened = []
        for comment in comments:
            flattened.append(comment)
            flattened.extend(self._flatten_comments(comment.replies))
        return flattened

    def _comment_matches_query(self, comment: Comment, query: str, match_mode: str) -> bool:
        text = comment.body.casefold()
        normalized_query = query.strip().casefold()
        if not normalized_query:
            return True

        if match_mode == "phrase":
            return normalized_query in text

        terms = [
            term
            for term in re.findall(r"[a-z0-9][a-z0-9_'-]*", normalized_query)
            if len(term) >= 3
        ]
        if not terms:
            return normalized_query in text

        hits = sum(1 for term in terms if term in text)
        if match_mode == "all_terms":
            return hits == len(terms)
        return hits > 0

    def _without_replies(self, comment: Comment) -> Comment:
        return comment.model_copy(update={"replies": []})

    def get_subreddit_hot_posts(self, subreddit_name: str, limit: int = 10) -> list[Post]:
        """Get hot posts from a specific subreddit"""
        posts = []
        for subm in self.client.p.subreddit.pull.hot(subreddit_name, limit):
            posts.append(self._build_post(subm))
        return posts

    def get_subreddit_new_posts(self, subreddit_name: str, limit: int = 10) -> list[Post]:
        """Get new posts from a specific subreddit"""
        posts = []
        for subm in self.client.p.subreddit.pull.new(subreddit_name, limit):
            posts.append(self._build_post(subm))
        return posts

    def get_subreddit_top_posts(self, subreddit_name: str, limit: int = 10, time: str = '') -> list[Post]:
        """Get top posts from a specific subreddit"""
        posts = []
        for subm in self.client.p.subreddit.pull.top(subreddit_name, limit, time=time):
            posts.append(self._build_post(subm))
        return posts

    def get_subreddit_rising_posts(self, subreddit_name: str, limit: int = 10) -> list[Post]:
        """Get rising posts from a specific subreddit"""
        posts = []
        for subm in self.client.p.subreddit.pull.rising(subreddit_name, limit):
            posts.append(self._build_post(subm))
        return posts

    def search_reddit_posts(
        self,
        query: str,
        limit: int = 25,
        sort: str = "relevance",
        time: str = "all",
    ) -> list[Post]:
        """Search posts across Reddit"""
        posts = []
        for subm in self.client.p.submission.search("", query, limit, sort=sort, time=time):
            posts.append(self._build_post(subm))
        return posts

    def search_subreddit_posts(
        self,
        subreddit_name: str,
        query: str,
        limit: int = 25,
        sort: str = "relevance",
        time: str = "all",
    ) -> list[Post]:
        """Search posts in a specific subreddit"""
        posts = []
        for subm in self.client.p.submission.search(subreddit_name, query, limit, sort=sort, time=time):
            posts.append(self._build_post(subm))
        return posts

    def search_subreddits(self, query: str, limit: int = 25) -> list[SubredditSearchResult]:
        """Search subreddits by name or description"""
        subreddits = []
        for subr in self.client.p.subreddit.search(query, limit):
            subreddits.append(self._build_subreddit_search_result(subr))
        return subreddits

    def search_post_comments(
        self,
        post_id: str,
        query: str,
        result_limit: int = 25,
        comment_limit: int = 500,
        depth: int = 10,
        sort: str = "confidence",
        match_mode: str = "any_terms",
        expand_more: bool = True,
        max_more_batches: int = 10,
    ) -> list[Comment]:
        """Search fetched comments from a post for matching text"""
        _, comments = self._get_post_comments_with_post(
            post_id,
            comment_limit,
            depth,
            sort,
            expand_more,
            max_more_batches,
        )
        matches = []
        for comment in self._flatten_comments(comments):
            if self._comment_matches_query(comment, query, match_mode):
                matches.append(self._without_replies(comment))
                if len(matches) >= result_limit:
                    break
        return matches

    def search_reddit_url_comments(
        self,
        post_urls: list[str],
        query: str,
        result_limit: int = 25,
        comment_limit: int = 500,
        depth: int = 10,
        sort: str = "confidence",
        match_mode: str = "any_terms",
        expand_more: bool = True,
        max_more_batches_per_post: int = 10,
    ) -> list[DiscussionCommentMatch]:
        """Search comments from a batch of Reddit post URLs or IDs"""
        if isinstance(post_urls, str):
            post_urls = [post_urls]

        results = []
        for post_url in post_urls:
            post, comments = self._get_post_comments_with_post(
                post_url,
                comment_limit,
                depth,
                sort,
                expand_more,
                max_more_batches_per_post,
            )
            for comment in self._flatten_comments(comments):
                if self._comment_matches_query(comment, query, match_mode):
                    results.append(DiscussionCommentMatch(
                        post=post,
                        comment=self._without_replies(comment),
                    ))
                    if len(results) >= result_limit:
                        return results
        return results

    def search_reddit_discussions(
        self,
        query: str,
        subreddit_name: str = "",
        post_limit: int = 10,
        result_limit: int = 25,
        post_sort: str = "relevance",
        post_time: str = "all",
        comment_limit: int = 500,
        comment_depth: int = 10,
        comment_sort: str = "confidence",
        match_mode: str = "any_terms",
        expand_more: bool = True,
        max_more_batches_per_post: int = 5,
    ) -> list[DiscussionCommentMatch]:
        """Search posts, then search fetched comments from those candidate posts"""
        if subreddit_name:
            posts = self.search_subreddit_posts(
                subreddit_name,
                query,
                post_limit,
                post_sort,
                post_time,
            )
        else:
            posts = self.search_reddit_posts(query, post_limit, post_sort, post_time)

        results = []
        for post in posts:
            comments = self.search_post_comments(
                post.id,
                query,
                result_limit - len(results),
                comment_limit,
                comment_depth,
                comment_sort,
                match_mode,
                expand_more,
                max_more_batches_per_post,
            )
            for comment in comments:
                results.append(DiscussionCommentMatch(post=post, comment=comment))
                if len(results) >= result_limit:
                    return results
        return results

    def get_post_content(
        self,
        post_id: str,
        comment_limit: int = 10,
        comment_depth: int = 3,
        comment_sort: str = "top",
        expand_more: bool = False,
        max_more_batches: int = 0,
    ) -> PostDetail:
        """Get detailed content of a specific post including comments"""
        post, comments = self._get_post_comments_with_post(
            post_id,
            comment_limit,
            comment_depth,
            comment_sort,
            expand_more,
            max_more_batches,
        )
        return PostDetail(post=post, comments=comments)

    def get_post_comments(
        self,
        post_id: str,
        limit: int = 10,
        depth: int = 3,
        sort: str = "top",
        expand_more: bool = False,
        max_more_batches: int = 0,
    ) -> list[Comment]:
        """Get comments from a post"""
        _, comments = self._get_post_comments_with_post(
            post_id,
            limit,
            depth,
            sort,
            expand_more,
            max_more_batches,
        )
        return comments


async def serve() -> None:
    server = Server("mcp-reddit")
    reddit_server = RedditServer()

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """List available Reddit tools."""
        return [
            Tool(
                name=RedditTools.GET_FRONTPAGE_POSTS.value,
                description="Get hot posts from Reddit frontpage",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "description": "Number of posts to return (default: 10)",
                            "default": 10,
                            "minimum": 1,
                            "maximum": 100
                        }
                    }
                }
            ),
            Tool(
                name=RedditTools.GET_SUBREDDIT_INFO.value,
                description="Get information about a subreddit",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "subreddit_name": {
                            "type": "string",
                            "description": "Name of the subreddit (e.g. 'Python', 'news')",
                        }
                    },
                    "required": ["subreddit_name"]
                }
            ),
            Tool(
                name=RedditTools.GET_SUBREDDIT_HOT_POSTS.value,
                description="Get hot posts from a specific subreddit",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "subreddit_name": {
                            "type": "string",
                            "description": "Name of the subreddit (e.g. 'Python', 'news')",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Number of posts to return (default: 10)",
                            "default": 10,
                            "minimum": 1,
                            "maximum": 100
                        }
                    },
                    "required": ["subreddit_name"]
                }
            ),
            Tool(
                name=RedditTools.GET_SUBREDDIT_NEW_POSTS.value,
                description="Get new posts from a specific subreddit",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "subreddit_name": {
                            "type": "string",
                            "description": "Name of the subreddit (e.g. 'Python', 'news')",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Number of posts to return (default: 10)",
                            "default": 10,
                            "minimum": 1,
                            "maximum": 100
                        }
                    },
                    "required": ["subreddit_name"]
                }
            ),
            Tool(
                name=RedditTools.GET_SUBREDDIT_TOP_POSTS.value,
                description="Get top posts from a specific subreddit",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "subreddit_name": {
                            "type": "string",
                            "description": "Name of the subreddit (e.g. 'Python', 'news')",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Number of posts to return (default: 10)",
                            "default": 10,
                            "minimum": 1,
                            "maximum": 100
                        },
                        "time": {
                            "type": "string",
                            "description": "Time filter for top posts (e.g. 'hour', 'day', 'week', 'month', 'year', 'all')",
                            "default": "",
                            "enum": ["", "hour", "day", "week", "month", "year", "all"]
                        }
                    },
                    "required": ["subreddit_name"]
                }
            ),
            Tool(
                name=RedditTools.GET_SUBREDDIT_RISING_POSTS.value,
                description="Get rising posts from a specific subreddit",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "subreddit_name": {
                            "type": "string",
                            "description": "Name of the subreddit (e.g. 'Python', 'news')",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Number of posts to return (default: 10)",
                            "default": 10,
                            "minimum": 1,
                            "maximum": 100
                        }
                    },
                    "required": ["subreddit_name"]
                }
            ),
            Tool(
                name=RedditTools.SEARCH_REDDIT_POSTS.value,
                description="Search posts across Reddit",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Number of posts to return (default: 25)",
                            "default": 25,
                            "minimum": 1,
                            "maximum": 100
                        },
                        "sort": {
                            "type": "string",
                            "description": "Sort order (default: 'relevance')",
                            "default": "relevance",
                            "enum": ["relevance", "hot", "top", "new", "comments"]
                        },
                        "time": {
                            "type": "string",
                            "description": "Time filter for search results (default: 'all')",
                            "default": "all",
                            "enum": ["all", "hour", "day", "week", "month", "year"]
                        }
                    },
                    "required": ["query"]
                }
            ),
            Tool(
                name=RedditTools.SEARCH_SUBREDDIT_POSTS.value,
                description="Search posts in a specific subreddit",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "subreddit_name": {
                            "type": "string",
                            "description": "Name of the subreddit (e.g. 'Python', 'news')",
                        },
                        "query": {
                            "type": "string",
                            "description": "Search query",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Number of posts to return (default: 25)",
                            "default": 25,
                            "minimum": 1,
                            "maximum": 100
                        },
                        "sort": {
                            "type": "string",
                            "description": "Sort order (default: 'relevance')",
                            "default": "relevance",
                            "enum": ["relevance", "hot", "top", "new", "comments"]
                        },
                        "time": {
                            "type": "string",
                            "description": "Time filter for search results (default: 'all')",
                            "default": "all",
                            "enum": ["all", "hour", "day", "week", "month", "year"]
                        }
                    },
                    "required": ["subreddit_name", "query"]
                }
            ),
            Tool(
                name=RedditTools.SEARCH_SUBREDDITS.value,
                description="Search subreddits by name or description",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Number of subreddits to return (default: 25)",
                            "default": 25,
                            "minimum": 1,
                            "maximum": 100
                        }
                    },
                    "required": ["query"]
                }
            ),
            Tool(
                name=RedditTools.SEARCH_POST_COMMENTS.value,
                description="Search fetched comments from a Reddit post ID or URL",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "post_id": {
                            "type": "string",
                            "description": "Post ID, t3 fullname, or Reddit comments URL",
                        },
                        "query": {
                            "type": "string",
                            "description": "Comment search query",
                        },
                        "result_limit": {
                            "type": "integer",
                            "description": "Maximum matching comments to return (default: 25)",
                            "default": 25,
                            "minimum": 1,
                            "maximum": 100
                        },
                        "comment_limit": {
                            "type": "integer",
                            "description": "Number of comments to fetch before local matching (default: 500)",
                            "default": 500,
                            "minimum": 1,
                            "maximum": 500
                        },
                        "depth": {
                            "type": "integer",
                            "description": "Maximum depth of comment tree to fetch (default: 10)",
                            "default": 10,
                            "minimum": 1,
                            "maximum": 10
                        },
                        "sort": {
                            "type": "string",
                            "description": "Comment sort order (default: 'confidence')",
                            "default": "confidence",
                            "enum": ["confidence", "top", "new", "controversial", "old", "random", "qa", "live"]
                        },
                        "match_mode": {
                            "type": "string",
                            "description": "Local comment matching mode (default: 'any_terms')",
                            "default": "any_terms",
                            "enum": ["any_terms", "all_terms", "phrase"]
                        },
                        "expand_more": {
                            "type": "boolean",
                            "description": "Expand Reddit 'load more comments' branches (default: true)",
                            "default": True
                        },
                        "max_more_batches": {
                            "type": "integer",
                            "description": "Maximum more-comments batches to expand (default: 10)",
                            "default": 10,
                            "minimum": 0,
                            "maximum": 25
                        }
                    },
                    "required": ["post_id", "query"]
                }
            ),
            Tool(
                name=RedditTools.SEARCH_REDDIT_URL_COMMENTS.value,
                description="Search comments from a batch of Reddit post URLs or IDs",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "post_urls": {
                            "type": "array",
                            "description": "Reddit post URLs, IDs, or t3 fullnames from a search engine",
                            "items": {"type": "string"},
                            "minItems": 1,
                            "maxItems": 25
                        },
                        "query": {
                            "type": "string",
                            "description": "Comment search query",
                        },
                        "result_limit": {
                            "type": "integer",
                            "description": "Maximum matching comments to return across all posts (default: 25)",
                            "default": 25,
                            "minimum": 1,
                            "maximum": 100
                        },
                        "comment_limit": {
                            "type": "integer",
                            "description": "Number of comments to fetch per post before local matching (default: 500)",
                            "default": 500,
                            "minimum": 1,
                            "maximum": 500
                        },
                        "depth": {
                            "type": "integer",
                            "description": "Maximum depth of comment tree to fetch (default: 10)",
                            "default": 10,
                            "minimum": 1,
                            "maximum": 10
                        },
                        "sort": {
                            "type": "string",
                            "description": "Comment sort order (default: 'confidence')",
                            "default": "confidence",
                            "enum": ["confidence", "top", "new", "controversial", "old", "random", "qa", "live"]
                        },
                        "match_mode": {
                            "type": "string",
                            "description": "Local comment matching mode (default: 'any_terms')",
                            "default": "any_terms",
                            "enum": ["any_terms", "all_terms", "phrase"]
                        },
                        "expand_more": {
                            "type": "boolean",
                            "description": "Expand Reddit 'load more comments' branches (default: true)",
                            "default": True
                        },
                        "max_more_batches_per_post": {
                            "type": "integer",
                            "description": "Maximum more-comments batches to expand per post (default: 10)",
                            "default": 10,
                            "minimum": 0,
                            "maximum": 25
                        }
                    },
                    "required": ["post_urls", "query"]
                }
            ),
            Tool(
                name=RedditTools.SEARCH_REDDIT_DISCUSSIONS.value,
                description="Search Reddit posts, then search comments from those candidate posts",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query",
                        },
                        "subreddit_name": {
                            "type": "string",
                            "description": "Optional subreddit to restrict the post search",
                            "default": ""
                        },
                        "post_limit": {
                            "type": "integer",
                            "description": "Number of candidate posts to inspect (default: 10)",
                            "default": 10,
                            "minimum": 1,
                            "maximum": 50
                        },
                        "result_limit": {
                            "type": "integer",
                            "description": "Maximum matching comments to return (default: 25)",
                            "default": 25,
                            "minimum": 1,
                            "maximum": 100
                        },
                        "post_sort": {
                            "type": "string",
                            "description": "Post search sort order (default: 'relevance')",
                            "default": "relevance",
                            "enum": ["relevance", "hot", "top", "new", "comments"]
                        },
                        "post_time": {
                            "type": "string",
                            "description": "Post search time filter (default: 'all')",
                            "default": "all",
                            "enum": ["all", "hour", "day", "week", "month", "year"]
                        },
                        "comment_limit": {
                            "type": "integer",
                            "description": "Number of comments to fetch per post before local matching (default: 500)",
                            "default": 500,
                            "minimum": 1,
                            "maximum": 500
                        },
                        "comment_depth": {
                            "type": "integer",
                            "description": "Maximum depth of comment tree to fetch (default: 10)",
                            "default": 10,
                            "minimum": 1,
                            "maximum": 10
                        },
                        "comment_sort": {
                            "type": "string",
                            "description": "Comment sort order (default: 'confidence')",
                            "default": "confidence",
                            "enum": ["confidence", "top", "new", "controversial", "old", "random", "qa", "live"]
                        },
                        "match_mode": {
                            "type": "string",
                            "description": "Local comment matching mode (default: 'any_terms')",
                            "default": "any_terms",
                            "enum": ["any_terms", "all_terms", "phrase"]
                        },
                        "expand_more": {
                            "type": "boolean",
                            "description": "Expand Reddit 'load more comments' branches (default: true)",
                            "default": True
                        },
                        "max_more_batches_per_post": {
                            "type": "integer",
                            "description": "Maximum more-comments batches to expand per post (default: 5)",
                            "default": 5,
                            "minimum": 0,
                            "maximum": 25
                        }
                    },
                    "required": ["query"]
                }
            ),
            Tool(
                name=RedditTools.GET_POST_CONTENT.value,
                description="Get detailed content of a specific post",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "post_id": {
                            "type": "string",
                            "description": "Post ID, t3 fullname, or Reddit comments URL",
                        },
                        "comment_limit": {
                            "type": "integer",
                            "description": "Number of top-level comments to return (default: 10)",
                            "default": 10,
                            "minimum": 1,
                            "maximum": 500
                        },
                        "comment_depth": {
                            "type": "integer",
                            "description": "Maximum depth of comment tree (default: 3)",
                            "default": 3,
                            "minimum": 1,
                            "maximum": 10
                        },
                        "comment_sort": {
                            "type": "string",
                            "description": "Comment sort order (default: 'top')",
                            "default": "top",
                            "enum": ["confidence", "top", "new", "controversial", "old", "random", "qa", "live"]
                        },
                        "expand_more": {
                            "type": "boolean",
                            "description": "Expand Reddit 'load more comments' branches (default: false)",
                            "default": False
                        },
                        "max_more_batches": {
                            "type": "integer",
                            "description": "Maximum more-comments batches to expand (default: 0)",
                            "default": 0,
                            "minimum": 0,
                            "maximum": 25
                        }
                    },
                    "required": ["post_id"]
                }
            ),
            Tool(
                name=RedditTools.GET_POST_COMMENTS.value,
                description="Get comments from a post",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "post_id": {
                            "type": "string",
                            "description": "Post ID, t3 fullname, or Reddit comments URL",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Number of comments to return (default: 10)",
                            "default": 10,
                            "minimum": 1,
                            "maximum": 500
                        },
                        "depth": {
                            "type": "integer",
                            "description": "Maximum depth of comment tree (default: 3)",
                            "default": 3,
                            "minimum": 1,
                            "maximum": 10
                        },
                        "sort": {
                            "type": "string",
                            "description": "Comment sort order (default: 'top')",
                            "default": "top",
                            "enum": ["confidence", "top", "new", "controversial", "old", "random", "qa", "live"]
                        },
                        "expand_more": {
                            "type": "boolean",
                            "description": "Expand Reddit 'load more comments' branches (default: false)",
                            "default": False
                        },
                        "max_more_batches": {
                            "type": "integer",
                            "description": "Maximum more-comments batches to expand (default: 0)",
                            "default": 0,
                            "minimum": 0,
                            "maximum": 25
                        }
                    },
                    "required": ["post_id"]
                }
            ),
        ]

    @server.call_tool()
    async def call_tool(
        name: str, arguments: dict
    ) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
        """Handle tool calls for Reddit API."""
        try:
            match name:
                case RedditTools.GET_FRONTPAGE_POSTS.value:
                    limit = arguments.get("limit", 10)
                    result = reddit_server.get_frontpage_posts(limit)

                case RedditTools.GET_SUBREDDIT_INFO.value:
                    subreddit_name = arguments.get("subreddit_name")
                    if not subreddit_name:
                        raise ValueError("Missing required argument: subreddit_name")
                    result = reddit_server.get_subreddit_info(subreddit_name)

                case RedditTools.GET_SUBREDDIT_HOT_POSTS.value:
                    subreddit_name = arguments.get("subreddit_name")
                    if not subreddit_name:
                        raise ValueError("Missing required argument: subreddit_name")
                    limit = arguments.get("limit", 10)
                    result = reddit_server.get_subreddit_hot_posts(subreddit_name, limit)

                case RedditTools.GET_SUBREDDIT_NEW_POSTS.value:
                    subreddit_name = arguments.get("subreddit_name")
                    if not subreddit_name:
                        raise ValueError("Missing required argument: subreddit_name")
                    limit = arguments.get("limit", 10)
                    result = reddit_server.get_subreddit_new_posts(subreddit_name, limit)

                case RedditTools.GET_SUBREDDIT_TOP_POSTS.value:
                    subreddit_name = arguments.get("subreddit_name")
                    if not subreddit_name:
                        raise ValueError("Missing required argument: subreddit_name")
                    limit = arguments.get("limit", 10)
                    time = arguments.get("time", "")
                    result = reddit_server.get_subreddit_top_posts(subreddit_name, limit, time)

                case RedditTools.GET_SUBREDDIT_RISING_POSTS.value:
                    subreddit_name = arguments.get("subreddit_name")
                    if not subreddit_name:
                        raise ValueError("Missing required argument: subreddit_name")
                    limit = arguments.get("limit", 10)
                    result = reddit_server.get_subreddit_rising_posts(subreddit_name, limit)

                case RedditTools.SEARCH_REDDIT_POSTS.value:
                    query = arguments.get("query")
                    if not query:
                        raise ValueError("Missing required argument: query")
                    limit = arguments.get("limit", 25)
                    sort = arguments.get("sort", "relevance")
                    time = arguments.get("time", "all")
                    result = reddit_server.search_reddit_posts(query, limit, sort, time)

                case RedditTools.SEARCH_SUBREDDIT_POSTS.value:
                    subreddit_name = arguments.get("subreddit_name")
                    if not subreddit_name:
                        raise ValueError("Missing required argument: subreddit_name")
                    query = arguments.get("query")
                    if not query:
                        raise ValueError("Missing required argument: query")
                    limit = arguments.get("limit", 25)
                    sort = arguments.get("sort", "relevance")
                    time = arguments.get("time", "all")
                    result = reddit_server.search_subreddit_posts(subreddit_name, query, limit, sort, time)

                case RedditTools.SEARCH_SUBREDDITS.value:
                    query = arguments.get("query")
                    if not query:
                        raise ValueError("Missing required argument: query")
                    limit = arguments.get("limit", 25)
                    result = reddit_server.search_subreddits(query, limit)

                case RedditTools.SEARCH_POST_COMMENTS.value:
                    post_id = arguments.get("post_id")
                    if not post_id:
                        raise ValueError("Missing required argument: post_id")
                    query = arguments.get("query")
                    if not query:
                        raise ValueError("Missing required argument: query")
                    result = reddit_server.search_post_comments(
                        post_id,
                        query,
                        arguments.get("result_limit", 25),
                        arguments.get("comment_limit", 500),
                        arguments.get("depth", 10),
                        arguments.get("sort", "confidence"),
                        arguments.get("match_mode", "any_terms"),
                        arguments.get("expand_more", True),
                        arguments.get("max_more_batches", 10),
                    )

                case RedditTools.SEARCH_REDDIT_URL_COMMENTS.value:
                    post_urls = arguments.get("post_urls")
                    if not post_urls:
                        raise ValueError("Missing required argument: post_urls")
                    query = arguments.get("query")
                    if not query:
                        raise ValueError("Missing required argument: query")
                    result = reddit_server.search_reddit_url_comments(
                        post_urls,
                        query,
                        arguments.get("result_limit", 25),
                        arguments.get("comment_limit", 500),
                        arguments.get("depth", 10),
                        arguments.get("sort", "confidence"),
                        arguments.get("match_mode", "any_terms"),
                        arguments.get("expand_more", True),
                        arguments.get("max_more_batches_per_post", 10),
                    )

                case RedditTools.SEARCH_REDDIT_DISCUSSIONS.value:
                    query = arguments.get("query")
                    if not query:
                        raise ValueError("Missing required argument: query")
                    result = reddit_server.search_reddit_discussions(
                        query,
                        arguments.get("subreddit_name", ""),
                        arguments.get("post_limit", 10),
                        arguments.get("result_limit", 25),
                        arguments.get("post_sort", "relevance"),
                        arguments.get("post_time", "all"),
                        arguments.get("comment_limit", 500),
                        arguments.get("comment_depth", 10),
                        arguments.get("comment_sort", "confidence"),
                        arguments.get("match_mode", "any_terms"),
                        arguments.get("expand_more", True),
                        arguments.get("max_more_batches_per_post", 5),
                    )

                case RedditTools.GET_POST_CONTENT.value:
                    post_id = arguments.get("post_id")
                    if not post_id:
                        raise ValueError("Missing required argument: post_id")
                    comment_limit = arguments.get("comment_limit", 10)
                    comment_depth = arguments.get("comment_depth", 3)
                    comment_sort = arguments.get("comment_sort", "top")
                    expand_more = arguments.get("expand_more", False)
                    max_more_batches = arguments.get("max_more_batches", 0)
                    result = reddit_server.get_post_content(
                        post_id,
                        comment_limit,
                        comment_depth,
                        comment_sort,
                        expand_more,
                        max_more_batches,
                    )

                case RedditTools.GET_POST_COMMENTS.value:
                    post_id = arguments.get("post_id")
                    if not post_id:
                        raise ValueError("Missing required argument: post_id")
                    limit = arguments.get("limit", 10)
                    depth = arguments.get("depth", 3)
                    sort = arguments.get("sort", "top")
                    expand_more = arguments.get("expand_more", False)
                    max_more_batches = arguments.get("max_more_batches", 0)
                    result = reddit_server.get_post_comments(
                        post_id,
                        limit,
                        depth,
                        sort,
                        expand_more,
                        max_more_batches,
                    )

                case _:
                    raise ValueError(f"Unknown tool: {name}")

            return [
                TextContent(type="text", text=json.dumps(result, default=lambda x: x.model_dump(), indent=2))
            ]

        except Exception as e:
            raise ValueError(f"Error processing mcp-server-reddit query: {str(e)}")

    options = server.create_initialization_options()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, options)
