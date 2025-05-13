import os
import json
from app import app
import io
import csv
import pandas as pd
from flask import render_template, redirect, url_for, request, Flask, send_file, make_response, jsonify

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

@app.route('/download/<product_id>/<format>')
def download_file(product_id, format):
    opinions_path = os.path.join("./app/data/opinions", f"{product_id}.json")
    if not os.path.exists(opinions_path):
        return "Brak danych opinii dla tego produktu.", 404

    with open(opinions_path, "r", encoding="utf-8") as f:
        opinions = json.load(f)

    if not opinions:
        return "Brak opinii do eksportu.", 400

    if format == 'json':
        return jsonify(opinions)

    elif format == 'csv':
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=opinions[0].keys())
        writer.writeheader()
        writer.writerows(opinions)
        response = make_response(output.getvalue())
        response.headers['Content-Disposition'] = f'attachment; filename=product_{product_id}.csv'
        response.mimetype = 'text/csv'
        return response

    elif format == 'xlsx':
        df = pd.DataFrame(opinions)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Opinie')
        output.seek(0)
        return send_file(output,
                         mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                         download_name=f'product_{product_id}.xlsx',
                         as_attachment=True)

    return "Nieznany format", 400