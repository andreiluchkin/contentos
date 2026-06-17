from enum import Enum


class PipelineStatus(str, Enum):
    INBOX = "inbox"
    IDEA_APPROVED = "idea_approved"
    DRAFT = "draft"
    REVIEW = "review"
    READY = "ready"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    ERROR = "error"


class Platform(str, Enum):
    TELEGRAM = "telegram"
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"
    YOUTUBE = "youtube"
    LINKEDIN = "linkedin"
    X = "x"


class ContentType(str, Enum):
    CASE = "case"
    BREAKDOWN = "breakdown"
    HOW_TO = "how_to"
    OPINION = "opinion"
    ROUNDUP = "roundup"
    STORY = "story"
    OBSERVATION = "observation"
    MISTAKE = "mistake"
    LESSON = "lesson"
    LAUNCH = "launch"


class MediaType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"


class RepurposeSourceType(str, Enum):
    VOICE_NOTE = "voice_note"
    VIDEO_FILE = "video_file"
    YOUTUBE_URL = "youtube_url"
    TEXT = "text"


class KBItemType(str, Enum):
    NOTE = "note"
    CASE = "case"
    POST = "post"
    DOCUMENT = "document"
