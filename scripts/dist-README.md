# RoboScope

Web-based Robot Framework Test Management Tool with Git integration, test execution, report analysis, environment management, and more.

## Quick Start

### 1. Install

**Linux / macOS:**
```bash
chmod +x install-mac-and-linux.sh
./install-mac-and-linux.sh
```

**Windows:**
```
install-windows.bat
```

This creates a Python virtual environment and installs all dependencies.

### 2. Start

**Linux / macOS:**
```bash
./start-mac-and-linux.sh
```

**Windows:**
```
start-windows.bat
```

### 3. Stop

**Linux / macOS:**
```bash
./stop-mac-and-linux.sh
```

**Windows:**
```
stop-windows.bat
```

### 4. Open

Open your browser at: **http://localhost:8145**

Default login:
- **Email:** `admin@roboscope.local`
- **Password:** `admin123`

> Change the admin password after first login via Settings > Users.

## Configuration

All settings are in the `.env` file (created automatically from `.env.example` on first install).

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `8145` | Server port |
| `HOST` | `0.0.0.0` | Bind address (`0.0.0.0` = all interfaces, `127.0.0.1` = localhost only) |
| `DATABASE_URL` | `sqlite:///./roboscope.db` | Database connection string |
| `SECRET_KEY` | `CHANGE-ME-IN-PRODUCTION` | JWT signing key (change this!) |
| `DEBUG` | `false` | Enable debug mode |
| `LOG_LEVEL` | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `WORKSPACE_DIR` | `~/.roboscope/workspace` | Directory for cloned Git repositories |
| `REPORTS_DIR` | `~/.roboscope/reports` | Directory for test execution reports |
| `VENVS_DIR` | `~/.roboscope/venvs` | Directory for Python virtual environments |

### Changing the Port

Edit `.env` and change `PORT`:
```
PORT=9000
```

Then restart with `./start-mac-and-linux.sh` (or `start-windows.bat`).

### Using PostgreSQL Instead of SQLite

Edit `.env`:
```
DATABASE_URL=postgresql://user:password@localhost:5432/roboscope
```

Note: PostgreSQL requires the `psycopg2` driver. Install it with:
```bash
.venv/bin/pip install psycopg2-binary
```

## System Requirements

- **Python 3.10 or higher** (3.12+ recommended)
- **No additional services required** (SQLite database, in-process task executor)
- **Supported platforms:** Linux (x86_64), macOS (Intel & Apple Silicon), Windows (x64)

### Checking Your Python Version

```bash
python3 --version
```

If you have multiple Python versions, you can specify which one to use before running `install-mac-and-linux.sh`:
```bash
# Use a specific Python version
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Features

- **Repository Management** — Clone and sync Git repositories, browse branches
- **Test Explorer** — Browse test files, view Robot Framework test cases and keywords
- **Test Execution** — Run tests via subprocess or Docker, with scheduling support
- **Environment Management** — Manage Python virtual environments, packages, and variables
- **Report Analysis** — Parse Robot Framework output.xml, compare test runs
- **Statistics & KPIs** — Success rates, trends, flaky test detection, deep analysis
- **Role-Based Access** — Viewer, Runner, Editor, Admin roles
- **Multi-Language UI** — English, German, French, Spanish
- **API Documentation** — Interactive Swagger UI at `/api/v1/docs`

## API

- **Swagger UI:** http://localhost:8145/api/v1/docs
- **ReDoc:** http://localhost:8145/api/v1/redoc
- **Health check:** http://localhost:8145/health

## FAQ — Common Problems

### "command not found: python3"

Python 3 is not installed or not in your PATH.

- **macOS:** `brew install python@3.12` or download from https://www.python.org/downloads/
- **Linux:** `sudo apt install python3` (Debian/Ubuntu) or `sudo dnf install python3` (Fedora)
- **Windows:** Download from https://www.python.org/downloads/ and ensure "Add to PATH" is checked during installation

### "ImportError: cannot import name 'StrEnum' from 'enum'"

You are running Python 3.10 or older. This has been fixed — if you see this error, you have an outdated version of RoboScope. Download the latest release.

### "ImportError: cannot import name 'UTC' from 'datetime'"

Same as above — you need a newer build of RoboScope. This was fixed for Python 3.10 compatibility.

### "ERROR: ... is not a supported wheel on this platform"

This can happen with the **offline** distribution if the bundled wheels don't include your platform. Solutions:
1. Use the **online** distribution instead (it downloads the correct wheels for your platform)
2. Ensure you're using a supported platform (Linux x86_64, macOS ARM/Intel, Windows x64)
3. Try upgrading pip: `.venv/bin/pip install --upgrade pip`

### "ERROR: Could not find a version that satisfies the requirement ..."

**Offline distribution:** The required wheel is missing. Use the online distribution instead.

**Online distribution:** Check your internet connection. If you're behind a proxy:
```bash
.venv/bin/pip install -r requirements.txt --proxy http://proxy:port
```

### "Address already in use" / "Port 8145 is already in use"

Another process is using port 8145. Either:
1. Stop the other process: `kill $(lsof -ti:8145)` (Linux/macOS)
2. Change the port in `.env`: `PORT=9000`

### "Error: Run ./install-mac-and-linux.sh first."

You need to run the install script before starting. It creates the virtual environment and installs dependencies.

### The page loads but shows a blank white screen

1. **Hard refresh** your browser: `Ctrl+Shift+R` (Windows/Linux) or `Cmd+Shift+R` (macOS)
2. **Clear browser cache** or try an incognito/private window
3. Check the browser console (`F12` > Console) for JavaScript errors

### "CSRF" or "CORS" errors in the browser console

If accessing RoboScope from a different hostname than `localhost`, add the hostname to the CORS configuration. Edit `.env`:
```
CORS_ORIGINS=["http://your-hostname:8145"]
```

### Database is locked (SQLite)

SQLite doesn't support concurrent writes well. This can happen under heavy load:
1. Ensure only one RoboScope instance is running
2. For production with multiple users, switch to PostgreSQL (see Configuration section above)

### How do I reset the admin password?

Log in as admin, go to **Settings > Users**, and use the password reset button. If you're locked out:
```bash
# Delete the database and restart (creates fresh admin)
rm roboscope.db
./start-mac-and-linux.sh
```

### How do I back up my data?

The SQLite database file is `roboscope.db` in the installation directory. Simply copy it:
```bash
cp roboscope.db roboscope-backup-$(date +%Y%m%d).db
```

### How do I update RoboScope?

1. Back up your `roboscope.db` and `.env` files
2. Extract the new release over the existing directory
3. Run `./install-mac-and-linux.sh` again to update dependencies
4. Run `./start-mac-and-linux.sh`

Your database and configuration will be preserved.

## Directory Structure

```
roboscope/
├── src/              # Backend application source
├── frontend_dist/    # Pre-built frontend (HTML, JS, CSS)
├── examples/         # Example Robot Framework test files
├── migrations/       # Database migration scripts
├── wheels/           # Python wheels for offline install (offline version only)
├── .env.example      # Configuration template
├── .env              # Your configuration (created by install script)
├── requirements.txt  # Python dependencies
├── install-mac-and-linux.sh   # Install script (Linux/macOS)
├── install-windows.bat        # Install script (Windows)
├── start-mac-and-linux.sh     # Start script (Linux/macOS)
├── start-windows.bat          # Start script (Windows)
├── stop-mac-and-linux.sh      # Stop script (Linux/macOS)
├── stop-windows.bat           # Stop script (Windows)
├── roboscope.db         # SQLite database (created on first run)
└── .venv/            # Python virtual environment (created by install script)
```

## License

Copyright (c) viadee Unternehmensberatung AG. All rights reserved.
