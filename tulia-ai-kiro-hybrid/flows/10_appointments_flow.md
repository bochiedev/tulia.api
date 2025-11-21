# 10 — Appointments Flow

Used by salons, clinics, service providers, etc.

## 10.1 Booking Flow

1. Intent: `BOOK_APPOINTMENT`
2. Router:
   - If service not specified:
     - Ask user to pick from service list.
   - If date/time not specified:
     - Ask user: “Ungependa siku gani na saa ngapi?”
3. Use availability rules from tenant:
   - `TenantSettings.business_hours`
   - Service-specific availability windows
4. Propose a slot:
   - “Niku-book pedicure leo saa kumi (4pm)?”
5. Confirm:
   - If user says yes:
     - Create `Appointment` with `CONFIRMED`.
     - Optionally trigger payment.
   - If no:
     - Offer alternative times.

## 10.2 Appointment Status

- Intent: `CHECK_APPOINTMENT_STATUS`
- Ask for phone or reference if multiple.
- Lookup upcoming appointments and reply.
