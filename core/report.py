"""Plain HTML report for a StarShoal run. No external assets."""
import html
import math

CSS = """
body{font-family:system-ui,Segoe UI,Arial,sans-serif;margin:2em;max-width:66em;color:#1b2b34}
h1{color:#0b4f6c}h2{border-bottom:1px solid #9cc;padding-bottom:.2em;margin-top:1.6em}
table{border-collapse:collapse;margin:.6em 0}th,td{border:1px solid #bcd;padding:.3em .6em;text-align:right}
th{background:#e6f2f5}td.l,th.l{text-align:left}.warn{background:#fff4e0;border-left:4px solid #e69500;padding:.5em 1em;margin:.5em 0}
code{background:#eef5f7;padding:0 .3em}.note{color:#678;font-size:.9em}
"""


def _f(v, d=2):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "n/a"
    return f"{v:.{d}f}" if isinstance(v, float) else str(v)


def _e(s):
    return html.escape(str(s))


def _metrics_table(rows, first_col="Set"):
    out = [f"<table><tr><th class='l'>{first_col}</th><th>n</th><th>RMSE (m)</th>"
           "<th>MAE (m)</th><th>Bias (m)</th><th>R²</th></tr>"]
    for label, m in rows:
        out.append(f"<tr><td class='l'>{_e(label)}</td><td>{m['n']}</td><td>{_f(m['rmse'])}</td>"
                   f"<td>{_f(m['mae'])}</td><td>{_f(m['bias'])}</td><td>{_f(m['r2'], 3)}</td></tr>")
    out.append("</table>")
    return "\n".join(out)


def _dist(d):
    return f"{_f(d['min'], 1)} / {_f(d['median'], 1)} / {_f(d['max'], 1)}"


def _linear(coef, names):
    terms = " ".join(f"{'+' if v >= 0 else '−'} {abs(v):.4f}·{_e(n)}" for v, n in zip(coef[1:], names))
    return f"<code>depth = {coef[0]:.4f} {terms}</code>"


def _model_text(r):
    parts = []
    if r["method"] == "stumpf_sw":
        a, b = r["switch"]
        parts.append(f"<p>Blue/red model: {_linear(r['coef_br'], ['pSDB_br'])}<br>"
                     f"Blue/green model: {_linear(r['coef_bg'], ['pSDB_bg'])}</p>")
        parts.append(f"<p>Switch decided with the blue/green depth: blue/red below {a:.2f} m, blue/green "
                     f"above {b:.2f} m, linear blend in between. Blue/green alone where red has no value.</p>")
    elif r.get("coef") is None:
        imp = ", ".join(f"{k} {v:.2f}" for k, v in sorted(r["importances"].items(), key=lambda kv: -kv[1]))
        parts.append(f"<p>Random Forest, {r['trees']} trees, min 2 samples per leaf. Feature importance: "
                     f"{_e(imp)}. It cannot predict outside the calibrated depth range.</p>")
        cv = r.get("coverage")
        if cv and cv["n"]:
            parts.append(
                "<p><b>Per-pixel uncertainty:</b> <code>sd_rf.tif</code> is the standard deviation of the "
                f"individual tree predictions (mean {cv['mean_sd']:.2f} m at the validation points). It measures "
                "how much the trees disagree, not a calibrated prediction interval. Check against the "
                f"{cv['n']} own validation points: {100 * cv['within1']:.0f} % of the errors fall within 1 sd and "
                f"{100 * cv['within2']:.0f} % within 2 sd (a calibrated normal interval would give 68 % and 95 %). "
                "Much lower values mean the spread underestimates the real error.</p>")
    else:
        parts.append(f"<p>{_linear(r['coef'], r['features'])}</p>")
    s = r.get("saturation")
    if s:
        if s["saturated"]:
            parts.append(f"<p><b>Optical depth limit:</b> pSDB stops growing at about {s['z_lim']:.2f} m "
                         f"(slope {s['slope_before']:.4f} before, {s['slope_after']:.4f} after). Calibrated "
                         f"with the {r['n_fit']} calibration points above that depth.</p>")
        else:
            parts.append(f"<p>Optical depth limit: none detected ({_e(s['reason'])}).</p>")
    return "\n".join(parts)


def build(settings, results, warnings, credit=""):
    p = ["<!doctype html><html><head><meta charset='utf-8'><title>StarShoal report</title>"
         f"<style>{CSS}</style></head><body><h1>StarShoal: bathymetry report</h1>"]
    if warnings:
        p.append("<h2>Warnings</h2>")
        p += [f"<div class='warn'>{_e(w)}</div>" for w in warnings]
    p.append("<h2>Settings</h2><table>")
    p += [f"<tr><td class='l'>{_e(k)}</td><td class='l'>{_e(v)}</td></tr>" for k, v in settings]
    p.append("</table>")

    if results:
        p.append("<h2>Comparison (validation)</h2>")
        p.append(f"<p>One calibration/validation split for every method ({_e(results[0]['split'])}). "
                 "Each method is fitted on its own valid calibration points and validated twice: on the "
                 "<b>common</b> points (valid for every method, same sample) and on its <b>own</b> points "
                 "(every validation point valid for it). A method that loses the deep points makes the "
                 "common sample shallower, which flatters every method on the common columns.</p>")
        p.append("<table><tr><th class='l'>Method</th><th>Depth limit (m)</th>"
                 "<th>Common n</th><th>Common RMSE</th><th>Common bias</th>"
                 "<th>Own n</th><th>Own RMSE</th><th>Own bias</th><th>Own RMSE ≤ limit</th>"
                 "<th>Own depths min / median / max</th><th>Points lost</th></tr>")
        for r in results:
            c, o, i = r["val_common"], r["val_own"], r["val_own_in"]
            p.append(f"<tr><td class='l'>{_e(r['label'])}</td><td>{_f(r['z_lim'], 1)}</td>"
                     f"<td>{c['n']}</td><td>{_f(c['rmse'])}</td><td>{_f(c['bias'])}</td>"
                     f"<td>{o['n']}</td><td>{_f(o['rmse'])}</td><td>{_f(o['bias'])}</td><td>{_f(i['rmse'])}</td>"
                     f"<td>{_dist(r['dist_own'])}</td><td>{r['lost_alone']} / {r['n_points']}</td></tr>")
        p.append("</table>")
        p.append(f"<p>Common validation sample, depths min / median / max: {_dist(results[0]['dist_common'])} m "
                 f"(n = {results[0]['dist_common']['n']}).</p>")
        p.append("<p class='note'>Depth limit: for Stumpf, where pSDB stops growing (or the deepest calibration "
                 "point if no flattening is found); for Lyzenga and Random Forest, the deepest calibration point. "
                 "'Own RMSE ≤ limit' uses only validation points not deeper than that limit.</p>")

    for r in results:
        p.append(f"<h2>{_e(r['label'])}</h2>")
        p.append(_model_text(r))
        p.append(_metrics_table([("Calibration (fitted points)", r["cal"]),
                                 ("Validation, common points", r["val_common"]),
                                 ("Validation, own points", r["val_own"]),
                                 ("Validation, own points ≤ limit", r["val_own_in"])]))
        p.append("<h3>Validation by depth range (own points)</h3>")
        p.append(_metrics_table([(b["range"], b) for b in r["bins"]], "Depth (m)"))

    p.append("<p class='note'>Metrics are computed on depth, positive down, whatever the output sign. "
             "Bias = mean(predicted − observed); positive means the model gives deeper values. "
             "R² = 1 − SSres/SStot on each set (it can be negative on validation).</p>")
    if credit:
        p.append(f"<p class='note'>{_e(credit)}</p>")
    p.append("</body></html>")
    return "\n".join(p)
