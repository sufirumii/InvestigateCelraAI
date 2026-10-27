"""ClinicalTrials.gov API v2 connector.

The registry is the highest-authority source in the system: it is structured,
timestamped and states *why* a study stopped, which is precisely the setback
evidence commercial teams need.
"""

from __future__ import annotations

from ..engine.normalize import clean_text, fingerprint, iso, now_utc, simhash
from .base import FetchError, IngestResult, http_json

API = "https://clinicaltrials.gov/api/v2/studies"

FIELDS = ",".join(
    [
        "protocolSection.identificationModule.nctId",
        "protocolSection.identificationModule.briefTitle",
        "protocolSection.statusModule.overallStatus",
        "protocolSection.statusModule.whyStopped",
        "protocolSection.statusModule.startDateStruct.date",
        "protocolSection.statusModule.lastUpdatePostDateStruct.date",
        "protocolSection.designModule.phases",
        "protocolSection.designModule.enrollmentInfo.count",
        "protocolSection.conditionsModule.conditions",
        "protocolSection.armsInterventionsModule.interventions",
        "protocolSection.sponsorCollaboratorsModule.leadSponsor.name",
        "protocolSection.descriptionModule.briefSummary",
    ]
)

SETBACK_STATUSES = {"TERMINATED", "SUSPENDED", "WITHDRAWN"}


def _get(d: dict, path: str, default=None):
    cur: object = d
    for part in path.split("."):
        if not isinstance(cur, dict):
            return default
        cur = cur.get(part)
        if cur is None:
            return default
    return cur


def _normalise(study: dict) -> dict:
    p = study.get("protocolSection", {}) or {}
    nct = _get(p, "identificationModule.nctId", "") or ""
    title = clean_text(_get(p, "identificationModule.briefTitle", "") or "")
    sponsor = _get(p, "sponsorCollaboratorsModule.leadSponsor.name", "") or ""
    phases = _get(p, "designModule.phases", []) or []
    conditions = _get(p, "conditionsModule.conditions", []) or []
    interventions = [
        i.get("name", "") for i in (_get(p, "armsInterventionsModule.interventions", []) or []) if i.get("name")
    ]
    return {
        "id": fingerprint("ctgov", nct or title),
        "nct_id": nct,
        "title": title,
        "sponsor": sponsor,
        "status": (_get(p, "statusModule.overallStatus", "") or "").replace("_", " ").title(),
        "phase": ", ".join(ph.replace("PHASE", "Phase ") for ph in phases),
        "conditions": "; ".join(conditions[:6]),
        "interventions": "; ".join(interventions[:6]),
        "enrollment": _get(p, "designModule.enrollmentInfo.count"),
        "start_date": _get(p, "statusModule.startDateStruct.date", "") or "",
        "updated_at": _get(p, "statusModule.lastUpdatePostDateStruct.date", "") or "",
        "why_stopped": clean_text(_get(p, "statusModule.whyStopped", "") or ""),
        "url": f"https://clinicaltrials.gov/study/{nct}" if nct else "",
        "_summary": clean_text(_get(p, "descriptionModule.briefSummary", "") or ""),
    }


def trial_to_document(trial: dict) -> dict:
    """Registry records also enter the newspaper as high-authority stories."""
    status = trial.get("status", "")
    stopped = trial.get("why_stopped", "")
    verb = "terminated" if status.upper() in {"TERMINATED"} else status.lower() or "updated"
    headline = f"{trial.get('sponsor') or 'Sponsor'} study {verb}: {trial.get('title','')}"
    body_parts = [
        trial.get("_summary", ""),
        f"Registry status: {status}." if status else "",
        f"Reason given for stopping: {stopped}" if stopped else "",
        f"Phase: {trial.get('phase')}." if trial.get("phase") else "",
        f"Conditions studied: {trial.get('conditions')}." if trial.get("conditions") else "",
        f"Interventions: {trial.get('interventions')}." if trial.get("interventions") else "",
        f"Planned enrolment n={trial.get('enrollment')}." if trial.get("enrollment") else "",
    ]
    body = " ".join(p for p in body_parts if p)
    published = trial.get("updated_at") or trial.get("start_date") or iso(now_utc())
    return {
        "id": fingerprint("ctgov-doc", trial["id"]),
        "source_id": "clinicaltrials",
        "source_name": "ClinicalTrials.gov",
        "tier": "registry",
        "kind": "trial",
        "title": headline[:280],
        "body": body,
        "url": trial.get("url", ""),
        "host": "clinicaltrials.gov",
        "published_at": iso(now_utc()) if len(published) < 10 else f"{published[:10]}T00:00:00Z",
        "fetched_at": iso(now_utc()),
        "simhash": str(simhash(f"{headline} {body}")),
        "extra": {"nctId": trial.get("nct_id"), "trialId": trial["id"]},
    }


def fetch_for_sponsors(sponsors: list[str], page_size: int = 20) -> IngestResult:
    result = IngestResult()
    for sponsor in sponsors:
        try:
            payload = http_json(
                API,
                params={
                    "query.spons": sponsor,
                    "fields": FIELDS,
                    "pageSize": page_size,
                    "sort": "LastUpdatePostDate:desc",
                },
            )
        except FetchError as exc:
            result.errors.append(f"clinicaltrials[{sponsor}]: {exc}")
            continue
        for study in payload.get("studies", []) or []:
            trial = _normalise(study)
            if not trial["title"]:
                continue
            summary = trial.pop("_summary", "")
            trial_with_summary = {**trial, "_summary": summary}
            result.trials.append(trial)
            result.documents.append(trial_to_document(trial_with_summary))
            result.fetched += 1
    return result
