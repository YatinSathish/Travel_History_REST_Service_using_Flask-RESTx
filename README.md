# 📌 Project Overview
Travel History REST API with Flask
This Flask-based REST API lets users track and manage countries they’ve visited. It integrates with the Trevor Blades GraphQL API to fetch country metadata, stores it locally in SQLite, and supports operations like retrieval, filtering, updating, and visualizing travel history across continents.
# 🧩 Features
`PUT /countries/<code>`: Import a new country by 2-letter code or update an existing one.
`GET /countries/<code>`: Retrieve country details including visit history.
PATCH /countries/<code>: Add more years to a country’s visit history.
DELETE /countries/<code>: Delete a country record.
GET /countries: List all visited countries with:

Pagination (page, size)

Filtering by continent, language, currency, or year visited

Sorting by fields like name, last_updated

GET /countries/visited: Generate and return a PNG chart showing the most visited continents.

Automatic population of country data using the external GraphQL API.

HATEOAS-style _links field in responses for navigation (self, prev, next).
## Requirements
This project requires the following Python packages:

Flask: A web framework for building APIs.

Flask-RESTx: An extension for Flask that simplifies the creation of RESTful APIs.

sqlite3: A database library used to manage country data.

requests: A library to make HTTP requests to external APIs.

matplotlib: A plotting library used for visualizing the travel history as PNG images.

datetime: To handle date and time operations.

## Installation

- Create a virtual environment if needed. - https://packaging.python.org/en/latest/guides/installing-using-pip-and-virtual-environments/
- Install the required libraries.

## How to run

You can run using python command in the command prompt.

python myTravelHistory_API.py {port_number}
