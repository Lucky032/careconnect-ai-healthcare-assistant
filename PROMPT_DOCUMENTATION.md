# CareConnect AI – Prompt Engineering Documentation

## 1. Project Overview

CareConnect AI is a web-based healthcare appointment assistant developed using Python, Flask, MySQL, and the Google Gemini API.

The application allows users to book appointments through a standard booking form and interact with an AI-powered assistant for general enquiries and appointment-related conversations. An administrative dashboard allows authorized administrators to view appointments and update their statuses.

This document describes the AI tools used, the actual application prompt, the prompt design techniques, AI-assisted development, challenges, and the final outcome.

## 2. Project Objectives

The main objectives of this project are:

- To develop a functional healthcare appointment booking application.
- To integrate a conversational AI assistant using the Google Gemini API.
- To extract appointment information from natural-language messages.
- To store appointment and enquiry information in a MySQL database.
- To provide an administrative interface for appointment management.
- To handle temporary AI service failures gracefully.
- To use AI-assisted development to support implementation and debugging.

## 3. Tools and Technologies

| Tool or Technology | Purpose |
|---|---|
| ChatGPT | Assisted with development planning, code implementation, debugging, and troubleshooting. |
| Google Gemini API | Generates AI responses and processes appointment-related information. |
| Python | Backend programming language. |
| Flask | Web application framework. |
| MySQL | Database for appointment and enquiry information. |
| HTML and CSS | User interface development. |
| python-dotenv | Loads environment variables for configuration and credentials. |

## 4. AI-Assisted Development Approach

ChatGPT was used as a development assistant during the implementation of CareConnect AI. The development workflow involved defining requirements, implementing application components, investigating errors, and refining the code while preserving existing functionality.

The following are representative development prompt examples describing the work. They are not presented as a verbatim transcript of the original ChatGPT conversation.

### 4.1 Project Planning

**Prompt example:**

"Help me build a healthcare appointment assistant using Python, Flask, MySQL, and the Google Gemini API. Include appointment booking, an AI assistant, an admin login, an appointment dashboard, and database integration."

**Objective:**

To define the project requirements and identify the main application components.

### 4.2 Backend Implementation

**Prompt example:**

"Help me implement the Flask backend, including appointment booking routes, database operations, admin authentication, and appointment status management."

**Objective:**

To connect the user interface to backend logic and database operations.

### 4.3 AI Integration

**Prompt example:**

"Help me integrate the Google Gemini API into my Flask application so users can interact with an AI assistant for general enquiries and appointment-related conversations."

**Objective:**

To integrate generative AI into the application workflow.

### 4.4 Debugging and Code Preservation

**Prompt example:**

"Investigate the Gemini API 503 service-unavailable error. Add appropriate retry handling and a user-friendly fallback response without disturbing existing working features."

**Objective:**

To address a temporary external service failure while preserving existing application functionality.

### 4.5 Development Principle

The development process emphasized reviewing the existing implementation before making changes. Fixes were intended to address specific problems rather than unnecessarily rewriting working features.

## 5. Actual Application Prompt Engineering

### 5.1 Appointment Information Extraction

**Purpose**

The application uses a prompt to extract appointment details from a user's natural-language message. The prompt instructs the Gemini model to return a single JSON object with specified fields and formats.

**Actual prompt from the application code**

```python
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
```

### 5.2 Prompt Design Techniques

The prompt uses several techniques to guide the model.

**1. Clear task definition**

The opening instruction explicitly defines the task as extracting appointment information from the user's message.

**2. Structured output**

The model is instructed to return one JSON object. This makes the response easier for the backend to process than unrestricted conversational text.

**3. Defined data fields**

The prompt specifies six fields: patient name, email, phone, appointment date, appointment time, and reason.

**4. Date context**

The current date is supplied through `today_text`, helping the model interpret relative expressions such as "tomorrow."

**5. Time normalization**

The prompt gives explicit examples for converting 12-hour time expressions into 24-hour time, such as converting 2 PM to 14:00.

**6. Context retention**

Previously collected details are included through `current_details`. The prompt instructs the model to preserve existing non-empty values unless the user clearly corrects them.

**7. Missing-information handling**

The model is instructed not to invent missing details and to return empty strings for unavailable values.

**8. Output constraints**

The instruction to return JSON only is intended to reduce extra text around the structured response.

### 5.3 Expected Output Structure

The model is instructed to return these fields:

- `patient_name`
- `email`
- `phone`
- `appointment_date`
- `appointment_time`
- `reason`

The expected formats are:

- Date: `YYYY-MM-DD`
- Time: `HH:MM` in 24-hour format
- Other values: strings, including empty strings when information is missing

**Illustrative example**

If a user says, "I need an appointment tomorrow at 2 PM," the model should interpret the date using the supplied current date and normalize the time to `14:00`.

The model should not invent a patient name, email address, phone number, or reason that the user has not provided.

The final result must still be validated by the application before any appointment is saved.

## 6. Prompt Iteration and Improvement

Prompt engineering involves defining a task, specifying the required output, providing relevant context, and evaluating whether the response meets the application's needs.

In this project, the appointment extraction prompt incorporates:

- Explicit task instructions.
- A defined JSON structure.
- Date and time formatting rules.
- Existing conversation details.
- Instructions to preserve previously collected information.
- Instructions not to invent missing information.

These design choices help make the model's output more consistent with the application's expected data structure.

**Documentation accuracy note:** The prompt above is verified against the code snippet provided for this documentation. A separate original-versus-revised prompt comparison has not been established from the available evidence. Therefore, this document does not claim that a specific before-and-after prompt revision was performed.

## 7. Challenges and Solutions

### Challenge 1: Integrating Generative AI

**Challenge:** Connecting the conversational AI model to the Flask backend.

**Approach:** Integrated the Google Gemini API into the application workflow.

### Challenge 2: Extracting Structured Appointment Information

**Challenge:** Users express appointment requirements in natural language rather than a fixed data format.

**Approach:** Designed a prompt specifying the required fields, date and time formats, context retention, and JSON-only output.

### Challenge 3: Temporary AI Service Failure

**Challenge:** The Gemini API returned a 503 service-unavailable error during development.

**Approach:** Added retry handling and a user-friendly fallback response so that a temporary AI service failure could be handled more gracefully.

### Challenge 4: Database Integration

**Challenge:** Persisting appointment and enquiry information.

**Approach:** Integrated MySQL database operations with the Flask application.

### Challenge 5: Preserving Existing Functionality

**Challenge:** Fixing issues without disrupting working application features.

**Approach:** Focused development changes on the reported issue and retained existing booking and administrative workflows.

## 8. Testing and Validation

The following features were reported as working during development:

- Home page.
- Standard appointment booking.
- AI assistant interaction.
- Admin login.
- Appointment dashboard.
- Appointment status updates.
- MySQL integration.

The Gemini API service-unavailable error was also addressed through retry and fallback handling.

Before submission, the final application should be tested again. Testing should confirm that appointment information is validated, invalid or incomplete AI responses are handled safely, and temporary service failures do not expose sensitive details or raw server errors.

Only tests actually performed should be described as completed.

## 9. Security and Responsible AI

The application uses environment variables to manage sensitive configuration values, including API keys and passwords.

The `.env` file must not be uploaded to a public repository.

The AI assistant is intended for general information and appointment assistance. It must not be presented as a replacement for medical diagnosis, professional healthcare advice, or emergency services.

AI-generated information should be treated as untrusted until validated by the application. The backend should independently validate required fields, date and time formats, clinic hours, and appointment availability before saving a booking.

## 10. Final Outcome

CareConnect AI combines a conversational AI interface with a healthcare appointment booking workflow, MySQL database integration, and an administrative dashboard.

The project demonstrates the practical application of generative AI, structured prompting, backend development, database integration, error handling, and AI-assisted software development.

## 11. Submission Evidence

The following materials should accompany the project where required by the assessment:

1. This prompt engineering documentation.
2. The project source code or an accessible project repository.
3. A demonstration video showing the application's implemented features.
4. Verified development prompts and genuine prompt revisions, where available.
5. Evidence of testing the main application workflows.

The submitted documentation should accurately distinguish verified implementation details from illustrative examples and proposed improvements.
