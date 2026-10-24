
from dotenv import load_dotenv
load_dotenv()

import os
import json
import re
import time as time_module
from datetime import date, datetime, time, timedelta
from pathlib import Path

from google import genai
from google.genai.errors import ServerError
import mysql.connector
from mysql.connector import Error
from flask import (
    Flask, flash, redirect, render_template, request, session, url_for
)

# --------------------------------------------------
# APPLICATION CONFIGURATION
# --------------------------------------------------

PROJECT_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = PROJECT_DIR / "frontend"

app = Flask(
    __name__,
    template_folder=str(FRONTEND_DIR / "Templates"),
    static_folder=str(FRONTEND_DIR / "Statics"),
    static_url_path="/static",
)

app.secret_key = os.environ.get("FLASK_SECRET_KEY", "")
if not app.secret_key:
    raise RuntimeError(
        "Set FLASK_SECRET_KEY in your .env file before starting Flask."
    )

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "127.0.0.1"),
    "port": int(os.environ.get("DB_PORT", "3306")),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", ""),
    "database": "ai_healthcare_assistant",
    "connection_timeout": 5,
}

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

APPOINTMENT_MINUTES = 10
CLINIC_OPEN = time(9, 0)
CLINIC_CLOSE = time(17, 0)


# --------------------------------------------------
# DATABASE
# --------------------------------------------------

def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)


# --------------------------------------------------
# APPOINTMENT TIME VALIDATION
# --------------------------------------------------

def parse_appointment_time(value):
    value = (value or "").strip()

    for fmt in ("%H:%M", "%H:%M:%S", "%I:%M %p", "%I %p"):
        try:
            parsed = datetime.strptime(value.upper(), fmt).time()
            return parsed.replace(second=0, microsecond=0)
        except ValueError:
            continue

    raise ValueError("Invalid appointment time")


def validate_appointment_slot(appointment_date, appointment_time):
    if appointment_date < date.today():
        return "Appointment date cannot be in the past."

    if appointment_time < CLINIC_OPEN or appointment_time >= CLINIC_CLOSE:
        return (
            "Appointments are available between 09:00 AM and 05:00 PM. "
            "The last start time is 04:50 PM."
        )

    if (
        appointment_time.minute % APPOINTMENT_MINUTES != 0
        or appointment_time.second != 0
    ):
        return (
            "Please choose a 10-minute slot, such as 09:00, 09:10, "
            "or 09:20."
        )

    return None


def create_appointment_safely(details):
    """Check overlapping active appointments before inserting a request."""
    connection = None
    cursor = None
    lock_name = (
        "careconnect-booking-"
        + details["appointment_date"].isoformat()
    )
    lock_acquired = False

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("SELECT GET_LOCK(%s, 10)", (lock_name,))
        lock_result = cursor.fetchone()
        lock_acquired = bool(lock_result and lock_result[0] == 1)

        if not lock_acquired:
            return (
                False,
                "Booking is busy right now. Please try again in a moment."
            )

        requested_start = details["appointment_time"]
        requested_end = (
            datetime.combine(
                details["appointment_date"], requested_start
            ) + timedelta(minutes=APPOINTMENT_MINUTES)
        ).time()

        cursor.execute(
            """
            SELECT appointment_time
            FROM appointments
            WHERE appointment_date = %s
              AND status IN ('Pending', 'Confirmed')
              AND appointment_time < %s
              AND ADDTIME(appointment_time, '00:10:00') > %s
            FOR UPDATE
            """,
            (
                details["appointment_date"],
                requested_end,
                requested_start,
            ),
        )

        if cursor.fetchone():
            connection.rollback()

            cursor.execute(
                """
                SELECT appointment_time
                FROM appointments
                WHERE appointment_date = %s
                  AND status IN ('Pending', 'Confirmed')
                """,
                (details["appointment_date"],),
            )
            occupied = [row[0] for row in cursor.fetchall()]
            suggestions = []

            candidate = (
                datetime.combine(
                    details["appointment_date"], requested_start
                ) + timedelta(minutes=APPOINTMENT_MINUTES)
            )
            closing = datetime.combine(
                details["appointment_date"], CLINIC_CLOSE
            )

            while (
                candidate + timedelta(minutes=APPOINTMENT_MINUTES)
                <= closing
                and len(suggestions) < 3
            ):
                candidate_time = candidate.time()
                candidate_end = (
                    candidate + timedelta(minutes=APPOINTMENT_MINUTES)
                ).time()

                overlaps = any(
                    existing < candidate_end
                    and (
                        datetime.combine(
                            details["appointment_date"], existing
                        ) + timedelta(minutes=APPOINTMENT_MINUTES)
                    ).time() > candidate_time
                    for existing in occupied
                )

                if not overlaps:
                    suggestions.append(candidate.strftime("%I:%M %p"))

                candidate += timedelta(minutes=APPOINTMENT_MINUTES)

            if suggestions:
                return (
                    False,
                    "That slot is already requested or booked. Next "
                    "available slots: "
                    + ", ".join(suggestions)
                    + ". Please send your preferred time."
                )

            return (
                False,
                "That slot is already requested or booked, and no later "
                "slots are available that day. Please choose another date."
            )

        cursor.execute(
            """
            INSERT INTO appointments
            (
                patient_name, email, phone, appointment_date,
                appointment_time, reason
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                details["patient_name"],
                details["email"],
                details["phone"],
                details["appointment_date"],
                details["appointment_time"],
                details["reason"],
            ),
        )

        connection.commit()
        return (
            True,
            "Appointment request submitted and is pending clinic confirmation."
        )

    except Error:
        if connection is not None:
            connection.rollback()

        app.logger.exception("Appointment database operation failed.")
        return (
            False,
            "We could not save the appointment request. Please try again."
        )

    finally:
        if cursor is not None:
            if lock_acquired:
                try:
                    cursor.execute("SELECT RELEASE_LOCK(%s)", (lock_name,))
                    cursor.fetchone()
                except Error:
                    app.logger.exception("Could not release appointment lock.")

            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()


# --------------------------------------------------
# HOME
# --------------------------------------------------

@app.get("/")
def home():
    return render_template("index.html")


# --------------------------------------------------
# NORMAL APPOINTMENT BOOKING
# --------------------------------------------------

@app.route("/book", methods=["GET", "POST"])
def book_appointment():
    if request.method == "GET":
        return render_template(
            "book_appointment.html",
            today=date.today().isoformat(),
        )

    patient_name = request.form.get("patient_name", "").strip()
    email = request.form.get("email", "").strip()
    phone = request.form.get("phone", "").strip()
    date_text = request.form.get("appointment_date", "").strip()
    time_text = request.form.get("appointment_time", "").strip()
    reason = request.form.get("reason", "").strip()

    if not all(
        [patient_name, email, phone, date_text, time_text, reason]
    ):
        flash("Please complete all required fields.", "error")
        return redirect(url_for("book_appointment"))

    if (
        len(patient_name) > 100
        or len(email) > 150
        or len(phone) > 20
        or len(reason) > 500
    ):
        flash("One or more fields exceed the allowed length.", "error")
        return redirect(url_for("book_appointment"))

    if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
        flash("Please enter a valid email address.", "error")
        return redirect(url_for("book_appointment"))

    try:
        appointment_date = date.fromisoformat(date_text)
        appointment_time = parse_appointment_time(time_text)
    except ValueError:
        flash("Please enter a valid appointment date and time.", "error")
        return redirect(url_for("book_appointment"))

    slot_error = validate_appointment_slot(
        appointment_date, appointment_time
    )
    if slot_error:
        flash(slot_error, "error")
        return redirect(url_for("book_appointment"))

    success, result_message = create_appointment_safely({
        "patient_name": patient_name,
        "email": email,
        "phone": phone,
        "appointment_date": appointment_date,
        "appointment_time": appointment_time,
        "reason": reason,
    })

    flash(result_message, "success" if success else "error")
    return redirect(url_for("book_appointment"))


# --------------------------------------------------
# GEMINI AI WITH RETRY
# --------------------------------------------------

def gemini_generate_with_retry(client, prompt):
    """
    Retry temporary Gemini server errors three times.
    Other exceptions are handled by the calling route.
    """
    for attempt in range(3):
        try:
            return client.models.generate_content(
                model="gemini-3.6-flash",
                contents=prompt,
            )
        except ServerError:
            if attempt == 2:
                raise

            # Wait 1.5 seconds, then 3 seconds before retrying.
            time_module.sleep(1.5 * (attempt + 1))


def generate_ai_response(message):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not configured.")

    client = genai.Client(api_key=api_key)

    prompt = f"""
You are CareConnect AI, a healthcare administrative assistant.
Be polite and concise. Do not diagnose, prescribe, or recommend treatments.
Do not invent clinic hours, address, fees, doctors, or availability.
Appointments are 10-minute requests between 09:00 and 17:00.
Never guess whether a slot is available; the website checks availability.
For emergencies, advise contacting local emergency services.
Do not ask for medical records or payment details.

Patient message: {message}
"""

    response = gemini_generate_with_retry(client, prompt)
    answer = (response.text or "").strip()

    if not answer:
        raise ValueError("Gemini returned an empty response.")

    return answer


def extract_booking_details(message, current_details):
    """Extract booking fields from the message; backend validates the fields."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not configured.")

    client = genai.Client(api_key=api_key)
    today_text = date.today().isoformat()

    prompt = f"""
Extract appointment information from the user's message into ONE valid JSON object.
Today is {today_text}. Clinic hours are 09:00 to 17:00, with valid start times
09:00, 09:10, ... 14:00, 14:10, ... 16:50.
"2 PM" MUST become "14:00"; "2:10 PM" MUST become "14:10".
Interpret relative dates using today's date.

Keys: patient_name, email, phone, appointment_date (YYYY-MM-DD),
appointment_time (HH:MM 24-hour), reason.
Values must be strings or empty strings.
Merge with existing details, preserving existing non-empty values unless
the user clearly corrects them. Never invent missing information.
Return JSON only.

Existing details: {json.dumps(current_details)}
User message: {message}
"""

    response = gemini_generate_with_retry(client, prompt)
    raw = (response.text or "").strip()
    raw = re.sub(
        r"^```(?:json)?\s*|\s*```$",
        "",
        raw,
        flags=re.IGNORECASE,
    )

    data = json.loads(raw)
    allowed = {
        "patient_name", "email", "phone",
        "appointment_date", "appointment_time", "reason",
    }

    merged = dict(current_details)

    for key in allowed:
        value = data.get(key, "")
        if isinstance(value, str) and value.strip():
            merged[key] = value.strip()

    return merged


def booking_missing_field(details):
    labels = {
        "patient_name": "your full name",
        "email": "your email address",
        "phone": "your phone number",
        "appointment_date": "the appointment date",
        "appointment_time": "the appointment time",
        "reason": "a brief reason for the visit (no detailed medical records)",
    }

    for key, label in labels.items():
        if not details.get(key):
            return key, label

    return None, None


def valid_booking_details(details):
    if len(details.get("patient_name", "")) > 100:
        return "Name must be 100 characters or fewer."

    if (
        len(details.get("email", "")) > 150
        or not re.fullmatch(
            r"[^\s@]+@[^\s@]+\.[^\s@]+",
            details.get("email", ""),
        )
    ):
        return "Please provide a valid email address."

    if (
        len(details.get("phone", "")) > 20
        or not re.fullmatch(
            r"[+()\d\s.-]{7,20}",
            details.get("phone", ""),
        )
    ):
        return "Please provide a valid phone number (7–20 characters)."

    if len(details.get("reason", "")) > 500:
        return "Reason must be 500 characters or fewer."

    try:
        appt_date = date.fromisoformat(details["appointment_date"])
        appt_time = parse_appointment_time(details["appointment_time"])
    except (ValueError, KeyError):
        return (
            "Please provide a clear date and time, for example "
            "2026-10-25 at 10:00 AM."
        )

    return validate_appointment_slot(appt_date, appt_time)


# --------------------------------------------------
# AI ASSISTANT
# --------------------------------------------------

@app.route("/assistant", methods=["GET", "POST"])
def assistant():
    message = ""
    answer = None
    history = session.get("assistant_history", [])

    if request.method == "POST":
        message = request.form.get("message", "").strip()

        if not message:
            flash("Please enter a message.", "error")
            return redirect(url_for("assistant"))

        if len(message) > 2000:
            flash("Your message must be 2,000 characters or fewer.", "error")
            return redirect(url_for("assistant"))

        lowered = message.lower()
        yes_words = {
            "yes", "yes please", "confirm", "confirm booking",
            "book it", "go ahead", "correct",
        }
        no_words = {
            "no", "no thanks", "cancel", "don't book",
            "do not book", "change",
        }

        draft = session.get("booking_draft")
        pending_confirmation = session.get(
            "booking_pending_confirmation", False
        )
        booking_intent = any(
            word in lowered
            for word in [
                "appointment", "book", "booking",
                "schedule", "visit", "slot",
            ]
        )

        if (
            draft
            and pending_confirmation
            and lowered.strip(" .!\t") in yes_words
        ):
            slot_error = valid_booking_details(draft)

            if slot_error:
                answer = (
                    f"I can't submit this request yet: {slot_error} "
                    "Please send the corrected detail."
                )
                session["booking_pending_confirmation"] = False
            else:
                parsed_date = date.fromisoformat(
                    draft["appointment_date"]
                )
                parsed_time = parse_appointment_time(
                    draft["appointment_time"]
                )

                success, result = create_appointment_safely({
                    **draft,
                    "appointment_date": parsed_date,
                    "appointment_time": parsed_time,
                })

                if success:
                    answer = (
                        f"{result} Your request is for "
                        f"{parsed_date.isoformat()} at "
                        f"{parsed_time.strftime('%I:%M %p')}. "
                        "The clinic will confirm it."
                    )
                    session.pop("booking_draft", None)
                    session.pop("booking_pending_confirmation", None)
                else:
                    answer = (
                        result
                        + " Please tell me another 10-minute slot "
                        "between 09:00 AM and 04:50 PM."
                    )
                    session["booking_pending_confirmation"] = False

        elif (
            draft
            and pending_confirmation
            and lowered.strip(" .!\t") in no_words
        ):
            session.pop("booking_draft", None)
            session.pop("booking_pending_confirmation", None)
            answer = (
                "No appointment has been submitted. Tell me what you'd "
                "like to change, or start a new booking request."
            )

        elif booking_intent or draft:
            try:
                details = extract_booking_details(message, draft or {})
                session["booking_draft"] = details

                missing_key, missing_label = booking_missing_field(details)

                if missing_key:
                    answer = (
                        "Sure, I can help with that. What is "
                        f"{missing_label}?"
                    )
                    session["booking_pending_confirmation"] = False

                else:
                    validation_error = valid_booking_details(details)

                    if validation_error:
                        answer = (
                            validation_error
                            + " Please send the corrected information."
                        )
                        session["booking_pending_confirmation"] = False

                    else:
                        parsed_date = date.fromisoformat(
                            details["appointment_date"]
                        )
                        parsed_time = parse_appointment_time(
                            details["appointment_time"]
                        )

                        answer = (
                            "Please review your appointment request:\n"
                            f"Name: {details['patient_name']}\n"
                            f"Email: {details['email']}\n"
                            f"Phone: {details['phone']}\n"
                            f"Date: {parsed_date.isoformat()}\n"
                            f"Time: {parsed_time.strftime('%I:%M %p')}\n"
                            f"Reason: {details['reason']}\n\n"
                            "I will check the slot when you confirm. "
                            "Reply YES to submit this request or NO to cancel."
                        )
                        session["booking_pending_confirmation"] = True

            except Exception:
                app.logger.exception("AI booking assistant failed.")
                answer = (
                    "Sorry, the AI assistant is temporarily busy. "
                    "No appointment has been booked. Please try again "
                    "in a minute, or use the normal Book Appointment form."
                )

        else:
            try:
                answer = generate_ai_response(message)
            except Exception:
                app.logger.exception("Gemini AI response generation failed.")
                answer = (
                    "The AI assistant is temporarily unavailable. "
                    "Please try again shortly."
                )

        category = "Appointments" if booking_intent or draft else "General"
        connection = None
        cursor = None

        try:
            connection = get_db_connection()
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO enquiries
                (patient_name, message, category, ai_response)
                VALUES (%s, %s, %s, %s)
                """,
                ("Guest", message, category, answer or ""),
            )
            connection.commit()

        except Error:
            app.logger.exception("Could not save the enquiry.")

        finally:
            if cursor is not None:
                cursor.close()

            if connection is not None and connection.is_connected():
                connection.close()

        history.append({"message": message, "answer": answer})
        session["assistant_history"] = history[-12:]
        session.modified = True

    return render_template(
        "assistant.html",
        answer=answer,
        message=message,
        history=history,
    )


# --------------------------------------------------
# ADMIN LOGIN
# --------------------------------------------------

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        password = request.form.get("password", "")

        if ADMIN_PASSWORD and password == ADMIN_PASSWORD:
            session.clear()
            session["is_admin"] = True
            return redirect(url_for("admin_dashboard"))

        flash(
            "Invalid admin password or admin password not configured.",
            "error",
        )

    return render_template("admin_login.html")


@app.post("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("home"))


# --------------------------------------------------
# ADMIN DASHBOARD
# --------------------------------------------------

@app.get("/admin")
def admin_dashboard():
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                COUNT(*) AS total,
                COALESCE(SUM(status = 'Pending'), 0) AS pending,
                COALESCE(SUM(status = 'Confirmed'), 0) AS confirmed,
                COALESCE(SUM(status = 'Cancelled'), 0) AS cancelled
            FROM appointments
            """
        )
        stats = cursor.fetchone()

        cursor.execute(
            """
            SELECT id, patient_name, email, phone, appointment_date,
                   appointment_time, reason, status, created_at
            FROM appointments
            ORDER BY created_at DESC
            LIMIT 100
            """
        )
        appointments = cursor.fetchall()

        return render_template(
            "dashboard.html",
            stats=stats,
            appointments=appointments,
        )

    except Error:
        app.logger.exception("Could not load admin dashboard.")
        flash("Unable to load dashboard data.", "error")
        return redirect(url_for("home"))

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()


@app.post("/admin/appointment/<int:appointment_id>/status")
def update_appointment_status(appointment_id):
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))

    status = request.form.get("status", "")
    allowed_statuses = {"Pending", "Confirmed", "Cancelled"}

    if status not in allowed_statuses:
        flash("Invalid appointment status.", "error")
        return redirect(url_for("admin_dashboard"))

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE appointments SET status = %s WHERE id = %s",
            (status, appointment_id),
        )
        connection.commit()

        if cursor.rowcount == 0:
            flash("Appointment not found.", "error")
        else:
            flash("Appointment status updated.", "success")

    except Error:
        app.logger.exception("Could not update appointment status.")
        flash("Could not update appointment status.", "error")

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()

    return redirect(url_for("admin_dashboard"))


# --------------------------------------------------
# HEALTH CHECK
# --------------------------------------------------

@app.get("/health")
def health_check():
    connection = None

    try:
        connection = get_db_connection()
        connection.ping(reconnect=False)
        return {"status": "ok", "database": "connected"}, 200

    except Error:
        return {"status": "error", "database": "unavailable"}, 503

    finally:
        if connection is not None and connection.is_connected():
            connection.close()


if __name__ == "__main__":
    app.run(debug=True)
