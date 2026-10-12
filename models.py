from dataclasses import dataclass, field
from datetime import date, datetime

STATUSES = ["Open", "In progress", "Awaiting hearing", "Closed"]


class ValidationError(ValueError):
    """Raised with a list of messages when a case has invalid data."""

    def __init__(self, errors):
        super().__init__("; ".join(errors))
        self.errors = errors


@dataclass
class Case:
    number: str
    client: str
    opened_on: str          # ISO date, YYYY-MM-DD
    status: str
    lawyer: str
    description: str = ""
    id: int = field(default=None)

    @classmethod
    def from_form(cls, form, case_id=None):
        """Build a Case from submitted form data, cleaning and validating it."""
        case = cls(
            number=(form.get("number") or "").strip(),
            client=(form.get("client") or "").strip(),
            opened_on=(form.get("opened_on") or "").strip(),
            status=(form.get("status") or "").strip(),
            lawyer=(form.get("lawyer") or "").strip(),
            description=(form.get("description") or "").strip(),
            id=case_id,
        )
        case.validate()
        return case

    def validate(self):
        errors = []
        for name in ("number", "client", "lawyer"):
            if not getattr(self, name):
                errors.append(f"{name.capitalize()} is required.")
        if self.status not in STATUSES:
            errors.append("Choose a valid status.")
        try:
            opened = datetime.strptime(self.opened_on, "%Y-%m-%d").date()
            if opened > date.today():
                errors.append("Opening date can't be in the future.")
        except ValueError:
            errors.append("Opening date must be a valid date.")
        if errors:
            raise ValidationError(errors)

    @property
    def days_open(self):
        return (date.today() - datetime.strptime(self.opened_on, "%Y-%m-%d").date()).days

    def __str__(self):
        return f"Case {self.number} - {self.client} ({self.status})"
