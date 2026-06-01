"""Post-process SUMO geo FCD Parquet into a tidy per-vehicle trajectory Parquet.

Long format (one row per vehicle per sampled timestep), which is what the
backend streams (chunked by time window) and deck.gl renders:

    t (int s, relative to run begin) | id | cls | lon | lat | speed | angle
"""

from __future__ import annotations

from pathlib import Path


def _classify(vtype) -> str:
    s = (vtype if isinstance(vtype, str) else "").lower()
    if "bus" in s or "coach" in s:
        return "bus"
    if "tram" in s or "rail" in s or "train" in s or "subway" in s:
        return "rail"
    if "truck" in s or "trailer" in s or "delivery" in s:
        return "truck"
    return "car"


def build_trajectory(fcd_path: Path, traj_path: Path, begin: int) -> dict:
    """Transform raw geo FCD into the trajectory trace; return summary stats."""
    import pyarrow.parquet as pq

    df = pq.read_table(fcd_path).to_pandas()
    df = df.rename(
        columns={
            "vehicle_id": "id",
            "vehicle_x": "lon",
            "vehicle_y": "lat",
            "vehicle_speed": "speed",
            "vehicle_angle": "angle",
        }
    )
    df["t"] = (df["timestep_time"] - begin).round().astype("int32")
    df["cls"] = df["vehicle_type"].map(_classify).astype("category")
    out = (
        df[["t", "id", "cls", "lon", "lat", "speed", "angle"]]
        .sort_values(["t", "id"])
        .reset_index(drop=True)
    )
    out["lon"] = out["lon"].astype("float64")
    out["lat"] = out["lat"].astype("float64")
    out["speed"] = out["speed"].astype("float32")
    out["angle"] = out["angle"].astype("float32")

    traj_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(traj_path, index=False)
    peak = int(out.groupby("t")["id"].nunique().max()) if len(out) else 0
    return {
        "rows": int(len(out)),
        "vehicles": int(out["id"].nunique()),
        "peak_active": peak,
        "t_max": int(out["t"].max()) if len(out) else 0,
        "by_class": {k: int(v) for k, v in out["cls"].value_counts().items()},
    }
