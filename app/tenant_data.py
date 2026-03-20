import base64

from sqlalchemy.orm import Session

from app.models import (
    SummaryAverageDiffs,
    SummaryConfigCount,
    SummaryDiffCount,
    Tenant,
)


def get_tenants(db: Session):
    return db.query(Tenant).all()


def get_counts(db: Session, baseline_id, tenant_id):
    config_counts = db.query(SummaryConfigCount).filter_by(tenant=baseline_id).all()
    diff_counts = db.query(SummaryDiffCount).filter_by(tenant=tenant_id).all()
    return config_counts, diff_counts


def get_feeds(db: Session, tenant_id):
    tenant = db.query(Tenant).filter_by(id=tenant_id).first()
    if not tenant:
        return ["No data"], ["No data"]
    backup_feed = (
        base64.b64decode(tenant.backup_feed).decode("utf-8").splitlines()
        if tenant.backup_feed
        else ["No data"]
    )
    update_feed = (
        base64.b64decode(tenant.update_feed).decode("utf-8").splitlines()
        if tenant.update_feed
        else ["No data"]
    )
    return backup_feed, update_feed


def get_line_data_diff(db: Session, tenant_id):
    records = db.query(SummaryDiffCount).filter_by(tenant=tenant_id).all()[-30:]
    labels = [str(r.last_update) for r in records]
    data = [r.diff_count for r in records]
    return labels, data, len(records)


def get_line_data_config(db: Session, baseline_id):
    records = db.query(SummaryConfigCount).filter_by(tenant=baseline_id).all()[-30:]
    labels = [str(r.last_update) for r in records]
    data = [r.config_count for r in records]
    return labels, data


def get_line_data_average(db: Session, tenant_id):
    records = db.query(SummaryAverageDiffs).filter_by(tenant=tenant_id).all()[-30:]
    labels = [str(r.last_update) for r in records]
    data = [r.average_diffs for r in records]
    return labels, data


def tenant_home_data(db: Session, tenant_id=None):
    tenants = get_tenants(db)

    baseline_tenant = db.query(Tenant).filter_by(baseline="true").first()
    baseline_id = baseline_tenant.id if baseline_tenant else None
    if not tenant_id:
        tenant_id = baseline_id

    config_count_data, diff_count_data = get_counts(db, baseline_id, tenant_id)

    count_data = config_count_data[-1] if config_count_data else None
    tracked_count = count_data.config_count if count_data else 0

    diff_data = diff_count_data[-1] if diff_count_data else None
    diff_count = diff_data.diff_count if diff_data else 0

    match_count = (
        (config_count_data[-1].config_count - diff_count_data[-1].diff_count)
        if config_count_data and diff_count_data
        else 0
    )

    feed_backup, feed_update = get_feeds(db, tenant_id)

    labels_diff, chart_diffs, diff_len = get_line_data_diff(db, tenant_id)
    labels_config, config_counts = get_line_data_config(db, baseline_id)
    labels_average, average_diffs = get_line_data_average(db, tenant_id)

    selected_tenant = db.query(Tenant).filter_by(id=tenant_id).first()
    selected_tenant_name = selected_tenant.display_name if selected_tenant else "Tenants"

    return {
        "tenants": tenants,
        "selected_tenant_name": selected_tenant_name,
        "trackedCount": tracked_count,
        "diffCount": diff_count,
        "matchCount": match_count,
        "backup_feed": feed_backup,
        "update_feed": feed_update,
        "labelsDiff": labels_diff,
        "diffs": chart_diffs,
        "diff_len": diff_len,
        "labelsConfig": labels_config,
        "config_counts": config_counts,
        "labelsAverage": labels_average,
        "average_diffs": average_diffs,
        "diff_data_last_update": diff_data.last_update if diff_data else None,
        "config_data_last_update": count_data.last_update if count_data else None,
    }
