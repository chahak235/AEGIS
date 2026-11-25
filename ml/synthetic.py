"""Synthetic (made-up but realistic) activity for training and evaluating the model.

Why synthetic? We have no real company's logs, and real security logs are
private. Synthetic data lets us control exactly what "normal" and "attack"
look like, and label every sample. The big limitation: the model learns OUR
idea of normal. Results here say how it does on these scenarios, NOT how it
would do on a real company's traffic. (Written up in docs/ml-evaluation.md.)

One SAMPLE = one account's events inside one 10-minute window.
We generate events (not numbers), then turn them into features with the same
app.ml.features.extract() the live system uses.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

WINDOW_SECONDS = 600
COMMON_RESOURCES = [f"/api/v1/{name}" for name in (
    "profile", "orders", "orders/list", "cart", "products", "products/search",
    "settings", "notifications", "messages", "reports", "invoices", "help",
)]
SENSITIVE_RESOURCES = ["/admin", "/admin/users", "/admin/roles", "/admin/export",
                       "/admin/billing", "/internal/keys", "/internal/config"]


@dataclass
class SimEvent:
    event_type: str
    occurred_at: datetime
    outcome: str
    resource: str | None
    actor_id: str = "sim-user"
    id: UUID = field(default_factory=uuid4)


class Generator:
    def __init__(self, seed: int):
        self.rng = random.Random(seed)  # fixed seed = same data every run (reproducible)
        self.t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def _at(self) -> datetime:
        return self.t0 + timedelta(seconds=self.rng.uniform(0, WINDOW_SECONDS))

    def _many(self, n, event_type, outcome, resources):
        return [SimEvent(event_type, self._at(), outcome, self.rng.choice(resources)) for _ in range(n)]

    def _resources(self, k_min, k_max, pool=COMMON_RESOURCES):
        return self.rng.sample(pool, k=min(len(pool), self.rng.randint(k_min, k_max)))

    # --- Normal behaviour -------------------------------------------------------

    def normal(self) -> list[SimEvent]:
        r = self.rng.random()
        if r < 0.55:                                     # ordinary browsing
            events = self._many(self.rng.randint(2, 35), "api.request", "success", self._resources(1, 6))
        elif r < 0.85:                                   # starts a session by logging in
            events = [SimEvent("auth.login.success", self._at(), "success", "/login")]
            events += self._many(self.rng.randint(3, 40), "api.request", "success", self._resources(2, 7))
        else:                                            # a busy power user
            events = self._many(self.rng.randint(40, 90), "api.request", "success", self._resources(4, 10))
        if self.rng.random() < 0.12:                     # typo: one or two failed logins, then success
            events += self._many(self.rng.randint(1, 2), "auth.login.failed", "failure", ["/login"])
            events.append(SimEvent("auth.login.success", self._at(), "success", "/login"))
        if self.rng.random() < 0.06:                     # clicked something they can't open
            events += self._many(1, "api.request", "denied", self._resources(1, 1))
        if self.rng.random() < 0.03:                     # an admin legitimately changes a permission
            events.append(SimEvent("account.permission.changed", self._at(), "success", "/admin/roles"))
        return events

    # --- Attacks ----------------------------------------------------------------

    def brute_force(self):
        return self._many(self.rng.randint(8, 40), "auth.login.failed", "failure", ["/login"])

    def stuffing_success(self):
        events = self._many(self.rng.randint(3, 8), "auth.login.failed", "failure", ["/login"])
        events.append(SimEvent("auth.login.success", self._at(), "success", "/login"))
        events += self._many(self.rng.randint(5, 20), "api.request", "success",
                             self._resources(4, 10, COMMON_RESOURCES + SENSITIVE_RESOURCES))
        return events

    def scraping(self):
        pool = COMMON_RESOURCES + [f"/api/v1/products/{i}" for i in range(200)]
        return self._many(self.rng.randint(150, 400), "api.request", "success", self._resources(40, 120, pool))

    def privilege_probing(self):
        events = self._many(self.rng.randint(3, 8), "api.request", "denied", self._resources(3, 7, SENSITIVE_RESOURCES))
        events += self._many(self.rng.randint(2, 10), "api.request", "success", self._resources(1, 4))
        return events

    def low_and_slow(self):
        """Deliberately stays UNDER every hand-written rule threshold:
        4 failed logins (AUTH-001 needs 5), 2-4 denied (ACCESS-001 needs 5), few requests."""
        events = self._many(4, "auth.login.failed", "failure", ["/login"])
        count = self.rng.randint(2, 4)  # draw in the same order as before, so the data stays reproducible
        events += self._many(count, "api.request", "denied", self._resources(2, 4, SENSITIVE_RESOURCES))
        events += self._many(self.rng.randint(8, 20), "api.request", "success",
                             self._resources(8, 15, COMMON_RESOURCES + SENSITIVE_RESOURCES))
        return events


ATTACKS = ("brute_force", "stuffing_success", "scraping", "privilege_probing", "low_and_slow")
