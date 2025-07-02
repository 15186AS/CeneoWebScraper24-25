import os
import json
import requests
from app import app
import io
from bs4 import BeautifulSoup
import csv
import requests
import pandas as pd
from flask import render_template, redirect, url_for, request, Flask, send_file, make_response, jsonify

def list_to_html(l):
    return "<ul>" + "".join([f"<li>{e}</li>" for e in l]) + "</ul>" if l else ""

def extract(ancestor, selector, attribute=None, multiple=False):
    if selector:
        if multiple:
            if attribute:
                return [tag[attribute].strip() for tag in ancestor.select(selector)]
            return [tag.text.strip() for tag in ancestor.select(selector)]
        if attribute:
            try:
                return ancestor.select_one(selector)[attribute].strip()
            except TypeError:
                return None
        try:
            return ancestor.select_one(selector).text.strip()
        except AttributeError:
            return None
    if attribute:
        return ancestor[attribute].strip()
    return None

selectors = {
    "opinion_id": (None,"data-entry-id"),
    "author":("span.user-post__author-name",),
    "recommendation":("span.user-post__author-recomendation > em",),
    "stars":("span.user-post__score-count",),
    "content":("div.user-post__text",),
    "pros":("div.review-feature__item--positive",None,True),
    "cons":("div.review-feature__item--negative",None,True),
    "useful":("button.vote-yes","data-total-vote",),
    "useless":("button.vote-no","data-total-vote",),
    "post_date":("span.user-post__published > time:nth-child(1)","datetime"),
    "purchase_date":("span.user-post__published > time:nth-child(2)","datetime")
    }                         



@app.route('/')
def index():
    return render_template("index.html")

@app.route('/extract', methods=['post'])
def extract_data():
    product_id = request.form.get('product_id')
    url = f"https://www.ceneo.pl/{product_id}#tab=reviews"
    response = requests.get(url)
    if response.status_code==200:
            page_dom = BeautifulSoup(response.text, "html.parser")
            opinions = page_dom.select("div.js_product-review:not(.user-post--highlighted)")
            if opinions:
                all_opinions=[]
                for opinion in opinions:
                    single_opinion = {
                        key: extract(opinion, value,) for key, value in selectors.items()
                    }
                    all_opinions.append(single_opinion)
                try:
                    url = "https://www.ceneo.pl"+extract(page_dom, "a.pagination__next", "href")
                except TypeError:
                    url = None
                if not os.path.exists("./app/data"):
                    os.mkdir(".app/data")
                if not os.path.exists("./app/data/opinions"):
                    os.mkdir(".app/data/opinions")
                with open(f"./app/data/opinions/{product_id}.json","w", encoding="UTF-8") as jf:
                    json.dump(all_opinions, jf, indent=4, ensure_ascii=False)
                return redirect(url_for('product', product_id=product_id))
            else:
                error = "dla produktu o podanym kodzie nie ma opinii"
                return render_template("extract.html", error=error)
        
    error = "cos poszlo nie tak"
    return render_template("extract.html", error=error)


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
    try:
        with open(f"./app/data/opinions/{product_id}.json", "r", encoding="UTF-8") as jf:
            try:
                opinions = json.load(jf)
            except json.JSONDecodeError:
                error = "Błędny format pliku"
                return render_template("product.html", error=error)
    except FileNotFoundError:
        error = "Dla prodktu o podanym id nie pobrano jeszcze opinii"
        return render_template("product.html", error=error)
    opinions = pd.DataFrame.from_dict(opinions)
    opinions.pros = opinions.pros.apply(list_to_html)
    opinions.cons = opinions.cons.apply(list_to_html)

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