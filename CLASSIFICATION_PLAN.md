# SentinelDesk Classification System — Technical Plan

**Author:** Ivy Chepkwony  
**Date:** 2026-11-21  
**Status:** Draft v2 — refined after external review  
**Scope:** Multi-task ticket classification pipeline (type, queue, priority) + critical incident risk detection

---

## 1. Problem context

Enterprise IT helpdesks process thousands of unstructured tickets daily. Two failure modes dominate:

1. **Triage bottlenecks**: Critical incidents (e.g., VPN outage cutting off hospital telemedicine) arrive in the same inbox as low-priority feature questions, delaying escalation by hours.
2. **Ungrounded auto-replies**: Off-the-shelf LLMs hallucinate product integrations, fabricate SLA guarantees, or give unsafe troubleshooting steps with no historical basis.

SentinelDesk addresses failure mode #1 with a classification system that predicts ticket type, routing queue, and priority — with empirically validated confidence scores that feed a risk-based escalation gate. Failure mode #2 is addressed downstream by the RAG system (out of scope for this document, but dependencies are defined in Section 9).

---

## 2. Dataset characteristics

**Source:** [Tobi-Bueck/customer-support-tickets](https://huggingface.co/datasets/Tobi-Bueck/customer-support-tickets) on Hugging Face (CC-BY-NC-4.0).

**Note on licensing:** CC-BY-NC-4.0 prohibits commercial use. This restriction applies if the project is developed beyond the hackathon.

### 2.1 Data source and preprocessing

The project uses the **organizer-recommended 20K CSV** (`dataset-tickets-multi-lang-4-20k.csv`), not the full 61,765-row HuggingFace dataset. The distribution analysis below was performed on the full dataset to understand the data landscape; the proportions carry over to the 20K subset.

Data preprocessing is handled by `scripts/prepare_data.py` (maintained by Alex), which:
- Reads the 20K CSV, assigns ticket IDs (`TKT-{n:05d}` from original row numbers)
- Strips whitespace, keeps blank subjects, skips tickets with blank bodies
- Validates that all label fields (type, queue, priority, language) are non-empty — this automatically excludes any unlabeled rows
- Performs a seed-42 shuffle and 80/20 split
- Outputs four files to `data/prepared/`:

| File | Columns | Use |
|------|---------|-----|
| `train.csv` | ticket_id, subject, body, type, queue, priority, language | Train classifiers on subject and body using historical labels |
| `knowledge_base.csv` | ticket_id, subject, body, answer, language | RAG retrieval index (historical tickets with answers) |
| `holdout_inputs.csv` | ticket_id, subject, body | Inference input only — no labels |
| `holdout_labels.csv` | ticket_id, type, queue, priority, language | Scoring only — never used in training, calibration, or retrieval |

The classification system consumes `train.csv` and `holdout_inputs.csv`. It never touches `knowledge_base.csv` (RAG's input) or `holdout_labels.csv` (scoring script's input).

### 2.2 Two distinct populations (full dataset context)

The full HuggingFace dataset contains 61,765 rows in **two separate populations**:

| Property | Core data | Extra data |
|----------|-----------|------------|
| **Rows** | 48,587 | 13,178 |
| **Languages** | English (58.2%) + German (41.8%) | German only (100%) |
| **Type labels** | Present (4 classes) | Missing (all null) |
| **Answer text** | Present (99.98%) | Missing (all null) |
| **Tags** | Present (tag_1 at 100%) | Missing (all null) |
| **Queues** | 10 standard IT queues | 42 niche queues (Pets, News, etc.) |
| **Priority values** | high, medium, low | high, medium, low + critical, very_low |

The 20K CSV is a subset of the core data. The `prepare_data.py` label-validation step provides an additional safeguard: any row without all labels is rejected.

### 2.3 Target distributions (core data, proportionally representative)

**Type** (4 classes — ~3.9:1 imbalance ratio):
- Incident: ~40.0%
- Request: ~28.7%
- Problem: ~21.0%
- Change: ~10.3%

**Queue** (10 classes — ~21.2:1 imbalance ratio):
- Technical Support: ~29.2%
- Product Support: ~18.4%
- Customer Service: ~15.3%
- IT Support: ~11.8%
- Billing and Payments: ~10.0%
- Returns and Exchanges: ~5.0%
- Service Outages and Maintenance: ~3.9%
- Sales and Pre-Sales: ~3.1%
- Human Resources: ~1.9%
- General Inquiry: ~1.4%

**Priority** (3 classes — ~2.0:1 imbalance ratio):
- medium: ~40.5%
- high: ~39.1%
- low: ~20.5%

Exact counts for the 20K CSV will be computed during training. The imbalance ratios and proportions are consistent across the full and subset datasets.

### 2.4 Input characteristics

- **Subject**: Mean ~45 chars, median ~42. **~8.6% are blank/null** — the pipeline must handle missing subjects. `prepare_data.py` preserves blank subjects.
- **Body**: Mean ~390 chars, median ~374. Range 4–2,259 chars.
- **Language**: Bilingual (en/de). The dataset includes a `language` column, but language must be auto-detected at inference time per the hackathon brief.
- **Duplicates**: ~17.3% of bodies are exact duplicates in the full dataset. Of those, only ~19 groups have inconsistent labels — label noise is very low. **Evaluation concern:** duplicated tickets may appear in both training and holdout splits, potentially inflating reported metrics (see Section 10.4).
- **Text style**: Formulaic and synthetic-looking. Most tickets open with "Dear Support Team / Sehr geehrtes Support-Team." Sentiment variation is low regardless of severity — a critical outage uses the same polite tone as a feature question. This means keyword/topic features matter more than tone/sentiment features.
- **Tags**: The dataset includes `tag_1` through `tag_8` for historical tickets. These are **not available at inference time** for incoming tickets, so they cannot be used as classifier inputs. They may be useful for understanding the taxonomy during analysis.

---

## 3. Classification task definition

### 3.1 Multi-task classification

Given a raw ticket (subject + body), the system predicts three targets independently:

| Target | Classes | Primary metric | Imbalance |
|--------|---------|----------------|-----------|
| Type | 4 (Incident, Request, Problem, Change) | Macro-F1 | ~3.9:1 |
| Queue | 10 (Technical Support, Product Support, ...) | Macro-F1 | ~21.2:1 |
| Priority | 3 (high, medium, low) | Macro-F1 | ~2.0:1 |

Each target gets its own classifier pipeline. The three pipelines share the same feature extraction stage but have independent models.

**Note on target independence:** These targets are not fully independent. An Incident is more likely to route to Technical Support; a Billing ticket is more likely to be a Request. We start with independent classifiers and revisit cross-target dependencies only if time permits and benchmarks suggest it.

### 3.2 Critical incident detection (dedicated binary classifier)

**High-Priority Incident Recall** — the system must reliably identify tickets that are both `type=Incident` AND `priority=high`. Missing these is the worst failure mode.

The original plan relied on the **intersection of two independently predicted classes** to catch critical incidents. This has a fundamental weakness: if the type classifier misclassifies a critical Incident as a Request, the escalation rule never fires — regardless of how accurately priority was predicted.

**Improvement:** We train a **dedicated binary classifier** for the composite target:

```
critical_incident = (type == "Incident") AND (priority == "high")
```

This model directly optimizes for detecting the dangerous combination, rather than relying on two independent predictions to both be correct. It produces a `critical_incident_risk` score (0.0–1.0) that feeds directly into the escalation gate.

We also compare against the product of independent probabilities as a baseline:

```
P(critical incident) ≈ P(type=Incident) × P(priority=high)
```

The dedicated classifier should outperform this product because the conditional-independence assumption rarely holds perfectly.

---

## 4. Model selection rationale

### 4.1 Why classical ML, not LLMs or transformers

| Approach | Accuracy | Training time | Inference latency | GPU needed | Probability estimates |
|----------|----------|---------------|-------------------|------------|----------------------|
| TF-IDF + classical ML | Strong | Seconds–minutes | <10ms | No | Usable after calibration |
| Fine-tuned transformer (DistilBERT/DeBERTa) | Slightly better | 30–60 min | 50–200ms | Yes | Requires calibration layer |
| LLM API (Claude/GPT) | Variable | None (zero-shot) | 500ms–2s | No (API) | Poor — not designed for calibrated probabilities |

**Decision:** Classical ML. The reasons:

1. **The dataset favors it.** The text is formulaic and keyword-rich. TF-IDF captures nearly all discriminative signal. Multiple studies on ITSM ticket datasets (see Section 4.2) found that TF-IDF + Linear SVM matches or outperforms transformer models on this specific task.
2. **Probability estimates are achievable.** Classical models produce probability estimates that can be validated and calibrated. This is essential for the escalation gate (see Section 4.4 on calibration).
3. **Latency and reproducibility.** The hackathon demo runs live. Classical models predict in <10ms per ticket. No GPU dependency, no API rate limits, no model availability issues during judging.
4. **Training iteration speed.** We can train, evaluate, and tune in seconds. With a 6-hour time limit, fast iteration cycles matter more than squeezing the last 1% of accuracy.

### 4.2 Literature support

The following published research supports classical ML for IT ticket classification:

- **TF-IDF + Linear SVM** consistently matches or outperforms embedding models on support ticket data, including in a study on 1.6 million tickets. Source: [Classifying Unstructured IT Service Desk Tickets Using Ensemble of Classifiers](https://arxiv.org/pdf/2103.15822).
- **Linear SVM and Random Forest** are the most consistently strong performers in a review of the ITSM classification literature. Source: [Centroid-Based Framework for Text Classification in ITSM Environments](https://arxiv.org/html/2511.20667v1).
- **Transformers show limited effectiveness** specifically on IT ticket classification according to multiple ITSM papers, likely because the text is too formulaic for contextual embeddings to add value over keyword features. Source: [Corporate IT-Support Help-Desk Hybrid-Automation](https://arxiv.org/pdf/1909.09018).
- **Ensemble approaches** (specifically stacking) outperform single models in a 2025 RIT master's thesis on IT ticket routing, which also recommends hybrid ML + rule-based systems for rare categories. Source: [IT Ticket Routing Thesis, RIT 2025](https://repository.rit.edu/theses/12020).
- **Class imbalance** is a recurring challenge in ticket priority classification, with medium-priority tickets vastly outnumbering critical ones. Source: [Automated Ticket Triage with Deep Learning, arXiv 2512.17916](https://arxiv.org/html/2512.17916v1).
- A 2025 SciTePress paper compares classical classifiers with CNNs, BiLSTMs, and BERT for ticket categorization and prioritization, finding classical models competitive. Source: [Customer Support Ticket Categorization and Prioritization](https://www.scitepress.org/publishedPapers/2025/136404/pdf/index.html).

### 4.3 Benchmark candidates

Rather than committing to a final model set upfront, we benchmark candidates and let the results decide. An ensemble is only beneficial if the models contribute **sufficiently different predictions**. We measure this explicitly (see Section 5.3).

**Linear SVM (Support Vector Machine)** — retain
- *What it does:* Finds the hyperplane in TF-IDF feature space that separates classes with maximum margin. Only uses data points near the boundary (support vectors).
- *Strength:* Best raw accuracy on high-dimensional sparse text features. Naturally resistant to overfitting in TF-IDF space.
- *Weakness:* Outputs distance-from-boundary, not probability estimates. Requires Platt scaling via `CalibratedClassifierCV` to produce usable confidence scores.
- *Expected role:* Accuracy anchor — the model most likely to get the right class.

**Logistic Regression** — retain
- *What it does:* Learns a weight for every feature (word), sums them, and passes through a sigmoid/softmax to produce class probability estimates.
- *Strength:* Produces probability estimates that **tend to be better-calibrated than other models**, though this is not guaranteed (see Section 4.4). Fully interpretable — feature coefficients explain which words drive predictions.
- *Weakness:* Linear-only on the features it sees. Cannot capture non-linear interactions.
- *Open question:* LR and Linear SVM are both linear models on the same TF-IDF features. Their decision boundaries may be similar enough that combining them provides limited additional information. We measure prediction disagreement rate to verify they are complementary before including both in an ensemble.

**Complement Naive Bayes (CNB)** — benchmark candidate
- *What it does:* A variant of Naive Bayes designed specifically for imbalanced text classification. Estimates parameters from the complement of each class (all data NOT in that class), which produces more stable estimates for minority classes.
- *Strength:* Naturally suited to sparse text, computationally inexpensive, potentially complementary to discriminative models (SVM, LR) because it uses a generative approach.
- *Weakness:* Strong feature-independence assumption. May underperform on tickets where word interactions matter.
- *Why included:* If we need a third model for an ensemble, CNB is more likely to be genuinely complementary to SVM/LR than another discriminative model, because its error patterns differ structurally.

**LightGBM (Light Gradient Boosting Machine)** — benchmark candidate, not guaranteed
- *What it does:* Builds a sequence of small decision trees, where each new tree corrects the mistakes of all previous trees. Uses histogram-based splitting for speed.
- *Strength:* Naturally combines TF-IDF features with engineered metadata features (text length, language, subject presence). Handles class imbalance via `is_unbalance=True`.
- *Concern:* Tree-based methods are not necessarily as effective as linear models on very high-dimensional sparse text. The ~50K TF-IDF features may be too sparse for effective tree splits. The engineered metadata features (8 features) may not carry enough signal to justify the additional model complexity.
- *Decision:* Benchmark LightGBM and compare against the other candidates. Retain only if it adds measurable value.

### 4.4 Calibration: an important clarification

The original plan described Logistic Regression as "naturally calibrated." This deserves correction.

**Probability estimates and calibrated probabilities are different things.**

- Logistic Regression **produces probability estimates** via softmax, which tend to be better-calibrated than most classifiers.
- But calibration is **not guaranteed**. It depends on dataset characteristics, class imbalance, regularization strength, and model specification.
- `class_weight='balanced'` specifically changes the relationship between predicted probabilities and true class frequencies.
- The meta-learner's probability outputs also need their own calibration assessment — a Logistic Regression trained on base model outputs is not automatically calibrated.

| Concept | Meaning |
|---------|---------|
| Classification confidence | The model's estimated probability for its predicted class |
| Calibration | Whether predicted probabilities correspond to observed frequencies |
| Classification accuracy | Whether the predicted class is correct |

**What we will do:** Train models normally, then empirically evaluate calibration on a held-out validation set using reliability diagrams and Brier scores. Apply sigmoid or isotonic calibration if needed. Evaluate calibration again on the final ensemble output.

---

## 5. Ensemble strategy

### 5.1 Approach: benchmark first, ensemble if justified

The original plan committed to stacking upfront. The refined approach is **data-driven**:

1. Train and evaluate each candidate model individually (SVM, LR, CNB, LightGBM).
2. Measure **prediction disagreement rates** and **pairwise error correlation** between models.
3. Only build an ensemble if the models make sufficiently different errors.
4. Compare **soft voting** (simple probability averaging) against **stacking** to verify that the added complexity is justified.

An ensemble is worth adopting only if it measurably outperforms the best single model on the validation set. A well-tuned single model with reliable calibration and a strong escalation gate is more defensible than a complex ensemble with marginal improvement.

### 5.2 Model diversity measurement (required before ensemble)

Before committing to an ensemble, compute for every pair of candidate models:

| Metric | What it tells you |
|--------|-------------------|
| Prediction disagreement rate | How often the models predict different classes |
| Pairwise error correlation | Whether the models tend to be wrong on the same tickets |
| Conditional accuracy | When model A is wrong, how often is model B right? |

If SVM and LR make nearly identical errors (high error correlation), combining them adds little. CNB or LightGBM would need to contribute a meaningfully different error pattern to justify a three-model ensemble.

### 5.3 Combination methods compared

If the models are sufficiently diverse, we choose between combination methods. This comparison uses a disagreement scenario where three models produce probabilities: SVM=0.95, LR=0.30, LightGBM=0.85:

| Method | Result | Limitation |
|--------|--------|------------|
| **Simple voting** (majority of argmax) | Incident (2-1 vote) | Ties with 3 models. Loses all probability nuance. |
| **Soft voting** (arithmetic mean of probabilities) | 0.700 | Assumes all models equally good. Fixed linear combination. But easy to implement, hard to overfit. |
| **Weighted soft voting** | 0.735 (example) | Better, but weights are fixed globally — SVM might deserve high weight on English but low on German billing. |
| **Stacking (meta-learner)** | Learned | Context-dependent weighting. Slightly more complex. Requires cross-validation for meta-features. |

**Decision process:** Compare soft voting against stacking on the validation set. If stacking provides >1% Macro-F1 improvement, adopt it. Otherwise, use soft voting — it is simpler, less prone to overfitting, and easier to explain to judges.

### 5.4 How stacking works (if adopted)

Stacking trains a "meta-learner" that learns **when to trust which model**:

1. **Generate out-of-fold predictions.** Run 5-fold cross-validation on each base model. For each fold, the model predicts on data it was not trained on. After all folds, every training sample has a prediction from each model — but each prediction was made by a model that never saw that sample during training.

2. **Build the meta-feature matrix.** For each training sample, concatenate the probability outputs from all base models. For a 4-class type prediction with 3 base models, this gives 12 meta-features.

3. **Train the meta-learner.** A Logistic Regression model learns patterns like:
   - "When SVM and LightGBM both output > 0.8, trust them"
   - "When all three disagree, the true confidence should be low" (triggers escalation)

4. **Predict at inference time.** A new ticket flows through all base models, their probability outputs are concatenated, and the meta-learner produces the final prediction.

**Critical implementation detail:** The TF-IDF vectorizer must be fitted **inside** each cross-validation fold, not on the entire training set before cross-validation. Otherwise, the vocabulary and document-frequency statistics leak information across folds. We achieve this by wrapping the vectorizer and classifier inside a scikit-learn `Pipeline`:

```python
from sklearn.pipeline import Pipeline

svm_pipeline = Pipeline([
    ('tfidf', TfidfVectorizer(...)),
    ('clf', CalibratedClassifierCV(LinearSVC(max_iter=10000), cv=5)),
])
```

This ensures that for every fold, the vectorizer is fit only on that fold's training partition.

---

## 6. Feature engineering

### 6.1 Text features

**TF-IDF Vectorizer** on the concatenated text `subject + " [SEP] " + body` (with blank subjects replaced by empty string):

- Word n-grams: unigrams + bigrams (1,2)
- Character n-grams: (3,5) — captures German compound words and partial word matches
- Max features: 50,000 (tunable)
- Sublinear TF: enabled (applies log normalization to term frequencies)
- Min document frequency: 2 (removes hapax legomena)

**Optional experiment (time permitting):** Separate TF-IDF vectorizers for subject and body, with the subject representation weighted more heavily. The subject often contains a concise issue description while the body provides supporting context — separate representations could allow the classifier to weight them differently. Only pursue this if initial results suggest subject signal is being drowned out.

### 6.2 Engineered features (used by LightGBM if retained)

| Feature | Type | Rationale |
|---------|------|-----------|
| `body_length` | int | Longer tickets may correlate with complex problems |
| `subject_length` | int (0 if blank) | Short/missing subjects may indicate urgency |
| `has_subject` | bool | ~8.6% of tickets lack a subject — this is a signal |
| `detected_language` | binary (en=0, de=1) | Detected from body text using same method in training and inference (see Section 6.3) |
| `word_count` | int | Complementary to char-level length |
| `avg_word_length` | float | German compound words are longer on average |
| `exclamation_count` | int | Urgency signal (limited due to synthetic text) |
| `question_mark_count` | int | Requests and inquiries tend to have more questions |

### 6.3 Language detection consistency

The original plan used the dataset's `language` column during training but auto-detection at inference. This creates a train/inference mismatch.

**Fix:** Run the same language-detection procedure on the raw ticket text in both training and inference. Do not use the dataset's `language` column as a feature — use it only for evaluation (reporting metrics split by language).

### 6.4 Feature pipeline

```
Raw ticket (subject, body)
    |
    +-- subject is blank? -> replace with ""
    |
    +-- combined_text = subject + " [SEP] " + body
    |
    +-- TF-IDF vectorizer -> sparse matrix (50K features)
    |      used by: all models
    |
    +-- detect_language(body) -> "en" or "de"
    |
    +-- engineered features -> dense array (8 features)
           used by: LightGBM if retained (hstack with TF-IDF)
```

---

## 7. Architecture and pipeline

### 7.1 Training pipeline

```
train.csv (from prepare_data.py)
    |
    +-- Load: ticket_id, subject, body, type, queue, priority, language
    |
    +-- Further split training data:
    |     +-- Development set: ~85% of train.csv (model training + cross-validation)
    |     +-- Validation set: ~15% of train.csv (calibration, threshold tuning, model selection)
    |
    +-- For each target (type, queue, priority):
    |     |
    |     +-- Benchmark individual models on development set:
    |     |     +-- SVM (Pipeline: TF-IDF -> CalibratedClassifierCV)
    |     |     +-- Logistic Regression (Pipeline: TF-IDF -> LR)
    |     |     +-- Complement Naive Bayes (Pipeline: TF-IDF -> CNB)
    |     |     +-- LightGBM (Pipeline: TF-IDF + engineered -> LGBM)
    |     |
    |     +-- Measure pairwise diversity (disagreement, error correlation)
    |     |
    |     +-- If ensemble justified:
    |     |     +-- Compare soft voting vs stacking on validation set
    |     |     +-- Select combination method
    |     |
    |     +-- Evaluate calibration on validation set
    |     +-- Apply post-hoc calibration if needed
    |
    +-- Train dedicated critical_incident binary classifier
    |     on: development set, target = (type==Incident AND priority==high)
    |
    +-- Tune escalation thresholds on validation set
    |
    +-- Retrain final models on full train.csv for inference
    |
    +-- Save all fitted models + vectorizer to disk
```

### 7.2 Inference pipeline

```
New ticket (subject, body)
    |
    +-- Feature extraction
    |     +-- TF-IDF transform (using fitted vectorizer)
    |     +-- Compute engineered features
    |     +-- Detect language
    |
    +-- For each target (type, queue, priority):
    |     +-- Model(s).predict_proba -> class probabilities
    |     +-- (If ensemble: combine via selected method)
    |     +-- Extract: predicted_class = argmax, confidence = max probability
    |
    +-- Critical incident binary classifier:
    |     +-- predict_proba -> critical_incident_risk score (0.0-1.0)
    |
    +-- Escalation gate (Section 7.3)
    |
    +-- Output: structured prediction (Section 9.2)
```

### 7.3 Escalation gate (risk-based)

The escalation gate uses **four independent conditions**, any of which triggers human escalation:

| # | Condition | Rationale |
|---|-----------|-----------|
| 1 | `critical_incident_risk >= threshold_risk` | Dedicated binary classifier catches critical incidents even when type or priority classifiers individually miss. |
| 2 | `type == "Incident" AND priority == "high"` (from main classifiers) | Rule-based backup — if both classifiers agree it's a critical incident, escalate regardless of the binary classifier's output. |
| 3 | `classification_margin < threshold_margin` for any target | Classification margin = difference between highest and second-highest class probability. A prediction of 0.51 vs 0.49 is fundamentally more uncertain than 0.95 vs 0.03, even if both have the same argmax. |
| 4 | `max_confidence < threshold_conf` for any target | Fallback: if no class exceeds a minimum confidence, escalate. |

All thresholds are tuned on the validation set by examining the precision-recall tradeoff of the escalation decision.

**Key operational metric:** Escalation rate at target recall. We report:

| High-Priority Incident Recall | % of all tickets escalated |
|-------------------------------|---------------------------|
| 80% | Measure |
| 90% | Measure |
| 95% | Measure |

A system achieving 95% recall by escalating 80% of all tickets is not useful. This table demonstrates the safety-efficiency tradeoff.

**Why four conditions instead of one:** Condition 1 (dedicated classifier) is the primary safety mechanism. Conditions 2–4 are defense in depth. Any one of them catching a dangerous ticket is a success; all four missing it is the failure we're optimizing against.

---

## 8. Tech stack

### 8.1 Dependencies

| Library | Version | Purpose |
|---------|---------|---------|
| `scikit-learn` | >=1.3 | SVM, Logistic Regression, CNB, TF-IDF, Pipeline, StackingClassifier, calibration, metrics |
| `lightgbm` | >=4.0 | LightGBM classifier (if benchmarks justify retention) |
| `pandas` | >=2.0 | Data manipulation |
| `numpy` | >=1.24 | Numerical operations |
| `scipy` | >=1.10 | Sparse matrix operations |
| `joblib` | (bundled with sklearn) | Model serialization |
| `langdetect` | >=1.0.9 | Language detection (consistent across training and inference) |

### 8.2 Implementation approach

Each model is wrapped in a scikit-learn `Pipeline` so the TF-IDF vectorizer is fitted per cross-validation fold:

```python
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import ComplementNB
from sklearn.calibration import CalibratedClassifierCV

svm_pipe = Pipeline([
    ('tfidf', TfidfVectorizer(
        ngram_range=(1, 2), sublinear_tf=True, max_features=50000,
        analyzer='word', min_df=2,
    )),
    ('clf', CalibratedClassifierCV(LinearSVC(max_iter=10000), cv=5)),
])

lr_pipe = Pipeline([
    ('tfidf', TfidfVectorizer(
        ngram_range=(1, 2), sublinear_tf=True, max_features=50000,
        analyzer='word', min_df=2,
    )),
    ('clf', LogisticRegression(max_iter=1000, solver='saga')),
])

cnb_pipe = Pipeline([
    ('tfidf', TfidfVectorizer(
        ngram_range=(1, 2), sublinear_tf=True, max_features=50000,
        analyzer='word', min_df=2,
    )),
    ('clf', ComplementNB(alpha=1.0)),
])
```

If stacking is adopted, `StackingClassifier` wraps these pipelines:

```python
from sklearn.ensemble import StackingClassifier

stacking_clf = StackingClassifier(
    estimators=[('svm', svm_pipe), ('lr', lr_pipe), ('cnb', cnb_pipe)],
    final_estimator=LogisticRegression(max_iter=1000),
    cv=5,
    stack_method='predict_proba',
    passthrough=False,
)
```

One classifier per target (type, queue, priority) + one binary classifier for critical incidents.

### 8.3 Class weighting

Class weighting changes the optimization objective and can affect probability calibration. We do not apply it automatically.

**Benchmark strategy:**
- Train each model **with and without** class weighting.
- Compare per-class precision, recall, and calibration.
- For LightGBM multiclass, verify that `is_unbalance=True` applies appropriately to all classes (it is primarily a binary-classification control).

For the queue classifier, pay particular attention to General Inquiry (~1.4%) and Human Resources (~1.9%). Their small sample sizes mean a model could perform poorly on them while still achieving a reasonable aggregate score.

---

## 9. Dependencies and interfaces

### 9.1 What the classification system needs from preprocessing

| Dependency | Source | Status |
|------------|--------|--------|
| `data/prepared/train.csv` | `scripts/prepare_data.py` | Available (run after downloading CSV) |
| `data/prepared/holdout_inputs.csv` | `scripts/prepare_data.py` | Available |
| `data/prepared/holdout_labels.csv` | `scripts/prepare_data.py` (scoring only) | Available |

The classification system reads `train.csv` as-is. It expects:
- `subject`: string (may be blank — handled by replacing with "")
- `body`: non-blank string
- `type`, `queue`, `priority`: non-blank label strings
- `language`: string (used only for evaluation splitting, not as a training feature — see Section 6.3)

**No additional preprocessing is requested.** The classification system handles its own text feature extraction (TF-IDF) and does not require external stemming, lemmatization, or additional cleaning.

### 9.2 What the classification system provides to the RAG pipeline and UI

```json
{
    "ticket_id": "TKT-00042",
    "predicted_type": "Incident",
    "predicted_queue": "Technical Support",
    "predicted_priority": "high",
    "confidence": {
        "type": 0.94,
        "queue": 0.89,
        "priority": 0.91
    },
    "critical_incident_risk": 0.96,
    "classification_margin": {
        "type": 0.71,
        "queue": 0.54,
        "priority": 0.68
    },
    "escalation": {
        "required": true,
        "reasons": ["High critical-incident risk (0.96)"]
    },
    "detected_language": "en",
    "inference_latency_ms": 8.4
}
```

*(Values are illustrative, not measured results.)*

The RAG system uses `predicted_type`, `predicted_queue`, and `detected_language` to filter or weight historical ticket retrieval. It uses `escalation.required` to determine whether to generate a draft reply at all.

The UI uses all fields for display: type/queue/priority badges, confidence bars, escalation status, and latency.

---

## 10. Evaluation plan

### 10.1 Evaluation structure

The holdout set (`holdout_labels.csv`) is used **once** for final evaluation. It is never used for training, model selection, threshold tuning, or calibration.

```
train.csv (from prepare_data.py)
    |
    +-- Development set (~85%): model training, cross-validation, ensemble building
    |
    +-- Validation set (~15%): calibration, threshold tuning, model comparison
    |
holdout_inputs.csv + holdout_labels.csv
    |
    +-- Final evaluation (one-time, after all decisions are made)
```

### 10.2 Metrics

**Per target (type, queue, priority):**

| Metric | Purpose |
|--------|---------|
| Macro-F1 | Overall performance, weights all classes equally |
| Weighted-F1 | Performance weighted by class frequency |
| Per-class precision and recall | Identifies specific classes the model struggles with |
| Confusion matrix | Reveals systematic misclassification patterns |
| Balanced accuracy | Average recall across classes |

**For the critical incident detector:**

| Metric | Purpose |
|--------|---------|
| Recall at various thresholds | How many critical incidents are caught |
| Precision at various thresholds | Of escalated tickets, how many are actually critical |
| False negatives (count) | Actual dangerous misses |
| Escalation rate at target recall | Operational efficiency (see Section 7.3) |

**For calibration:**

| Metric | Purpose |
|--------|---------|
| Reliability diagram | Visual check: do predicted probabilities match observed frequencies? |
| Brier score | Summary measure of calibration quality |
| Expected Calibration Error (ECE) | Binned calibration error |

### 10.3 Language-specific evaluation (required)

Report all metrics separately for English and German:

| Metric | Overall | English | German |
|--------|---------|---------|--------|
| Type Macro-F1 | — | — | — |
| Queue Macro-F1 | — | — | — |
| Priority Macro-F1 | — | — | — |
| High-Priority Incident Recall | — | — | — |

If one language performs significantly worse, investigate whether character n-grams, language-specific patterns, or the dataset distribution are contributing to the difference.

### 10.4 Known evaluation concern: duplicate leakage

~17.3% of ticket bodies are exact duplicates in the full dataset. The current split (`prepare_data.py`) does not group duplicates, so identical tickets may appear in both training and holdout. This could inflate reported metrics.

**Mitigation options** (for the preprocessing team to consider):
1. Report results with the standard split (current baseline).
2. Additionally report results with a grouped split (`GroupShuffleSplit`) where identical bodies go to the same partition.
3. If both results are similar, duplicate leakage is not materially affecting evaluation.

This is worth raising during judging because it demonstrates awareness of evaluation validity.

### 10.5 Performance targets

These are aspirations based on the literature, not commitments:

| Metric | Target | Notes |
|--------|--------|-------|
| Type Macro-F1 | >= 0.80 | Achievable with TF-IDF + SVM based on ITSM literature |
| Queue Macro-F1 | >= 0.70 | Ambitious given 21:1 imbalance |
| Priority Macro-F1 | >= 0.65 | Hardest target — priority is partly a business judgment |
| High-Priority Incident Recall | >= 0.90 | Must be evaluated against associated escalation rate |

The incident recall target specifically must be evaluated against the escalation rate — 90% recall achieved by escalating 80% of tickets is not a useful triage system.

### 10.6 Baseline comparison

Individual models are benchmarked before any ensemble:

| Model | Expected type Macro-F1 | Notes |
|-------|------------------------|-------|
| TF-IDF + Linear SVM | ~0.78–0.82 | Literature baseline for ITSM text |
| TF-IDF + Logistic Regression | ~0.76–0.80 | Potentially redundant with SVM — verify diversity |
| TF-IDF + Complement NB | ~0.72–0.78 | May complement discriminative models |
| TF-IDF + LightGBM | ~0.77–0.81 | Benefits from engineered features if they carry signal |
| Soft voting (best 2-3) | ~0.80–0.84 | Only if models are diverse |
| Stacking (if justified) | ~0.82–0.86 | Only if >1% improvement over soft voting |

These are estimates, not measured results. The benchmarking phase determines which models are retained.

---

## 11. Risks and mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Queue imbalance (21:1)** | Poor recall on General Inquiry, HR, Sales | Benchmark with/without class weighting. Monitor per-class recall. |
| **German text performance** | Models may underperform on one language | Character n-grams help with German. Report language-specific metrics. |
| **Priority weakly determined by text** | Priority depends on business context, not just content | Priority prediction will likely have the lowest F1. The dedicated critical incident classifier compensates. |
| **Synthetic data artifacts** | Formulaic text may not represent real-world tickets | Acceptable for hackathon scope. Note in demo. |
| **Calibration unreliable** | Escalation gate depends on probability estimates | Empirically evaluate calibration. Apply post-hoc calibration if needed. Never assume calibration. |
| **Ensemble overfitting** | Stacking meta-learner could memorize patterns | 5-fold CV for out-of-fold predictions. Only adopt stacking if validation improvement is measurable. |
| **Missing subjects at inference** | ~8.6% blank subjects | Pipeline handles blanks by design — empty string substitution + `has_subject` feature. |
| **Duplicate leakage** | Inflated holdout metrics | Report grouped-split results alongside standard split if feasible. Flag to judges. |
| **Class weighting + calibration interaction** | Balanced class weights distort probability estimates | Evaluate calibration with and without class weighting. |

---

## 12. Implementation timeline

Data preprocessing is already handled by `scripts/prepare_data.py`. This timeline covers classification work only:

| Time | Task | Deliverable |
|------|------|-------------|
| Hour 0–0.5 | Load train.csv, build feature pipeline | TF-IDF + engineered features working |
| Hour 0.5–1.5 | Benchmark individual models | SVM, LR, CNB, (LightGBM) trained and evaluated with per-class metrics |
| Hour 1.5–2 | Diversity analysis + ensemble decision | Disagreement rates computed. Soft voting or stacking selected (or best single model if no diversity). |
| Hour 2–2.5 | Critical incident binary classifier | Dedicated risk model trained and evaluated |
| Hour 2.5–3 | Calibration + escalation gate | Calibration evaluated, thresholds tuned on validation set, escalation rate at target recall computed |
| Hour 3–3.5 | Integration | Structured output function ready for RAG and UI consumption |
| Hour 3.5+ | Holdout evaluation + handoff | Final metrics reported, models serialized |

---

## 13. What differentiates this system (for judges)

This system is positioned as a **risk-aware, evidence-grounded decision-support system**, not simply an AI ticket classifier.

A conventional classifier answers: "What category does this ticket belong to?"

This system answers:
1. What is this ticket about? (type)
2. Which department should handle it? (queue)
3. How urgent is it? (priority)
4. How likely is it to represent a critical incident? (dedicated risk score)
5. How confident are we in those assessments? (empirically calibrated)
6. Should a human intervene? (risk-based escalation with multiple safeguards)

The strongest demonstration is not three correct predictions — it is showing:
- A routine ticket confidently auto-drafted.
- A critical incident immediately escalated.
- An uncertain ticket sent to human review — proving the system knows when it should not decide.

That third case is the most compelling, because it demonstrates responsible automation.

---

## 14. References

1. [Classifying the Unstructured IT Service Desk Tickets Using Ensemble of Classifiers](https://arxiv.org/pdf/2103.15822) — Ensemble methods on ITSM tickets.
2. [A Centroid-Based Framework for Text Classification in ITSM Environments](https://arxiv.org/html/2511.20667v1) — TF-IDF and SBERT comparison on 1.6M tickets.
3. [Customer Support Ticket Categorization and Prioritization (2025)](https://www.scitepress.org/publishedPapers/2025/136404/pdf/index.html) — Classical vs. deep learning on ticket data.
4. [IT Ticket Routing — RIT Master's Thesis (2025)](https://repository.rit.edu/theses/12020) — SVM, RF, ensemble evaluation with rule-based hybrid.
5. [Corporate IT-Support Help-Desk Hybrid-Automation](https://arxiv.org/pdf/1909.09018) — Classical ML automation of helpdesk triage.
6. [Automated Ticket Triage with Deep Learning (2025)](https://arxiv.org/html/2512.17916v1) — Class imbalance analysis in ticket priority prediction.
7. [Tobi-Bueck/customer-support-tickets Dataset](https://huggingface.co/datasets/Tobi-Bueck/customer-support-tickets) — Source dataset (CC-BY-NC-4.0).

---

## Appendix A: Response to external review

This plan was reviewed externally (ChatGPT). Below is a summary of what was accepted, modified, or declined.

### Accepted and incorporated

| Feedback | Change made |
|----------|-------------|
| LR is not automatically calibrated | Corrected throughout. Added Section 4.4 on calibration methodology. All confidence scores are now described as "probability estimates requiring empirical validation." |
| Dedicated high-priority incident binary classifier | Added as Section 3.2 and integrated into the escalation gate (Section 7.3 condition #1). |
| TF-IDF must be inside cross-validation folds | Fixed. All models are wrapped in sklearn `Pipeline` so the vectorizer is fitted per fold. |
| Benchmark Complement Naive Bayes | Added as a candidate in Section 4.3. CNB is structurally complementary to discriminative models. |
| Stacking should be contingent on benchmarks | Restructured Section 5. Ensemble is now adopted only if measured diversity and improvement justify it. |
| Soft voting as a baseline comparison | Added to Section 5.3. Stacking must beat soft voting by >1% to be adopted. |
| Language-specific evaluation | Made a formal requirement in Section 10.3. |
| Classification margin for uncertainty | Added as escalation condition #3 in Section 7.3. |
| Escalation rate at target recall | Added as an operational metric in Section 7.3. |
| Consistent language detection | Fixed in Section 6.3. Same detection method used in training and inference. |
| Evaluation structure (train/validation/holdout isolation) | Restructured in Section 10.1. Validation set carved from train.csv for calibration and thresholds. |
| Duplicate leakage concern | Documented in Section 10.4 with mitigation options. |
| Class weighting needs benchmarking | Added Section 8.3. No automatic class weighting — benchmark with and without. |

### Noted but not incorporated (time constraint or scope)

| Feedback | Reason |
|----------|--------|
| Separate subject/body TF-IDF vectorizers | Listed as optional experiment in Section 6.1. Good idea but low priority under time constraint. |
| Major incident detection (clustering related tickets) | Out of classification scope. Could be a stretch goal for the broader system. |
| Domain-specific keyword urgency indicators | The formulaic text limits keyword value. TF-IDF already captures discriminative terms. Would consider if calibration shows priority classifier is weak. |
| Cross-target dependencies (type informs queue) | Noted in Section 3.1. Start with independent classifiers; revisit only if time permits. |
| Tags as auxiliary analysis | Correctly identified as unavailable at inference time (Section 2.4). |

### Declined

| Feedback | Reason |
|----------|--------|
| Replace LightGBM with CNB as default | Both are benchmark candidates. Data decides, not assumption. |
| Fully remove stacking architecture | Retained as contingent option. If benchmarks justify it, the extra complexity is worth it. If not, we use soft voting or the best single model. |
