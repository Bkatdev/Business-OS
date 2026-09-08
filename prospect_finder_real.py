import os
import sqlite3
import requests
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv


# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "business_os.db"

load_dotenv(BASE_DIR / ".env")

API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")

if not API_KEY:
    raise ValueError("GOOGLE_PLACES_API_KEY was not found in .env")


# ---------------------------------------------------------
# DATABASE SETUP / MIGRATION
# ---------------------------------------------------------

def prepare_database():
    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()

    columns = cursor.execute(
        "PRAGMA table_info(businesses)"
    ).fetchall()

    column_names = [column[1] for column in columns]

    if "address" not in column_names:
        print("Adding address field to database...")
        cursor.execute(
            "ALTER TABLE businesses ADD COLUMN address TEXT DEFAULT ''"
        )

    if "google_place_id" not in column_names:
        print("Adding Google Place ID field to database...")
        cursor.execute(
            "ALTER TABLE businesses ADD COLUMN google_place_id TEXT DEFAULT ''"
        )

    connection.commit()
    connection.close()


# ---------------------------------------------------------
# GOOGLE PLACES
# ---------------------------------------------------------

def find_prospects(search_query, page_size=10):
    url = "https://places.googleapis.com/v1/places:searchText"

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": ",".join([
            "places.id",
            "places.displayName",
            "places.formattedAddress",
            "places.rating",
            "places.userRatingCount",
            "places.websiteUri",
            "places.nationalPhoneNumber",
        ]),
    }

    body = {
        "textQuery": search_query,
        "pageSize": page_size,
    }

    response = requests.post(
        url,
        headers=headers,
        json=body,
        timeout=20,
    )

    if response.status_code != 200:
        print()
        print("Google Places API returned an error:")
        print(response.status_code)
        print(response.text)
        raise SystemExit()

    return response.json().get("places", [])


# ---------------------------------------------------------
# DATA HELPERS
# ---------------------------------------------------------

def extract_city(address):
    parts = [part.strip() for part in address.split(",")]

    if len(parts) >= 4:
        return parts[-3]

    if len(parts) >= 2:
        return parts[1]

    return ""


def business_is_duplicate(cursor, google_place_id, name, phone, website):
    if google_place_id:
        existing = cursor.execute(
            """
            SELECT id
            FROM businesses
            WHERE google_place_id = ?
            """,
            (google_place_id,),
        ).fetchone()

        if existing:
            return True

    if phone:
        existing = cursor.execute(
            """
            SELECT id
            FROM businesses
            WHERE phone = ?
            AND LOWER(name) = LOWER(?)
            """,
            (phone, name),
        ).fetchone()

        if existing:
            return True

    if website:
        existing = cursor.execute(
            """
            SELECT id
            FROM businesses
            WHERE LOWER(website) = LOWER(?)
            AND LOWER(name) = LOWER(?)
            """,
            (website, name),
        ).fetchone()

        if existing:
            return True

    return False


# ---------------------------------------------------------
# SAVE PROSPECT
# ---------------------------------------------------------

def save_prospect(place):
    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()

    name = place.get("displayName", {}).get("text", "Unknown")
    address = place.get("formattedAddress", "")
    rating = place.get("rating")
    reviews = place.get("userRatingCount", 0)
    website = place.get("websiteUri", "")
    phone = place.get("nationalPhoneNumber", "")
    google_place_id = place.get("id", "")
    created_at = datetime.now().isoformat(timespec="seconds")

    if business_is_duplicate(
        cursor,
        google_place_id,
        name,
        phone,
        website,
    ):
        connection.close()
        return False, name

    cursor.execute(
        """
        INSERT INTO businesses (
            name,
            city,
            category,
            reviews,
            rating,
            website,
            phone,
            email,
            online_booking,
            emergency_service,
            website_chat,
            estimate_form,
            status,
            notes,
            created_at,
            address,
            google_place_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            name,
            extract_city(address),
            "Tree Care",
            reviews,
            rating,
            website,
            phone,
            "",
            0,
            0,
            0,
            0,
            "Not Contacted",
            "",
            created_at,
            address,
            google_place_id,
        ),
    )

    connection.commit()
    connection.close()

    return True, name


# ---------------------------------------------------------
# RUN PROSPECT FINDER
# ---------------------------------------------------------

def main():
    print()
    print("BUSINESS OS - REAL PROSPECT FINDER")
    print("=" * 70)

    prepare_database()

    search_query = "tree service near East Brunswick, New Jersey"

    print()
    print("Searching Google for:")
    print(search_query)
    print()

    prospects = find_prospects(
        search_query,
        page_size=10,
    )

    if not prospects:
        print("No prospects found.")
        return

    print(f"Google returned {len(prospects)} businesses.")
    print()

    added = 0
    skipped = 0

    for place in prospects:
        was_added, name = save_prospect(place)

        if was_added:
            print(f"[ADDED]   {name}")
            added += 1
        else:
            print(f"[SKIPPED] {name} - already in database")
            skipped += 1

    print()
    print("=" * 70)
    print(f"New prospects added: {added}")
    print(f"Duplicates skipped:  {skipped}")
    print()
    print("Prospect Finder complete.")
    print("Open Business OS to see the new prospects.")
    print()


if __name__ == "__main__":
    main()