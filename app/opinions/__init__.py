from flask import Blueprint

opinions_bp = Blueprint('opinions', __name__, template_folder='templates') # Upewnij się, że jest 'templates'
from . import routes