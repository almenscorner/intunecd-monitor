import base64

from app.models import intunecd_tenants, summary_config_count, summary_diff_count, summary_average_diffs


def get_tenants():
    """Get a list of all tenants.

    Returns:
        list: A list of all tenants.
    """
    tenants = intunecd_tenants.query.all()
    return tenants


def get_counts(baseline_id, tenant_id):
    """Get a list of all config and diff counts.

    Returns:
        list: A list of all config and diff counts.
    """
    config_counts = summary_config_count.query.filter_by(tenant=baseline_id).all()
    diff_counts = summary_diff_count.query.filter_by(tenant=tenant_id).all()

    return config_counts, diff_counts


def get_feeds(id):
    """Get a list of all backup and update feeds.

    Returns:
        list: A list of all backup and update feeds.
    """
    tenant = intunecd_tenants.query.filter_by(id=id).first()
    if not tenant:
        return ["No data"], ["No data"]
    backup_feed = base64.b64decode(tenant.backup_feed).decode("utf-8").splitlines() if tenant.backup_feed else ["No data"]
    update_feed = base64.b64decode(tenant.update_feed).decode("utf-8").splitlines() if tenant.update_feed else ["No data"]
    update_feed = [line for line in update_feed if line != "-" * 90]

    return backup_feed, update_feed


def get_line_data_diff(tenant_id):
    """Get the last 30 records of data for the diff line chart.

    Args:
        tenant_id (int): The ID of the tenant to retrieve data for.

    Returns:
        tuple: A tuple containing the labels and data for the diff line chart.
    """
    line_data_diff = summary_diff_count.query.filter_by(tenant=tenant_id).all()[-30:]
    chart_data_diff = [(item.last_update, item.diff_count) for item in line_data_diff]
    diff_chart_lables = [row[0] for row in chart_data_diff]
    diff_chart_diffs = [row[1] for row in chart_data_diff]

    return diff_chart_lables, diff_chart_diffs, len(line_data_diff)


def get_line_data_config(baseline_id):
    """Get the last 30 records of data for the config line chart.

    Args:
        baseline_id (int): The ID of the baseline tenant to retrieve data for.

    Returns:
        tuple: A tuple containing the labels and data for the config line chart.
    """
    line_data_config = summary_config_count.query.filter_by(tenant=baseline_id).all()[-30:]
    chart_data_config = [(item.last_update, item.config_count) for item in line_data_config]
    labelsConfig = [row[0] for row in chart_data_config]
    config_counts = [row[1] for row in chart_data_config]

    return labelsConfig, config_counts


def get_line_data_average(tenant_id):
    """Get the last 30 records of data for the average diff line chart.

    Args:
        tenant_id (int): The ID of the tenant to retrieve data for.

    Returns:
        tuple: A tuple containing the labels and data for the average diff line chart.
    """
    line_data_average = summary_average_diffs.query.filter_by(tenant=tenant_id).all()[-30:]
    chart_data_average = [(item.last_update, item.average_diffs) for item in line_data_average]
    labelsAverage = [row[0] for row in chart_data_average]
    average_diffs = [row[1] for row in chart_data_average]

    return labelsAverage, average_diffs


def tenant_home_data(tenant_id=None):
    """Get data for a specific tenant."""
    tenants = get_tenants()

    baseline_tenant = intunecd_tenants.query.filter_by(baseline="true").first()
    baseline_id = baseline_tenant.id if baseline_tenant else None
    if not tenant_id:
        tenant_id = baseline_id

    # Get the config count from the baseline tenant and diff count from the current tenant
    config_count_data, diff_count_data = get_counts(baseline_id, tenant_id)

    # Set the count data to the last item in the list
    count_data = config_count_data[-1] if config_count_data else None
    trackedCount = count_data.config_count if count_data else 0

    # Set the diff data to the last item in the list
    diff_data = diff_count_data[-1] if diff_count_data else None
    diffCount = diff_data.diff_count if diff_data else 0

    matchCount = (
        (config_count_data[-1].config_count - diff_count_data[-1].diff_count) if config_count_data and diff_count_data else 0
    )

    # Get the current backup and update feed from the current tenant
    feed_backup, feed_update = get_feeds(tenant_id)

    # Get the last 30 records of data for the line charts
    labels_Diff, chart_diffs, diff_len = get_line_data_diff(tenant_id)
    labelsConfig, config_counts = get_line_data_config(baseline_id)
    labelsAverage, average_diffs = get_line_data_average(tenant_id)

    selected_tenant_name = intunecd_tenants.query.filter_by(id=tenant_id).first().display_name if tenant_id else "Tenants"

    return {
        "tenants": tenants,
        "selected_tenant_name": selected_tenant_name,
        "trackedCount": trackedCount,
        "diffCount": diffCount,
        "matchCount": matchCount,
        "backup_feed": feed_backup,
        "update_feed": feed_update,
        "labelsDiff": labels_Diff,
        "diffs": chart_diffs,
        "diff_len": diff_len,
        "labelsConfig": labelsConfig,
        "config_counts": config_counts,
        "labelsAverage": labelsAverage,
        "average_diffs": average_diffs,
        "diff_data_last_update": diff_data.last_update if diff_data else None,
        "config_data_last_update": count_data.last_update if count_data else None,
    }
