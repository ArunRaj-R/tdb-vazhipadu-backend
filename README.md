# TDB Vazhipadu Booking Backend

A backend service built with **Python & Django** for managing and booking *vazhipadu* (temple ritual offerings) under a Temple Board (such as Devaswom Board).

---

## 📌 Overview

A **Vazhipadu** is a sacred ritual offering performed at a temple on behalf of a devotee. The devotee pays a fixed fee, and temple priests conduct the ritual—typically dedicated to a specific deity in the devotee's name, birth star (*Nakshatram*), or birth date.

This application provides the core backend API and administrative counter interface for managing offering catalogs, devotee bookings, daily priest ritual schedules, and receipts.

---

## ✨ Features

- **Vazhipadu Catalog Management**:
  - List of offerings with fixed fees, associated deities, and descriptions.
  - Active/inactive status and daily booking quota limits.
- **Offering Booking**:
  - Devotee details: Name, Star (*Nakshatram*), Birth Date, or Gotra.
  - Selection of Deity, Offering item(s), and Date of Performance.
  - Receipt/Token number generation with payment status tracking (Paid, Pending).
- **Daily Priest Schedule**:
  - Filter and generate daily offering charts for priests sorted by deity and ritual type.
  - Mark offerings as *Completed / Performed*.
- **Temple Board Admin & Counter Staff**:
  - Role-based access for counter clerks (booking issuance) and temple administrators (offerings & financial reporting).
  - Django Admin pre-configured for administrative workflows.

---

## 🛠️ Tech Stack

- **Language**: Python 3.10+
- **Framework**: Django & Django REST Framework (DRF)
- **Database**: SQLite (Development) / PostgreSQL (Production)
- **Authentication**: Session-based (Django Admin / Counter staff) & Token/JWT (REST API)

---

## 🗂️ Proposed Domain Models

```text
Deity
 └── id, name, description

Vazhipadu (Offering)
 └── id, name, deity (FK), fixed_price, description, is_active

Booking
 └── id, booking_number, booking_date, performance_date, total_amount, payment_status, created_at

BookingItem
 └── id, booking (FK), vazhipadu (FK), devotee_name, star (nakshatram), performer_status (Pending/Completed)
```

---

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.10 or higher
- `git`
- `virtualenv` or `venv`

### 2. Setup Virtual Environment

```bash
# Clone the repository
git clone <repository-url>
cd tdb-vazhipadu-backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Linux/macOS:
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install django djangorestframework
# or if requirements.txt exists:
# pip install -r requirements.txt
```

### 4. Run Migrations & Setup Admin

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
```

### 5. Start Development Server

```bash
python manage.py runserver
```

Access the Django admin console at `http://127.0.0.1:8000/admin/`.

---

## 📡 Key API Endpoints (Planned)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/offerings/` | List all active vazhipadu offerings |
| `POST` | `/api/bookings/` | Create a new vazhipadu booking |
| `GET` | `/api/bookings/<id>/` | Retrieve booking details and receipt |
| `GET` | `/api/priest/schedule/` | Daily schedule of rituals to perform |
| `PATCH`| `/api/priest/items/<id>/complete/` | Mark offering ritual as completed |

---

## 🗺️ Roadmap

- [ ] PDF receipt generation for counter printing.
- [ ] Payment gateway integration for online devotee bookings.
- [ ] SMS / WhatsApp notification for booking confirmation and ritual completion.
- [ ] Multi-temple management for temple board central administration.
