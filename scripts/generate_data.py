import argparse

from rto_audit.config import DEFAULT_DATA_PATH, GROUND_TRUTH_PATH
from rto_audit.datagen import generate_delivery_logs


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic delivery event logs.")
    parser.add_argument("--couriers", type=int, default=50)
    parser.add_argument("--events", type=int, default=20_000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    events_df, ground_truth_df = generate_delivery_logs(
        n_couriers=args.couriers, n_events=args.events, seed=args.seed
    )

    DEFAULT_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    events_df.write_csv(DEFAULT_DATA_PATH)
    ground_truth_df.write_csv(GROUND_TRUTH_PATH)

    print(f"Wrote {events_df.height} events for {args.couriers} couriers to {DEFAULT_DATA_PATH}")
    print(f"Wrote ground-truth profiles for {ground_truth_df.height} couriers to {GROUND_TRUTH_PATH}")


if __name__ == "__main__":
    main()
