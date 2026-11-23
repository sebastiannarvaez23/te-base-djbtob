"""Pure benefit-window computation."""

from datetime import datetime

from dateutil.relativedelta import relativedelta


def build_benefit_window(*, months: int, start: datetime) -> tuple[datetime, datetime]:
    end = start + relativedelta(months=months)
    return start, end
