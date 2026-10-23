from pathlib import Path

import joblib
import pandas as pd
import yaml
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    params = yaml.safe_load((ROOT / "params.yaml").read_text(encoding="utf-8"))
    frame = pd.read_csv(ROOT / "data/processed/train.csv")
    features = frame.drop(columns=["machine_failure", "machine_id"])
    target = frame["machine_failure"]
    categorical = ["machine_type"]
    numerical = [column for column in features.columns if column not in categorical]
    preprocessor = ColumnTransformer(
        [
            ("cat", OneHotEncoder(handle_unknown="ignore"), categorical),
            ("num", StandardScaler(), numerical),
        ]
    )
    estimator = LogisticRegression(
        C=params["model"]["C"],
        max_iter=params["model"]["max_iter"],
        random_state=params["seed"],
    )
    pipeline = Pipeline(
        [("preprocess", preprocessor), ("model", estimator)]
    )
    pipeline.fit(features, target)
    output = ROOT / "models/model.joblib"
    output.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, output)


if __name__ == "__main__":
    main()
