# FairTrace

AI-powered fraud detection and verification platform built for the Google Solution Hackathon.

---

## Overview

FairTrace helps organizations detect suspicious activity, verify records, and improve trust using AI-assisted workflows. The platform combines a Python backend, Firebase integration, and a modern frontend dashboard to deliver actionable insights.

Instead of just generating reports, FairTrace focuses on practical workflows — detecting anomalies, flagging potential risks, and presenting them in a way that teams can understand and act on quickly.

---

## ⚠️ Deployment Status

> 🚧 **Note:** Deployment is currently not configured.
> This project is intended to be run **locally** for demonstration and development purposes.

---

## Features

* AI-assisted fraud / bias detection workflows
* Secure user authentication
* Record verification system
* Dashboard for monitoring cases and results
* Firebase integration for cloud services
* Responsive frontend UI

---

## 📊 Sample Dataset

A sample dataset is included in the repository:

```bash
data/sample_dataset.csv
```

You can use this file to test the system by uploading it through the application.

### 🧪 What you can test with it:

* Bias detection (Disparate Impact Ratio)
* Fraud / anomaly patterns
* Incident creation workflow
* Dashboard visualizations

---

### 📌 Dataset Parameters

The dataset contains the following fields:

```text
id        → Unique record identifier  
gender    → Protected attribute (e.g., Male/Female)  
age       → Age of the individual  
decision  → Model/system decision (Approved/Rejected)  
outcome   → Binary result (1 = positive, 0 = negative)
```

> ⚠️ This dataset is synthetic and created for demonstration purposes only.
> It does not contain real user data.

---

## Tech Stack

### Frontend

* JavaScript / React
* HTML / CSS

### Backend

* Python
* REST APIs
* SQLite (local development)

### Cloud / Services

* Firebase
* Gemini API / AI integrations

---

## Project Structure

```text
fairtrace/
├── backend/
├── frontend/
├── data/
│   └── sample_dataset.csv
└── README.md
```

---

## 🚀 Getting Started (Local Setup)

### Backend Setup

```bash
cd fairtrace/backend
python -m venv venv
```

#### Activate environment

**Windows:**

```bash
venv\Scripts\activate
```

**Mac/Linux:**

```bash
source venv/bin/activate
```

---

#### Install dependencies

```bash
pip install -r requirements.txt
```

---

#### Run backend

```bash
python main.py
```

Backend will run at:

```
http://localhost:5000
```

---

### Frontend Setup

```bash
cd fairtrace/frontend
npm install
npm run dev
```

Frontend will run at:

```
http://localhost:3000
```

---

## Environment Variables

Create a `.env` file in the backend folder:

```env
GEMINI_API_KEY=your_key_here
FIREBASE_PROJECT_ID=your_project_id
```

---

## Use Cases

* Fraud detection
* Certificate / identity verification
* Bias analysis
* Trust scoring systems
* Risk monitoring dashboards

---

## Future Improvements

* Real-time alerts
* Advanced analytics
* Role-based access control
* Cloud deployment support
* Improved model explainability

---

## Team

Built for the Google Solution Hackathon.

---

## License

MIT License
