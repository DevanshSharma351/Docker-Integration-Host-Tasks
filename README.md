# Docker Integration Host

**Docker Integration Host** is a powerful orchestration tool designed to manage multiple containers and networks across different hosts from a single, centralized interface. It aims to simplify the complexity of distributed container management, providing a unified platform for monitoring, scaling, and configuring your Docker infrastructure.

## Features

- **Single Host Management**: Orchestrate containers across multiple remote hosts.
- **Network Orchestration**: Manage and bridge networks between different Docker environments.
- **Centralized Control**: Unified dashboard for viewing and controlling container lifecycles.

## Getting Started

### Backend Setup (Django)

The backend handles the orchestration logic, communication with remote Docker hosts, and state management.

1. **Navigate to the backend directory:**
   ```bash
   cd backend
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run database migrations:**
   ```bash
   python manage.py migrate
   ```

5. **Start the Django development server:**
   ```bash
   python manage.py runserver
   ```
   The backend will be running at `http://localhost:8000`.

### Frontend Setup (Vite + React)

The frontend provides the user interface for managing your containers and network configurations.

1. **Navigate to the frontend directory:**
   ```bash
   cd frontend
   ```

2. **Install dependencies:**
   ```bash
   npm install
   ```

3. **Start the development server:**
   ```bash
   npm run dev
   ```
   The frontend will be running at `http://localhost:5173`.

## Architecture

- **Backend**: Django REST Framework
- **Frontend**: React with Vite and Tailwind CSS
