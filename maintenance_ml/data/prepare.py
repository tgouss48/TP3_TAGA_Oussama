from pathlib import Path

import pandas as pd
import yaml
from sklearn.model_selection import train_test_split


ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    params = yaml.safe_load((ROOT / "params.yaml").read_text(encoding="utf-8"))
    frame = pd.read_csv(ROOT / "data/raw/machines.csv")
    train, test = train_test_split(
        frame,
        test_size=params["test_size"],
        random_state=params["seed"],
        stratify=frame["machine_failure"],
    )
    output = ROOT / "data/processed"
    output.mkdir(parents=True, exist_ok=True)
    train.to_csv(output / "train.csv", index=False)
    test.to_csv(output / "test.csv", index=False)


if __name__ == "__main__":
    main()
