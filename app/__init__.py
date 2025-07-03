from flask import Flask

def create_app():
    app = Flask(__name__)

    # Rejestracja Blueprintu dla głównych tras
    from app.main.routes import main_bp
    app.register_blueprint(main_bp)

    # Rejestracja Blueprintu dla opinii
    from app.opinions.routes import opinions_bp
    app.register_blueprint(opinions_bp)

    # TA LINIA ZOSTAŁA USUNIĘTA: from app import views

    return app

app = create_app()