"""Seed synthetic demo cases (docs/demo-cases.md) for instant testing.

Runs at backend startup when ADD_DEMO_DATA=true (see startup.sh). Safe to
run on every boot: every row is get-or-created by its natural key, so it
is a no-op once the demo data exists. Always exits 0 so it never blocks
startup. All names, phones, and emails are synthetic.
"""

import os
import sys
from datetime import date


def _wanted():
    return os.environ.get("ADD_DEMO_DATA", "").strip().lower() == "true"


PATIENTS = [
    {
        "email": "demo-a@example.com",
        "full_name": "Demo Patient A",
        "phone": "+256700000101",
        "date_of_birth": date(1974, 3, 12),
        "sex": "Female",
        "district": "Wakiso",
        "address": "Kira",
        "visits": [
            {
                "visit_date": date(2026, 8, 4),
                "clinic": "HIV Clinic",
                "source": "typed",
                "notes": (
                    "Known HIV on ART, hypertension, type 2 diabetes. "
                    "ART adherence good. Counselled on salt reduction. "
                    "Return in 3 months."
                ),
                "sections": [
                    ("lab", "Viral load suppressed (<50 copies/mL). HbA1c 8.1%."),
                    ("vitals", "BP 150/95, weight 68 kg."),
                    (
                        "prescription",
                        "Continue tenofovir/lamivudine/dolutegravir daily, "
                        "amlodipine 5 mg daily, metformin 500 mg twice daily.",
                    ),
                ],
            },
            {
                "visit_date": date(2026, 9, 8),
                "clinic": "NCD Clinic",
                "source": "typed",
                "notes": (
                    "Feet normal, no chest pain, no shortness of breath. "
                    "Diet counselling repeated."
                ),
                "sections": [
                    ("vitals", "BP 146/92."),
                    ("lab", "Fasting glucose 9.4 mmol/L. Metformin continued."),
                ],
            },
            {
                "visit_date": date(2026, 10, 12),
                "clinic": "OPD",
                "source": "typed",
                "notes": (
                    "Dry cough for 1 week, no fever, no weight loss, no night "
                    "sweats. Chest clear on auscultation. Advised to return "
                    "if cough persists."
                ),
                "sections": [
                    (
                        "diagnosis",
                        "Bacterial chest infection (clinical).",
                    ),
                    (
                        "prescription",
                        "Amoxicillin 500 mg three times daily for 5 days.",
                    ),
                ],
            },
            {
                "visit_date": None,  # today (the demo visit)
                "clinic": "OPD",
                "source": "typed",
                "notes": (
                    "Cough now 2 weeks and worsening, night sweats started "
                    "this week, coughing household contact. BP 148/94, "
                    "random glucose 10.2 mmol/L, SpO2 97%. MDT review requested."
                ),
                "sections": [
                    ("lab", "Sputum collected for GeneXpert. Kidney function test requested (overdue)."),
                    ("imaging", "Chest X-ray requested."),
                ],
                "attachment": (
                    "demo-a-genexpert-request.txt",
                    "GeneXpert request: sputum collected 2-week worsening cough + night sweats, TB contact. Chest X-ray requested.",
                ),
            },
        ],
    },
    {
        "email": "demo-b@example.com",
        "full_name": "Demo Patient B",
        "phone": "+256700000102",
        "date_of_birth": date(1962, 7, 25),
        "sex": "Male",
        "district": "Kampala",
        "address": "Kawempe",
        "visits": [
            {
                "visit_date": date(2026, 9, 15),
                "clinic": "NCD Clinic",
                "source": "typed",
                "notes": (
                    "Known hypertension, chronic kidney disease stage 3. "
                    "No oedema, no headaches. Low-salt diet reinforced."
                ),
                "sections": [
                    ("vitals", "BP 158/98."),
                    ("lab", "eGFR 42 mL/min, potassium normal."),
                    ("prescription", "Continue lisinopril 10 mg daily with monitoring."),
                ],
            },
            {
                "visit_date": None,
                "clinic": "NCD Clinic",
                "source": "typed",
                "notes": (
                    "BP 162/100 on repeat, mild ankle swelling in the "
                    "evenings. Referral to physician discussed; patient "
                    "prefers to continue local care for now."
                ),
                "sections": [
                    ("lab", "Creatinine due for recheck."),
                    ("prescription", "Lisinopril continued, review in 2 weeks with new creatinine result."),
                ],
            },
        ],
    },
    {
        "email": "demo-c@example.com",
        "full_name": "Demo Patient C",
        "phone": "+256700000103",
        "date_of_birth": date(1988, 11, 2),
        "sex": "Female",
        "district": "Gulu",
        "address": "Pece",
        "visits": [
            {
                "visit_date": date(2026, 10, 2),
                "clinic": "HIV Clinic",
                "source": "typed",
                "notes": (
                    "Known HIV on ART. Good adherence, viral load suppressed. "
                    "Low mood and poor sleep for 2 months, appetite reduced. "
                    "No risk to self or others disclosed. Supportive "
                    "counselling given, sleep hygiene discussed."
                ),
                "sections": [
                    ("prescription", "Continue tenofovir/lamivudine/dolutegravir daily."),
                ],
            },
            {
                "visit_date": None,
                "clinic": "HIV Clinic",
                "source": "typed",
                "notes": (
                    "Mood still low, missing clinic appointments. PHQ-2 score "
                    "elevated. Referral for mental health review discussed; "
                    "patient agrees. Follow up in 2 weeks."
                ),
                "sections": [
                    ("referral", "Mental health review (patient agrees)."),
                ],
            },
        ],
    },
]

CLINICS = ["OPD", "HIV Clinic", "NCD Clinic"]


def main() -> int:
    if not _wanted():
        print("add_demodata: ADD_DEMO_DATA != true - skipping")
        return 0

    from pathlib import Path

    from sqlalchemy import select

    from app.clinics.models import Clinic
    from app.core.config import settings
    from app.db.session import SessionLocal
    from app.patients.models import Attachment, Patient, Visit, VisitSection
    from app.users.models import User

    try:
        db = SessionLocal()
        try:
            staff = db.scalar(
                select(User).where(User.role == "admin").order_by(User.email)
            ) or db.scalar(select(User).order_by(User.email))
            if staff is None:
                print("add_demodata: no users yet - skipping (admin seeds first)")
                return 0

            clinics = {}
            for name in CLINICS:
                clinic = db.scalar(select(Clinic).where(Clinic.name == name))
                if clinic is None:
                    clinic = Clinic(name=name, created_by=staff.id)
                    db.add(clinic)
                    db.flush()
                clinics[name] = clinic

            created_patients, created_visits = 0, 0
            for spec in PATIENTS:
                patient = db.scalar(
                    select(Patient).where(Patient.email == spec["email"])
                )
                if patient is None:
                    patient = Patient(
                        full_name=spec["full_name"],
                        date_of_birth=spec["date_of_birth"],
                        sex=spec["sex"],
                        phone=spec["phone"],
                        email=spec["email"],
                        district=spec["district"],
                        address=spec["address"],
                        created_by=staff.id,
                    )
                    db.add(patient)
                    db.flush()
                    created_patients += 1
                for vspec in spec["visits"]:
                    visit_date = vspec["visit_date"] or date.today()
                    visit = db.scalar(
                        select(Visit).where(
                            Visit.patient_id == patient.id,
                            Visit.visit_date == visit_date,
                            Visit.notes == vspec["notes"],
                        )
                    )
                    if visit is None:
                        visit = Visit(
                            patient_id=patient.id,
                            visit_date=visit_date,
                            notes=vspec["notes"],
                            source=vspec["source"],
                            clinic_id=clinics[vspec["clinic"]].id,
                            created_by=staff.id,
                        )
                        db.add(visit)
                        db.flush()
                        created_visits += 1
                    for section, content in vspec.get("sections", []):
                        exists = db.scalar(
                            select(VisitSection).where(
                                VisitSection.visit_id == visit.id,
                                VisitSection.section == section,
                                VisitSection.content == content,
                            )
                        )
                        if exists is None:
                            db.add(
                                VisitSection(
                                    visit_id=visit.id,
                                    section=section,
                                    content=content,
                                    created_by=staff.id,
                                )
                            )
                    if "attachment" in vspec:
                        filename, body = vspec["attachment"]
                        exists = db.scalar(
                            select(Attachment).where(
                                Attachment.visit_id == visit.id,
                                Attachment.filename == filename,
                            )
                        )
                        if exists is None:
                            upload_dir = Path(settings.upload_dir)
                            upload_dir.mkdir(parents=True, exist_ok=True)
                            stored = upload_dir / f"demo-{filename}"
                            stored.write_text(body, encoding="utf-8")
                            db.add(
                                Attachment(
                                    visit_id=visit.id,
                                    filename=filename,
                                    stored_path=str(stored),
                                    content_type="text/plain",
                                    created_by=staff.id,
                                )
                            )
            db.commit()
            print(
                f"add_demodata: ready "
                f"({created_patients} new patients, {created_visits} new visits)"
            )

            # Best-effort vectors so retrieval works on the demo data too.
            # Never blocks boot: the model server may not be up yet.
            try:
                from app.mdt.tasks import embed_patient_chunks

                for spec in PATIENTS:
                    patient = db.scalar(
                        select(Patient).where(Patient.email == spec["email"])
                    )
                    if patient is not None:
                        embed_patient_chunks(patient.id)
                print("add_demodata: demo vectors indexed")
            except Exception as exc:
                print(f"add_demodata: vector indexing skipped ({exc})")
            return 0
        finally:
            db.close()
    except Exception as exc:  # never block boot on a seed failure
        print(f"add_demodata: failed ({exc}) - continuing boot")
        return 0


if __name__ == "__main__":
    sys.exit(main())
