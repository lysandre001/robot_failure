"""Stance annotation prompt — keep in sync with paper Appendix B."""

SYSTEM_PROMPT = (
    "You are an expert annotator of Chinese social-media comments about "
    "humanoid robots. Classify the OVERALL STANCE of the comment toward "
    "humanoid robots, given the post it replies to. Output JSON only."
)

USER_TEMPLATE = """\
POST TITLE: {post_title}
POST BODY: {post_body}
ROBOT PERFORMANCE STATE: {post_category}
COMMENT: {comment_text}

Output JSON of the form:
{{"stance": one of "支持" / "中立" / "反对",
 "reason": a one-sentence Chinese justification}}.
Do not output anything outside the JSON object."""


def build_messages(post_title: str, post_body: str, post_category: str, comment_text: str):
    """Return OpenAI/OpenRouter chat-completion messages list."""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": USER_TEMPLATE.format(
                post_title=(post_title or "")[:500],
                post_body=(post_body or "")[:1500],
                post_category=post_category or "unknown",
                comment_text=(comment_text or "").strip()[:1500],
            ),
        },
    ]
