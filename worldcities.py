import csv
import os

CITY_FILE = os.path.join(os.path.dirname(__file__), "cities1000.txt")

def load_cities():
    if not os.path.exists(CITY_FILE):
        raise FileNotFoundError("cities1000.txt not found.")

    cities = {}

    with open(CITY_FILE, "r", encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.reader(f, delimiter="\t")

        for row in reader:
            if len(row) < 18:
                continue

            geoname_id = row[0]
            name = row[1]
            ascii_name = row[2]
            latitude = row[4]
            longitude = row[5]
            feature_class = row[6]
            country_code = row[8]
            population = row[14]
            timezone = row[17]

            if feature_class != "P":
                continue

            try:
                lat = float(latitude)
                lon = float(longitude)
            except ValueError:
                continue

            try:
                pop = int(population or 0)
            except ValueError:
                pop = 0

            cities[geoname_id] = {
                "id": geoname_id,
                "name": name,
                "ascii_name": ascii_name,
                "country": country_code,
                "lat": lat,
                "lon": lon,
                "timezone": timezone,
                "population": pop
            }

    return cities


CITIES = load_cities()


def search_cities(query, limit=10):
    query = (query or "").strip().lower()

    if len(query) < 2:
        return []

    results = []

    for city in CITIES.values():
        name = city["name"].lower()
        ascii_name = city["ascii_name"].lower()

        if query in name or query in ascii_name:
            results.append(city)

    results.sort(key=lambda c: (-c["population"], c["name"]))

    return results[:limit]