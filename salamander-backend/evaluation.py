import csv
import hashlib
import json
import os
import math
import sys
import platform
import subprocess
from datetime import datetime, timezone
import numpy as np
import scipy
from scipy.stats import wilcoxon
from recommend import (
    get_catalog_with_embeddings,
    filter_similar_to_rejected,
    intra_list_distance,
    get_book_weight,
    _to_vector,
)
from collaborative import (
    generate_synthetic_peers,
    to_preferences,
    cf_preference,
    build_cf_model,
    rank_cf,
    blend_alpha,
    blend_scores,
)

K = 10
POOL = K * 6
N_PEERS = 300
EVAL_SEED = 2026
TRAIN_FRACTION = 0.8
HOLDOUT_FRACTION = 0.25
MIN_LIKED = 4
STRATEGIES = ["popularity", "content", "collaborative", "hybrid"]
PAIRS = [("hybrid", "content"), ("hybrid", "collaborative"), ("collaborative", "content"), ("content", "popularity"), ("hybrid", "popularity"), ("collaborative", "popularity")]
ALPHA_SWEEP = (0.00, 0.25, 0.50, 0.75, 1.00)
RESULTS_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "evaluation_runs")

def precision_at_k(recs, relevant, k=K):
    return len(set(recs[:k]) & relevant) / k

def recall_at_k(recs, relevant, k=K):
    return len(set(recs[:k]) & relevant) / len(relevant) if relevant else 0.0

def ndcg_at_k(recs, relevant, k=K):
    dcg = sum(1.0 / math.log2(i + 2) for i, b in enumerate(recs[:k]) if b in relevant)
    ideal = sum(1.0 / math.log2(i + 2) for i in range(min(len(relevant), k)))
    return dcg / ideal if ideal else 0.0

def split_readers(peers, seed=EVAL_SEED, train_fraction=TRAIN_FRACTION):
    users = sorted(peers)
    order = np.random.default_rng(seed).permutation(len(users))
    cut = int(len(users) * train_fraction)
    train = {users[i]: peers[users[i]] for i in order[:cut]}
    test = {users[i]: peers[users[i]] for i in order[cut:]}
    return train, test

def hold_out(log, rng):
    liked = sorted(b for b, (s, v) in log.items() if cf_preference(s, v) > 0)
    if len(liked) < MIN_LIKED:
        return None
    n_hide = max(1, round(HOLDOUT_FRACTION * len(liked)))
    hidden = {str(b) for b in rng.choice(liked, size=n_hide, replace=False)}
    visible = {b: sv for b, sv in log.items() if b not in hidden}
    return visible, hidden

class Context:
    def __init__(self, catalog, train_logs):
        self.ids = [b["id"] for b in catalog]
        self.index = {b: i for i, b in enumerate(self.ids)}
        self.raw = np.array([_to_vector(b["embedding"]) for b in catalog])
        norms = np.linalg.norm(self.raw, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        self.unit = self.raw / norms
        profiles = {u: to_preferences(log) for u, log in train_logs.items()}
        self.model = build_cf_model(profiles, self.ids)
        liked = np.zeros(len(self.ids))
        for prefs in profiles.values():
            for b, p in prefs.items():
                if p > 0 and b in self.index:
                    liked[self.index[b]] += 1
        self.liked_count = liked
        self.popularity = (liked + 1) / (len(profiles) + 2)
        self.pop_order = list(np.argsort(-liked, kind="stable"))

def content_scores(visible, ctx):
    total, weight_sum = None, 0.0
    for b, (s, v) in visible.items():
        if s == "want_to_read" or b not in ctx.index:
            continue
        w = get_book_weight(s, v)
        vec = ctx.raw[ctx.index[b]] * w
        total = vec if total is None else total + vec
        weight_sum += w
    if total is None or weight_sum == 0:
        return None
    centroid = total / weight_sum
    norm = np.linalg.norm(centroid)
    if norm == 0:
        return None
    return ctx.unit @ (centroid / norm)

def finalize(ranked_idx, visible, ctx, k=K):
    logged = set(visible)
    candidates = []
    for i in ranked_idx:
        book_id = ctx.ids[i]
        if book_id in logged:
            continue
        candidates.append({"id": book_id, "embedding": ctx.raw[i]})
        if len(candidates) == POOL:
            break
    rejected = [{"id": b, "embedding": ctx.raw[ctx.index[b]]}
                for b, (s, v) in visible.items() if (s == "dnf" or v == -1) and b in ctx.index]
    return [c["id"] for c in filter_similar_to_rejected(candidates, rejected)[:k]]

def rec_popularity(visible, ctx):
    return finalize(ctx.pop_order, visible, ctx)

def rec_content(visible, ctx):
    sc = content_scores(visible, ctx)
    if sc is None:
        return []
    return finalize(np.argsort(-sc, kind="stable"), visible, ctx)

def _cf(visible, ctx):
    prefs = to_preferences(visible)
    ranked = rank_cf(prefs, ctx.model, exclude_ids=set(visible), n=len(ctx.ids))
    return prefs, ranked

def rec_collaborative(visible, ctx):
    _, ranked = _cf(visible, ctx)
    return finalize([ctx.index[b] for b, _, _ in ranked], visible, ctx)

def rec_hybrid(visible, ctx, alpha=None):
    prefs, ranked = _cf(visible, ctx)
    sc = content_scores(visible, ctx)
    if sc is None:
        return []
    weight = blend_alpha(sum(1 for p in prefs.values() if p > 0)) if alpha is None else alpha
    order = np.argsort(-sc, kind="stable")
    if weight == 0.0:
        return finalize(order, visible, ctx)
    logged = set(visible)
    content_top = [i for i in order if ctx.ids[i] not in logged][:POOL]
    cf_top = [ctx.index[b] for b, _, _ in ranked[:POOL]]
    candidates = list(dict.fromkeys(content_top + cf_top))
    cf_all = {b: s for b, s, _ in ranked}
    content = {ctx.ids[i]: float(sc[i]) for i in candidates}
    cf = {ctx.ids[i]: cf_all.get(ctx.ids[i], 0.0) for i in candidates}
    blended = blend_scores(content, cf, weight)
    return finalize([ctx.index[b] for b, _, _, _ in blended], visible, ctx)

RECOMMENDERS = {
    "popularity": rec_popularity,
    "content": rec_content,
    "collaborative": rec_collaborative,
    "hybrid": rec_hybrid,
}

def evaluate(cases, ctx):
    scores = {s: {"precision": [], "recall": [], "ndcg": []} for s in STRATEGIES}
    shown = {s: [] for s in STRATEGIES}
    for visible, hidden in cases:
        for name in STRATEGIES:
            recs = RECOMMENDERS[name](visible, ctx)
            scores[name]["precision"].append(precision_at_k(recs, hidden))
            scores[name]["recall"].append(recall_at_k(recs, hidden))
            scores[name]["ndcg"].append(ndcg_at_k(recs, hidden))
            shown[name].append(recs)
    return scores, shown

def list_level_metrics(shown, ctx):
    out = {}
    total = len(ctx.ids)
    for name, lists in shown.items():
        unique = {b for recs in lists for b in recs}
        novelty = [-math.log2(ctx.popularity[ctx.index[b]]) for recs in lists for b in recs]
        diversity = [intra_list_distance([ctx.raw[ctx.index[b]] for b in recs]) for recs in lists if len(recs) > 1]
        out[name] = {
            "coverage": len(unique) / total,
            "novelty": float(np.mean(novelty)) if novelty else 0.0,
            "diversity": float(np.mean(diversity)) if diversity else 0.0,
        }
    return out

def paired_test(a, b):
    diff = np.array(a) - np.array(b)
    if np.allclose(diff, 0):
        return 0.0, 1.0
    try:
        return float(diff.mean()), float(wilcoxon(a, b).pvalue)
    except ValueError:
        return float(diff.mean()), 1.0

def make_run_dir(root, stamp, seed):
    base = os.path.join(root, f"{stamp}_seed{seed}")
    path, n = base, 1
    while os.path.exists(path):
        n += 1
        path = f"{base}_{n}"
    os.makedirs(path)
    return path

def git_commit():
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                                timeout=5, cwd=os.path.dirname(os.path.abspath(__file__)))
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"

def save_run(run_dir, lines, config, cases, scores):
    with open(os.path.join(run_dir, "results.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    with open(os.path.join(run_dir, "config.json"), "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    header = ["reader", "visible_liked", "hidden"] + [f"{s}_{m}" for s in STRATEGIES for m in ("precision", "recall", "ndcg")]
    with open(os.path.join(run_dir, "per_reader_scores.csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for i, (visible, hidden) in enumerate(cases):
            liked = sum(1 for s, v in visible.values() if cf_preference(s, v) > 0)
            row = [i + 1, liked, len(hidden)]
            for s in STRATEGIES:
                row += [round(scores[s][m][i], 6) for m in ("precision", "recall", "ndcg")]
            writer.writerow(row)

def run(seed=EVAL_SEED):
    started = datetime.now()
    run_id = f"{started.strftime('%Y-%m-%d_%H%M%S')}_seed{seed}"
    lines = []

    def out(text=""):
        print(text)
        lines.append(text)

    out("T35")
    out(f"Run: {started.strftime('%Y-%m-%d %H:%M:%S')} | seed {seed}")
    out("LIMITATION: all readers are simulated from catalog genre tags; this demonstrates the")
    out("evaluation method; the readers' genre focus and popularity skew can favor some strategies. It is not")
    out("evidence about real readers.")
    out()

    catalog = get_catalog_with_embeddings()
    catalog = [b for b in catalog if b.get("embedding") is not None]
    peers = generate_synthetic_peers(catalog, n_users=N_PEERS, seed=seed)
    train, test = split_readers(peers, seed=seed)
    rng = np.random.default_rng(seed + 1)
    cases = []
    for user in sorted(test):
        split = hold_out(test[user], rng)
        if split:
            cases.append(split)
    ctx = Context(catalog, train)

    out(f"Catalog: {len(ctx.ids)} books | simulated readers: {len(peers)} "
        f"({len(train)} train, {len(test)} test) | evaluated readers: {len(cases)} | K={K}")
    out(f"Each evaluated reader: about {int(HOLDOUT_FRACTION * 100)}% of liked books hidden, "
        f"average {np.mean([len(h) for _, h in cases]):.1f} hidden books")
    if len(cases) < 20:
        out("WARNING: fewer than 20 evaluated readers. The statistics are unreliable.")
    out()

    scores, shown = evaluate(cases, ctx)
    extras = list_level_metrics(shown, ctx)

    out(f"{'strategy':<14}{'P@10':>8}{'R@10':>8}{'NDCG@10':>9}{'coverage':>10}{'novelty':>9}{'diversity':>11}")
    for name in STRATEGIES:
        s, e = scores[name], extras[name]
        out(f"{name:<14}{np.mean(s['precision']):>8.3f}{np.mean(s['recall']):>8.3f}{np.mean(s['ndcg']):>9.3f}"
            f"{e['coverage']:>10.3f}{e['novelty']:>9.2f}{e['diversity']:>11.3f}")
    out()

    out(f"Paired Wilcoxon signed-rank tests (reader by reader; adjusted p = p x {len(PAIRS)} comparisons, capped at 1)")
    out(f"{'comparison':<28}{'metric':<8}{'mean diff':>10}{'p':>10}{'adj p':>10}")
    for metric in ("ndcg", "recall"):
        for a, b in PAIRS:
            diff, p = paired_test(scores[a][metric], scores[b][metric])
            out(f"{a + ' vs ' + b:<28}{metric:<8}{diff:>+10.3f}{p:>10.4f}{min(1.0, p * len(PAIRS)):>10.4f}")
    out()

    depth = np.array([sum(1 for s, v in visible.values() if cf_preference(s, v) > 0) for visible, _ in cases])
    median = float(np.median(depth))
    out(f"Mean NDCG@10 by visible history depth (median split at {median:.0f} liked books)")
    out(f"{'strategy':<14}{'thinner':>9}{'deeper':>9}")
    for name in STRATEGIES:
        nd = np.array(scores[name]["ndcg"])
        thin, deep = nd[depth <= median], nd[depth > median]
        out(f"{name:<14}{(thin.mean() if len(thin) else float('nan')):>9.3f}{(deep.mean() if len(deep) else float('nan')):>9.3f}")
    out()

    out("Hybrid with a fixed collaborative weight (the app uses a depth-based weight; 0 = content only, 1 = collaborative only)")
    out(f"{'weight':<10}{'R@10':>8}{'NDCG@10':>9}")
    for a in ALPHA_SWEEP:
        sweep = [rec_hybrid(visible, ctx, alpha=a) for visible, _ in cases]
        r = np.mean([recall_at_k(recs, h) for recs, (_, h) in zip(sweep, cases)])
        n = np.mean([ndcg_at_k(recs, h) for recs, (_, h) in zip(sweep, cases)])
        out(f"{a:<10.2f}{r:>8.3f}{n:>9.3f}")
    out("Note: the readers are simulated, so this sweep reflects how the simulation was built.")
    out("Salamander's weights should not be tuned on it; it shows the shape of the trade-off, not the best setting.")

    config = {
        "run_id": run_id,
        "started_local": started.isoformat(timespec="seconds"),
        "started_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "seed": seed,
        "k": K,
        "candidate_pool": POOL,
        "simulated_readers": len(peers),
        "train_readers": len(train),
        "test_readers": len(test),
        "evaluated_readers": len(cases),
        "train_fraction": TRAIN_FRACTION,
        "holdout_fraction": HOLDOUT_FRACTION,
        "min_liked_to_evaluate": MIN_LIKED,
        "strategies": STRATEGIES,
        "pairs_tested": [list(p) for p in PAIRS],
        "alpha_sweep": list(ALPHA_SWEEP),
        "catalog_books": len(ctx.ids),
        "catalog_fingerprint": hashlib.sha256("\n".join(sorted(map(str, ctx.ids))).encode()).hexdigest()[:12],
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "numpy": np.__version__,
        "scipy": scipy.__version__,
    }
    run_dir = make_run_dir(RESULTS_ROOT, started.strftime("%Y-%m-%d_%H%M%S"), seed)
    save_run(run_dir, lines, config, cases, scores)
    print(f"\n(this run was saved in {run_dir})")

def selftest():
    results = []

    def check(label, ok):
        print(f" {label}: {'OK' if ok else 'FAIL'}")
        results.append(bool(ok))

    print("T35: self-test of the metrics and not the database")
    rel = {"a", "b"}
    check("a perfect list scores 1 on precision-capped recall and NDCG",
            recall_at_k(["a", "b", "x"], rel) == 1.0 and abs(ndcg_at_k(["a", "b", "x"], rel) - 1.0) < 1e-9)
    check("a list with no hits scores 0", ndcg_at_k(["x", "y"], rel) == 0 and recall_at_k(["x"], rel) == 0)
    check("precision divides by K, not by list length", abs(precision_at_k(["a"], rel, k=10) - 0.1) < 1e-9)
    check("NDCG rewards hits near the top",
            ndcg_at_k(["a", "x", "x", "x"], {"a"}) > ndcg_at_k(["x", "x", "x", "a"], {"a"}))
    check("an empty relevant set scores 0 without dividing by zero",
            recall_at_k(["a"], set()) == 0.0 and ndcg_at_k(["a"], set()) == 0.0)

    peers = {f"u{i}": {f"b{j}": ("finished", 0) for j in range(6)} for i in range(20)}
    train, test = split_readers(peers, seed=1)
    check("train and test readers are disjoint and together cover everyone",
            not (set(train) & set(test)) and set(train) | set(test) == set(peers))
    check("the split is deterministic for a given seed", split_readers(peers, seed=1)[0].keys() == train.keys())
    log = {f"b{j}": ("finished", 0) for j in range(8)}
    visible, hidden = hold_out(log, np.random.default_rng(0))
    check("hold-out hides about a quarter of liked books and removes them from view",
            len(hidden) == 2 and not (set(visible) & hidden) and len(visible) == 6)
    check("readers with too few liked books are skipped",
            hold_out({f"b{j}": ("finished", 0) for j in range(MIN_LIKED - 1)}, np.random.default_rng(0)) is None)
    check("want_to_read and dnf books are never hidden (they are not 'liked')",
            all(b not in hold_out({**log, "w": ("want_to_read", 0), "d": ("dnf", 0)}, np.random.default_rng(3))[1] for b in ("w", "d")))
    check("identical scores give a zero difference and p of 1", paired_test([0.1, 0.2], [0.1, 0.2]) == (0.0, 1.0))

    import tempfile
    with tempfile.TemporaryDirectory() as root:
        first = make_run_dir(root, "2026-10-18_180000", 2026)
        second = make_run_dir(root, "2026-10-18_180000", 2026)
        check("two runs in the same second get separate folders and neither is overwritten",
                first != second and os.path.isdir(first) and os.path.isdir(second))
        cfg = {"seed": 1}
        save_run(first, ["line"], cfg, [({"b": ("finished", 0)}, {"x"})],
                    {s: {"precision": [0.1], "recall": [0.2], "ndcg": [0.3]} for s in STRATEGIES})
        check("a saved run holds the report, the settings and the per-reader scores",
                sorted(os.listdir(first)) == ["config.json", "per_reader_scores.csv", "results.txt"])

    failures = results.count(False)
    print(f"\n{'PASS' if failures == 0 else 'FAIL'}: {failures} mismatches")

if __name__=="__main__":
    if "--selftest" in sys.argv:
        selftest()
    elif "--seed" in sys.argv:
        run(seed=int(sys.argv[sys.argv.index("--seed") + 1]))
    else:
        run()