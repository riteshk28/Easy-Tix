import uuid

import os



class Config:

    # Use test keys during development

    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY')

    STRIPE_PUBLIC_KEY = os.environ.get('STRIPE_PUBLIC_KEY')

    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')

    

    # Get this from your Stripe Dashboard > Products > Pro Plan > API ID

    STRIPE_PRICE_IDS = {

        'pro': os.environ.get('STRIPE_PRO_PRICE_ID')

    }

    

    # Other configurations

    SECRET_KEY = os.environ.get('SECRET_KEY', 'your-secret-key-here')

    # CSRF settings
    WTF_CSRF_ENABLED = True
    WTF_CSRF_SECRET_KEY = os.environ.get('WTF_CSRF_SECRET_KEY', SECRET_KEY)

    

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

    MAILERSEND_API_KEY = os.getenv('MAILERSEND_API_KEY')

    MAILERSEND_FROM_EMAIL = os.getenv('MAILERSEND_FROM_EMAIL')

    MAILERSEND_FROM_NAME = os.getenv('MAILERSEND_FROM_NAME', 'Easy-Tix Support')

    MAILERSEND_DOMAIN = os.getenv('MAILERSEND_DOMAIN')

    MAILERSEND_PASSWORD_RESET_TEMPLATE_ID = os.getenv('MAILERSEND_PASSWORD_RESET_TEMPLATE_ID')

    

    # SMTP settings (if needed as backup)

    SMTP_SERVER = 'smtp.mailersend.net'

    SMTP_PORT = 587

    SMTP_USERNAME = os.getenv('SMTP_USERNAME')

    SMTP_PASSWORD = os.getenv('SMTP_PASSWORD') 

    

    # Email Configuration

    CLOUDMAILIN_ADDRESS = os.getenv('CLOUDMAILIN_ADDRESS') 

    CLOUDMAILIN_API_KEY = os.getenv('CLOUDMAILIN_API_KEY')  # The part before @ in your address

    CLOUDMAILIN_BASE_URL = os.getenv('CLOUDMAILIN_BASE_URL')

    CLOUDMAILIN_TARGET_URL = os.getenv('CLOUDMAILIN_TARGET_URL')  # Your webhook URL

    

    # Remove these as we'll use the CloudMailin address directly

    # SUPPORT_EMAIL_ALIAS = f'support-{uuid.uuid4()}@cloudmailin.net'

    # GMAIL_FORWARD_TEST = True

    

    # Remove duplicate entries

    # CLOUDMAILIN_WEBHOOK_URL = '...'  # Remove this as we use TARGET_URL instead 

    

    # CloudMailin Configuration

  

    CLOUDMAILIN_WEBHOOK_URL = 'https://easy-tix-gold.vercel.app/api/email/incoming'  # Get this from ngrok 

    

    # Update application name

    APP_NAME = "Easy-Tix"

    APP_TAGLINE = "HelpDesk Made Easy"    

    # Superadmin setup

    SETUP_KEY = os.getenv('SETUP_KEY')  # Change this to something secure

    SUPERADMIN_EMAIL = os.getenv('SUPERADMIN_EMAIL')

    SUPERADMIN_PASSWORD = os.getenv('SUPERADMIN_PASSWORD')

    # Skip webhook verification in development
    if os.environ.get('FLASK_ENV') == 'development':
        STRIPE_WEBHOOK_SECRET = None

    # SuperAdmin Support Portal URL
    SUPERADMIN_PORTAL_URL = 'https://easy-tix-gold.vercel.app/public/e9d78280-f5cb-47f3-8b3d-6a99ce658767/submit'

    # Add to existing Config class
    METABASE_URL = os.getenv('METABASE_URL')
    METABASE_SECRET_KEY = os.getenv('METABASE_SECRET_KEY')


