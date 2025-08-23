# Bojim BOQ Production Software - Setup Guide

This guide will help you set up and run the Bojim BOQ Production Software on your laptop, assuming no prior technical knowledge.

## What You'll Need

- A Windows, Mac, or Linux laptop with internet connection
- About 2GB of free disk space
- Administrator/admin privileges on your computer

## Step 1: Install Required Software

### 1.1 Install Python (Programming Language)

**Windows:**
1. Go to https://www.python.org/downloads/
2. Click "Download Python 3.12.x" (latest version)
3. Run the downloaded file
4. **IMPORTANT:** Check "Add Python to PATH" during installation
5. Click "Install Now"
6. Wait for installation to complete

**Mac:**
1. Go to https://www.python.org/downloads/
2. Click "Download Python 3.12.x"
3. Open the downloaded .pkg file
4. Follow the installation wizard
5. Open Terminal (press Cmd+Space, type "Terminal", press Enter)
6. Type: `python3 --version` and press Enter to verify installation

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv
```

### 1.2 Install Node.js (For the Web Interface)

**Windows/Mac:**
1. Go to https://nodejs.org/
2. Download the "LTS" version (recommended)
3. Run the installer and follow the setup wizard
4. Accept all default settings

**Linux:**
```bash
curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
sudo apt-get install -y nodejs
```

### 1.3 Install Git (Version Control)

**Windows:**
1. Go to https://git-scm.com/download/win
2. Download and run the installer
3. Accept all default settings during installation

**Mac:**
1. Open Terminal
2. Type: `git --version` and press Enter
3. If not installed, it will prompt you to install Xcode Command Line Tools

**Linux:**
```bash
sudo apt install git
```

### 1.4 Install Tesseract OCR (For Reading Text in Drawings)

**Windows:**
1. Go to https://github.com/UB-Mannheim/tesseract/wiki
2. Download the latest installer for Windows
3. Run the installer and note the installation path (usually C:\Program Files\Tesseract-OCR)
4. Add Tesseract to your system PATH:
   - Press Windows key + R, type "sysdm.cpl", press Enter
   - Click "Environment Variables"
   - Under "System Variables", find "Path" and click "Edit"
   - Click "New" and add the Tesseract installation path
   - Click OK on all windows

**Mac:**
1. Install Homebrew first (if not already installed):
   - Open Terminal
   - Paste: `/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"`
   - Press Enter and follow prompts
2. Install Tesseract:
   ```bash
   brew install tesseract
   ```

**Linux:**
```bash
sudo apt install tesseract-ocr tesseract-ocr-eng
```

## Step 2: Download the Software

1. Open Terminal (Mac/Linux) or Command Prompt (Windows)
2. Navigate to where you want to install the software:
   ```bash
   cd Desktop
   ```
3. Download the software:
   ```bash
   git clone https://github.com/your-repo/automated-boq-system.git
   cd automated-boq-system
   ```

## Step 3: Set Up the Backend (Server)

1. Navigate to the backend folder:
   ```bash
   cd automated-boq-backend
   ```

2. Install Poetry (Python package manager):
   **Windows:**
   ```bash
   pip install poetry
   ```
   **Mac/Linux:**
   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   ```

3. Install backend dependencies:
   ```bash
   poetry install
   ```

4. Start the backend server:
   ```bash
   poetry run fastapi dev app/main.py
   ```

   You should see output like:
   ```
   INFO:     Uvicorn running on http://127.0.0.1:8000
   ```

   **Keep this window open** - this is your backend server running.

## Step 4: Set Up the Frontend (Web Interface)

1. Open a **new** Terminal/Command Prompt window
2. Navigate to the frontend folder:
   ```bash
   cd Desktop/automated-boq-system/automated-boq-frontend
   ```

3. Install frontend dependencies:
   ```bash
   npm install
   ```

4. Start the frontend server:
   ```bash
   npm run dev
   ```

   You should see output like:
   ```
   Local:   http://localhost:5173/
   ```

## Step 5: Access the Application

1. Open your web browser (Chrome, Firefox, Safari, etc.)
2. Go to: `http://localhost:5173`
3. You should see the Bojim BOQ Production Software login page

## Step 6: First Time Setup

### Create Your Account
1. Click "Register" on the login page
2. Fill in your details:
   - Email: your email address
   - Name: your full name
   - Role: select "Client" (for creating projects)
   - Company: your company name
   - Password: create a secure password
3. Click "Register"

### Login
1. Use your email and password to log in
2. You'll be taken to the dashboard

## Step 7: Using the Software

### Creating Your First Project
1. Click "Create New Project"
2. Enter project details:
   - Project Name: e.g., "Office Building Renovation"
   - Description: brief project description
   - Measurement Standard: choose SMM7, RICS NRM, or CESMM
3. Click "Create Project"

### Uploading Drawings
1. Click on your project to open it
2. Click "Upload Drawings"
3. Select your PDF or AutoCAD files (.pdf, .dwg, .dxf)
4. Wait for processing to complete
5. Review the quality assessment and any architect queries generated

### Generating BOQ
1. After drawings are processed, click "Generate BOQ"
2. Wait for the system to analyze drawings and create quantities
3. Download the Excel BOQ file for pricing

### Cost Estimation
1. Click "Get Cost Estimate" to see project costs
2. Adjust hourly rate if needed
3. Select currency (GBP, USD, EUR, AED)

## Troubleshooting

### Common Issues

**"Python not found" error:**
- Make sure you checked "Add Python to PATH" during installation
- Restart your computer and try again

**"poetry not found" error:**
- Close and reopen Terminal/Command Prompt
- Try: `pip install poetry` again

**"npm not found" error:**
- Make sure Node.js installed correctly
- Restart your computer and try again

**Backend won't start:**
- Make sure you're in the `automated-boq-backend` folder
- Try: `poetry shell` then `fastapi dev app/main.py`

**Frontend won't start:**
- Make sure you're in the `automated-boq-frontend` folder
- Try deleting `node_modules` folder and running `npm install` again

**Tesseract errors:**
- Windows: Make sure Tesseract is in your PATH
- Mac: Try `brew reinstall tesseract`
- Linux: Try `sudo apt reinstall tesseract-ocr`

### Getting Help

If you encounter issues:
1. Check that both backend and frontend servers are running
2. Make sure you're using the correct URLs (localhost:8000 for backend, localhost:5173 for frontend)
3. Try restarting both servers
4. Check the Terminal/Command Prompt windows for error messages

### System Requirements

**Minimum:**
- 4GB RAM
- 2GB free disk space
- Internet connection for initial setup

**Recommended:**
- 8GB RAM
- 5GB free disk space
- Fast internet connection for drawing uploads

## Daily Usage

Once set up, to use the software daily:

1. Open two Terminal/Command Prompt windows
2. In first window:
   ```bash
   cd Desktop/automated-boq-system/automated-boq-backend
   poetry run fastapi dev app/main.py
   ```
3. In second window:
   ```bash
   cd Desktop/automated-boq-system/automated-boq-frontend
   npm run dev
   ```
4. Open browser to `http://localhost:5173`

## Features Overview

### Drawing Quality Assessment
- Automatic quality scoring (0-100)
- Identifies missing dimensions, unclear text, missing scale
- Generates professional queries for architects/engineers

### BOQ Generation
- Supports PDF and AutoCAD formats
- Complies with SMM7, RICS NRM, and CESMM standards
- Automatic quantity takeoff from drawings

### Cost Estimation
- Multi-currency support (GBP, USD, EUR, AED)
- Configurable hourly rates
- Detailed cost breakdowns

### Bidding Portal
- Online bid submission
- Automatic bid evaluation and ranking
- Excel BOQ templates with protected cells

### Export Features
- Excel BOQ files with formulas
- Architect query reports
- Bid comparison reports

## Security Notes

- The system uses an in-memory database (data resets when servers restart)
- For production use, consider setting up a permanent database
- Keep your login credentials secure
- Regular backups recommended for important projects

## Support

For technical support or questions about using the Bojim BOQ Production Software, please contact your system administrator or the development team.
