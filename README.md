# TDB Vazhipadu Booking Backend

A production-grade backend service built with **Python & Django REST Framework** for managing and booking *vazhipadu* (temple ritual offerings) under a Temple Board (such as Travancore Devaswom Board).

---

## 📌 Pull Request Milestones

The project was implemented strictly in branch-per-feature team workflow, with each milestone thoroughly tested, reviewed, and merged into `main`:

| Milestone | Branch | Pull Request | Status | Highlights |
|---|---|---|---|---|
| **P1** | `feature/p1-offerings` | [PR #1: P1 – Offerings and Orders API](https://github.com/ArunRaj-R/tdb-vazhipadu-backend/pull/1) | Merged | Offering catalogue, order placement with multi-performer items, authoritative server-side pricing, unified JSON errors. |
| **P2** | `feature/p2-order-search` | [PR #2: P2 – Order Search](https://github.com/ArunRaj-R/tdb-vazhipadu-backend/pull/2) | Merged | High-performance B-tree indexes, stable gapless pagination, filtering by temple, date, status, and devotee phone search. |
| **P3** | `feature/p3-daily-limits` | [PR #3: P3 – Daily Limits](https://github.com/ArunRaj-R/tdb-vazhipadu-backend/pull/3) | Merged | Offering daily limits, `select_for_update` row locking, verified under 20 simultaneous concurrent requests. |
| **P4** | `feature/p4-cancellation-and-reports` | [PR #4: P4 – Cancellation and Daily Collection](https://github.com/ArunRaj-R/tdb-vazhipadu-backend/pull/4) | Merged | Order cancellation, quota release, IST calendar day daily collection report matching to the paisa. |

---

## 🏛️ Domain Architecture

```text
Temple
 └── id, name, code, created_at

Offering (Vazhipadu)
 └── id, temple (FK), name, price, is_active, daily_limit, created_at

Order
 └── id, temple (FK), devotee_name, phone_number, date, total_amount, status, created_at
     Indexes: (temple, date), (temple, status), (temple, phone_number), (phone_number), (temple, date, status)

OrderItem
 └── id, order (FK), offering (FK), devotee_name, nakshatra, quantity, unit_price, total_price
```

### Key Design Decisions:
- **Order vs. OrderItem Granularity**: In real temple counter bookings, a single transaction (Order) placed by a family contact (`phone_number`, `devotee_name`) can contain offerings performed for distinct family members with their own names and birth stars (*Nakshatram*). Each ritual item is cleanly stored on `OrderItem`.
- **Authoritative Server Pricing**: Prices are fetched directly from the database within `transaction.atomic()` to prevent client tampering.
- **Financial Precision**: All monetary calculations use `DecimalField` (fixed-point arithmetic) to prevent floating-point inaccuracies.
- **Indian Standard Time (IST)**: Dates and financial collection reports are strictly bounded from `00:00:00` to `23:59:59.999999` in `Asia/Kolkata`.

---

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.10+
- `virtualenv` or `venv`

### 2. Setup Virtual Environment

```bash
# Clone the repository
git clone https://github.com/ArunRaj-R/tdb-vazhipadu-backend.git
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
pip install -r requirements.txt
```

### 4. Run Migrations & Start Server

```bash
python manage.py migrate
python manage.py createsuperuser  # Optional, for admin access
python manage.py runserver
```

Server runs at `http://127.0.0.1:8000/`.

---

## 🧪 Running Automated Tests

All acceptance criteria across P1 to P4 are verified through 14 comprehensive automated unit, integration, and multi-threaded concurrency tests:

```bash
python manage.py test vazhipadu
```

Expected output:
```text
Creating test database for alias 'default'...
..............
----------------------------------------------------------------------
Ran 14 tests in 0.321s

OK
Destroying test database for alias 'default'...
```

---

## 📡 API Reference & Examples

### 1. Offerings Catalogue
- **List offerings**: `GET /api/offerings/?temple=1&is_active=true`
- **Create offering**: `POST /api/offerings/`
  ```json
  {
    "temple": 1,
    "name": "Pushpanjali",
    "price": "30.00",
    "is_active": true,
    "daily_limit": 50
  }
  ```

### 2. Place an Order (P1, P3)
- **Endpoint**: `POST /api/orders/`
- **Request Body**:
  ```json
  {
    "temple": 1,
    "devotee_name": "Arun Raj",
    "phone_number": "9876543210",
    "date": "2026-11-01",
    "items": [
      {
        "offering_id": 1,
        "quantity": 2,
        "devotee_name": "Arun Raj",
        "nakshatra": "Aswathy"
      },
      {
        "offering_id": 2,
        "quantity": 1,
        "devotee_name": "Priya",
        "nakshatra": "Rohini"
      }
    ]
  }
  ```
- **Response** (`201 Created`):
  ```json
  {
    "id": 101,
    "temple": 1,
    "temple_name": "Sree Mahadeva Temple",
    "devotee_name": "Arun Raj",
    "phone_number": "9876543210",
    "date": "2026-11-01",
    "total_amount": "110.00",
    "status": "CONFIRMED",
    "created_at": "2026-10-26T12:00:00+05:30",
    "items": [
      {
        "id": 201,
        "offering_id": 1,
        "offering_name": "Pushpanjali",
        "quantity": 2,
        "unit_price": "30.00",
        "total_price": "60.00",
        "devotee_name": "Arun Raj",
        "nakshatra": "Aswathy"
      },
      {
        "id": 202,
        "offering_id": 2,
        "offering_name": "Archana",
        "quantity": 1,
        "unit_price": "50.00",
        "total_price": "50.00",
        "devotee_name": "Priya",
        "nakshatra": "Rohini"
      }
    ]
  }
  ```

### 3. Search & List Orders (P2)
- **Endpoint**: `GET /api/orders/?temple=1&date=2026-11-01&status=CONFIRMED&phone_number=9876543210&page=1&page_size=10`
- **Response**:
  ```json
  {
    "count": 1,
    "total_pages": 1,
    "current_page": 1,
    "next": null,
    "previous": null,
    "results": [...]
  }
  ```

### 4. Cancel an Order (P4)
- **Endpoint**: `POST /api/orders/<id>/cancel/`
- Cancels the order (`status = "CANCELLED"`) and immediately frees up its quota for that date's daily limit.

### 5. Daily Collection Report (P4)
- **Endpoint**: `GET /api/reports/daily-collection/?temple=1&date=2026-11-01`
- **Response**:
  ```json
  {
    "temple_id": 1,
    "temple_name": "Sree Mahadeva Temple",
    "date": "2026-11-01",
    "timezone": "Asia/Kolkata",
    "order_count": 1,
    "total_amount": "110.00",
    "offerings": [
      {
        "offering_id": 1,
        "offering_name": "Pushpanjali",
        "count": 2,
        "total_amount": "60.00"
      },
      {
        "offering_id": 2,
        "offering_name": "Archana",
        "count": 1,
        "total_amount": "50.00"
      }
    ]
  }
  ```
  *(Note: Report total `110.00` strictly equals `60.00 + 50.00` down to the paisa)*

---

## 📂 File Architecture Guide

| File | Purpose |
|---|---|
| `vazhipadu/models.py` | Defines `Temple`, `Offering`, `Order`, and `OrderItem` models with foreign keys, text choices, indexes, and constraints. |
| `vazhipadu/serializers.py` | Serializers with validation, `select_for_update` row locks, daily quota checks, and atomic order creation. |
| `vazhipadu/views.py` | API ViewSets (`TempleViewSet`, `OfferingViewSet`, `OrderViewSet`), cancellation action, and `DailyCollectionReportView`. |
| `vazhipadu/pagination.py` | `StandardResultsSetPagination` providing deterministic order pagination with total pages and count metadata. |
| `vazhipadu/exceptions.py` | Global exception handler returning standard JSON error envelope `{"error": {"code": "...", "message": "...", "details": ...}}`. |
| `vazhipadu/tests.py` | Comprehensive test suite covering P1 to P4 acceptance criteria and 20 simultaneous thread concurrency. |
| `vazhipadu/admin.py` | Django admin configuration with search, filters, and tabular order item inlines. |
| `vazhipadu/urls.py` | DRF router registration and report URL routing under `/api/`. |
| `config/settings.py` | Project settings configured with `Asia/Kolkata` timezone, DRF settings, and installed apps. |
