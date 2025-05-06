import os
import json
from app import app
from flask import render_template, redirect, url_for, request

@app.route('/')
def index():
    return render_template("index.html")

@app.route('/extract', methods=['post'])
def extract_data():
    product_id = request.form.get('product_id')
    return redirect(url_for('product', product_id=product_id))

@app.route('/extract', methods=['get'])
def display_form():
    return render_template("extract.html")

@app.route('/products')
def products():
    products = []
    for file in os.listdir("./app/data/products"):
        if file.endswith(".json"):
            with open(os.path.join("./app/data/products", file), "r", encoding="utf-8") as f:
                data = json.load(f)
                products.append(data)
    return render_template("products.html", products=products)

@app.route('/author')
def author():
    return render_template("author.html")

@app.route('/product/<product_id>')
def product(product_id):
    product_path = os.path.join("./app/data/products", f"{product_id}.json")
    if not os.path.exists(product_path):
        return f"Produkt o ID {product_id} nie istnieje.", 404
    with open(product_path, "r", encoding="utf-8") as f:
        product_data = json.load(f)
    opinions_path = os.path.join("./app/data/opinions", f"{product_id}.json")
    if os.path.exists(opinions_path):
        with open(opinions_path, "r", encoding="utf-8") as f:
            opinions_data = json.load(f)
    else:
        opinions_data = []
    return render_template("product.html", product=product_data, opinions=opinions_data)