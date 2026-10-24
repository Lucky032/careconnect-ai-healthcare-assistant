# CareConnect AI – Healthcare Appointment Assistant

## Project Overview
CareConnect AI is a web-based healthcare appointment assistant that helps users book appointments and ask healthcare-related general enquiries through an AI-powered conversational interface.

## Features
- **Appointment Booking:** Patients can submit their name, contact details, preferred date and time, and reason for the appointment.
- **AI Assistant:** Uses the Google Gemini API to respond to general enquiries and assist with appointment-related conversations.
- **Admin Login:** Provides an authenticated admin area.
- **Appointment Dashboard:** Allows the administrator to view appointments and manage their statuses.
- **Database Integration:** Stores appointment and enquiry information in MySQL.
- **Health Check:** Includes a `/health` endpoint.

## Technology Stack
- Python
- Flask
- MySQL
- Google Gemini API
- HTML, CSS
- python-dotenv

## Project Structure
```text
AI_Healthcare_Assistant/
├── backend/
│   └── main.py
├── frontend/
│   ├── Templates/
│   └── Statics/
│       └── css/
│           └── style.css
├── .env
└── README.md
```

## Setup Instructions

1. Install Python and MySQL.
2. Create a MySQL database named `ai_healthcare_assistant` and configure the required tables.
3. Create a virtual environment and install the project's dependencies.
4. Create a `.env` file in the project root with the required environment variables:
   - `GEMINI_API_KEY`
   - `FLASK_SECRET_KEY`
   - `DB_PASSWORD`
   - `ADMIN_PASSWORD`
5. Configure any additional database settings required by the application.
6. Start the Flask application using the project's configured Python entry point.
7. Open the local URL displayed in the terminal.

**Security:** Never publish API keys, passwords, or the `.env` file in a public repository.

## AI Usage
The Google Gemini API powers the conversational assistant. Prompt instructions guide the model to respond to general healthcare enquiries and help identify appointment-related details. The application handles temporary AI service errors with a user-friendly response.

## Limitations
The assistant is intended for general information and appointment assistance, not medical diagnosis or emergency care. Users should consult qualified healthcare professionals for medical advice.

## Author
Developed as a practical AI and automation project.
