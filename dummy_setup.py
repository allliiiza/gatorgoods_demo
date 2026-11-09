import crud, database, schemas, models

from sqlalchemy.exc import IntegrityError

import json
import argparse
import random


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", default="static/dummy-items.json")
    args = parser.parse_args()

    db = database.SessionLocal()
    db.rollback()

    models.Base.metadata.drop_all(database.engine)
    models.Base.metadata.create_all(database.engine)

    with open("static/dummy-users.json", "r") as f:
        users = json.load(f)

    db_users = []
    for user in users:
        db_user = schemas.UserCreate(email=user["email"], password="password123", display_name=user["name"], bio=user["bio"])
        try:
            db_users.append(crud.create_user(db, db_user))
            crud.edit_user_moderator(db, db_users[-1].id, True)
        except IntegrityError:
            db.rollback()
            db_users.append(db.query(models.User).filter_by(display_name=user["name"]).first())

    with open("static/dummy-courses.json", "r") as f:
        courses = json.load(f)

    for course in courses:
        try: crud.create_course_tag(db, course)
        except IntegrityError: db.rollback()

    with open("static/dummy-categories.json", "r") as f:
        categories = json.load(f)

    for category in categories:
        try: crud.create_category(db, category)
        except IntegrityError: db.rollback()

    with open("static/dummy-pickup-locations.json", "r") as f:
        locations = json.load(f)

    for location in locations:
        try: crud.create_pickup_location(db, location["name"], location["description"])
        except IntegrityError: db.rollback()

    with open("static/dummy-items.json", "r") as f:
        items = json.load(f)

    for item in items:
        listing = schemas.ListingCreateAuthorized(
                title=item["name"],
                description=item["description"],
                price=item["price"],
                category_name=item["category_name"],
                pickup_location_name=locations[0]["name"],
                images=item["images"],
                seller=schemas.UserReference.model_validate(db_users[random.randint(0, len(db_users)-1)])
        )

        try:
            listing = crud.create_listing(db, listing)
            crud.approve_listing(db, listing.id)
        except IntegrityError: db.rollback()

    db.close()
