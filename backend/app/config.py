"""
Configuration management
Loads configuration from the project root .env file
"""

import os
from dotenv import load_dotenv

# Load .env file from project root
# Path: AgenikPredict/.env (relative to backend/app/config.py)
project_root_env = os.path.join(os.path.dirname(__file__), '../../.env')

if os.path.exists(project_root_env):
    load_dotenv(project_root_env, override=True)
else:
    # If no root .env, try loading environment variables (for production)
    load_dotenv(override=True)


class Config:
    """Flask configuration class"""

    # Flask config
    SECRET_KEY = os.environ.get('SECRET_KEY', 'agenikpredict-secret-key')
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'

    # Auth config
    JWT_SECRET = os.environ.get('JWT_SECRET', SECRET_KEY)
    RESEND_API_KEY = os.environ.get('RESEND_API_KEY')
    RESEND_FROM_EMAIL = os.environ.get('RESEND_FROM_EMAIL', 'AgenikPredict <noreply@agenikpredict.com>')
    APP_URL = os.environ.get('APP_URL', 'http://localhost:3000')

    # JSON config - disable ASCII escaping for proper Unicode display
    JSON_AS_ASCII = False

    # LLM config (OpenAI-compatible format)
    LLM_API_KEY = os.environ.get('LLM_API_KEY')
    LLM_BASE_URL = os.environ.get('LLM_BASE_URL', 'https://openrouter.ai/api/v1')
    LLM_MODEL_NAME = os.environ.get('LLM_MODEL_NAME', 'anthropic/claude-sonnet-4.6')

    # OpenAI direct (for Whisper transcription — separate from OpenRouter)
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')

    # Zep config
    ZEP_API_KEY = os.environ.get('ZEP_API_KEY')

    # File upload config
    MAX_CONTENT_LENGTH = 200 * 1024 * 1024  # 200MB (video files can be large)
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '../uploads')
    ALLOWED_EXTENSIONS = {
        'pdf', 'md', 'txt', 'markdown',
        'jpg', 'jpeg', 'png', 'webp', 'gif', 'bmp',
        'mp4', 'mov', 'avi', 'webm', 'mkv',
    }
    IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp', 'gif', 'bmp'}
    VIDEO_EXTENSIONS = {'mp4', 'mov', 'avi', 'webm', 'mkv'}

    # Text processing config
    DEFAULT_CHUNK_SIZE = 500
    DEFAULT_CHUNK_OVERLAP = 50

    # OASIS simulation config
    OASIS_DEFAULT_MAX_ROUNDS = int(os.environ.get('OASIS_DEFAULT_MAX_ROUNDS', '10'))
    OASIS_SIMULATION_DATA_DIR = os.path.join(os.path.dirname(__file__), '../uploads/simulations')

    # OASIS platform available actions
    OASIS_TWITTER_ACTIONS = [
        'CREATE_POST', 'LIKE_POST', 'REPOST', 'FOLLOW', 'DO_NOTHING', 'QUOTE_POST'
    ]
    OASIS_REDDIT_ACTIONS = [
        'LIKE_POST', 'DISLIKE_POST', 'CREATE_POST', 'CREATE_COMMENT',
        'LIKE_COMMENT', 'DISLIKE_COMMENT', 'SEARCH_POSTS', 'SEARCH_USER',
        'TREND', 'REFRESH', 'DO_NOTHING', 'FOLLOW', 'MUTE'
    ]

    # Report Agent config
    REPORT_AGENT_MAX_TOOL_CALLS = int(os.environ.get('REPORT_AGENT_MAX_TOOL_CALLS', '5'))
    REPORT_AGENT_MAX_REFLECTION_ROUNDS = int(os.environ.get('REPORT_AGENT_MAX_REFLECTION_ROUNDS', '2'))
    REPORT_AGENT_TEMPERATURE = float(os.environ.get('REPORT_AGENT_TEMPERATURE', '0.5'))

    # Stripe billing config
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY')
    STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY')
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')
    STRIPE_PRICE_5 = os.environ.get('STRIPE_PRICE_5')
    STRIPE_PRICE_20 = os.environ.get('STRIPE_PRICE_20')
    STRIPE_PRICE_50 = os.environ.get('STRIPE_PRICE_50')
    STRIPE_PRICE_100 = os.environ.get('STRIPE_PRICE_100')

    # Market data config
    TWELVE_DATA_API_KEY = os.environ.get('TWELVE_DATA_API_KEY')

    @classmethod
    def validate(cls):
        """Validate required configuration"""
        errors = []
        if not cls.LLM_API_KEY:
            errors.append("LLM_API_KEY is not configured")
        if not cls.ZEP_API_KEY:
            errors.append("ZEP_API_KEY is not configured")
        return errors
