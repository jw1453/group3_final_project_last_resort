from flask import Flask, render_template, request
import sqlite3
import json

app = Flask(__name__)
DB_NAME = "hotel_data.db"


def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


# ──────────────────────────────────────────────
# Page 1: Reservations & Room Assignment
# ──────────────────────────────────────────────
@app.route("/")
def home():
    conn = get_db()

    selected_date = request.args.get("search_date", "2025-08-15")
    start_date = request.args.get("start_date", selected_date)
    end_date = request.args.get("end_date", start_date)
    selected_hotel_id = request.args.get("hotel_id", type=int)
    bed_type      = request.args.get("bed_type", "")
    proximity     = request.args.get("proximity", "")
    min_rating    = request.args.get("min_rating", "", type=str)
    smoking       = request.args.get("smoking", "")
    room_function = request.args.get("room_function", "")
    hotels = conn.execute(
        "SELECT hotelId, hotelName FROM hotel ORDER BY hotelName;"
    ).fetchall()

    # ── Query 1: Who is arriving on a specific date? ──
    arrivals_sql = """
        SELECT
            r.reservationId,
            SUBSTR(
                SUBSTR(c.contactInfo, 1, INSTR(c.contactInfo, '@') - 1),
                1,
                INSTR(SUBSTR(c.contactInfo, 1, INSTR(c.contactInfo, '@') - 1), '.') - 1
            ) AS first_name,
            RTRIM(
                SUBSTR(
                    SUBSTR(c.contactInfo, 1, INSTR(c.contactInfo, '@') - 1),
                    INSTR(SUBSTR(c.contactInfo, 1, INSTR(c.contactInfo, '@') - 1), '.') + 1
                ),
                '0123456789'
            ) AS last_name,
            r.guestCount,
            r.endDate AS check_out_date
        FROM reservation r
        JOIN customer c ON r.customerId = c.customerId
        WHERE r.startDate BETWEEN ? AND ?
    """
    arrivals_params = [start_date, end_date]
    if selected_hotel_id is not None:
        arrivals_sql += """
            AND EXISTS (
                SELECT 1
                FROM room_assignment ra_h
                JOIN room rm_h ON ra_h.roomId = rm_h.roomId
                JOIN hotel_floor hf_h ON rm_h.floorId = hf_h.floorId
                JOIN wing w_h ON hf_h.wingId = w_h.wingId
                JOIN building b_h ON w_h.buildingId = b_h.buildingId
                WHERE ra_h.reservationId = r.reservationId
                  AND b_h.hotelId = ?
            )
        """
        arrivals_params.append(selected_hotel_id)
    arrivals_sql += ";"
    arrivals = conn.execute(arrivals_sql, arrivals_params).fetchall()

    # ── Query 4: What rooms are available during a given date range? ──
    room_where = """
        WHERE rm.roomId NOT IN (
            SELECT ra.roomId FROM room_assignment ra
            JOIN reservation res ON ra.reservationId = res.reservationId
            WHERE res.startDate <= ?
              AND res.endDate >= ?
        )
        AND (
            rm.roomFunction IN ('sleeping_only', 'convertible')
            OR (rm.roomFunction = 'meeting_only' AND rm.hasToilet = 1)
        )
    """
    room_params = [end_date, start_date]

    if bed_type:
        room_where += """
            AND EXISTS (
                SELECT 1
                FROM room_bed rb
                WHERE rb.roomId = rm.roomId
                  AND rb.bedSize = ?
            )
        """
        room_params.append(bed_type)

    if proximity:
        room_where += " AND w.proximity = ?"
        room_params.append(proximity)

    if min_rating:
        room_where += " AND rm.roomRating >= ?"
        room_params.append(int(min_rating))

    if smoking == "no":
        room_where += " AND rm.isSmoking = 0"
    elif smoking == "yes":
        room_where += " AND rm.isSmoking = 1"

    if room_function == "sleeping":
        room_where += " AND rm.roomFunction IN ('sleeping_only', 'convertible')"
    elif room_function == "meeting":
        room_where += " AND rm.roomFunction = 'meeting_only' AND rm.hasToilet = 1"

    if selected_hotel_id is not None:
        room_where += " AND b.hotelId = ?"
        room_params.append(selected_hotel_id)

    available_rooms = conn.execute(f"""
        SELECT DISTINCT rm.roomId, rm.roomNumber, rm.roomRating,
                rm.roomRate, rm.roomStatus, rm.isSmoking, rm.roomFunction
        FROM room rm
        JOIN hotel_floor hf ON rm.floorId = hf.floorId
        JOIN wing w ON hf.wingId = w.wingId
        JOIN building b ON w.buildingId = b.buildingId
        {room_where}
        ORDER BY rm.roomRating DESC, rm.roomNumber ASC;
    """, room_params).fetchall()

    # ── Query 5: Which of the available rooms has been booked the most? ──
    top_room_sql = """
        SELECT rm.roomNumber, COUNT(ra.assignmentId) AS total_times_booked
        FROM room rm
        LEFT JOIN room_assignment ra ON rm.roomId = ra.roomId
    """
    top_room_params = []
    if selected_hotel_id is not None:
        top_room_sql += """
            JOIN hotel_floor hf ON rm.floorId = hf.floorId
            JOIN wing w ON hf.wingId = w.wingId
            JOIN building b ON w.buildingId = b.buildingId
        """
    top_room_sql += """
        WHERE (
            rm.roomFunction IN ('sleeping_only', 'convertible')
            OR (rm.roomFunction = 'meeting_only' AND rm.hasToilet = 1)
        )
    """
    if selected_hotel_id is not None:
        top_room_sql += " AND b.hotelId = ?"
        top_room_params.append(selected_hotel_id)
    top_room_sql += """
        GROUP BY rm.roomId
        ORDER BY total_times_booked DESC
        LIMIT 1;
    """
    top_room = conn.execute(top_room_sql, top_room_params).fetchone()

    # ── Query 3: Who are the top corporate clients? ──
    top_corps_sql = """
        SELECT o.name AS corporate_group,
                COUNT(DISTINCT r.reservationId) AS total_reservations,
                ROUND(SUM(ch.amount), 2) AS total_money_spent
        FROM organization o
        JOIN customer c ON o.organizationId = c.organizationId
        JOIN reservation r ON c.customerId = r.customerId
        JOIN billing_party bp ON r.reservationId = bp.reservationId
        JOIN charge ch ON bp.billingPartyId = ch.billingPartyId
    """
    top_corps_params = []
    if selected_hotel_id is not None:
        top_corps_sql += """
            JOIN room_assignment ra_h ON ch.assignmentId = ra_h.assignmentId
            JOIN room rm_h ON ra_h.roomId = rm_h.roomId
            JOIN hotel_floor hf_h ON rm_h.floorId = hf_h.floorId
            JOIN wing w_h ON hf_h.wingId = w_h.wingId
            JOIN building b_h ON w_h.buildingId = b_h.buildingId
            WHERE b_h.hotelId = ?
        """
        top_corps_params.append(selected_hotel_id)
    top_corps_sql += """
        GROUP BY o.organizationId
        ORDER BY total_money_spent DESC
        LIMIT 5;
    """
    top_corps = conn.execute(top_corps_sql, top_corps_params).fetchall()

    conn.close()

    return render_template(
        "index.html",
        hotels=hotels,
        selected_hotel_id=selected_hotel_id,
        selected_date=selected_date,
        start_date=start_date,
        end_date=end_date,
        bed_type=bed_type,
        proximity=proximity,
        min_rating=min_rating,
        smoking=smoking,
        room_function=room_function,
        arrivals=arrivals,
        available_rooms=available_rooms,
        top_room=top_room,
        top_corp_labels=json.dumps([c["corporate_group"] for c in top_corps]),
        top_corp_spend=json.dumps([c["total_money_spent"] for c in top_corps]),
        top_corps=top_corps,
    )


# ──────────────────────────────────────────────
# Page 2: Billing Breakdown
# ──────────────────────────────────────────────
@app.route("/billing")
def billing():
    conn = get_db()

    search_query = request.args.get("q", "", type=str).strip()
    selected_hotel_id = request.args.get("hotel_id", type=int)
    hotel_options = conn.execute(
        "SELECT hotelId, hotelName FROM hotel ORDER BY hotelName;"
    ).fetchall()

    # ── Query 2: What charges are associated with a specific stay? ──
    charges_sql = """
        SELECT
            bp.reservationId,
            ch.chargeId,
            ch.chargeType,
            ch.amount,
            ch.dateBilled,
            ch.datePaid,
            ch.paymentMethod,
            SUBSTR(
                SUBSTR(c.contactInfo, 1, INSTR(c.contactInfo, '@') - 1),
                1,
                INSTR(SUBSTR(c.contactInfo, 1, INSTR(c.contactInfo, '@') - 1), '.') - 1
            ) AS first_name,
            RTRIM(
                SUBSTR(
                    SUBSTR(c.contactInfo, 1, INSTR(c.contactInfo, '@') - 1),
                    INSTR(SUBSTR(c.contactInfo, 1, INSTR(c.contactInfo, '@') - 1), '.') + 1
                ),
                '0123456789'
            ) AS last_name
        FROM charge ch
        JOIN billing_party bp ON ch.billingPartyId = bp.billingPartyId
        JOIN reservation r ON bp.reservationId = r.reservationId
        JOIN customer c ON r.customerId = c.customerId
    """
    charges_params = []
    where_clauses = []
    if selected_hotel_id is not None:
        where_clauses.append("""
            EXISTS (
                SELECT 1
                FROM room_assignment ra_h
                JOIN room rm_h ON ra_h.roomId = rm_h.roomId
                JOIN hotel_floor hf_h ON rm_h.floorId = hf_h.floorId
                JOIN wing w_h ON hf_h.wingId = w_h.wingId
                JOIN building b_h ON w_h.buildingId = b_h.buildingId
                WHERE ra_h.assignmentId = ch.assignmentId
                  AND b_h.hotelId = ?
            )
        """)
        charges_params.append(selected_hotel_id)
    if search_query:
        if search_query.isdigit():
            where_clauses.append("bp.reservationId = ?")
            charges_params.append(int(search_query))
        else:
            where_clauses.append("""
                LOWER(
                    SUBSTR(
                        SUBSTR(c.contactInfo, 1, INSTR(c.contactInfo, '@') - 1),
                        1,
                        INSTR(SUBSTR(c.contactInfo, 1, INSTR(c.contactInfo, '@') - 1), '.') - 1
                    ) || ' ' ||
                    RTRIM(
                        SUBSTR(
                            SUBSTR(c.contactInfo, 1, INSTR(c.contactInfo, '@') - 1),
                            INSTR(SUBSTR(c.contactInfo, 1, INSTR(c.contactInfo, '@') - 1), '.') + 1
                        ),
                        '0123456789'
                    )
                ) = ?
            """)
            charges_params.append(search_query.lower())

    if where_clauses:
        charges_sql += " WHERE " + " AND ".join(where_clauses)
    charges_sql += " ORDER BY bp.reservationId, ch.dateBilled;"
    raw_charges = conn.execute(charges_sql, charges_params).fetchall()
    charges = [
        {
            "reservationId": row["reservationId"],
            "chargeId": row["chargeId"],
            "chargeType": row["chargeType"],
            "amount": row["amount"],
            "dateBilled": row["dateBilled"],
            "datePaid": row["datePaid"],
            "paymentMethod": row["paymentMethod"],
            "guest_name": f"{row['first_name'].title()} {row['last_name'].title()}",
        }
        for row in raw_charges
    ]

    total = sum(c["amount"] for c in charges)

    # ── Query 8: What is the monthly revenue by hotel? ──
    rev_trend_sql = """
        SELECT h.hotelName,
                strftime('%Y-%m', ch.dateBilled) AS rev_month,
                ROUND(SUM(ch.amount), 2) AS total_revenue
        FROM charge ch
        JOIN room_assignment ra ON ch.assignmentId = ra.assignmentId
        JOIN room rm ON ra.roomId = rm.roomId
        JOIN hotel_floor hf ON rm.floorId = hf.floorId
        JOIN wing w ON hf.wingId = w.wingId
        JOIN building b ON w.buildingId = b.buildingId
        JOIN hotel h ON b.hotelId = h.hotelId
    """
    rev_trend_params = []
    if selected_hotel_id is not None:
        rev_trend_sql += " WHERE b.hotelId = ?"
        rev_trend_params.append(selected_hotel_id)
    rev_trend_sql += """
        GROUP BY h.hotelName, rev_month
        ORDER BY rev_month ASC, h.hotelName ASC;
    """
    rev_trend = conn.execute(rev_trend_sql, rev_trend_params).fetchall()

    months = sorted(set(r["rev_month"] for r in rev_trend))
    chart_hotels = sorted(set(r["hotelName"] for r in rev_trend))
    rev_map = {(r["hotelName"], r["rev_month"]): r["total_revenue"] for r in rev_trend}

    palette = ["#2c3e50", "#8e44ad", "#16a085", "#e67e22", "#c0392b",
                "#2980b9", "#27ae60", "#d35400"]
    datasets = []
    for i, hotel in enumerate(chart_hotels):
        datasets.append({
            "label": hotel,
            "data": [rev_map.get((hotel, m), 0) for m in months],
            "borderColor": palette[i % len(palette)],
            "backgroundColor": palette[i % len(palette)] + "22",
            "tension": 0.3,
            "fill": False,
        })

    conn.close()

    return render_template(
        "billing.html",
        hotels=hotel_options,
        selected_hotel_id=selected_hotel_id,
        search_query=search_query,
        charges=charges,
        total=total,
        rev_labels=json.dumps(months),
        rev_datasets=json.dumps(datasets),
    )


# ──────────────────────────────────────────────
# Page 3: Events
# ──────────────────────────────────────────────
@app.route("/events")
def events():
    conn = get_db()

    start_date = request.args.get("start_date", "2025-08-01")
    end_date = request.args.get("end_date", "2025-08-31")
    selected_hotel_id = request.args.get("hotel_id", type=int)
    hotels = conn.execute(
        "SELECT hotelId, hotelName FROM hotel ORDER BY hotelName;"
    ).fetchall()

    events_sql = """
        SELECT
            er.eventId,
            er.eventDate,
            er.roomId,
            rm.roomFunction,
            e.duration,
            COUNT(DISTINCT ea.customerId) AS attendee_count
        FROM event_room er
        JOIN event e ON er.eventId = e.eventId
        JOIN room rm ON er.roomId = rm.roomId
        JOIN hotel_floor hf ON rm.floorId = hf.floorId
        JOIN wing w ON hf.wingId = w.wingId
        JOIN building b ON w.buildingId = b.buildingId
        LEFT JOIN event_attendance ea ON er.eventId = ea.eventId
        WHERE er.eventDate BETWEEN ? AND ?
          AND rm.hasPermanentBeds = 0
    """
    events_params = [start_date, end_date]
    if selected_hotel_id is not None:
        events_sql += " AND b.hotelId = ?"
        events_params.append(selected_hotel_id)
    events_sql += """
        GROUP BY er.eventRoomId
        ORDER BY er.eventDate, er.eventId;
    """
    events_in_range = conn.execute(events_sql, events_params).fetchall()

    # ── Query 9: Which meeting rooms have the most total events? ──
    meeting_rooms_sql = """
        SELECT
            rm.roomId,
            rm.roomNumber,
            rm.roomFunction,
            rm.hasToilet,
            COUNT(DISTINCT er.eventId) AS total_events
        FROM room rm
        JOIN hotel_floor hf ON rm.floorId = hf.floorId
        JOIN wing w ON hf.wingId = w.wingId
        JOIN building b ON w.buildingId = b.buildingId
        LEFT JOIN event_room er
            ON er.roomId = rm.roomId
           AND er.eventDate BETWEEN ? AND ?
        WHERE rm.hasPermanentBeds = 0
    """
    meeting_rooms_params = [start_date, end_date]
    if selected_hotel_id is not None:
        meeting_rooms_sql += " AND b.hotelId = ?"
        meeting_rooms_params.append(selected_hotel_id)
    meeting_rooms_sql += """
        GROUP BY rm.roomId, rm.roomNumber, rm.roomFunction, rm.hasToilet
        ORDER BY total_events DESC, rm.roomNumber;
    """
    meeting_rooms = conn.execute(meeting_rooms_sql, meeting_rooms_params).fetchall()

    # ── Query 6: What is the average attendance for events in a given date range? ──
    avg_sql = """
        WITH FilteredEvents AS (
            SELECT DISTINCT er.eventId
            FROM event_room er
            JOIN room rm ON er.roomId = rm.roomId
            JOIN hotel_floor hf ON rm.floorId = hf.floorId
            JOIN wing w ON hf.wingId = w.wingId
            JOIN building b ON w.buildingId = b.buildingId
            WHERE er.eventDate BETWEEN ? AND ?
    """
    avg_params = [start_date, end_date]
    if selected_hotel_id is not None:
        avg_sql += " AND b.hotelId = ?"
        avg_params.append(selected_hotel_id)
    avg_sql += """
        ),
        EventCounts AS (
            SELECT fe.eventId, COUNT(ea.customerId) AS attendee_count
            FROM FilteredEvents fe
            LEFT JOIN event_attendance ea ON fe.eventId = ea.eventId
            GROUP BY fe.eventId
        )
        SELECT ROUND(AVG(attendee_count), 2) AS avg_attendance
        FROM EventCounts;
    """
    avg_attendance_row = conn.execute(avg_sql, avg_params).fetchone()

    # ── Query 7: Which reader locations have the most swipes? ──
    readers = conn.execute("""
        SELECT r.locationType, COUNT(cs.swipeId) AS total_swipes
        FROM reader r
        JOIN card_swipe cs ON r.readerId = cs.readerId
        GROUP BY r.locationType
        ORDER BY total_swipes DESC;
    """).fetchall()

    conn.close()

    return render_template(
        "events.html",
        hotels=hotels,
        selected_hotel_id=selected_hotel_id,
        start_date=start_date,
        end_date=end_date,
        events_in_range=events_in_range,
        meeting_rooms=meeting_rooms,
        reader_labels=json.dumps([r["locationType"] for r in readers]),
        reader_counts=json.dumps([r["total_swipes"] for r in readers]),
        avg_attendance=(
            avg_attendance_row["avg_attendance"]
            if avg_attendance_row and avg_attendance_row["avg_attendance"] is not None
            else "N/A"
        ),
    )


if __name__ == "__main__":
    app.run(debug=True, port=5000)
