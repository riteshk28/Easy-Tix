import uuid

import os



class Config:

    # Use test keys during development

    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY', 'sk_test_51PjB1DCAG2id8PGup8xoSmRpDVzeVdk6BqlDJ0RtXhTOGASgXmZGv6Axhcqw9pLLsauS2zir5FV0eVixeKkiuscq004ZzZVvIE')

    STRIPE_PUBLIC_KEY = os.environ.get('STRIPE_PUBLIC_KEY', 'pk_test_51PjB1DCAG2id8PGuLWS21ps83GNrfJAFON5BCnUFW5C4AFuCdGqBsP5KzAJDrr0hTAnrIfDsqAw2Z9BhA1Kayaai005XOGltGF')

    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')

    

    # Get this from your Stripe Dashboard > Products > Pro Plan > API ID

    STRIPE_PRICE_IDS = {

        'pro': os.environ.get('STRIPE_PRO_PRICE_ID', 'price_1Qf6ZeCAG2id8PGuxsKmTMSm')

    }

    

    # Other configurations

    SECRET_KEY = 'your-secret-key-here'

    

    # Database configuration with better connection handling

    database_url = os.environ.get('DATABASE_URL', 'sqlite:///servicedesk.db')

    if database_url and 'neon.tech' in database_url:

        if database_url.startswith("postgres://"):

            database_url = database_url.replace("postgres://", "postgresql://", 1)

        

        # Only add sslmode to URL

        if '?' not in database_url:

            database_url += '?sslmode=require'

        elif 'sslmode=' not in database_url:

            database_url += '&sslmode=require'



    SQLALCHEMY_DATABASE_URI = database_url

    SQLALCHEMY_ENGINE_OPTIONS = {

        'pool_pre_ping': True,

        'pool_recycle': 1800,

        'pool_timeout': 30,

        'pool_size': 30,

        'max_overflow': 0

    }

    

    # PostgreSQL specific connect args

    if 'neon.tech' in database_url:

        SQLALCHEMY_ENGINE_OPTIONS['connect_args'] = {

            'connect_timeout': 10,

            'keepalives': 1,

            'keepalives_idle': 30,

            'keepalives_interval': 10,

            'keepalives_count': 5

        }

    

    # MailerSend Configuration

    MAILERSEND_API_KEY = 'mlsn.d42af72d7025054e59908a60bf396c9bc28b6cab4596054e0454becc0000613b'

    MAILERSEND_FROM_EMAIL = 'MS_WiZzl5@trial-jy7zpl9yy25g5vx6.mlsender.net'

    MAILERSEND_FROM_NAME = 'ServiceDesk Support'

    MAILERSEND_DOMAIN = 'trial-jy7zpl9yy25g5vx6.mlsender.net'

    

    # SMTP settings (if needed as backup)

    SMTP_SERVER = 'smtp.mailersend.net'

    SMTP_PORT = 587

    SMTP_USERNAME = 'MS_WiZzl5@trial-jy7zpl9yy25g5vx6.mlsender.net'

    SMTP_PASSWORD = '9MxEBy0e1C1aAvev' 

    

    # Email Configuration

    CLOUDMAILIN_ADDRESS = '364fe2ab6334d1d485a5@cloudmailin.net'

    CLOUDMAILIN_API_KEY = '364fe2ab6334d1d485a5'  # The part before @ in your address

    CLOUDMAILIN_BASE_URL = 'https://api.cloudmailin.com/api/v0.1'

    CLOUDMAILIN_TARGET_URL = 'https://easy-tix-gold.vercel.app/api/email/incoming'  # Your webhook URL

    

    # Remove these as we'll use the CloudMailin address directly

    # SUPPORT_EMAIL_ALIAS = f'support-{uuid.uuid4()}@cloudmailin.net'

    # GMAIL_FORWARD_TEST = True

    

    # Remove duplicate entries

    # CLOUDMAILIN_WEBHOOK_URL = '...'  # Remove this as we use TARGET_URL instead 

    

    # CloudMailin Configuration

    CLOUDMAILIN_ADDRESS = '364fe2ab6334d1d485a5@cloudmailin.net'

    CLOUDMAILIN_WEBHOOK_URL = 'https://easy-tix-gold.vercel.app/api/email/incoming'  # Get this from ngrok 

    

    # Update application name

    APP_NAME = "Easy-Tix"

    APP_TAGLINE = "HelpDesk Made Easy"    

    # Superadmin setup

    SETUP_KEY = 'setup_key_123456789'  # Change this to something secure

    SUPERADMIN_EMAIL = os.getenv('SUPERADMIN_EMAIL')

    SUPERADMIN_PASSWORD = os.getenv('SUPERADMIN_PASSWORD')

    # Skip webhook verification in development
    if os.environ.get('FLASK_ENV') == 'development':
        STRIPE_WEBHOOK_SECRET = None

    # SuperAdmin Support Portal URL
    SUPERADMIN_PORTAL_URL = 'https://easy-tix-gold.vercel.app/public/e9d78280-f5cb-47f3-8b3d-6a99ce658767/submit'


