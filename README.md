# Docker Integration Host

A full-stack Docker Management Dashboard built with Django REST Framework (Backend) and React (Frontend). This application allows you to remotely manage Docker hosts, pull/push images, monitor containers, and manage role-based access controls across your infrastructure.

## Project Structure

The repository is split into two independent modules:
- `backend/`: Django API server providing endpoints for Docker SDK integration, database persistence, and RBAC authentication.
- `frontend/`: React single-page application serving the dashboard UI.

---

## Local Setup Guidelines

### Prerequisites
- Python 3.10+
- Node.js 18+
- Docker Engine locally installed and running (for local container management endpoints)
- Git

### 1. Backend Setup (Django)

Open your terminal and navigate to the project root:

1. **Change to the backend directory**
   ```bash
   cd backend
   ```

2. **Create and activate a Python virtual environment**
   - Windows:
     ```bash
     python -m venv venv
     .\venv\Scripts\activate
     ```
   - macOS / Linux:
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```

3. **Install the required dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run Database Migrations**
   Initialize the SQLite database schema:
   ```bash
   python manage.py migrate
   ```

5. **Create a Superuser** (Required to access all features & bypass RBAC limitations out-of-the-box):
   ```bash
   python manage.py createsuperuser
   ```

6. **Start the Development Server**
   ```bash
   python manage.py runserver
   ```
   *The API will be available at `http://127.0.0.1:8000/`*

---

### 2. Frontend Setup (React)

Open a **new, separate terminal tab/window** and navigate to the project root:

1. **Change to the frontend directory**
   ```bash
   cd frontend
   ```

2. **Install node dependencies**
   ```bash
   npm install
   ```

3. **Start the Development Server**
   ```bash
   npm run dev
   ```
   *The React dashboard will be accessible at the Localhost URL provided in the terminal (usually `http://localhost:5173`).*

---

## Post-Setup Verification

1. Head to your frontend dashboard URL in the browser.
2. Login using the Superuser credentials you just generated.
3. **Module 1 (RBAC & Auth):** Confirm your user role functions properly, and try assigning hosts.
4. **Module 2 (Containers):** Verify you can list, stop, and boot containers directly from your dashboard.
5. **Module 3 (Images):** Switch over to the Images tab to pull real images from registries seamlessly using the background queue jobs!

## Important Notes for Windows Users 

A platform-specific handler is automatically enabled within `backend/containers/models.py`. If you define "local-docker" as your host, the Docker daemon socket transparently defaults to `npipe:////./pipe/docker_engine`, meaning everything connects naturally without Unix socket errors! Make sure Docker Desktop is open and running in the background before testing the UI.
