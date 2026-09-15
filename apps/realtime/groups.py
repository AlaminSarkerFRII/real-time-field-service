"""The one place channel-layer group names are ever constructed — see
docs/architecture.md #6. Every consumer and every broadcaster imports these
instead of formatting the string itself."""


def org_group(org_id: object) -> str:
    return f"org.{org_id}"


def job_group(job_id: object) -> str:
    return f"job.{job_id}"


def user_group(user_id: object) -> str:
    return f"user.{user_id}"
