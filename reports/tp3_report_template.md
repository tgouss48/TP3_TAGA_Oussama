# Rapport TP3 — Serving, CI/CD et promotion

Nom :

Prénom :

Nom de l'archive : `MLOps_TP3_Nom_Prenom.zip`

## Mode d'emploi

Ce rapport individuel est le seul compte rendu à remettre. Remplacez les
marqueurs `[À COMPLÉTER]`, citez les commandes réellement exécutées et reliez
chaque affirmation à un fichier, une sortie ou une capture de
`reports/figures/`. Le rapport doit couvrir Q1 à Q8.

Checklist :

- [ ] import réel du TP2 `ACCEPT` ou `make bootstrap-reference` documenté ;
- [ ] `make doctor`, tests verts et échec contrôlé ;
- [ ] rapport JUnit `reports/test_report.xml` ;
- [ ] contrat API et réponses HTTP ;
- [ ] image, conteneur et smoke test Docker ;
- [ ] CI verte et échec contrôlé ;
- [ ] enregistrement, sélection, promotion et rollback ;
- [ ] `contracts/openapi.json` et `reports/release_manifest.json` ;
- [ ] `make validate-submission` ;
- [ ] archive créée avec `make package ARCHIVE=MLOps_TP3_Nom_Prenom.zip`.

## 0. Continuité avec le TP2

| Élément TP2 | Valeur observée | Preuve | Réutilisé dans TP3 ? |
|---|---|---|---|
| `reports/quality_gate_decision.json` | [À COMPLÉTER] | [À COMPLÉTER] | [À COMPLÉTER] |
| `models/model.joblib` | [À COMPLÉTER] | [À COMPLÉTER] | [À COMPLÉTER] |
| `reports/metrics.json` | [À COMPLÉTER] | [À COMPLÉTER] | [À COMPLÉTER] |
| `reports/run_manifest.json` | [À COMPLÉTER] | [À COMPLÉTER] | [À COMPLÉTER] |
| `data_sha256` | [À COMPLÉTER] | [À COMPLÉTER] | [À COMPLÉTER] |

Indiquez si vous avez utilisé `make import-tp2` ou `make bootstrap-reference`.
Indiquez la source exacte du workspace TP2 et expliquez que l'import est validé
avant copie. Expliquez pourquoi un modèle `REJECT` ne peut pas être enregistré.

## 1. Contrat d'inférence

| Endpoint/cas | Commande ou payload | Code HTTP | Réponse observée | Preuve |
|---|---|---:|---|---|
| `/health` | [À COMPLÉTER] | [À COMPLÉTER] | [À COMPLÉTER] | [À COMPLÉTER] |
| `/model-info` | [À COMPLÉTER] | [À COMPLÉTER] | [À COMPLÉTER] | [À COMPLÉTER] |
| `/predict` valide | [À COMPLÉTER] | [À COMPLÉTER] | [À COMPLÉTER] | [À COMPLÉTER] |
| `/v1/predict` et `X-Request-ID` | [À COMPLÉTER] | [À COMPLÉTER] | [À COMPLÉTER] | [À COMPLÉTER] |
| champ manquant | [À COMPLÉTER] | [À COMPLÉTER] | [À COMPLÉTER] | [À COMPLÉTER] |
| champ inconnu | [À COMPLÉTER] | [À COMPLÉTER] | [À COMPLÉTER] | [À COMPLÉTER] |
| valeur invalide | [À COMPLÉTER] | [À COMPLÉTER] | [À COMPLÉTER] | [À COMPLÉTER] |
| `/metrics` | [À COMPLÉTER] | [À COMPLÉTER] | [À COMPLÉTER] | [À COMPLÉTER] |

Expliquez comment Pydantic protège le modèle avant l'appel d'inférence et
comment la réponse identifie la version réellement servie. Précisez que la
configuration vient de `configs/service.yaml` et indiquez toute surcharge par
variable d'environnement. Joignez également le contrat
`contracts/openapi.json` et expliquez la compatibilité entre les routes
historiques et `/v1`.

Précisez que `/metrics` est un endpoint technique scruté par Prometheus. Le
frontend métier ne doit pas afficher ce flux ni héberger le dashboard MLOps ;
la stack d'observabilité sera démontrée dans TP4.

## 2. Docker et exécution

| Élément | Commande | Sortie observée | Preuve |
|---|---|---|---|
| Image | [À COMPLÉTER] | [À COMPLÉTER] | [À COMPLÉTER] |
| Conteneur | [À COMPLÉTER] | [À COMPLÉTER] | [À COMPLÉTER] |
| Utilisateur effectif | [À COMPLÉTER] | [À COMPLÉTER] | [À COMPLÉTER] |
| Healthcheck | [À COMPLÉTER] | [À COMPLÉTER] | [À COMPLÉTER] |
| Smoke test | [À COMPLÉTER] | [À COMPLÉTER] | [À COMPLÉTER] |

Distinguez ce que garantissent l'image, le conteneur, l'artefact modèle et le
Registry. Indiquez les limites de Docker et précisez si les données brutes sont
ou non embarquées dans l'image.

## 3. CI

| Exécution | Commit | Étape | Résultat | Preuve |
|---|---|---|---|---|
| Job vert | [À COMPLÉTER] | [À COMPLÉTER] | [À COMPLÉTER] | [À COMPLÉTER] |
| Échec contrôlé | [À COMPLÉTER] | [À COMPLÉTER] | [À COMPLÉTER] | [À COMPLÉTER] |

Décrivez l'ordre `uv sync`, lint, tests, build Docker et smoke test. Expliquez
pourquoi une pull request verte ne déclenche jamais automatiquement la
promotion.

## 4. Enregistrement Registry

| Champ | Valeur de `reports/registration.json` |
|---|---|
| Modèle enregistré | [À COMPLÉTER] |
| Version | [À COMPLÉTER] |
| Run ID | [À COMPLÉTER] |
| Hash des données | [À COMPLÉTER] |
| Gate | [À COMPLÉTER] |
| Signature et exemple d'entrée | [À COMPLÉTER] |

Expliquez quelles preuves empêchent l'enregistrement d'un candidat `REJECT`.

## 5. Sélection du challenger

Décrivez séparément l'éligibilité, le classement et la désignation de l'alias
`challenger`.

| Version | Gate | F1 | Recall | Latence | Éligible | Rang |
|---|---|---:|---:|---:|---|---:|
| [À COMPLÉTER] | [À COMPLÉTER] | [À COMPLÉTER] | [À COMPLÉTER] | [À COMPLÉTER] | [À COMPLÉTER] | [À COMPLÉTER] |
| [À COMPLÉTER] | [À COMPLÉTER] | [À COMPLÉTER] | [À COMPLÉTER] | [À COMPLÉTER] | [À COMPLÉTER] | [À COMPLÉTER] |

## 6. Promotion

| Élément | Valeur ou preuve |
|---|---|
| Champion avant décision | [À COMPLÉTER] |
| Challenger | [À COMPLÉTER] |
| Décision | `PROMOTE` / `KEEP_CHAMPION` |
| Gain F1 | [À COMPLÉTER] |
| Gain recall | [À COMPLÉTER] |
| Alias après décision | [À COMPLÉTER] |
| JSON | `reports/promotion_decision.json` |

Expliquez pourquoi un candidat éligible peut être conservé comme challenger.
Indiquez les deux versions comparées et la version portée par `champion` après
la décision.

## 7. Rollback

| Moment | Alias `champion` | Version | Preuve |
|---|---|---|---|
| Avant rollback | [À COMPLÉTER] | [À COMPLÉTER] | [À COMPLÉTER] |
| Après rollback | [À COMPLÉTER] | [À COMPLÉTER] | [À COMPLÉTER] |

Indiquez la commande utilisée et expliquez pourquoi aucune version n'est
supprimée. Vérifiez que `previous_version` et `restored_version` sont
différentes dans `reports/rollback_decision.json`.

## Questions d'ingénierie

Répondez en au moins 80 caractères par question et citez une preuve réelle.

### Q1 — Continuité TP2 et serving

Pourquoi le fichier `model.joblib` du TP2 ne constitue-t-il pas à lui seul un
contrat de service ?

**Réponse de l'étudiant :**

[À COMPLÉTER]

### Q2 — Validation Pydantic

Que protège Pydantic avant l'appel au modèle ?

**Réponse de l'étudiant :**

[À COMPLÉTER]

### Q3 — Docker

Que rend Docker reproductible et que ne garantit-il pas ?

**Réponse de l'étudiant :**

[À COMPLÉTER]

### Q4 — CI et promotion

Pourquoi `CI PASS` ne signifie-t-il pas `PROMOTE` ?

**Réponse de l'étudiant :**

[À COMPLÉTER]

### Q5 — Sélection multicritère

Pourquoi `max(accuracy)` est-il insuffisant dans ce contexte ?

**Réponse de l'étudiant :**

[À COMPLÉTER]

### Q6 — Gate et policy

Donnez un cas observé ou chiffré où le gate passe mais où le champion est
conservé.

**Réponse de l'étudiant :**

[À COMPLÉTER]

### Q7 — Alias et rollback

Comparez l'alias `champion` à une version codée en dur et décrivez le rollback.

**Réponse de l'étudiant :**

[À COMPLÉTER]

### Q8 — Responsabilité humaine et limites

Où placer une validation humaine ou métier, et quelle preuve supplémentaire
serait nécessaire avant une mise en production ?

**Réponse de l'étudiant :**

[À COMPLÉTER]

## Index des preuves

| Libellé | Fichier dans `reports/figures/` | Ce que la preuve démontre |
|---|---|---|
| Installation et `make doctor` | [À COMPLÉTER] | [À COMPLÉTER] |
| Tests API | [À COMPLÉTER] | [À COMPLÉTER] |
| Réponses des trois endpoints | [À COMPLÉTER] | [À COMPLÉTER] |
| Contrat OpenAPI | [À COMPLÉTER] | [À COMPLÉTER] |
| Erreur HTTP 422 | [À COMPLÉTER] | [À COMPLÉTER] |
| Image Docker | [À COMPLÉTER] | [À COMPLÉTER] |
| Conteneur Docker | [À COMPLÉTER] | [À COMPLÉTER] |
| Job CI vert | [À COMPLÉTER] | [À COMPLÉTER] |
| Job CI échoué | [À COMPLÉTER] | [À COMPLÉTER] |
| Version Registry | [À COMPLÉTER] | [À COMPLÉTER] |
| Décision de promotion | [À COMPLÉTER] | [À COMPLÉTER] |
| Rollback | [À COMPLÉTER] | [À COMPLÉTER] |
| Release manifest | [À COMPLÉTER] | [À COMPLÉTER] |

## Conclusion

Résumez la chaîne `TP2 ACCEPT → Registry → service → CI → promotion →
champion`, les limites restantes et la preuve transmise au TP4.

[À COMPLÉTER]
