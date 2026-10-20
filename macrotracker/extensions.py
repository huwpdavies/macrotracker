from flask_migrate import Migrate
from flask_wtf import CSRFProtect
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
migrate = Migrate()
csrf = CSRFProtect()
