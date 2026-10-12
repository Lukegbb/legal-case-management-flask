"""Legal case management - Flask web app."""
import os
from datetime import date

from flask import Flask, Response, abort, flash, redirect, render_template, request, url_for

from database import CaseRepository, DuplicateCaseError
from models import STATUSES, Case, ValidationError
from reports import build_summary, cases_to_csv


def create_app(database=None):
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-only-change-me")
    repo = CaseRepository(database or os.getenv("DATABASE", "cases.db"))

    def filters():
        return {k: request.args.get(k, "").strip() for k in ("q", "status", "lawyer")}

    @app.context_processor
    def globals_for_templates():
        return {"statuses": STATUSES, "today": date.today().isoformat()}

    @app.get("/")
    def index():
        f = filters()
        cases = repo.search(f["q"], f["status"], f["lawyer"])
        return render_template("index.html", cases=cases, filters=f, lawyers=repo.lawyers(), form={})

    @app.post("/cases")
    def add_case():
        try:
            repo.add(Case.from_form(request.form))
        except ValidationError as exc:
            for message in exc.errors:
                flash(message, "error")
            return render_template("index.html", cases=repo.search(), filters={}, lawyers=repo.lawyers(),
                                   form=request.form), 400
        except DuplicateCaseError as exc:
            flash(str(exc), "error")
            return render_template("index.html", cases=repo.search(), filters={}, lawyers=repo.lawyers(),
                                   form=request.form), 409
        flash("Case added.", "success")
        return redirect(url_for("index"))

    @app.route("/cases/<int:case_id>/edit", methods=["GET", "POST"])
    def edit_case(case_id):
        case = repo.get(case_id) or abort(404)
        if request.method == "POST":
            try:
                repo.update(Case.from_form(request.form, case_id=case_id))
                flash("Case updated.", "success")
                return redirect(url_for("index"))
            except (ValidationError, DuplicateCaseError) as exc:
                for message in getattr(exc, "errors", [str(exc)]):
                    flash(message, "error")
                return render_template("edit.html", case=case, form=request.form), 400
        return render_template("edit.html", case=case, form=case.__dict__)

    @app.post("/cases/<int:case_id>/delete")
    def delete_case(case_id):
        if not repo.delete(case_id):
            abort(404)
        flash("Case deleted.", "success")
        return redirect(url_for("index"))

    @app.get("/report")
    def report():
        return render_template("report.html", summary=build_summary(repo))

    @app.get("/export.csv")
    def export_csv():
        f = filters()
        csv_text = cases_to_csv(repo.search(f["q"], f["status"], f["lawyer"]))
        return Response(csv_text, mimetype="text/csv",
                        headers={"Content-Disposition": "attachment; filename=cases.csv"})

    return app


if __name__ == "__main__":
    create_app().run(debug=os.getenv("FLASK_DEBUG") == "1")
