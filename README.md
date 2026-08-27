````markdown
## First-time setup

Make sure you have:

- Python 3.11+
- Node.js
- npm

### 1. Create the Python virtual environment

From the project root:

```bash
cd backend
python3.11 -m venv .venv

Replace 3.11 with your desired Python version, e.g. python3.12 -m venv .venv.
````

### 2. Activate the virtual environment

**Linux / macOS:**

```bash
source .venv/bin/activate
```

**Windows PowerShell:**

```powershell
.venv\Scripts\Activate.ps1
```

### 3. Install backend dependencies

With the virtual environment activated:

```bash
pip install -r requirements.txt
```

### 4. Install frontend dependencies

From the project root:

```bash
cd frontend
npm install
cd ..
```

### 5. Start the application

From the project root:

```bash
./start.sh
```

The application will start both services:

* Frontend: `http://localhost:5173`
* Backend: `http://localhost:8000`

`start.sh` only starts the backend and frontend. It does **not** install dependencies.

### Subsequent runs

The virtual environment and dependencies only need to be set up once.

For subsequent runs on Linux / macOS:

```bash
cd backend
source .venv/bin/activate
cd ..
./start.sh
```

For Windows PowerShell:

```powershell
cd backend
.venv\Scripts\Activate.ps1
cd ..
.\start.sh
```

For backend environment variables and frontend-specific configuration, see the existing READMEs inside `backend/` and `frontend/`.

```
```
