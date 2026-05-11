import os
import sqlite3
import random
from datetime import datetime, timedelta

# --- Configuration ---
DB_NAME = "hotel_data.db"
NUM_CUSTOMERS = 800
NUM_RESERVATIONS = 2500
NUM_EVENTS = 400
START_DATE = datetime(2025, 6, 1)   
END_DATE = datetime(2027, 5, 31)    
DATE_RANGE_DAYS = (END_DATE - START_DATE).days

def setup_database(cursor):
    """Creates the tables based on your schema."""
    schema = """
    PRAGMA foreign_keys = ON;

    CREATE TABLE IF NOT EXISTS hotel (hotelId INTEGER PRIMARY KEY, hotelName TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS organization (organizationId INTEGER PRIMARY KEY, name TEXT NOT NULL, contactpersonId INTEGER);
    CREATE TABLE IF NOT EXISTS customer (customerId INTEGER PRIMARY KEY, customerType TEXT NOT NULL, contactInfo TEXT NOT NULL UNIQUE, phoneNumber TEXT NOT NULL, organizationId INTEGER NOT NULL, currentLocation TEXT, FOREIGN KEY (organizationId) REFERENCES organization(organizationId));
    CREATE TABLE IF NOT EXISTS building (buildingId INTEGER PRIMARY KEY, hotelId INTEGER NOT NULL, buildingName TEXT NOT NULL, FOREIGN KEY (hotelId) REFERENCES hotel(hotelId));
    CREATE TABLE IF NOT EXISTS wing (wingId INTEGER PRIMARY KEY, buildingId INTEGER NOT NULL, wingName TEXT NOT NULL UNIQUE, proximity TEXT NOT NULL, sequenceNum INTEGER, FOREIGN KEY (buildingId) REFERENCES building(buildingId));
    CREATE TABLE IF NOT EXISTS hotel_floor (floorId INTEGER PRIMARY KEY, wingId INTEGER NOT NULL, floorNo INTEGER NOT NULL, FOREIGN KEY (wingId) REFERENCES wing(wingId));
    CREATE TABLE IF NOT EXISTS room (
        roomId INTEGER PRIMARY KEY,
        floorId INTEGER NOT NULL,
        roomNumber TEXT NOT NULL,
        roomRating INTEGER NOT NULL,
        roomStatus TEXT NOT NULL,
        roomRate REAL NOT NULL,
        isSmoking INTEGER CHECK (isSmoking IN (0,1)),
        roomFunction TEXT NOT NULL CHECK (roomFunction IN ('sleeping_only','meeting_only','convertible')),
        hasToilet INTEGER NOT NULL CHECK (hasToilet IN (0,1)),
        hasPermanentBeds INTEGER NOT NULL CHECK (hasPermanentBeds IN (0,1)),
        hasWallBed INTEGER NOT NULL CHECK (hasWallBed IN (0,1)),
        hasOpenArea INTEGER NOT NULL CHECK (hasOpenArea IN (0,1)),
        baseMeetingRate REAL NOT NULL,
        FOREIGN KEY (floorId) REFERENCES hotel_floor(floorId)
    );
    CREATE TABLE IF NOT EXISTS room_bed (
        roomId INTEGER NOT NULL,
        bedSize TEXT NOT NULL CHECK (bedSize IN ('double','double_xl','queen','king','rollaway')),
        bedType TEXT NOT NULL CHECK (bedType IN ('perm','roll')),
        bedCount INTEGER NOT NULL CHECK (bedCount >= 0 AND bedCount <= 4),
        PRIMARY KEY (roomId, bedSize, bedType),
        FOREIGN KEY (roomId) REFERENCES room(roomId)
    );
    CREATE TABLE IF NOT EXISTS room_adjacency (
        roomId1 INTEGER NOT NULL,
        roomId2 INTEGER NOT NULL,
        hasConnection INTEGER NOT NULL CHECK (hasConnection IN (0,1)),
        PRIMARY KEY (roomId1, roomId2),
        FOREIGN KEY (roomId1) REFERENCES room(roomId),
        FOREIGN KEY (roomId2) REFERENCES room(roomId)
    );
    CREATE TABLE IF NOT EXISTS time_slot (timeSlotId INTEGER PRIMARY KEY, slotName TEXT NOT NULL, isEating INTEGER CHECK (isEating IN (0,1)));
    CREATE TABLE IF NOT EXISTS reservation (reservationId INTEGER PRIMARY KEY, customerId INTEGER NOT NULL, dateBooked TEXT NOT NULL, guestCount INTEGER NOT NULL, startDate TEXT NOT NULL, endDate TEXT NOT NULL, deposit REAL CHECK (deposit > 0), FOREIGN KEY (customerId) REFERENCES customer(customerId));
    CREATE TABLE IF NOT EXISTS reservation_requirement (requirementId INTEGER PRIMARY KEY, reservationId INTEGER NOT NULL, dateEntered TEXT NOT NULL, bedType TEXT, guestCount INTEGER, locationPreference TEXT, isSmoking INTEGER CHECK (isSmoking IN (0,1)), proximity TEXT, callerId INTEGER, FOREIGN KEY (reservationId) REFERENCES reservation(reservationId));
    CREATE TABLE IF NOT EXISTS room_assignment (assignmentId INTEGER PRIMARY KEY, roomId INTEGER NOT NULL, reservationId INTEGER NOT NULL, timeSlotId INTEGER NOT NULL, requirementId INTEGER NOT NULL, FOREIGN KEY (roomId) REFERENCES room(roomId), FOREIGN KEY (reservationId) REFERENCES reservation(reservationId), FOREIGN KEY (timeSlotId) REFERENCES time_slot(timeSlotId));
    CREATE TABLE IF NOT EXISTS customer_history (customerHistoryId INTEGER PRIMARY KEY, reservationId INTEGER NOT NULL, flexibility TEXT, paymentSpeed TEXT, cooperativeness TEXT, customerId INTEGER NOT NULL, FOREIGN KEY (reservationId) REFERENCES reservation(reservationId), FOREIGN KEY (customerId) REFERENCES customer(customerId));
    CREATE TABLE IF NOT EXISTS billing_party (billingPartyId INTEGER PRIMARY KEY, customerType TEXT NOT NULL, reservationId INTEGER NOT NULL, customerId INTEGER NOT NULL, FOREIGN KEY (customerId) REFERENCES customer(customerId));
    CREATE TABLE IF NOT EXISTS charge (chargeId INTEGER PRIMARY KEY, assignmentId INTEGER NOT NULL, amount REAL NOT NULL, paymentMethod TEXT NOT NULL, billingPartyId INTEGER NOT NULL, dateBilled TEXT NOT NULL, datePaid TEXT NOT NULL, chargeType TEXT NOT NULL, FOREIGN KEY (assignmentId) REFERENCES room_assignment(assignmentId), FOREIGN KEY (billingPartyId) REFERENCES billing_party(billingPartyId));
    CREATE TABLE IF NOT EXISTS event (eventId INTEGER PRIMARY KEY, duration TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS event_room (eventRoomId INTEGER PRIMARY KEY, roomId INTEGER NOT NULL, eventDate TEXT NOT NULL, eventId INTEGER NOT NULL, FOREIGN KEY (roomId) REFERENCES room(roomId), FOREIGN KEY (eventId) REFERENCES event(eventId));
    CREATE TABLE IF NOT EXISTS event_attendance (eventId INTEGER, role TEXT, customerId INTEGER, PRIMARY KEY (eventId, customerId), FOREIGN KEY (eventId) REFERENCES event(eventId), FOREIGN KEY (customerId) REFERENCES customer(customerId));
    CREATE TABLE IF NOT EXISTS reader (readerId INTEGER PRIMARY KEY, locationType TEXT NOT NULL, locationId INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS access_card (cardId INTEGER PRIMARY KEY, customerId INTEGER NOT NULL, pin TEXT NOT NULL, FOREIGN KEY (customerId) REFERENCES customer(customerId));
    CREATE TABLE IF NOT EXISTS card_swipe (swipeId INTEGER PRIMARY KEY, cardId INTEGER NOT NULL, timeRecord TEXT NOT NULL, direction TEXT NOT NULL, readerId INTEGER NOT NULL, FOREIGN KEY (cardId) REFERENCES access_card(cardId), FOREIGN KEY (readerId) REFERENCES reader(readerId));
    """
    cursor.executescript(schema)

def generate_data():
    if os.path.exists(DB_NAME):
        os.remove(DB_NAME)
        print(f"Old database '{DB_NAME}' removed. Starting fresh...")

    conn = sqlite3.connect(DB_NAME)
    curr = conn.cursor()
    setup_database(curr)

    print("Generating Hotels & Infrastructure...")
    hotels = [(1, "Grand Central Plaza"), (2, "Soho Suites & Spa"), (3, "The Majestic Pearl"), (4, "Oceanfront Resort"), (5, "Summit Mountain Lodge")]
    curr.executemany("INSERT INTO hotel VALUES (?,?)", hotels)

    # Corporate group names
    company_names = [
        "Nexus Industries", "Apex Financial Partners", "Global Horizon Logistics",
        "Vertex Software Solutions", "Pinnacle Health Group", "Meridian Consulting",
        "Quantum Technologies", "Starlight Media", "Blue Ocean Ventures",
        "Stellar Dynamics", "Vanguard Systems", "Synergy Holdings",
        "OmniCorp International", "Summit Enterprises", "Atlas Innovations"
    ]
    orgs = [(i + 1, name, random.randint(1, 100)) for i, name in enumerate(company_names)]
    curr.executemany("INSERT INTO organization VALUES (?,?,?)", orgs)

    sleeping_rooms = []
    meeting_rooms = []
    floor_id, wing_id, building_id = 1, 1, 1
    rooms_by_floor = {}
    room_meta = {}
    
    for h_id, _ in hotels:
        for b in range(1, 3):
            curr.execute("INSERT INTO building VALUES (?,?,?)", (building_id, h_id, f"Tower {b}"))
            for w in range(1, 3):
                curr.execute("INSERT INTO wing VALUES (?,?,?,?,?)", (wing_id, building_id, f"Wing {wing_id}", random.choice(["Poolside", "Garden View", "City View", "Parking"]), w))
                for f in range(1, 6):
                    curr.execute("INSERT INTO hotel_floor VALUES (?,?,?)", (floor_id, wing_id, f))
                    for r in range(1, 11):
                        rid = floor_id * 100 + r
                        rating = random.choices([3, 4, 5], weights=[0.4, 0.4, 0.2])[0]
                        base_rate = {3: random.uniform(120, 180), 4: random.uniform(190, 350), 5: random.uniform(400, 800)}[rating]
                        rate = round(base_rate, 2)
                        
                        room_function = random.choices(
                            ["sleeping_only", "meeting_only", "convertible"],
                            weights=[0.65, 0.20, 0.15]
                        )[0]
                        is_smoking = random.choice([0, 0, 0, 1])

                        if room_function == "sleeping_only":
                            has_toilet = 1
                            has_permanent_beds = 1
                            has_wall_bed = 0
                            has_open_area = random.choice([0, 1])
                        elif room_function == "meeting_only":
                            has_toilet = random.choice([0, 1, 1])  # some can be used in a pinch for sleeping
                            has_permanent_beds = 0
                            has_wall_bed = 0
                            has_open_area = 1
                        else:  # convertible
                            has_toilet = 1
                            has_permanent_beds = 0
                            has_wall_bed = 1
                            has_open_area = 1

                        base_meeting_rate = round(rate * random.uniform(0.35, 0.65), 2)

                        curr.execute(
                            "INSERT INTO room VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                            (
                                rid, floor_id, f"{f}{r:02d}", rating, "vacant", rate, is_smoking,
                                room_function, has_toilet, has_permanent_beds, has_wall_bed,
                                has_open_area, base_meeting_rate
                            )
                        )

                        # Sleeping eligibility: sleeping rooms + convertible + meeting rooms with toilet (pinch case).
                        if room_function in ("sleeping_only", "convertible") or (room_function == "meeting_only" and has_toilet == 1):
                            sleeping_rooms.append((rid, rate))

                        # Meeting eligibility: meeting-only + convertible; permanent-bed rooms excluded.
                        if room_function in ("meeting_only", "convertible") and has_permanent_beds == 0:
                            meeting_rooms.append((rid, base_meeting_rate))
                        rooms_by_floor.setdefault(floor_id, []).append(rid)
                        room_meta[rid] = {
                            "room_function": room_function,
                            "has_toilet": has_toilet,
                            "has_permanent_beds": has_permanent_beds,
                            "has_wall_bed": has_wall_bed,
                        }
                    floor_id += 1
                wing_id += 1
            building_id += 1

    print("Generating Room Beds & Adjacency...")
    for rid, meta in room_meta.items():
        if meta["room_function"] == "sleeping_only":
            bed_patterns = [
                [("queen", "perm", 1)],
                [("king", "perm", 1)],
                [("double", "perm", 2)],
                [("double_xl", "perm", 2)],
                [("queen", "perm", 1), ("rollaway", "roll", 1)],
            ]
            for bed in random.choice(bed_patterns):
                curr.execute("INSERT INTO room_bed VALUES (?,?,?,?)", (rid, bed[0], bed[1], bed[2]))
        elif meta["room_function"] == "convertible":
            bed_patterns = [
                [("queen", "perm", 1)],
                [("double", "perm", 1), ("rollaway", "roll", 1)],
                [("queen", "perm", 1), ("rollaway", "roll", 2)],
            ]
            for bed in random.choice(bed_patterns):
                curr.execute("INSERT INTO room_bed VALUES (?,?,?,?)", (rid, bed[0], bed[1], bed[2]))
        elif meta["has_toilet"] == 1 and random.random() < 0.35:
            curr.execute("INSERT INTO room_bed VALUES (?,?,?,?)", (rid, "rollaway", "roll", random.randint(1, 2)))

    # Adjacency by floor (neighboring room numbers), plus occasional extra cross-links.
    for _, floor_rooms in rooms_by_floor.items():
        floor_rooms = sorted(floor_rooms)
        for i in range(len(floor_rooms) - 1):
            r1, r2 = floor_rooms[i], floor_rooms[i + 1]
            has_conn = 1 if random.random() < 0.28 else 0
            curr.execute("INSERT INTO room_adjacency VALUES (?,?,?)", (r1, r2, has_conn))
            curr.execute("INSERT INTO room_adjacency VALUES (?,?,?)", (r2, r1, has_conn))
        for _ in range(2):
            r1, r2 = random.sample(floor_rooms, 2)
            curr.execute("INSERT OR IGNORE INTO room_adjacency VALUES (?,?,?)", (r1, r2, 1))
            curr.execute("INSERT OR IGNORE INTO room_adjacency VALUES (?,?,?)", (r2, r1, 1))

    print("Generating Customers...")
    customer_ids = list(range(1, NUM_CUSTOMERS + 1))
    first_names = ["Alice", "Bob", "Charlie", "Diana", "Ethan", "Fiona", "George", "Hannah", "Ian", "Julia"]
    last_names = ["Smith", "Jones", "Taylor", "Brown", "Williams", "Wilson", "Johnson", "Davies", "Evans", "Thomas"]
    
    for c_id in customer_ids:
        fname = random.choice(first_names)
        lname = random.choice(last_names)
        # Using @gmail.com for legitimate-looking emails
        email = f"{fname.lower()}.{lname.lower()}{c_id}@gmail.com"
        curr.execute("INSERT INTO customer VALUES (?,?,?,?,?,?)",
                     (c_id, random.choice(['guest', 'guest', 'host']), email, f"{random.randint(200,999)}-555-{random.randint(1000,9999)}", random.randint(1, 15), random.choice(["NY", "CA", "TX", "FL", "IL"])))

    print("Generating Time Slots & Readers...")
    curr.executemany(
        "INSERT INTO time_slot VALUES (?,?,?)",
        [
            (1, 'Breakfast', 1),
            (2, 'Morning', 0),
            (3, 'Lunch', 1),
            (4, 'Afternoon', 0),
            (5, 'Supper', 1),
            (6, 'Evening', 0),
            (7, 'Night', 0),
        ]
    )
    
    readers = [(1, "Lobby Main", 1), (2, "Fitness Center", 2), (3, "Pool Deck", 3), (4, "Parking Garage", 4), (5, "Executive Lounge", 5)]
    curr.executemany("INSERT INTO reader VALUES (?,?,?)", readers)

    print("Generating Reservations & Billing...")
    charge_id = 1
    swipe_id = 1
    for res_id in range(1, NUM_RESERVATIONS + 1):
        c_id = random.choice(customer_ids)
        start_date = START_DATE + timedelta(days=random.randint(0, DATE_RANGE_DAYS))
        days_in_advance = random.randint(7, 730)
        booked_date = start_date - timedelta(days=days_in_advance)
        stay_length = random.choices([1, 2, 3, 4, 5, 7, 10, 14], weights=[0.18, 0.28, 0.2, 0.1, 0.1, 0.07, 0.05, 0.02])[0]
        end_date = start_date + timedelta(days=stay_length)
        deposit = round(random.uniform(50, 200), 2)
        
        curr.execute("INSERT INTO reservation VALUES (?,?,?,?,?,?,?)",
                     (res_id, c_id, booked_date.strftime("%Y-%m-%d"), random.randint(1,4), start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"), deposit))
        
        flex = "late checkout requested" if random.random() < 0.30 else "standard checkout"
        curr.execute(
            "INSERT INTO reservation_requirement VALUES (?,?,?,?,?,?,?,?,?)",
            (
                res_id, res_id, booked_date.strftime("%Y-%m-%d"),
                random.choice(["king", "queen", "double", "double_xl"]),
                random.randint(1, 4),
                random.choice(["High Floor", "Near Elevator", "Quiet Room", "Extra Open Area"]),
                random.choice([0, 1]),
                random.choice(["Pool", "City View", "Garden View", "Parking"]),
                None
            )
        )
        
        curr.execute("INSERT INTO customer_history (customerHistoryId, reservationId, flexibility, paymentSpeed, cooperativeness, customerId) VALUES (?,?,?,?,?,?)",
                     (res_id, res_id, flex, random.choice(["fast", "medium", "slow"]), random.choice(["high", "medium", "low"]), c_id))

        room_id, room_rate = random.choice(sleeping_rooms)
        curr.execute("INSERT INTO room_assignment VALUES (?,?,?,?,?)", (res_id, room_id, res_id, random.randint(1, 7), res_id))

        curr.execute("INSERT INTO billing_party VALUES (?,?,?,?)", (res_id, 'guest', res_id, c_id))
        
        room_total = round(stay_length * room_rate, 2)
        curr.execute("INSERT INTO charge VALUES (?,?,?,?,?,?,?,?)",
                     (charge_id, res_id, room_total, random.choice(['card', 'card', 'cash']), res_id, end_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"), 'room'))
        charge_id += 1

        if flex == "late checkout requested":
            curr.execute("INSERT INTO charge VALUES (?,?,?,?,?,?,?,?)",
                         (charge_id, res_id, 45.00, 'card', res_id, end_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"), 'late_checkout'))
            charge_id += 1
            
        if random.random() < 0.4:
            curr.execute("INSERT INTO charge VALUES (?,?,?,?,?,?,?,?)",
                         (charge_id, res_id, round(random.uniform(25, 150), 2), 'card', res_id, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"), 'room_service'))
            charge_id += 1
        if random.random() < 0.25:
            curr.execute("INSERT INTO charge VALUES (?,?,?,?,?,?,?,?)",
                         (charge_id, res_id, round(random.uniform(8, 75), 2), random.choice(['card', 'cash']), res_id, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"), random.choice(['business_services', 'retail_shop', 'restaurant'])))
            charge_id += 1

        if random.random() < 0.8:
            curr.execute("INSERT OR IGNORE INTO access_card VALUES (?,?,?)", (c_id, c_id, f"{random.randint(1000, 9999)}"))
            
            for _ in range(random.randint(1, 3)):
                visit_date = start_date + timedelta(days=random.randint(0, stay_length))
                base_time = visit_date.replace(hour=random.randint(7, 20), minute=random.randint(0, 59))
                reader = random.randint(1, 5)
                
                curr.execute("INSERT INTO card_swipe VALUES (?,?,?,?,?)", (swipe_id, c_id, base_time.strftime("%Y-%m-%d %H:%M"), 'in', reader))
                swipe_id += 1
                
                out_time = base_time + timedelta(minutes=random.randint(15, 90))
                curr.execute("INSERT INTO card_swipe VALUES (?,?,?,?,?)", (swipe_id, c_id, out_time.strftime("%Y-%m-%d %H:%M"), 'out', reader))
                swipe_id += 1

    print("Generating Events...")
    for e_id in range(1, NUM_EVENTS + 1):
        e_date = START_DATE + timedelta(days=random.randint(0, DATE_RANGE_DAYS))
        duration = f"0{random.randint(1, 5)}:00" if random.random() < 0.9 else "08:00"
        
        curr.execute("INSERT INTO event VALUES (?,?)", (e_id, duration))
        event_room_pool = meeting_rooms if meeting_rooms else sleeping_rooms
        curr.execute("INSERT INTO event_room VALUES (?,?,?,?)", (e_id, random.choice(event_room_pool)[0], e_date.strftime("%Y-%m-%d"), e_id))
        
        attendee_count = random.randint(15, 60)
        attendees = random.sample(customer_ids, attendee_count)
        for att_id in attendees:
            curr.execute("INSERT INTO event_attendance VALUES (?,?,?)", (e_id, 'attendee', att_id))

    conn.commit()
    conn.close()
    print(f"\nSuccess! Highly realistic database '{DB_NAME}' created for dates strictly between {START_DATE.strftime('%Y-%m-%d')} and {END_DATE.strftime('%Y-%m-%d')}.")

if __name__ == "__main__":
    generate_data()

