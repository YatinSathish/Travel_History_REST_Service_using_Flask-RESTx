#! /usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import sqlite3
import requests
from datetime import datetime
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator
import io
from flask import Flask, request, send_file
from flask_restx import Api, Resource, fields

# Initialize Flask app
app = Flask(__name__)

api = Api(app, title="myTravelHistory", description="Track visited countries", version="1.0")
DB_NAME = f"countries.db" 
conn = sqlite3.connect(DB_NAME, check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS countries (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    native TEXT NOT NULL,
    flag TEXT NOT NULL,
    capital TEXT NOT NULL,
    continent TEXT NOT NULL,
    languages TEXT NOT NULL,  
    currency TEXT NOT NULL,  
    years_visited TEXT NOT NULL,
    last_updated TEXT NOT NULL,
    continent_code TEXT NOT NULL 
)
""")
conn.commit()

# GraphQL API to fetch country info
GRAPHQL_URL = "https://countries.trevorblades.com"

# Defines a REST resource for a specific country based on its 2-letter code
@api.route('/countries/<string:code>')
class CountryResource(Resource):
    @api.expect(api.model('PutCountry', {
        'years_visited': fields.List(fields.Integer, required=False, example=[2011])
    }))

    def put(self, code):
        code = code.upper()
        if len(code) != 2:
            return {"message": "Invalid country code."}, 400

        data = request.json or {}
        years_visited = data.get("years_visited", [])

        current_year = datetime.now().year
        if any(y < 1900 or y > current_year for y in years_visited):
            return {"message": "Years visited must be between 1900 and the current year."}, 400
        years_visited = sorted(set(years_visited))

        cursor.execute("SELECT years_visited FROM countries WHERE code = ?", (code,))
        existing_record = cursor.fetchone()
        is_new = existing_record is None # Checking if record already exists

        query = f"""
        query {{
            country(code: "{code}") {{
                name
                native
                emoji
                capital
                continent {{ code, name }}
                languages {{ code, name, native }}
                currencies
            }}
        }}
        """

        try:
            response = requests.post(GRAPHQL_URL, json={'query': query}, timeout=5)
            response.raise_for_status()
            country_data = response.json().get("data", {}).get("country")
        except requests.exceptions.Timeout:
            return {"message": "External API timed out."}, 504

        if not country_data:
            return {"message": "Country not found."}, 404

        name = country_data["name"]
        native = country_data["native"]
        flag = country_data["emoji"]
        capital = country_data["capital"]
        continent = country_data["continent"]["name"]
        continent_code = country_data["continent"]["code"]
        languages = country_data["languages"]
        currencies = country_data["currencies"]
        last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if existing_record:
            existing_years = set(map(int, existing_record[0].split(","))) if existing_record[0] else set()
            years_visited = sorted(existing_years | set(years_visited))

        languages_str = ",".join(f"{lang['code']}|{lang['name']}|{lang['native']}" for lang in languages)
        currencies_str = ",".join(currencies)
        years_visited_str = ",".join(map(str, years_visited))

        cursor.execute("""
            INSERT INTO countries (code, name, native, flag, capital, continent, languages, currency, years_visited, last_updated, continent_code)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(code) DO UPDATE SET
                years_visited=excluded.years_visited,
                last_updated=excluded.last_updated
        """, (code, name, native, flag, capital, continent, languages_str, currencies_str, years_visited_str, last_updated, continent_code))
        conn.commit()

        cursor.execute("SELECT code FROM countries WHERE code < ? ORDER BY code DESC LIMIT 1", (code,))
        prev_country = cursor.fetchone()
        cursor.execute("SELECT code FROM countries WHERE code > ? ORDER BY code ASC LIMIT 1", (code,))
        next_country = cursor.fetchone()

        host = request.host_url.rstrip("/")
        response_data = {
            "code": code,
            "name": name,
            "native": native,
            "flag": flag,
            "capital": capital,
            "continent": continent,
            "languages": languages,
            "currencies": currencies,
            "years_visited": years_visited,
            "last_updated": last_updated,
            "_links": {
                "self": {"href": f"{host}/countries/{code}"},
                "prev": {"href": f"{host}/countries/{prev_country[0]}"} if prev_country else None,
                "next": {"href": f"{host}/countries/{next_country[0]}"} if next_country else None
            }
        }
        return response_data, 201 if is_new else 200

    def get(self, code):
        page = request.args.get('page', default=1, type=int)
        per_page = request.args.get('per_page', default=10, type=int)
        sort_by = request.args.get('sort_by', default="name", type=str).lower()
        order = request.args.get('order', default="asc", type=str).lower()
        code = code.upper()
        
        if len(code) != 2:
            return {"message": "Invalid country code."}, 400

        cursor.execute("""
            SELECT code, name, native, flag, capital, continent, languages, currency, years_visited, last_updated
            FROM countries WHERE code = ?
        """, (code,))
        country = cursor.fetchone()

        if not country:
            return {"message": "Country not found."}, 404

        code, name, native, flag, capital, continent, languages_str, currencies_str, years_visited_str, last_updated = country

        languages = [{"code": lang.split("|")[0], "name": lang.split("|")[1], "native": lang.split("|")[2]} for lang in languages_str.split(",")] if languages_str else []
        currencies = currencies_str.split(",") if currencies_str else []
        years_visited = list(map(int, years_visited_str.split(","))) if years_visited_str else []

        cursor.execute("SELECT code FROM countries WHERE code < ? ORDER BY code DESC LIMIT 1", (code,))
        prev_country = cursor.fetchone()
        cursor.execute("SELECT code FROM countries WHERE code > ? ORDER BY code ASC LIMIT 1", (code,))
        next_country = cursor.fetchone()

        host = request.host_url.rstrip("/")
        response_data = {
            "code": code,
            "name": name,
            "native": native,
            "flag": flag,
            "capital": capital,
            "continent": continent,
            "languages": languages,
            "currencies": currencies,
            "years_visited": years_visited,
            "last_updated": last_updated,
            "_links": {
                "self": {"href": f"{host}/countries/{code}"},
                "prev": {"href": f"{host}/countries/{prev_country[0]}"} if prev_country else None,
                "next": {"href": f"{host}/countries/{next_country[0]}"} if next_country else None
            }
        }

        return response_data, 200
    
    # DELETE a country from the database
    def delete(self, code):
        code = code.upper()
        if len(code) != 2:
            return {"message": "Invalid country code."}, 400

        cursor.execute("SELECT code, name FROM countries WHERE code = ?", (code,))
        country = cursor.fetchone()
        if not country:
           return {"message": "Country not found."}, 404
        
        country_name = country[1]
        cursor.execute("SELECT code FROM countries WHERE code < ? ORDER BY code DESC LIMIT 1", (code,))
        prev_country = cursor.fetchone()
        cursor.execute("SELECT code FROM countries WHERE code > ? ORDER BY code ASC LIMIT 1", (code,))
        next_country = cursor.fetchone()

        cursor.execute("DELETE FROM countries WHERE code = ?", (code,))
        conn.commit()

        host = request.host_url.rstrip("/")
        response_data = {"message": f"{country_name} deleted"}
        return response_data, 200

    @api.expect(api.model('PatchCountry', {
        'years_visited': fields.List(fields.Integer, required=True, example=[2022, 2023, 2024])
    }))

    # PATCH request to update the years_visited field of a country
    def patch(self, code):
        code = code.upper()
        if len(code) != 2:
            return {"message": "Invalid country code."}, 400

        data = request.json or {}
        new_years = data.get("years_visited", [])

        current_year = datetime.now().year
        if any(y < 1900 or y > current_year for y in new_years):
            return {"message": "Years visited must be between 1900 and the current year."}, 400
        
        cursor.execute("SELECT * FROM countries WHERE code = ?", (code,))
        country = cursor.fetchone()
        if not country:
            return {"message": "Country not found."}, 404

        code, name, native, flag, capital, continent, languages_str, currencies_str, existing_years_str, _, _ = country

        # Merge existing and new years
        existing_years = set(map(int, existing_years_str.split(","))) if existing_years_str else set()
        updated_years = sorted(existing_years | set(new_years))
        updated_years_str = ",".join(map(str, updated_years))

        last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        cursor.execute("""
            UPDATE countries SET years_visited = ?, last_updated = ? WHERE code = ?
        """, (updated_years_str, last_updated, code))
        conn.commit()

        languages = [{"code": lang.split("|")[0], "name": lang.split("|")[1], "native": lang.split("|")[2]} for lang in languages_str.split(",")] if languages_str else []
        currencies = currencies_str.split(",") if currencies_str else []
        
        host = request.host_url.rstrip("/")
        response_data = {
            "code": code,
            "name": name,
            "native": native,
            "flag": flag,
            "capital": capital,
            "continent": continent,
            "languages": languages,
            "currencies": currencies,
            "years_visited": updated_years,
            "last_updated": last_updated,
            "_links": {
                "self": {"href": f"{host}/countries/{code}"}
            }
        }

        return response_data, 200
    
@api.route('/countries')
class CountryListResource(Resource):
    @api.doc(params={
        'continent': 'Two-letter continent code to filter (e.g., EU, AS)',
        'currency': 'Three-letter currency code to filter (e.g., USD, AUD)',
        'language': 'Two-letter language code to filter (e.g., en, fr)',
        'year': 'Year to filter countries visited (e.g., 2024)',
        'sort': 'Comma-separated list of fields (e.g., name,-last_updated)',
        'page': 'Page number (default: 1)',
        'size': 'Number of items per page (default: 10)'
    })
    def get(self):

        # Get filter and pagination parameters from query string
        continent = request.args.get('continent')
        currency = request.args.get('currency')
        language = request.args.get('language')
        year = request.args.get('year', type=int)
        sort = request.args.get('sort', default='code')
        page = request.args.get('page', default=1, type=int)
        size = request.args.get('size', default=10, type=int)

        query = "SELECT code, name, continent, years_visited, last_updated FROM countries WHERE 1=1"
        params = []

        # Apply filters if provided
        if continent:
            query += " AND continent_code = ?"
            params.append(continent.upper())
        if currency:
            query += " AND currency LIKE ?"
            params.append(f"%{currency.upper()}%")
        if language:
            query += " AND languages LIKE ?"
            params.append(f"%{language.lower()}|%")
        if year:
            query += " AND years_visited LIKE ?"
            params.append(f"%{year}%")

        allowed_fields = ['code', 'name', 'continent', 'last_updated']
        sort_clauses = []

        for field in sort.split(','):
            direction = "ASC"
            if field.startswith('-'):
                direction = "DESC"
                field = field[1:]
            if field in allowed_fields:
                sort_clauses.append(f"{field} {direction}")
        if sort_clauses:
            query += " ORDER BY " + ", ".join(sort_clauses)
        else:
            query += " ORDER BY code ASC"

        offset = (page - 1) * size
        query += " LIMIT ? OFFSET ?"
        params.extend([size, offset])

        cursor.execute(query, params)
        countries = cursor.fetchall()

        count_query = "SELECT COUNT(*) FROM countries WHERE 1=1"
        count_params = params[:-2] 
        if continent:
            count_query += " AND continent_code = ?"
        if currency:
            count_query += " AND currency LIKE ?"
        if language:
            count_query += " AND languages LIKE ?"
        if year:
            count_query += " AND years_visited LIKE ?"
        cursor.execute(count_query, count_params)
        total_count = cursor.fetchone()[0]
        total_pages = (total_count + size - 1) // size

        items = []
        host = request.host_url.rstrip("/")
        for c in countries:
            code, name, continent, years_visited, last_updated = c
            items.append({
                "code": code,
                "name": name,
                "continent": continent,
                "years_visited": list(map(int, years_visited.split(','))) if years_visited else [],
                "last_updated": last_updated,
                "_links": {
                    "self": {"href": f"{host}/countries/{code}"}
                }
            })

        query_params = []
        if continent:
            query_params.append(f"continent={continent}")
        if currency:
            query_params.append(f"currency={currency}")
        if language:
            query_params.append(f"language={language}")
        if year:
            query_params.append(f"year={year}")
        if sort:
            query_params.append(f"sort={sort}")
        query_params.append(f"page={page}")
        query_params.append(f"size={size}")
        query_string = "&".join(query_params)

        return {
            "_metadata": {
                "page": page,
                "size": size,
                "total_pages": total_pages,
                "total_countries": total_count
            },
            "countries": items,
            "_links": {
                "self": {
                    "href": f"{host}/countries?{query_string}"
                }
            }
        }, 200

@api.route('/countries/visited')
class VisitedCountriesResource(Resource):
    def get(self):
        cursor.execute("SELECT name, continent, years_visited FROM countries")
        countries = cursor.fetchall()
        visited_counts = {} 
        for name, continent, years in countries:
            if years:
                visited_counts[continent] = visited_counts.get(continent, 0) + 1

        if not visited_counts:
            return {"message": "No visited countries found."}, 204

        fig, ax = plt.subplots()
        sorted_counts = dict(sorted(visited_counts.items(), key=lambda x: x[1], reverse=True))
        ax.barh(list(sorted_counts.keys()), list(sorted_counts.values()), color='blue')

        ax.set_title("Top Visited Continents", fontsize=14)
        ax.set_xlabel("Number of Countries Visited")
        ax.set_ylabel("Continent")
        ax.xaxis.set_major_locator(MultipleLocator(1))

        img_bytes = io.BytesIO()
        plt.tight_layout()
        plt.savefig(img_bytes, format='png')
        img_bytes.seek(0)
        plt.close(fig)

        return send_file(img_bytes, mimetype='image/png')

if __name__ == "__main__":
    if len(sys.argv) > 1:
        app.run(debug=True, port=int(sys.argv[1]))
    else:
        app.run(debug=True)
