import os
import tempfile
import unittest

from app import create_app
from database import CaseRepository, DuplicateCaseError
from models import Case, ValidationError
from reports import build_summary, cases_to_csv


def sample(number="2024-001", **overrides):
    data = dict(number=number, client="Murphy Ltd", opened_on="2024-03-01",
                status="Open", lawyer="A. Walsh", description="Contract dispute")
    data.update(overrides)
    return data


class TempDbTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "test.db")

    def tearDown(self):
        self.tmp.cleanup()


class ModelTests(unittest.TestCase):
    def test_valid_form_is_cleaned(self):
        case = Case.from_form(sample(client="  Murphy Ltd  "))
        self.assertEqual(case.client, "Murphy Ltd")

    def test_invalid_form_collects_all_errors(self):
        with self.assertRaises(ValidationError) as ctx:
            Case.from_form(sample(number="", status="Unknown", opened_on="31/02/2024"))
        self.assertEqual(len(ctx.exception.errors), 3)

    def test_future_date_rejected(self):
        with self.assertRaises(ValidationError):
            Case.from_form(sample(opened_on="2999-01-01"))


class RepositoryTests(TempDbTestCase):
    def setUp(self):
        super().setUp()
        self.repo = CaseRepository(self.db_path)
        self.repo.add(Case(**sample("A-1")))
        self.repo.add(Case(**sample("A-2", status="Closed", lawyer="B. Ryan", client="Quinn")))

    def test_duplicate_number_rejected(self):
        with self.assertRaises(DuplicateCaseError):
            self.repo.add(Case(**sample("A-1")))

    def test_search_filters(self):
        self.assertEqual([c.number for c in self.repo.search(status="Closed")], ["A-2"])
        self.assertEqual([c.number for c in self.repo.search(text="quinn")], ["A-2"])
        self.assertEqual(len(self.repo.search(lawyer="A. Walsh")), 1)

    def test_update_and_delete(self):
        case = self.repo.search(text="A-1")[0]
        case.status = "In progress"
        self.repo.update(case)
        self.assertEqual(self.repo.get(case.id).status, "In progress")
        self.assertTrue(self.repo.delete(case.id))
        self.assertIsNone(self.repo.get(case.id))

    def test_summary_and_csv(self):
        summary = build_summary(self.repo)
        self.assertEqual(summary["total"], 2)
        self.assertEqual(summary["active"], 1)
        self.assertEqual(summary["by_status"]["Closed"], 1)
        csv_text = cases_to_csv(self.repo.search())
        self.assertTrue(csv_text.startswith("number,client"))
        self.assertIn("Quinn", csv_text)


class WebTests(TempDbTestCase):
    def setUp(self):
        super().setUp()
        app = create_app(self.db_path)
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_add_list_and_report(self):
        res = self.client.post("/cases", data=sample(), follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Murphy Ltd", res.data)
        self.assertIn(b"Case added", res.data)
        self.assertEqual(self.client.get("/report").status_code, 200)

    def test_invalid_case_shows_errors(self):
        res = self.client.post("/cases", data=sample(client=""))
        self.assertEqual(res.status_code, 400)
        self.assertIn(b"Client is required", res.data)

    def test_duplicate_case_returns_409(self):
        self.client.post("/cases", data=sample())
        self.assertEqual(self.client.post("/cases", data=sample()).status_code, 409)

    def test_edit_and_delete(self):
        self.client.post("/cases", data=sample())
        res = self.client.post("/cases/1/edit", data=sample(status="Closed"), follow_redirects=True)
        self.assertIn(b"Case updated", res.data)
        self.assertEqual(self.client.post("/cases/1/delete").status_code, 302)
        self.assertEqual(self.client.get("/cases/1/edit").status_code, 404)

    def test_csv_export(self):
        self.client.post("/cases", data=sample())
        res = self.client.get("/export.csv")
        self.assertEqual(res.mimetype, "text/csv")
        self.assertIn(b"2024-001", res.data)


if __name__ == "__main__":
    unittest.main()
