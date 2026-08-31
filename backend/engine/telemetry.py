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

    def is_etoro_uk_market_open(self) -> Tuple[bool, str]:
        """
        Validates whether eToro UK US-equities trading session is open:
        Monday - Friday: 14:30 UK (13:30 UTC) to 21:00 UK (20:00 UTC).
        """
        now_utc = datetime.now(timezone.utc)
        weekday = now_utc.weekday() # 0 = Mon, 4 = Fri, 5 = Sat, 6 = Sun

        if weekday >= 5:
            return False, "Market Closed (Weekend: eToro opens Monday 14:30 UK)"

        time_minutes = now_utc.hour * 60 + now_utc.minute
        open_minutes = 13 * 60 + 30 # 13:30 UTC = 14:30 UK BST (09:30 US EST)
        close_minutes = 20 * 60 + 0 # 20:00 UTC = 21:00 UK BST (16:00 US EST)

        if time_minutes < open_minutes:
            mins_left = open_minutes - time_minutes
            hrs = mins_left // 60
            mins = mins_left % 60
            return False, f"Market Pre-Session (Opens in {hrs}h {mins}m at 14:30 UK)"
        elif time_minutes >= close_minutes:
            return False, "Market Closed (After-Hours: Next session at 14:30 UK)"
        else:
            return True, "eToro UK US-Market Session Active (14:30 - 21:00 UK)"

    def sync_drift(self) -> SyncDriftOutput:
        """
        drift_ms = random(0..250) (or microsecond clock variance)
        status = "OK" if drift_ms < 120 else "DRIFTING"
        """
        drift_ms = int(random.triangular(5, 220, 45))
        status = "OK" if drift_ms < 120 else "DRIFTING"
        
        market_open, session_msg = self.is_etoro_uk_market_open()
        now_utc = datetime.now(timezone.utc)

        return SyncDriftOutput(
            drift_ms=drift_ms,
            status=status,
            market_open=market_open,
            exchange_time=now_utc.strftime("%Y-%m-%d %H:%M:%S UTC"),
            timestamp=now_utc.isoformat()
        )

