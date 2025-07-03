from . import main_bp
from flask import render_template

@main_bp.route('/')
def index():
    return render_template("index.html")

@main_bp.route('/author')
def author():
    return render_template("author.html")