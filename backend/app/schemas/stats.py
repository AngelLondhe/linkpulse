import datetime as dt

from pydantic import BaseModel


class TimeseriesPoint(BaseModel):
    date: dt.date
    clicks: int
    unique_visitors: int


class Bucket(BaseModel):
    label: str
    count: int


class LinkStats(BaseModel):
    link_id: int
    start: dt.date
    end: dt.date
    timezone: str
    total_clicks: int
    unique_visitors: int
    all_time_clicks: int
    bot_clicks: int  # in the window; excluded from every other figure unless include_bots
    include_bots: bool
    timeseries: list[TimeseriesPoint]
    referrers: list[Bucket]
    devices: list[Bucket]
    browsers: list[Bucket]
    os: list[Bucket]
    countries: list[Bucket]
