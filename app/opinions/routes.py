# app/opinions/routes.py

from . import opinions_bp
from flask import render_template, redirect, url_for, request, jsonify, make_response, send_file
import os
import json
import requests
import io
from bs4 import BeautifulSoup
import csv
import pandas as pd

# --- Funkcje pomocnicze ---
def list_to_html(l):
    """Konwertuje listę stringów na listę HTML <ul><li>...</li></ul>."""
    return "<ul>" + "".join([f"<li>{e}</li>" for e in l]) + "</ul>" if l else ""

def truncate_text(text, max_length=100): # Zmieniono max_length na 100 zgodnie z Twoją prośbą
    """
    Skraca tekst do określonej długości, dodając "..." i zwraca skrócony oraz pełny tekst.
    Zwraca (skrócony_tekst, reszta_tekstu_do_rozwiniecia)
    """
    if not text:
        return "", ""
    if not isinstance(text, str):
        # Konwertuj na string, jeśli nie jest (np. None, int, float, list itp.)
        text = str(text)

    if len(text) > max_length: # Zmieniono warunek na > max_length
        return text[:max_length] + "...", text[max_length:]
    return text, "" # Pełny tekst, brak potrzeby rozwijania

def extract(ancestor, selector, attribute=None, multiple=False):
    """
    Ekstrahuje dane z elementu BeautifulSoup.
    ancestor: obiekt BeautifulSoup, z którego wyszukujemy.
    selector: selektor CSS do znalezienia elementu.
    attribute: atrybut do pobrania (np. 'href', 'data-entry-id'). Jeśli None, pobiera tekst.
    multiple: True, jeśli chcemy pobrać listę wszystkich pasujących elementów, False dla pierwszego.
    """
    if selector:
        if multiple:
            # Upewnij się, że atrybut istnieje, zanim spróbujesz go pobrać
            if attribute:
                return [tag[attribute].strip() for tag in ancestor.select(selector) if attribute in tag.attrs]
            return [tag.text.strip() for tag in ancestor.select(selector)]
        if attribute:
            try:
                found_tag = ancestor.select_one(selector)
                if found_tag and attribute in found_tag.attrs:
                    return found_tag[attribute].strip()
                return None
            except TypeError: # Może wystąpić, jeśli select_one zwróci None
                return None
        try:
            found_tag = ancestor.select_one(selector)
            if found_tag:
                return found_tag.text.strip()
            return None
        except AttributeError: # Może wystąpić, jeśli select_one zwróci None
            return None
    if attribute:
        # Jeśli selektor jest None, pracujemy bezpośrednio na ancestor
        if attribute in ancestor.attrs:
            return ancestor[attribute].strip()
        return None
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



### Trasy Blueprintu (`opinions_bp`)


@opinions_bp.route('/extract', methods=['post'])
def extract_data():
    """
    Obsługuje żądania POST do ekstrakcji opinii dla danego product_id.
    Pobiera opinie z Ceneo.pl, zapisuje je do pliku JSON i przekierowuje
    na stronę szczegółów produktu.
    """
    product_id = request.form.get('product_id')
    print(f"DEBUG: Próba ekstrakcji dla ID: {product_id}")

    if not product_id:
        error = "Nie podano kodu produktu."
        print(f"DEBUG: Brak ID produktu. Błąd: {error}")
        return render_template("extract.html", error=error)
    
    url = f"https://www.ceneo.pl/{product_id}#tab=reviews"
    print(f"DEBUG: Próba pobrania URL: {url}")

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        print(f"DEBUG: Status kodu odpowiedzi: {response.status_code}")
    except requests.exceptions.RequestException as e:
        error = f"Błąd podczas pobierania strony produktu ({product_id}): {e}"
        print(f"DEBUG: Wystąpił błąd podczas requests.get: {e}")
        return render_template("extract.html", error=error)

    page_dom = BeautifulSoup(response.text, "html.parser")

    # === Ekstrakcja nazwy produktu ===
    product_name_element = page_dom.select_one('h1.product-top__product-info__name')
    product_name = product_name_element.text.strip() if product_name_element else f"Nieznany produkt ({product_id})"
    print(f"DEBUG: Wyekstrahowana nazwa produktu: {product_name}")

    opinions_html = page_dom.select("div.js_product-review:not(.user-post--highlighted)")
    print(f"DEBUG: Znaleziono {len(opinions_html)} elementów opinii HTML.")

    data_dir = os.path.join(opinions_bp.root_path, '..', 'data')
    opinions_dir = os.path.join(data_dir, 'opinions')
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(opinions_dir, exist_ok=True)
    file_path = os.path.join(opinions_dir, f"{product_id}.json")
    print(f"DEBUG: Docelowa ścieżka pliku: {file_path}")

    if opinions_html:
        all_opinions=[]
        for opinion_element in opinions_html:
            single_opinion = {
                key: extract(opinion_element, *value) for key, value in selectors.items()
            }
            # Dodatkowe logowanie dla poszczególnych opinii
            # print(f"DEBUG: Wyekstrahowana treść opinii (pierwsze 50 znaków): {single_opinion.get('content', '')[:50]}")
            all_opinions.append(single_opinion)

        print(f"DEBUG: Wyekstrahowano {len(all_opinions)} opinii.")

        product_data_to_save = {
            "product_id": product_id,
            "product_name": product_name,
            "opinions": all_opinions
        }

        try:
            with open(file_path, "w", encoding="UTF-8") as jf:
                json.dump(product_data_to_save, jf, indent=4, ensure_ascii=False)
            print(f"DEBUG: Plik {product_id}.json został pomyślnie zapisany.")
            return redirect(url_for('opinions.product', product_id=product_id))
        except IOError as e:
            error = f"Błąd zapisu pliku dla produktu ({product_id}): {e}"
            print(f"DEBUG: Błąd zapisu pliku: {e}")
            return render_template("extract.html", error=error)
    else:
        # Jeśli brak opinii, ale jest nazwa produktu, też możemy ją zapisać z pustą listą opinii
        product_data_to_save = {
            "product_id": product_id,
            "product_name": product_name,
            "opinions": []
        }

        try:
            with open(file_path, "w", encoding="UTF-8") as jf:
                json.dump(product_data_to_save, jf, indent=4, ensure_ascii=False)
            print(f"DEBUG: Plik {product_id}.json został zapisany z pustą listą opinii.")
        except IOError as e:
            error = f"Błąd zapisu pustego pliku dla produktu ({product_id}): {e}"
            print(f"DEBUG: Błąd zapisu pustego pliku: {e}")
            return render_template("extract.html", error=error)


        error = f"Dla produktu o kodzie {product_id} ({product_name}) nie znaleziono opinii na stronie. Dane produktu zostały zapisane."
        print(f"DEBUG: Brak opinii. Komunikat błędu dla użytkownika: {error}")
        return render_template("extract.html", error=error)


@opinions_bp.route('/extract', methods=['get'])
def display_form():
    """Wyświetla formularz do wprowadzania kodu produktu."""
    return render_template("extract.html")


@opinions_bp.route('/products')
def products():
    """Wyświetla listę produktów ze statystykami opinii."""
    products_list = []
    opinions_data_dir = os.path.join(opinions_bp.root_path, '..', 'data', 'opinions')

    os.makedirs(opinions_data_dir, exist_ok=True) # Upewnij się, że katalog istnieje

    for file_name in os.listdir(opinions_data_dir):
        if file_name.endswith(".json"):
            product_id = file_name.replace('.json', '')
            file_path = os.path.join(opinions_data_dir, file_name)

            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    full_product_data = json.load(f)

                if "opinions" in full_product_data and isinstance(full_product_data["opinions"], list):
                    opinions = full_product_data["opinions"]
                    product_name = full_product_data.get("product_name", f"Produkt {product_id} (nazwa nieznana)")
                else:
                    opinions = full_product_data
                    product_name = f"Produkt {product_id} (stary format danych)"

                if opinions:
                    df = pd.DataFrame(opinions)
                    df['stars_numeric'] = df['stars'].apply(lambda x: float(x.split('/')[0]) if isinstance(x, str) and '/' in x else 0)

                    recommendation_counts = df['recommendation'].value_counts().to_dict()
                    total_opinions = len(df)

                    product_stats = {
                        "id": product_id,
                        "product_name": product_name,
                        "opinions_count": total_opinions,
                        "average_stars": round(df['stars_numeric'].mean(), 2) if total_opinions > 0 else 0,
                        "recommendation_distr": {
                            "Polecam": recommendation_counts.get("Polecam", 0),
                            "Nie polecam": recommendation_counts.get("Nie polecam", 0),
                            "Brak oceny": total_opinions - recommendation_counts.get("Polecam", 0) - recommendation_counts.get("Nie polecam", 0)
                        },
                        "pros_count": df['pros'].apply(lambda x: len(x) if x else 0).sum(),
                        "cons_count": df['cons'].apply(lambda x: len(x) if x else 0).sum()
                    }
                    products_list.append(product_stats)
                else:
                    products_list.append({
                        "id": product_id,
                        "product_name": product_name,
                        "opinions_count": 0, "average_stars": 0,
                        "recommendation_distr": {"Polecam":0, "Nie polecam":0, "Brak oceny":0},
                        "pros_count":0, "cons_count":0
                    })

            except (json.JSONDecodeError, FileNotFoundError, KeyError, ValueError) as e:
                print(f"Błąd podczas ładowania/przetwarzania pliku {file_name}: {e}")
                products_list.append({
                    "id": product_id,
                    "product_name": f"Produkt {product_id} (błąd danych)",
                    "opinions_count": 0, "average_stars": 0,
                    "recommendation_distr": {"Polecam":0, "Nie polecam":0, "Brak oceny":0},
                    "pros_count":0, "cons_count":0
                })

    products_list.sort(key=lambda x: x['id'])
    return render_template("products.html", products=products_list)


@opinions_bp.route('/product/<product_id>')
def product(product_id):
    """Wyświetla szczegóły i opinie dla konkretnego produktu."""
    opinions_path = os.path.join(opinions_bp.root_path, '..', 'data', 'opinions', f"{product_id}.json")

    try:
        with open(opinions_path, "r", encoding="UTF-8") as jf:
            full_product_data = json.load(jf)

        if "opinions" in full_product_data and isinstance(full_product_data["opinions"], list):
            opinions = full_product_data["opinions"]
            product_name = full_product_data.get("product_name", f"Produkt {product_id} (nazwa nieznana)")
        else:
            opinions = full_product_data
            product_name = f"Produkt {product_id} (stary format danych)"

    except FileNotFoundError:
        error = f"Dla produktu o id {product_id} nie pobrano jeszcze opinii."
        return render_template("product.html", error=error)
    except json.JSONDecodeError:
        error = "Błędny format pliku opinii. Plik może być uszkodzony lub pusty."
        return render_template("product.html", error=error)

    if not opinions:
        error = f"Plik opinii dla produktu o id {product_id} jest pusty lub nie zawiera opinii."
        return render_template("product.html", error=error)

    opinions_df = pd.DataFrame.from_dict(opinions)

    opinions_df['pros'] = opinions_df['pros'].apply(list_to_html)
    opinions_df['cons'] = opinions_df['cons'].apply(list_to_html)

    opinions_df['display_content'] = ''
    opinions_df['full_original_content'] = ''

    for index, row in opinions_df.iterrows():
        short_text, remaining_text = truncate_text(row['content'])
        opinions_df.loc[index, 'display_content'] = short_text
        opinions_df.loc[index, 'full_original_content'] = remaining_text

    return render_template("product.html", opinions=opinions_df, product_id=product_id, product_name=product_name)


@opinions_bp.route('/download/<product_id>/<format>')
def download_file(product_id, format):
    """Udostępnia pliki z opiniami do pobrania w różnych formatach (JSON, CSV, XLSX)."""
    opinions_path = os.path.join(opinions_bp.root_path, '..', 'data', 'opinions', f"{product_id}.json")

    if not os.path.exists(opinions_path):
        return "Brak danych opinii dla tego produktu.", 404

    try:
        with open(opinions_path, "r", encoding="utf-8") as f:
            full_product_data = json.load(f)

        if "opinions" in full_product_data and isinstance(full_product_data["opinions"], list):
            opinions = full_product_data["opinions"]
        else:
            opinions = full_product_data
    except (json.JSONDecodeError, FileNotFoundError):
        return "Błąd wczytywania danych opinii.", 500


    if not opinions:
        return "Brak opinii do eksportu.", 400

    if format == 'json':
        response = make_response(json.dumps(opinions, indent=4, ensure_ascii=False))
        response.headers['Content-Disposition'] = f'attachment; filename=product_{product_id}.json'
        response.mimetype = 'application/json'
        return response

    elif format == 'csv':
        df = pd.DataFrame(opinions)
        output = io.StringIO()
        df.to_csv(output, index=False, quoting=csv.QUOTE_ALL, encoding='utf-8-sig')
        response = make_response(output.getvalue())
        response.headers['Content-Disposition'] = f'attachment; filename=product_{product_id}.csv'
        response.mimetype = 'text/csv'
        response.headers['Content-type'] = 'text/csv; charset=utf-8-sig'
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