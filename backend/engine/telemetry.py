"""
TelemetryModule tracking clock sync drift, system heartbeat, and API health.
"""
import time
import random
from datetime import datetime, timezone
from .models import HeartbeatOutput, SyncDriftOutput

class TelemetryModule:
    def __init__(self):
        self.start_time = time.time()

    def heartbeat(self) -> HeartbeatOutput:
        """
        alive = true
        timestamp = time.now()
        """
        uptime = time.time() - self.start_time
        return HeartbeatOutput(
            alive=True,
            timestamp=datetime.now(timezone.utc).isoformat(),
            uptime_seconds=round(uptime, 1),
            status="healthy"
        )

    def sync_drift(self) -> SyncDriftOutput:
        """
        drift_ms = random(0..250) (or microsecond clock variance)
        status = "OK" if drift_ms < 120 else "DRIFTING"
        """
        drift_ms = int(random.triangular(5, 220, 45))
        status = "OK" if drift_ms < 120 else "DRIFTING"
        
        # Check US market hours approx (14:30 to 21:00 UTC)
        now_utc = datetime.now(timezone.utc)
        is_weekday = now_utc.weekday() < 5
        market_open = is_weekday and (14 <= now_utc.hour < 21)

        return SyncDriftOutput(
            drift_ms=drift_ms,
            status=status,
            market_open=market_open,
            exchange_time=now_utc.strftime("%Y-%m-%d %H:%M:%S UTC"),
            timestamp=now_utc.isoformat()
        )
