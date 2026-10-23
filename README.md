# Starter TP3 — Serving, Registry, CI/CD et promotion

TP individuel : construisez, testez et documentez le service dans votre propre
copie du kit. L'archive se décompresse directement à la racine du projet, là où
se trouvent `pyproject.toml`, `uv.lock` et `Makefile`.

## Objectif et continuité avec le TP2

Le TP2 est le point d'entrée : seul un modèle dont
`reports/quality_gate_decision.json` porte `decision: ACCEPT` peut être servi et
enregistré. Le TP3 ajoute le cycle de vie professionnel :

```text
TP2 ACCEPT → import/bootstrap → MLflow Registry → challenger
→ CI + image Docker → promotion contrôlée → champion → TP4
```

Deux parcours d'entrée sont disponibles :

```bash
make import-tp2 TP2_DIR=/chemin/vers/TP2
make bootstrap-reference       # secours reproductible si TP2 est indisponible
```

Le second parcours produit un checkpoint local identifié comme
`bootstrap-reference`. Il doit être signalé comme tel dans le rapport. Le TP3
ne réentraîne jamais implicitement un modèle pendant `make pipeline`.

`make import-tp2` vérifie tous les fichiers obligatoires, le quality gate, les
métriques, le manifeste et le hash avant de copier quoi que ce soit. En cas de
`REJECT` ou de manifeste incohérent, l'espace TP3 reste inchangé.

## Démarrage

Prérequis : Python 3.10+, Git, `uv`, Docker démarré et `curl`.

```bash
make install
make doctor
make report
```

Avec un livrable TP2 :

```bash
make import-tp2 TP2_DIR=/chemin/vers/TP2
make validate-tp2
```

Sans livrable TP2 :

```bash
make bootstrap-reference
make validate-tp2
```

## Parcours obligatoire

### 1. Contrat et service FastAPI

Le service expose `/health`, `/model-info`, `/predict` et `/metrics`, ainsi que
leurs équivalents versionnés sous `/v1`. Les routes historiques restent
disponibles pour assurer une migration progressive vers le contrat versionné.
`/metrics` est un endpoint machine-to-machine destiné à Prometheus : il ne
constitue pas une page de monitoring et ne doit pas être consommé par un
frontend métier comme un dashboard.
Pydantic refuse les champs inconnus (`extra="forbid"`) et les valeurs hors
contrat. `/health` retourne `503` si le modèle n'est pas chargé. Les réponses de
`/model-info` et `/predict` identifient toujours le nom, l'alias et la version
effectivement résolus.

Chaque réponse contient `X-Request-ID`. Les erreurs `422` et `503` utilisent une
enveloppe JSON stable (`error.code`, `error.message`, `error.request_id` et,
si nécessaire, `error.details`). Les origines CORS sont désactivées par défaut
et peuvent être autorisées explicitement avec `CORS_ALLOWED_ORIGINS` pour un
frontend local.

```bash
make test
make openapi
make api                  # autre terminal
python scripts/smoke_test.py --base-url http://127.0.0.1:8000
```

Le service Registry utilise par défaut :

```text
models:/predictive-maintenance@champion
```

La configuration unique est dans `configs/service.yaml` et est effectivement
consommée par l'API. Les variables `MLFLOW_TRACKING_URI`, `MODEL_NAME`,
`MODEL_ALIAS` et `MODEL_SOURCE` ne servent qu'à surcharger explicitement cette
configuration. Le mode local `MODEL_SOURCE=local` est réservé au smoke test
Docker et exige lui aussi un gate `ACCEPT` et un hash cohérent.

Le contrat OpenAPI exporté se trouve dans `contracts/openapi.json`. Après une
modification de route ou de schéma, exécutez `make openapi` et vérifiez le test
`tests/test_openapi_contract.py`.

### 2. Registry MLflow et promotion

Dans un terminal séparé, démarrez le backend local SQLite :

```bash
make mlflow-server
```

Puis, dans le workspace :

```bash
make register
make select
make promote
```

Pour observer une vraie comparaison, enregistrez deux candidats issus de deux
entrées TP2 `ACCEPT` distinctes. Promouvez le premier, sélectionnez le second,
puis documentez `PROMOTE` ou `KEEP_CHAMPION`. Pour le rollback, choisissez une
version différente de la version actuellement portée par `champion` : le script
refuse explicitement un rollback sans changement d'alias.

Les scripts appliquent `configs/promotion_policy.yaml` dans cet ordre :

1. vérifier le quality gate, les métriques et la latence ;
2. classer les versions éligibles et affecter `challenger` ;
3. comparer challenger et champion ;
4. écrire `PROMOTE` ou `KEEP_CHAMPION` ;
5. ne déplacer `champion` que si la politique l'autorise.

Un candidat éligible n'est donc pas automatiquement promu. Les anciens stages
MLflow ne sont pas utilisés : seuls les alias `challenger` et `champion` sont
attendus. Les cinq preuves JSON sont obligatoires :

```text
reports/registration.json
reports/model_selection.json
reports/promotion_decision.json
reports/rollback_decision.json
reports/release_manifest.json
```

Avant de transmettre le résultat au TP4, vérifiez que
`release_manifest.json` décrit le modèle effectivement porté par l'alias
`champion`. Sa version peut différer de celle de `registration.json` après
`KEEP_CHAMPION` ou rollback ; elle doit correspondre à la décision finale,
porter son propre `run_id`, le même `data_sha256` et `quality_gate: ACCEPT`.
TP4 refusera un handoff incomplet, un candidat `REJECT` ou une version
effective incohérente.

Démonstration du retour arrière :

```bash
make rollback ROLLBACK_VERSION=1
```

Le rollback réaffecte `champion` sans supprimer de version et doit être vérifié
avec `/model-info`.

### 3. Docker et smoke test

Le Dockerfile installe les dépendances runtime exportées depuis `uv.lock`,
utilise l'utilisateur non-root `app`, déclare un `HEALTHCHECK` et n'embarque ni
base MLflow, ni cache, ni secret. Le runtime utilise `mlflow-skinny` ; le paquet
MLflow complet reste réservé aux commandes de développement et au serveur local
du Registry ; `skops` est conservé dans le runtime pour charger les artefacts
scikit-learn produits par MLflow.

Les commandes Docker appliquent également un système de fichiers en lecture
seule, un `/tmp` temporaire, la suppression des capabilities et
`no-new-privileges`.

```bash
make docker-build
make docker-smoke
```

Le smoke test vérifie `/health`, `/model-info`, `/predict` et `/metrics`, et
nettoie le conteneur même si une requête échoue. Les logs doivent montrer le
démarrage Uvicorn, jamais un entraînement.

Les contrôles de chaîne logicielle sont disponibles séparément :

```bash
make security-audit       # pip-audit sur requirements.txt
make image-scan           # Trivy, si installé
```

Ils complètent la CI de base sans rendre le TP dépendant d'un scanner local
particulier.

### 4. CI GitHub Actions

`.github/workflows/mlops-ci.yml` reproduit le parcours local :

```text
uv sync --locked → ruff → pytest/JUnit → bootstrap de référence
→ docker build → conteneur → smoke test HTTP
```

La CI vérifie le candidat et l'image, mais ne lance jamais `register`, `select`,
`promote` ou `rollback`. Une promotion est une décision de release explicite,
auditable et séparée de la pull request.

Provoquez aussi un échec contrôlé (par exemple un test ou une commande de
validation isolée), puis remettez le dépôt dans son état nominal et archivez la
preuve de l'échec ainsi que celle du job vert.

## Rapport et archive

```bash
make report
```

Complétez l'unique fichier `reports/tp3_report.md` et placez les captures réelles
dans `reports/figures/`. Le rapport doit contenir la continuité TP2, le contrat
API, Docker, la CI, l'enregistrement, la sélection, la promotion, le rollback,
le contrat OpenAPI, `release_manifest.json`, les réponses Q1 à Q8 et l'index des
preuves. Le validateur exige au moins treize preuves visuelles, les cinq JSON
Registry/release, un rapport JUnit vert et
l'absence de marqueurs de brouillon.

Avant remise :

```bash
make validate-submission
make package ARCHIVE=MLOps_TP3_Nom_Prenom.zip
unzip -tq MLOps_TP3_Nom_Prenom.zip
```

L'archive est individuelle et exclut `.venv`, caches, bases MLflow locales,
fichiers temporaires, logs et secrets, mais conserve le rapport, les décisions,
le JUnit et les preuves nécessaires à l'audit. Le TP4 consommera directement l'alias
`models:/predictive-maintenance@champion`, `/model-info` et le contrat de
`/predict`.
