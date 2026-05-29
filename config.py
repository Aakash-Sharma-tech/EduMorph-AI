import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'super-secret-key-edumorph'
    
    # Adapt database URL for SQLAlchemy 1.4+ (Render uses postgres:// scheme)
    uri = os.environ.get('DATABASE_URL') or os.environ.get('uri') or 'sqlite:///' + os.path.join(basedir, 'app.db')
    if uri.startswith("postgres://"):
        uri = uri.replace("postgres://", "postgresql://", 1)
        
    SQLALCHEMY_DATABASE_URI = uri
    SQLALCHEMY_TRACK_MODIFICATIONS = False

