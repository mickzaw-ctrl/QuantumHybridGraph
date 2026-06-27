#!/usr/bin/env python3
"""SocialTrendPredictor — lightweight trend forecasting for social media signals.

The module is dependency-light and works with standard Python only. It can ingest
post-level metrics, aggregate them into time buckets, compute trend momentum and
produce short-horizon forecasts for hashtags/keywords.

It is designed as an MVP foundation for future integrations with X/Twitter,
TikTok, Instagram, YouTube, Reddit, LinkedIn or internal social listening data.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import csv
import json
import math
import re
from collections import defaultdict
from typing import Any, Iterable


HASHTAG_RE = re.compile(r"(?<!\w)#([\w\-]+)", re.UNICODE)
WORD_RE = re.compile(r"[A-Za-zÀ-ž0-9_\-]{3,}", re.UNICODE)


@dataclass(frozen=True)
class SocialPost:
    """One social media observation/post."""

    timestamp: datetime
    platform: str
    text: str
    author: str = "unknown"
    likes: int = 0
    shares: int = 0
    comments: int = 0
    views: int = 0

    @property
    def engagement(self) -> float:
        """Weighted engagement score."""
        return float(self.likes + 2 * self.comments + 3 * self.shares + 0.01 * self.views)

    def terms(self, include_keywords: bool = True) -> set[str]:
        """Extract hashtags and optional keywords from the text."""
        hashtags = {"#" + tag.lower() for tag in HASHTAG_RE.findall(self.text)}
        if not include_keywords:
            return hashtags
        text_without_hashtags = HASHTAG_RE.sub(" ", self.text)
        words = {word.lower() for word in WORD_RE.findall(text_without_hashtags)}
        stopwords = {
            "the", "and", "for", "with", "this", "that", "from", "are", "was", "were",
            "about", "market", "discussion", "innovation", "trend", "trends", "forecast", "forecasting",
            "jest", "oraz", "dla", "czy", "jak", "nie", "tak", "się", "sie", "www",
        }
        return hashtags | {word for word in words if word not in stopwords}

    @staticmethod
    def from_dict(row: dict[str, Any]) -> "SocialPost":
        ts = row.get("timestamp") or row.get("created_at") or row.get("time")
        if isinstance(ts, datetime):
            timestamp = ts
        else:
            timestamp = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        return SocialPost(
            timestamp=timestamp,
            platform=str(row.get("platform", "unknown")),
            text=str(row.get("text", "")),
            author=str(row.get("author", "unknown")),
            likes=int(float(row.get("likes", 0) or 0)),
            shares=int(float(row.get("shares", 0) or 0)),
            comments=int(float(row.get("comments", 0) or 0)),
            views=int(float(row.get("views", 0) or 0)),
        )


@dataclass(frozen=True)
class TrendForecast:
    """Forecast for one term/hashtag."""

    term: str
    current_score: float
    predicted_score: float
    velocity: float
    acceleration: float
    z_score: float
    confidence: float
    status: str
    history: list[float]

    def as_dict(self) -> dict[str, Any]:
        return {
            "term": self.term,
            "current_score": round(self.current_score, 6),
            "predicted_score": round(self.predicted_score, 6),
            "velocity": round(self.velocity, 6),
            "acceleration": round(self.acceleration, 6),
            "z_score": round(self.z_score, 6),
            "confidence": round(self.confidence, 6),
            "status": self.status,
            "history": [round(x, 6) for x in self.history],
        }


class SocialTrendPredictor:
    """Trend detection and short-horizon forecasting engine."""

    def __init__(self, bucket_minutes: int = 60, include_keywords: bool = True):
        self.bucket_minutes = max(1, int(bucket_minutes))
        self.include_keywords = include_keywords
        self.posts: list[SocialPost] = []

    def add_post(self, post: SocialPost) -> None:
        self.posts.append(post)

    def add_posts(self, posts: Iterable[SocialPost]) -> None:
        for post in posts:
            self.add_post(post)

    def load_csv(self, path: str) -> None:
        """Load posts from CSV with columns: timestamp, platform, text, likes, shares, comments, views."""
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                self.add_post(SocialPost.from_dict(row))

    def load_jsonl(self, path: str) -> None:
        """Load posts from JSON Lines."""
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    self.add_post(SocialPost.from_dict(json.loads(line)))

    def _bucket_start(self, timestamp: datetime) -> datetime:
        timestamp = timestamp.astimezone(timezone.utc)
        minutes = (timestamp.minute // self.bucket_minutes) * self.bucket_minutes
        return timestamp.replace(minute=minutes, second=0, microsecond=0)

    def aggregate(self, min_mentions: int = 1) -> tuple[list[datetime], dict[str, list[float]], dict[str, int]]:
        """Aggregate engagement per term per time bucket."""
        if not self.posts:
            return [], {}, {}
        buckets = sorted({self._bucket_start(post.timestamp) for post in self.posts})
        bucket_index = {bucket: i for i, bucket in enumerate(buckets)}
        series: dict[str, list[float]] = defaultdict(lambda: [0.0 for _ in buckets])
        mentions: dict[str, int] = defaultdict(int)

        for post in self.posts:
            idx = bucket_index[self._bucket_start(post.timestamp)]
            for term in post.terms(include_keywords=self.include_keywords):
                series[term][idx] += post.engagement
                mentions[term] += 1

        filtered = {term: values for term, values in series.items() if mentions[term] >= min_mentions}
        filtered_mentions = {term: mentions[term] for term in filtered}
        return buckets, filtered, filtered_mentions

    @staticmethod
    def _linear_forecast(values: list[float], horizon: int) -> float:
        if not values:
            return 0.0
        if len(values) == 1:
            return max(0.0, values[-1])
        n = len(values)
        xs = list(range(n))
        x_mean = sum(xs) / n
        y_mean = sum(values) / n
        denom = sum((x - x_mean) ** 2 for x in xs) or 1.0
        slope = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, values)) / denom
        intercept = y_mean - slope * x_mean
        return max(0.0, intercept + slope * (n - 1 + horizon))

    @staticmethod
    def _z_score(current: float, values: list[float]) -> float:
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        std = math.sqrt(variance)
        if std == 0:
            return 0.0
        return (current - mean) / std

    @staticmethod
    def _confidence(values: list[float], predicted: float) -> float:
        if len(values) < 3:
            return 0.35
        volatility = sum(abs(values[i] - values[i - 1]) for i in range(1, len(values))) / (len(values) - 1)
        scale = max(1.0, sum(values) / len(values), predicted)
        stability = max(0.0, 1.0 - volatility / scale)
        signal = min(1.0, max(values) / scale)
        return max(0.05, min(0.95, 0.25 + 0.55 * stability + 0.20 * signal))

    @staticmethod
    def _status(current: float, predicted: float, velocity: float, acceleration: float, z_score: float) -> str:
        if z_score >= 2.0 and velocity > 0:
            return "BREAKOUT"
        if predicted > current * 1.25 and velocity > 0:
            return "EMERGING"
        if velocity > 0 and acceleration >= 0:
            return "GROWING"
        if velocity < 0 and predicted < current:
            return "DECLINING"
        return "STABLE"

    def forecast(
        self,
        horizon_buckets: int = 1,
        lookback_buckets: int = 8,
        min_mentions: int = 2,
        top_n: int = 20,
    ) -> list[TrendForecast]:
        """Forecast top trends for the next horizon."""
        _, series, _ = self.aggregate(min_mentions=min_mentions)
        forecasts: list[TrendForecast] = []
        for term, full_values in series.items():
            values = full_values[-lookback_buckets:] if lookback_buckets > 0 else full_values
            if not values:
                continue
            current = values[-1]
            previous = values[-2] if len(values) >= 2 else 0.0
            prev_previous = values[-3] if len(values) >= 3 else previous
            velocity = current - previous
            acceleration = (current - previous) - (previous - prev_previous)
            predicted = self._linear_forecast(values, horizon=horizon_buckets)
            z_score = self._z_score(current, values[:-1] or values)
            confidence = self._confidence(values, predicted)
            status = self._status(current, predicted, velocity, acceleration, z_score)
            forecasts.append(
                TrendForecast(
                    term=term,
                    current_score=current,
                    predicted_score=predicted,
                    velocity=velocity,
                    acceleration=acceleration,
                    z_score=z_score,
                    confidence=confidence,
                    status=status,
                    history=values,
                )
            )
        forecasts.sort(key=lambda item: (item.predicted_score, item.velocity, item.z_score, item.confidence), reverse=True)
        return forecasts[:top_n]

    def report(self, **forecast_kwargs: Any) -> dict[str, Any]:
        buckets, _, mentions = self.aggregate(min_mentions=1)
        forecasts = self.forecast(**forecast_kwargs)
        return {
            "bucket_minutes": self.bucket_minutes,
            "posts": len(self.posts),
            "buckets": [bucket.isoformat() for bucket in buckets],
            "terms_observed": len(mentions),
            "top_mentions": sorted(mentions.items(), key=lambda item: item[1], reverse=True)[:20],
            "forecasts": [forecast.as_dict() for forecast in forecasts],
        }

    def export_json(self, path: str, **forecast_kwargs: Any) -> str:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.report(**forecast_kwargs), f, indent=2, ensure_ascii=False)
        return path

    def export_markdown(self, path: str, **forecast_kwargs: Any) -> str:
        report = self.report(**forecast_kwargs)
        lines = [
            "# Social Trend Forecast Report",
            "",
            f"Posts: **{report['posts']}**",
            f"Bucket size: **{report['bucket_minutes']} minutes**",
            f"Observed terms: **{report['terms_observed']}**",
            "",
            "| Rank | Term | Status | Current | Predicted | Velocity | Z-score | Confidence |",
            "|---:|---|---|---:|---:|---:|---:|---:|",
        ]
        for i, forecast in enumerate(report["forecasts"], 1):
            lines.append(
                f"| {i} | `{forecast['term']}` | {forecast['status']} | {forecast['current_score']} | "
                f"{forecast['predicted_score']} | {forecast['velocity']} | {forecast['z_score']} | {forecast['confidence']} |"
            )
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return path


def generate_demo_posts(now: datetime | None = None) -> list[SocialPost]:
    """Generate deterministic demo posts with one emerging trend."""
    now = now or datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    posts: list[SocialPost] = []
    topics = ["#ai", "#quantum", "#fintech"]
    for bucket in range(8):
        ts = now - timedelta(hours=7 - bucket)
        for topic in topics:
            base = 8 + bucket if topic != "#quantum" else 4 + bucket * bucket
            posts.append(
                SocialPost(
                    timestamp=ts,
                    platform="demo",
                    text=f"Market discussion about {topic} and innovation",
                    author=f"demo_{bucket}_{topic}",
                    likes=base * 3,
                    shares=base,
                    comments=max(1, base // 2),
                    views=base * 100,
                )
            )
    return posts


if __name__ == "__main__":
    predictor = SocialTrendPredictor(bucket_minutes=60)
    predictor.add_posts(generate_demo_posts())
    print(json.dumps(predictor.report(min_mentions=2, top_n=10), indent=2, ensure_ascii=False))
