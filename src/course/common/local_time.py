from datetime import date, datetime, timedelta, timezone

# The platform's local time zone: Baku. Azerbaijan has used UTC+4 all year since 2016 (no daylight
# saving), so a fixed offset is exact and avoids the tz database (zoneinfo needs tzdata on Windows).
LOCAL_TIMEZONE = timezone(timedelta(hours=4), "Asia/Baku")


def local_today(now: datetime) -> date:
    """The local calendar date at ``now``. Course dates are local dates, so "today" must be too."""
    return now.astimezone(LOCAL_TIMEZONE).date()
