# Echo Desk — College Complaint Portal

A Flask + MongoDB college complaint portal with student registration/login, an admin dashboard, complaint submission, status history, and Socket.IO live status updates.

## Requirements
- Python 3.10+
- MongoDB running locally, or a MongoDB Atlas URI

## Setup (Windows / VS Code)
1. Extract this project folder.
2. Open a terminal in the `EchoDesk_Complete_Project` folder.
3. Create and activate a virtual environment:
   ```powershell
   python -m venv venv
   .\venv\Scripts\activate
   ```
4. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```
5. Copy `.env.example` to `.env`, then set a strong `SECRET_KEY` and your MongoDB URI.
6. Create the first admin:
   ```powershell
   python create_admin.py
   ```
7. Start the app:
   ```powershell
   python app.py
   ```
8. Open http://127.0.0.1:5000

## Features
- Student self-registration (student role only)
- Admin account provisioned by a separate script
- Login/logout with hashed passwords
- Submit complaint with category and department
- Student-only complaint tracking
- Admin status updates and remarks
- Complaint history timeline
- Socket.IO status updates to the complaint owner's room

## Notes
- This is a development starter, not a production-hardened deployment.
- Before public deployment, add CSRF protection (for example Flask-WTF), login rate limiting, email verification, secure production cookie settings, stronger validation, backups, and production server configuration.
- Do not expose `.env`, commit secrets, or enable Flask debug mode in production.
- Live tracking is status-based, not GPS tracking.

## Separate login pages
- Student login: http://127.0.0.1:5000/student/login
- Admin login: http://127.0.0.1:5000/admin/login

The home page also links to both login pages. Student and admin roles are checked by the backend.
The student tracking page shows a status progress bar that updates live when an admin changes the complaint status.


## Email notifications for complaint updates

The admin dashboard includes a checked-by-default **Email student about this update** option. When selected, saving the complaint status and admin remarks sends an email to the student's registered email address. This also sends a resolution email when the status is set to **Resolved**. If email is not configured or sending fails, the complaint update is still saved and the dashboard shows an email error.

1. Copy `.env.example` to `.env` (or add these values to your existing `.env`).
2. Configure `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, and `SMTP_FROM`. For Gmail, use a Google App Password rather than your regular account password. Keep `.env` private and never commit it to GitHub.
3. For Gmail with port 587, keep `SMTP_USE_SSL=false`. For providers that require implicit SSL, use their SSL port (often 465) and set `SMTP_USE_SSL=true`.
4. Restart `python app.py`, update a test complaint, and check the student's inbox/spam folder.

Uncheck the email option when you want to save a status/remarks update without sending an email. The student's email is taken from the address used during registration.
