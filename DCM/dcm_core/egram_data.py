
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import List, Optional
import json
from datetime import datetime

@dataclass
class ParamsRecorded:
    #rates
    lrl_ppm: int = 60
    url_ppm: int = 120

    #atrial
    a_amp_mV: float = 3000.0
    a_pw_ms: float = 0.4

    #ventricular
    v_amp_mV: float = 3500.0
    v_pw_ms: float = 0.4

    #refractory
    arp_ms: int = 250
    vrp_ms: int = 320

    #sensing thresholds
    a_sense_mV: float = 2.5
    v_sense_mV: float = 2.5

    #PVARP
    pvarp_ms: int = 250
    pvarp_ext_ms: int = 0

    #rate smoothing
    hys_on: bool = False

    rs_percent: int = 0
    
    #rate adaptive
    msr_bpm: int = 120
    at_level: str = "Med"
    react_time_s: int = 30
    response_fac: int = 8
    recovery_time_min: int = 5

    #AV delays
    favd_ms: int = 150
    davd_ms: int = 180
    savd_ms: int = 150

@dataclass
class EgramMeta:
    """Session-level metadata for an egram recording."""

    session_id: str
    user: Optional[str] = None
    device_id: Optional[str] = None
    source: str = "hardware"
    dcm_version: Optional[str] = None
    created_utc: str = field(
        default_factory=lambda: datetime.utcnow().isoformat(timespec="seconds") + "Z"
    )

@dataclass
class EgramBlock:
    channel: str  
    # "A", "V", or "AV"
    sample_rate_Hz: int
    atr_samples: List[int] = field(default_factory=list)
    ven_samples: List[int] = field(default_factory=list)
    atr_markers: List[str] = field(default_factory=list)
    ven_markers: List[str] = field(default_factory=list)

@dataclass
class EgramRecord:
    meta: EgramMeta
    mode: Optional[str]
    params: ParamsRecorded
    blocks: List[EgramBlock] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, indent: Optional[int] = None) -> str:
        return json.dumps(self.to_dict(), indent=indent)

def new_template(
    session_id: str,
    mode: Optional[str],
    params: ParamsRecorded,
    user: Optional[str] = None,
    source: str = "hardware",
) -> EgramRecord:
    """Factory used by export_current_to_json and for new recordings."""
    meta = EgramMeta(
        session_id=session_id,
        user=user,
        source=source,
    )
    return EgramRecord(meta=meta, mode=mode, params=params)